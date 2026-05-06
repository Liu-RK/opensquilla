"""Context window compaction — summarize older messages to free token budget."""

from __future__ import annotations

import inspect
import json
from dataclasses import dataclass, field
from typing import Any, cast

import httpx
import structlog

from opensquilla.env import trust_env as _trust_env
from opensquilla.provider.openrouter_attribution import openrouter_app_headers
from opensquilla.provider.protocol import provider_connection_config

log = structlog.get_logger(__name__)

_COMPACTION_TIMEOUT = 30.0


@dataclass
class CompactionConfig:
    base_chunk_ratio: float = 0.4
    min_chunk_ratio: float = 0.15
    safety_margin: float = 1.2
    default_parts: int = 2
    identifier_policy: str = "strict"  # strict | custom | off
    model: str | None = None  # None = use session model
    api_key: str = ""
    base_url: str = "https://openrouter.ai/api/v1"
    timeout_seconds: float = 30.0


@dataclass
class CompactionRequest:
    session_id: str
    entries: list[dict[str, Any]]  # list of {role, content, token_count?}
    context_window_tokens: int
    config: CompactionConfig = field(default_factory=CompactionConfig)


@dataclass
class CompactionResult:
    summary: str
    kept_entries: list[dict[str, Any]]
    removed_count: int
    chunks_processed: int
    summary_source: str = "unknown"  # skipped | fallback | llm | mixed | unknown


def _string_value(value: Any) -> str:
    if value is None:
        return ""
    get_secret_value = getattr(value, "get_secret_value", None)
    if callable(get_secret_value):
        value = get_secret_value()
    return str(value).strip()


def build_compaction_config_from_provider(
    provider: Any | None,
    *,
    model_override: str | None = None,
    default_model: str | None = None,
    compaction_config: Any | None = None,
) -> CompactionConfig:
    """Build CompactionConfig from a resolved provider without owning selection."""

    timeout_seconds = getattr(compaction_config, "timeout_seconds", _COMPACTION_TIMEOUT)
    try:
        timeout = float(timeout_seconds)
    except (TypeError, ValueError):
        timeout = _COMPACTION_TIMEOUT

    cfg = CompactionConfig(timeout_seconds=timeout)
    if compaction_config is not None and not bool(getattr(compaction_config, "enabled", True)):
        return cfg

    configured_model = getattr(compaction_config, "model", None) if compaction_config else None
    connection_config = provider_connection_config(provider)
    api_key = connection_config.api_key
    model = connection_config.model
    base_url = connection_config.base_url

    cfg.api_key = api_key
    cfg.model = configured_model or model_override or model or default_model
    if base_url:
        cfg.base_url = base_url
    return cfg


def compact_accepts_config(compact_fn: Any) -> bool:
    """Return whether a compact callable can accept the optional config arg."""

    side_effect = getattr(compact_fn, "side_effect", None)
    if callable(side_effect):
        compact_fn = side_effect

    try:
        params = list(inspect.signature(compact_fn).parameters.values())
    except (TypeError, ValueError):
        return True

    variadic_kinds = {
        inspect.Parameter.VAR_POSITIONAL,
        inspect.Parameter.VAR_KEYWORD,
    }
    if any(p.kind in variadic_kinds for p in params):
        return True
    if any(p.name == "config" for p in params):
        return True

    positional_kinds = {
        inspect.Parameter.POSITIONAL_ONLY,
        inspect.Parameter.POSITIONAL_OR_KEYWORD,
        inspect.Parameter.KEYWORD_ONLY,
    }
    return len([p for p in params if p.kind in positional_kinds]) >= 3


async def call_compact_with_optional_config(
    compact_fn: Any,
    session_key: str,
    context_window_tokens: int,
    config: CompactionConfig | None,
) -> str:
    """Call compact with config only when the target supports the argument."""

    if config is not None and compact_accepts_config(compact_fn):
        return cast(str, await compact_fn(session_key, context_window_tokens, config))
    return cast(str, await compact_fn(session_key, context_window_tokens))


def _estimate_tokens(text: str) -> int:
    """Delegate to centralized tokenizer (tiktoken with len//4 fallback)."""
    from opensquilla.session.tokenizer import estimate_tokens

    return estimate_tokens(text)


