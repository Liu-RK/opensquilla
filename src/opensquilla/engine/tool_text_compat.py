"""Helpers for model text that encodes tool calls."""

from __future__ import annotations

import json
import re

_PLAIN_JSON_TOOL_CALL_RE = re.compile(
    r"^\s*([A-Za-z_][A-Za-z0-9_.:-]*)\s*(\{.*\})\s*$",
    re.DOTALL,
)
_PLAIN_JSON_TOOL_PREFIX_RE = re.compile(
    r"([A-Za-z_][A-Za-z0-9_.:-]*)\s*(?=\{)",
)


def _find_trailing_tool_call_start(text: str, tool_name: str) -> int | None:
    decoder = json.JSONDecoder()
    for match in reversed(list(_PLAIN_JSON_TOOL_PREFIX_RE.finditer(text))):
        if match.group(1) != tool_name:
            continue
        try:
            arguments, end = decoder.raw_decode(text, match.end())
        except json.JSONDecodeError:
            continue
        if text[end:].strip():
            continue
        if not isinstance(arguments, dict):
            continue
        return match.start()
    return None


def strip_synthetic_tool_call_text(text: str, tool_name: str) -> str:
    """Remove trailing machine-readable tool-call text synthesized into a tool call."""

    if not text:
        return text

    if "<minimax:tool_call>" in text:
        return ""

    lines = text.splitlines()
    for index in range(len(lines) - 1, -1, -1):
        if lines[index].strip():
            candidate = lines[index]
            break
    else:
        return text

    match = _PLAIN_JSON_TOOL_CALL_RE.match(candidate)
    if match is None or match.group(1) != tool_name:
        start = _find_trailing_tool_call_start(text, tool_name)
        if start is None:
            return text
        return text[:start].rstrip()

    prefix = "\n".join(lines[:index]).rstrip()
    return prefix


def strip_synthetic_tool_call_suffix(text: str, tool_names: list[str]) -> str:
    """Remove text-encoded tool calls for any of the supplied synthetic tools."""

    cleaned = text
    for tool_name in tool_names:
        cleaned = strip_synthetic_tool_call_text(cleaned, tool_name)
    return cleaned
