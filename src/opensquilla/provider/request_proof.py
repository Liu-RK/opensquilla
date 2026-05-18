"""Provider-adapter final payload budget proof helpers."""

from __future__ import annotations

import json
import os
from copy import deepcopy
from typing import Any

_COMPACTED_STRING_MAX_CHARS = 1200


class ProviderRequestBudgetExceededError(RuntimeError):
    def __init__(self, proof: dict[str, Any]) -> None:
        self.proof = proof
        super().__init__("provider_request_budget_exhausted")


ProviderRequestBudgetExceeded = ProviderRequestBudgetExceededError


def _payload_chars(payload: Any) -> int:
    return len(json.dumps(payload, ensure_ascii=False, separators=(",", ":")))


def _is_data_url(value: str) -> bool:
    return value.startswith("data:") and ";base64," in value[:128]


def _media_placeholder(kind: str, value: str) -> str:
    return f"[provider_request_{kind}_omitted: {len(value)} chars]"


def _budget_projection(payload: Any) -> tuple[Any, int, int]:
    media_chars = 0
    media_blocks = 0

    def visit(value: Any) -> Any:
        nonlocal media_chars, media_blocks
        if isinstance(value, list):
            return [visit(item) for item in value]
        if not isinstance(value, dict):
            return value

        if value.get("type") == "image_url":
            image_url = value.get("image_url")
            if isinstance(image_url, dict):
                url = image_url.get("url")
                if isinstance(url, str) and _is_data_url(url):
                    media_chars += len(url)
                    media_blocks += 1
                    replaced = dict(value)
                    replaced["image_url"] = {
                        **image_url,
                        "url": _media_placeholder("image_url", url),
                    }
                    return replaced

        source = value.get("source")
        if isinstance(source, dict) and source.get("type") == "base64":
            data = source.get("data")
            media_type = source.get("media_type")
            if (
                isinstance(data, str)
                and isinstance(media_type, str)
                and (media_type.startswith("image/") or media_type == "application/pdf")
            ):
                media_chars += len(data)
                media_blocks += 1
                replaced = dict(value)
                replaced["source"] = {
                    **source,
                    "data": _media_placeholder("base64_media", data),
                }
                return replaced

        return {key: visit(item) for key, item in value.items()}

    return visit(payload), media_chars, media_blocks


def _top_contributors(payload: Any, *, limit: int = 5) -> list[dict[str, Any]]:
    contributors: list[dict[str, Any]] = []

    def visit(value: Any, path: str) -> None:
        if isinstance(value, str):
            contributors.append({"path": path, "chars": len(value)})
            return
        if isinstance(value, list):
            for index, item in enumerate(value):
                visit(item, f"{path}[{index}]")
            return
        if isinstance(value, dict):
            for key, item in value.items():
                visit(item, f"{path}.{key}")

    visit(payload, "$")
    contributors.sort(key=lambda item: int(item["chars"]), reverse=True)
    return contributors[:limit]


def _compact_string(value: str) -> str:
    if len(value) <= _COMPACTED_STRING_MAX_CHARS:
        return value
    head = value[:900]
    tail = value[-200:]
    omitted = len(value) - len(head) - len(tail)
    return f"{head}\n\n[provider_request_compacted: omitted {omitted} chars]\n\n{tail}"


def _compact_tool_payload_once(payload: dict[str, Any]) -> dict[str, Any]:
    compacted = deepcopy(payload)
    for message in compacted.get("messages", []):
        if not isinstance(message, dict):
            continue
        content = message.get("content")
        if message.get("role") == "tool" and isinstance(content, str):
            message["content"] = _compact_string(content)
            continue
        if not isinstance(content, list):
            continue
        for block in content:
            if not isinstance(block, dict) or block.get("type") != "tool_result":
                continue
            block_content = block.get("content")
            if isinstance(block_content, str):
                block["content"] = _compact_string(block_content)
            elif isinstance(block_content, list):
                for item in block_content:
                    if isinstance(item, dict) and isinstance(item.get("text"), str):
                        item["text"] = _compact_string(item["text"])
    return compacted


def prove_provider_payload(
    payload: dict[str, Any],
    *,
    projection_adapter: str,
    proof_budget: int,
    status_projection_mode: str = "native_or_none",
    fallback_reason: str | None = None,
) -> dict[str, Any]:
    budget_payload, media_chars, media_blocks = _budget_projection(payload)
    estimated_chars = _payload_chars(budget_payload)
    estimated_tokens = max(1, estimated_chars // 4)
    fits = proof_budget <= 0 or estimated_chars <= proof_budget
    proof: dict[str, Any] = {
        "projection_adapter": projection_adapter,
        "execution_status_version": 1,
        "status_projection_mode": status_projection_mode,
        "estimated_chars": estimated_chars,
        "estimated_tokens": estimated_tokens,
        "proof_budget": proof_budget,
        "fits": fits,
        "compact_needed": not fits,
        "recent_tail_too_large": False,
        "compaction_not_smaller": False,
        "provider_window_mismatch": False,
        "fallback_reason": fallback_reason,
        "top_contributors": _top_contributors(budget_payload),
        "retry_count": 0,
    }
    if media_blocks:
        proof["media_chars_excluded"] = media_chars
        proof["media_blocks_excluded"] = media_blocks
    if not fits:
        proof["fallback_reason"] = "provider_request_budget_exhausted"
        raise ProviderRequestBudgetExceededError(proof)
    return proof


def prove_or_compact_provider_payload(
    payload: dict[str, Any],
    *,
    projection_adapter: str,
    proof_budget: int,
    status_projection_mode: str = "native_or_none",
    fallback_reason: str | None = None,
) -> tuple[dict[str, Any], dict[str, Any] | None]:
    if proof_budget <= 0:
        return payload, None
    try:
        return payload, prove_provider_payload(
            payload,
            projection_adapter=projection_adapter,
            proof_budget=proof_budget,
            status_projection_mode=status_projection_mode,
            fallback_reason=fallback_reason,
        )
    except ProviderRequestBudgetExceededError as first_error:
        first_chars = int(first_error.proof["estimated_chars"])

    compacted = _compact_tool_payload_once(payload)
    compacted_chars = _payload_chars(compacted)
    try:
        proof = prove_provider_payload(
            compacted,
            projection_adapter=projection_adapter,
            proof_budget=proof_budget,
            status_projection_mode=status_projection_mode,
            fallback_reason=fallback_reason,
        )
    except ProviderRequestBudgetExceededError as exc:
        exc.proof["retry_count"] = 1
        exc.proof["compact_needed"] = True
        exc.proof["compaction_not_smaller"] = compacted_chars >= first_chars
        exc.proof["recent_tail_too_large"] = bool(exc.proof.get("top_contributors"))
        raise
    proof["retry_count"] = 1
    proof["compact_needed"] = True
    proof["compaction_not_smaller"] = compacted_chars >= first_chars
    proof["recent_tail_too_large"] = False
    return compacted, proof


def prove_provider_payload_from_env(
    payload: dict[str, Any],
    *,
    projection_adapter: str,
    status_projection_mode: str = "native_or_none",
    fallback_reason: str | None = None,
) -> dict[str, Any] | None:
    raw = os.environ.get("OPENSQUILLA_PROVIDER_REQUEST_PROOF_MAX_CHARS")
    if not raw:
        return None
    try:
        proof_budget = int(raw)
    except ValueError:
        return None
    return prove_provider_payload(
        payload,
        projection_adapter=projection_adapter,
        proof_budget=proof_budget,
        status_projection_mode=status_projection_mode,
        fallback_reason=fallback_reason,
    )
