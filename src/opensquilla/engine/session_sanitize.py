"""Provider-request sanitization for OpenSquilla session history.

This module builds a clean request view from in-memory history. It removes
OpenSquilla/provider bookkeeping that the model does not need while preserving
the user-visible content and persisted transcript state.
"""

from __future__ import annotations

import json
from dataclasses import asdict, dataclass, is_dataclass
from pathlib import Path
from typing import Any

from pydantic import BaseModel

from opensquilla.provider import (
    ContentBlockText,
    ContentBlockThinking,
    ContentBlockToolResult,
    ContentBlockToolUse,
    Message,
)
from opensquilla.provider.types import ContentBlockDocument, ContentBlockImage

_BLOCK_FIELDS: dict[str, set[str]] = {
    "text": {"type", "text"},
    "tool_use": {"type", "id", "name", "input"},
    "tool_result": {"type", "tool_use_id", "content", "is_error"},
    "image": {"type", "source_type", "media_type", "data"},
    "document": {"type", "source_type", "media_type", "data", "title"},
    "thinking": {"type", "thinking", "signature"},
}

_BLOCK_MODELS: dict[str, type[BaseModel]] = {
    "text": ContentBlockText,
    "tool_use": ContentBlockToolUse,
    "tool_result": ContentBlockToolResult,
    "image": ContentBlockImage,
    "document": ContentBlockDocument,
    "thinking": ContentBlockThinking,
}


@dataclass(frozen=True)
class SessionSanitizeResult:
    """Metrics for one sanitized request-view build."""

    messages_in: int
    messages_out: int
    payload_chars_before: int
    payload_chars_after: int
    metadata_keys_removed: int = 0

    @property
    def changed(self) -> bool:
        return (
            self.metadata_keys_removed > 0
            or self.messages_in != self.messages_out
            or self.payload_chars_before != self.payload_chars_after
        )


def session_payload_chars(messages: list[Message]) -> int:
    """Return a stable JSON character estimate for a provider message list."""

    return len(json.dumps(_to_jsonable(messages), ensure_ascii=False, sort_keys=True))


def sanitize_session_messages(
    messages: list[Message],
) -> tuple[list[Message], SessionSanitizeResult]:
    """Return a provider-safe request view without mutating stored history.

    The sanitizer only removes metadata from message/block envelopes. It does
    not truncate or summarize tool result content; that remains the separate
    ``tool_result_compression`` responsibility.
    """

    payload_chars_before = session_payload_chars(messages)
    sanitized: list[Message] = []
    metadata_keys_removed = 0
    touched = False

    for message in messages:
        content, removed, content_changed = _sanitize_content(message.content)
        metadata_keys_removed += removed
        if content_changed:
            touched = True
            sanitized.append(
                Message(
                    role=message.role,
                    content=content,
                    reasoning_content=message.reasoning_content,
                )
            )
        else:
            sanitized.append(message)

    if not touched:
        sanitized = messages

    payload_chars_after = session_payload_chars(sanitized)
    return sanitized, SessionSanitizeResult(
        messages_in=len(messages),
        messages_out=len(sanitized),
        payload_chars_before=payload_chars_before,
        payload_chars_after=payload_chars_after,
        metadata_keys_removed=metadata_keys_removed,
    )


def _sanitize_content(content: Any) -> tuple[Any, int, bool]:
    if not isinstance(content, list):
        return content, 0, False

    sanitized_blocks: list[Any] = []
    removed_total = 0
    touched = False
    for block in content:
        sanitized_block, removed, changed = _sanitize_block(block)
        removed_total += removed
        touched = touched or changed
        sanitized_blocks.append(sanitized_block)

    if not touched:
        return content, removed_total, False
    return sanitized_blocks, removed_total, True


def _sanitize_block(block: Any) -> tuple[Any, int, bool]:
    if isinstance(block, dict):
        return _sanitize_block_dict(block)

    model_dump = getattr(block, "model_dump", None)
    if callable(model_dump):
        payload = model_dump(mode="python")
        sanitized, removed, changed = _sanitize_block_dict(payload)
        if not changed:
            return block, 0, False
        return sanitized, removed, True

    return block, 0, False


def _sanitize_block_dict(block: dict[str, Any]) -> tuple[Any, int, bool]:
    block_type = block.get("type")
    if not isinstance(block_type, str):
        return block, 0, False

    allowed = _BLOCK_FIELDS.get(block_type)
    if allowed is None:
        return block, 0, False

    cleaned = {key: block[key] for key in allowed if key in block}
    removed = len([key for key in block if key not in allowed])
    model_cls = _BLOCK_MODELS.get(block_type)
    if model_cls is None:
        return cleaned, removed, removed > 0

    try:
        return model_cls(**cleaned), removed, removed > 0
    except Exception:
        return cleaned, removed, removed > 0


def _to_jsonable(value: Any) -> Any:
    if isinstance(value, Message):
        payload: dict[str, Any] = {
            "role": value.role,
            "content": _to_jsonable(value.content),
        }
        if value.reasoning_content is not None:
            payload["reasoning_content"] = value.reasoning_content
        return payload
    if isinstance(value, BaseModel):
        return value.model_dump(mode="json")
    if is_dataclass(value) and not isinstance(value, type):
        return asdict(value)
    if isinstance(value, list):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, tuple):
        return [_to_jsonable(item) for item in value]
    if isinstance(value, dict):
        return {str(key): _to_jsonable(item) for key, item in value.items()}
    if isinstance(value, Path):
        return str(value)
    try:
        json.dumps(value)
    except TypeError:
        return repr(value)
    return value
