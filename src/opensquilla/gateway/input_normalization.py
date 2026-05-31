"""Normalize large/raw ingress text into semantic intent plus material metadata."""

from __future__ import annotations

import base64
from dataclasses import dataclass, field
from datetime import UTC, datetime
from typing import Any, Literal

LARGE_PASTE_CHARS = 20_000
PAGE_DUMP_CHARS = 8_000
PAGE_DUMP_MARKER_MIN_SCORE = 3
INLINE_TEXT_ATTACHMENT_MAX_BYTES = 2 * 1000 * 1000
TOO_LARGE_MESSAGE = (
    "The pasted text is too large to send directly; please attach a shorter file "
    "or summarize it."
)

NormalizedInputKind = Literal["plain", "large_paste", "page_dump", "too_large"]

_PAGE_DUMP_MARKERS: tuple[str, ...] = (
    "Chat session",
    "agent:main:webchat:",
    "Still waiting for agent response",
    "AI MODEL ROUTER",
    "The provider returned an empty response",
    "Pulsing",
    "Running",
    "Send a message",
    "SYSTEM",
    "SQUILLA",
)


@dataclass(frozen=True)
class NormalizedInput:
    kind: NormalizedInputKind
    message_text: str
    semantic_message: str
    generated_attachments: list[dict[str, Any]] = field(default_factory=list)
    material_chars: int = 0
    material_estimated_tokens: int = 0
    metadata: dict[str, Any] = field(default_factory=dict)


def estimate_text_tokens(text: str) -> int:
    return max(1, len(text) // 4) if text else 0


def page_dump_marker_score(text: str) -> int:
    if not text:
        return 0
    lowered = text.lower()
    return sum(1 for marker in _PAGE_DUMP_MARKERS if marker.lower() in lowered)


def _normalized_source_hint(source_hint: dict[str, Any] | None) -> dict[str, str]:
    if not isinstance(source_hint, dict):
        return {}

    accepted_keys = {
        "caller_kind": ("caller_kind", "callerKind"),
        "channel_kind": ("channel_kind", "channelKind"),
        "source_kind": ("source_kind", "sourceKind"),
    }
    normalized: dict[str, str] = {}
    for canonical_key, aliases in accepted_keys.items():
        for alias in aliases:
            value = source_hint.get(alias)
            if isinstance(value, str):
                normalized[canonical_key] = value.strip().lower()
                break
    return normalized


def _is_web_source(source_hint: dict[str, Any] | None) -> bool:
    normalized = _normalized_source_hint(source_hint)
    return (
        normalized.get("caller_kind") == "web"
        or normalized.get("channel_kind") in {"web", "webchat"}
        or normalized.get("source_kind") == "webui"
    )


def _attachment_name(kind: NormalizedInputKind) -> str:
    stamp = datetime.now(UTC).strftime("%Y%m%d-%H%M%S")
    prefix = "webchat-page-dump" if kind == "page_dump" else "webchat-paste"
    return f"{prefix}-{stamp}.txt"


def _generated_text_attachment(text: str, *, kind: NormalizedInputKind) -> dict[str, Any]:
    payload = text.encode("utf-8")
    return {
        "type": "text/plain",
        "mime": "text/plain",
        "name": _attachment_name(kind),
        "data": base64.b64encode(payload).decode("ascii"),
        "size": len(payload),
        "_generated_by": "input_normalization",
        "_normalization_kind": kind,
    }


def _guarded_message(kind: NormalizedInputKind) -> str:
    if kind == "page_dump":
        return "Please process the attached WebChat page dump."
    if kind == "too_large":
        return TOO_LARGE_MESSAGE
    return "Please process the attached pasted text."


def normalize_incoming_text(
    message_text: str,
    *,
    source_hint: dict[str, Any] | None,
    attachments: list[dict[str, Any]] | None,
) -> NormalizedInput:
    text = message_text or ""
    marker_score = page_dump_marker_score(text)
    is_page_dump = len(text) >= PAGE_DUMP_CHARS and marker_score >= PAGE_DUMP_MARKER_MIN_SCORE
    is_large_paste = len(text) >= LARGE_PASTE_CHARS
    material_tokens = estimate_text_tokens(text)
    metadata = {
        "source": "input_normalization",
        "original_chars": len(text),
        "material_estimated_tokens": material_tokens,
        "marker_score": marker_score,
        "generated_attachment_count": 0,
    }

    if not _is_web_source(source_hint) or not (is_page_dump or is_large_paste):
        metadata["guard_action"] = "none"
        return NormalizedInput(
            kind="plain",
            message_text=text,
            semantic_message=text,
            material_chars=len(text),
            material_estimated_tokens=material_tokens,
            metadata=metadata,
        )

    kind: NormalizedInputKind = "page_dump" if is_page_dump else "large_paste"
    raw_bytes = text.encode("utf-8")
    if len(raw_bytes) > INLINE_TEXT_ATTACHMENT_MAX_BYTES:
        message = _guarded_message("too_large")
        metadata["guard_action"] = "blocked_text_too_large"
        return NormalizedInput(
            kind="too_large",
            message_text=message,
            semantic_message=message,
            material_chars=len(text),
            material_estimated_tokens=material_tokens,
            metadata=metadata,
        )

    generated = [_generated_text_attachment(text, kind=kind)]
    message = _guarded_message(kind)
    metadata["guard_action"] = "generated_text_attachment"
    metadata["generated_attachment_count"] = len(generated)
    return NormalizedInput(
        kind=kind,
        message_text=message,
        semantic_message=message,
        generated_attachments=generated,
        material_chars=len(text),
        material_estimated_tokens=material_tokens,
        metadata=metadata,
    )