def _entry_tokens(entry: dict[str, Any]) -> int:
    if entry.get("token_count"):
        return int(entry["token_count"])
    content = entry.get("content") or ""
    return _estimate_tokens(str(content))


def _chunk_entries(entries: list[dict[str, Any]], chunk_ratio: float) -> list[list[dict[str, Any]]]:
    """Split entries into chunks based on ratio of total entries."""
    if not entries:
        return []
    chunk_size = max(1, int(len(entries) * chunk_ratio))
    return [entries[i : i + chunk_size] for i in range(0, len(entries), chunk_size)]


def _build_strict_identifier_instruction() -> str:
    return (
        "IMPORTANT: Preserve all opaque identifiers exactly as written — "
        "UUIDs, hashes, IDs, tokens, API keys, hostnames, IPs, ports, URLs, file names. "
        "Do NOT shorten, reconstruct, or paraphrase any identifier."
    )


def _summarize_if_envelope(content: str) -> str:
    """Replace attachment-envelope JSON with a concise placeholder.

    User messages carrying images are persisted as
    ``{"text": "...", "attachments": [{"type": "image/png", "data": "<base64>"}...]}``
    (see gateway/rpc_sessions.py:_persist_user_message). Feeding the raw JSON
    blob to the compaction LLM wastes context on base64 and confuses the summary.
    Detect the envelope shape and return ``text`` plus a short attachment
    descriptor instead. Non-envelope strings pass through unchanged.
    """
    if not content.startswith('{"text":'):
        return content
    try:
        parsed = json.loads(content)
    except (json.JSONDecodeError, ValueError):
        return content
    if not isinstance(parsed, dict) or "text" not in parsed:
        return content
    text = parsed.get("text")
    if not isinstance(text, str):
        return content
    atts = parsed.get("attachments") or []
    if not isinstance(atts, list) or not atts:
        return text
    descs: list[str] = []
    for att in atts:
        if not isinstance(att, dict):
            continue
        name = att.get("name") or "image"
        media = att.get("type") or "image/*"
        descs.append(f"{name} ({media})")
    if descs:
        return f"{text}\n[user attached: {', '.join(descs)}]"
    return text


def _format_chunk_for_llm(chunk: list[dict[str, Any]]) -> str:
    """Format conversation entries into readable text for the compaction LLM."""
    lines: list[str] = []
    for entry in chunk:
        role = entry.get("role", "unknown")
        content = _summarize_if_envelope(str(entry.get("content") or ""))
        lines.append(f"[{role}]: {content}")
    return "\n\n".join(lines)


def _summarize_chunk_fallback(chunk: list[dict[str, Any]], policy: str) -> str:
    """Fallback summary when LLM call fails."""
    lines: list[str] = []
    if policy == "strict":
        lines.append(_build_strict_identifier_instruction())
    lines.append(f"[Summary of {len(chunk)} messages]")
    for entry in chunk:
        role = entry.get("role", "unknown")
        content = _summarize_if_envelope(str(entry.get("content") or ""))
        preview = content[:200] + ("..." if len(content) > 200 else "")
        lines.append(f"  [{role}]: {preview}")
    return "\n".join(lines)


async def call_compaction_llm(
    chunk_text: str,
    identifier_instruction: str,
    model: str,
    api_key: str,
    base_url: str = "https://openrouter.ai/api/v1",
    timeout: float = _COMPACTION_TIMEOUT,
) -> str | None:
    """Call LLM to summarize a conversation chunk. Returns None on failure."""
    if not api_key:
        return None

    url = base_url.rstrip("/")
    if not url.endswith("/v1"):
        url += "/v1"
    url += "/chat/completions"

    system = (
        "You are a conversation compactor. Summarize the conversation concisely, "
        "preserving key facts, decisions, open questions, and action items. "
        "Write in the same language as the conversation. "
        "Focus on recent context over older history."
    )
    if identifier_instruction:
        system = f"{system}\n\n{identifier_instruction}"

    payload = {
        "model": model,
        "messages": [
            {"role": "system", "content": system},
            {"role": "user", "content": f"Summarize this conversation:\n\n{chunk_text}"},
        ],
        "max_tokens": 1024,
        "temperature": 0,
        "stream": False,
    }
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Content-Type": "application/json",
    }
    headers.update(openrouter_app_headers(url))

    try:
        async with httpx.AsyncClient(timeout=timeout, trust_env=_trust_env()) as client:
            resp = await client.post(url, json=payload, headers=headers)
            resp.raise_for_status()
            data = resp.json()
            return cast(str, data["choices"][0]["message"]["content"])
    except Exception as exc:
        log.warning("compaction.llm_call_failed", model=model, error=str(exc))
        return None


def _merge_summaries(summaries: list[str]) -> str:
    """Merge chunk summaries into a single cohesive summary.

    Spec requirements: MUST PRESERVE active tasks + status, batch progress,
    last user request, decisions + rationale, TODOs/open questions,
    commitments/follow-ups. Prioritize recent context over older history.
    """
    if len(summaries) == 1:
        return summaries[0]
    merged_lines = ["[Merged context summary]"]
    # Later summaries (more recent) appear last — they take priority
    for i, summary in enumerate(summaries):
        merged_lines.append(f"\n--- Part {i + 1} ---\n{summary}")
    return "\n".join(merged_lines)


async def compact_context(request: CompactionRequest) -> CompactionResult:
    """
    Determine which entries to compact, summarize them, and return what to keep.

    Strategy:
    - Calculate how many tokens we need to free (entries * safety_margin vs window)
    - Split entries to compact into chunks using base_chunk_ratio
    - Summarize each chunk via LLM (fallback to text preview on failure)
    - Keep the most recent entries that fit within budget
    """
    cfg = request.config
    entries = request.entries
    window = request.context_window_tokens

    if not entries:
        return CompactionResult(
            summary="",
            kept_entries=[],
            removed_count=0,
            chunks_processed=0,
            summary_source="skipped",
        )

    total_tokens = sum(_entry_tokens(e) for e in entries)

    # If we're within budget, no compaction needed
    if total_tokens * cfg.safety_margin <= window:
        return CompactionResult(
            summary="",
            kept_entries=entries,
            removed_count=0,
            chunks_processed=0,
            summary_source="skipped",
        )

    # Determine how many recent entries to keep (fitting in half the window)
    keep_budget = window // 2
    kept: list[dict[str, Any]] = []
    kept_tokens = 0
    for entry in reversed(entries):
        t = _entry_tokens(entry)
        if kept_tokens + t <= keep_budget:
            kept.insert(0, entry)
            kept_tokens += t
        else:
            break

    to_compact = entries[: len(entries) - len(kept)]

    if not to_compact:
        return CompactionResult(
            summary="",
            kept_entries=entries,
            removed_count=0,
            chunks_processed=0,
            summary_source="skipped",
        )

    # Determine chunk ratio, falling back to min if chunk would be too large
    chunk_ratio = max(cfg.min_chunk_ratio, cfg.base_chunk_ratio / cfg.default_parts)
    chunks = _chunk_entries(to_compact, chunk_ratio)

    id_instruction = (
        _build_strict_identifier_instruction() if cfg.identifier_policy == "strict" else ""
    )

    summaries: list[str] = []
    llm_chunks = 0
    fallback_chunks = 0
    for chunk in chunks:
        if cfg.api_key and cfg.model:
            llm_result = await call_compaction_llm(
                chunk_text=_format_chunk_for_llm(chunk),
                identifier_instruction=id_instruction,
                model=cfg.model,
                api_key=cfg.api_key,
                base_url=cfg.base_url,
                timeout=cfg.timeout_seconds,
            )
            if llm_result:
                summaries.append(llm_result)
                llm_chunks += 1
                continue
        # Fallback: structured preview (no API key, or LLM call failed)
        summaries.append(_summarize_chunk_fallback(chunk, cfg.identifier_policy))
        fallback_chunks += 1

    merged = _merge_summaries(summaries)
    if llm_chunks and fallback_chunks:
        summary_source = "mixed"
    elif llm_chunks:
        summary_source = "llm"
    else:
        summary_source = "fallback"

    log.info(
        "compaction.done",
        removed=len(to_compact),
        kept=len(kept),
        chunks=len(chunks),
        llm_model=cfg.model or "fallback",
        summary_source=summary_source,
    )

    return CompactionResult(
        summary=merged,
        kept_entries=kept,
        removed_count=len(to_compact),
        chunks_processed=len(chunks),
        summary_source=summary_source,
    )
