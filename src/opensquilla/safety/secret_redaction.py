"""Best-effort redaction for secret-looking text before persistence or LLM replay."""

from __future__ import annotations

import re
from bisect import bisect_left
from collections import Counter
from typing import Any

_REDACTED = "[REDACTED]"
REDACTED_SECRET_VALUE = _REDACTED

_SECRET_TOKEN_PATTERNS: tuple[re.Pattern[str], ...] = (
    re.compile(r"\bsk-or-v1-[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bsk-[A-Za-z0-9_-]{20,}\b"),
    # TokenRhythm keys use underscores (sk_tr_...), invisible to the
    # hyphen-anchored patterns above. The tail class includes -_ like the
    # sk- pattern's so a key abutting punctuation over-masks instead of
    # failing the trailing \b and leaking whole.
    re.compile(r"\bsk_tr_[A-Za-z0-9_-]{16,}\b"),
    re.compile(r"\bgh[pousr]_[A-Za-z0-9_]{20,}\b"),
)
# Matches an Authorization / Proxy-Authorization header for ANY scheme (Bearer,
# Basic, Digest, Negotiate, NTLM, token, ...) and masks the entire credential
# after the header, up to a line boundary. A known scheme word is preserved for
# readability (optional group 2); an unknown/absent scheme is masked whole. The
# prior Bearer-only regex left Basic/Digest credentials (which contain '=', ' ',
# '"') exposed.
_AUTH_HEADER_RE = re.compile(
    r"(?i)((?:proxy-)?authorization\s*:\s*)"
    r"((?:bearer|basic|digest|negotiate|ntlm|token)\s+)?"
    r"[^\r\n]+"
)


def _redact_auth_header(match: re.Match[str]) -> str:
    header = match.group(1)
    scheme = match.group(2) or ""
    return f"{header}{scheme}{_REDACTED}"


_SECRET_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]+)\s*([:=])\s*"
    r"(\[REDACTED\](?:[^\s,;'\")}\]]+)?|[^\s,;'\")}\]]+)"
)
# Second pass: values that start with a quote are invisible to the pattern above
# (its value class excludes quotes so nested assignments inside quoted strings can
# still be redacted individually). Match whole quoted values here so
# ``password: "hunter2"`` is masked; the trailing ``["']\S*`` arm covers
# unterminated quotes.
_SECRET_QUOTED_ASSIGNMENT_RE = re.compile(
    r"(?i)\b([A-Za-z0-9_.-]+)\s*([:=])\s*"
    r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*'|[\"']\S*)"
)
_SECRET_QUOTED_KEY_ASSIGNMENT_RE = re.compile(
    r"(?i)([\"'])([A-Za-z0-9_.-]+)\1(\s*[:=]\s*)"
    r"(\"(?:\\.|[^\"\\])*\"|'(?:\\.|[^'\\])*')"
)

_SECRET_KEY_PARTS = (
    "authorization",
    "api-key",
    "apikey",
    "api_key",
    "x-api-key",
    "password",
    "secret",
    "credential",
)
_SECRET_KEY_EXACT = {
    "token",
    "access_token",
    "refresh_token",
    "id_token",
    "bearer_token",
}


def is_secret_key(key: str) -> bool:
    lowered = key.lower()
    return lowered in _SECRET_KEY_EXACT or any(part in lowered for part in _SECRET_KEY_PARTS)


def _is_secret_assignment_key(key: str) -> bool:
    lowered = key.lower()
    if lowered == "authorization":
        return False
    return is_secret_key(lowered) or lowered.endswith(("token", ".token", "_token", "-token"))


def _redact_assignment(match: re.Match[str]) -> str:
    key, separator = match.group(1), match.group(2)
    if not _is_secret_assignment_key(key):
        return match.group(0)
    return f"{key}{separator}{_REDACTED}"


def _redact_quoted_key_assignment(match: re.Match[str]) -> str:
    quote, key, separator, value = (
        match.group(1),
        match.group(2),
        match.group(3),
        match.group(4),
    )
    if not is_secret_key(key):
        return match.group(0)
    value_quote = value[0] if value.startswith(("\"", "'")) else ""
    return f"{quote}{key}{quote}{separator}{value_quote}{_REDACTED}{value_quote}"


def redact_secret_text(text: str) -> str:
    redacted = text
    redacted = _AUTH_HEADER_RE.sub(_redact_auth_header, redacted)
    redacted = _SECRET_QUOTED_KEY_ASSIGNMENT_RE.sub(
        _redact_quoted_key_assignment,
        redacted,
    )
    redacted = _SECRET_ASSIGNMENT_RE.sub(_redact_assignment, redacted)
    redacted = _SECRET_QUOTED_ASSIGNMENT_RE.sub(_redact_assignment, redacted)
    for pattern in _SECRET_TOKEN_PATTERNS:
        redacted = pattern.sub(_REDACTED, redacted)
    return redacted


def redact_secret_value(value: Any, *, key: str | None = None) -> Any:
    if key and is_secret_key(key):
        return _REDACTED
    if isinstance(value, str):
        return redact_secret_text(value)
    if isinstance(value, dict):
        return {str(k): redact_secret_value(v, key=str(k)) for k, v in value.items()}
    if isinstance(value, list):
        return [redact_secret_value(item) for item in value]
    if isinstance(value, tuple):
        return tuple(redact_secret_value(item) for item in value)
    return value


class RedactedSecretResolutionError(ValueError):
    """Raised when a protected redaction placeholder cannot be resolved safely."""


def find_redacted_secret_matches(text: str, masked_text: str) -> list[tuple[int, int]]:
    """Find source spans whose redacted form exactly equals ``masked_text``."""

    if _REDACTED not in masked_text:
        return []
    pieces = masked_text.split(_REDACTED)
    expression = r"[^\r\n]+".join(re.escape(piece) for piece in pieces)
    pattern = re.compile(expression)
    matches: list[tuple[int, int]] = []
    for match in pattern.finditer(text):
        if redact_secret_text(match.group(0)) == masked_text:
            matches.append((match.start(), match.end()))
    return matches


def restore_redacted_secret_placeholders(original: str, proposed: str) -> str:
    """Restore unchanged secret values in model-proposed text.

    A redaction marker means "keep the value from the corresponding original
    position". Explicit replacement values remain untouched.
    """

    if _REDACTED not in proposed:
        return proposed

    original_lines = original.splitlines(keepends=True)
    proposed_lines = proposed.splitlines(keepends=True)
    masked_lines = [redact_secret_text(line) for line in original_lines]
    masked_keys = [_line_without_ending(line) for line in masked_lines]
    proposed_keys = [_line_without_ending(line) for line in proposed_lines]

    anchor_pairs = _unique_context_anchor_pairs(masked_keys, proposed_keys)
    proposed_anchor_indices = [proposed_index for proposed_index, _original_index in anchor_pairs]

    used_original_lines: set[int] = set()
    resolved_lines = list(proposed_lines)
    for proposed_index, proposed_line in enumerate(proposed_lines):
        if _REDACTED not in proposed_line:
            continue

        def _try_original_line(index: int) -> str | None:
            if (
                index in used_original_lines
                or _line_without_ending(original_lines[index]) == masked_keys[index]
            ):
                return None
            try:
                return _restore_redacted_line_values(
                    original_lines[index],
                    masked_lines[index],
                    proposed_line,
                )
            except RedactedSecretResolutionError:
                return None

        anchored = {
            index: resolved
            for index in _context_candidate_indices(
                proposed_index,
                anchor_pairs,
                proposed_anchor_indices,
                original_line_count=len(original_lines),
            )
            if (resolved := _try_original_line(index)) is not None
        }
        if len(anchored) == 1:
            compatible = anchored
        elif anchored:
            compatible = {}
        else:
            compatible = {
                index: resolved
                for index in range(len(original_lines))
                if (resolved := _try_original_line(index)) is not None
            }

        original_index = next(iter(compatible)) if len(compatible) == 1 else None
        if original_index is None:
            raise RedactedSecretResolutionError(
                "A [REDACTED] placeholder has no unambiguous corresponding existing secret "
                "line. Keep unique surrounding context or provide an explicit new value."
            )
        used_original_lines.add(original_index)
        resolved_lines[proposed_index] = compatible[original_index]

    return "".join(resolved_lines)


def _line_without_ending(line: str) -> str:
    return line.rstrip("\r\n")


def _line_ending(line: str) -> str:
    if line.endswith("\r\n"):
        return "\r\n"
    if line.endswith("\n"):
        return "\n"
    if line.endswith("\r"):
        return "\r"
    return ""


def _redacted_marker_anchors(line: str) -> tuple[str | None, ...]:
    """Return the assignment/header key immediately preceding each marker."""

    anchors: list[str | None] = []
    for prefix in line.split(_REDACTED)[:-1]:
        match = re.search(
            r"(?i)[\"']?([A-Za-z0-9_.-]+)[\"']?\s*[:=][^:=\r\n]*$",
            prefix,
        )
        anchors.append(match.group(1).lower() if match is not None else None)
    return tuple(anchors)


def _unique_context_anchor_pairs(
    original_lines: list[str],
    proposed_lines: list[str],
) -> list[tuple[int, int]]:
    """Return unique unchanged non-secret lines as proposed/original anchors."""

    original_counts = Counter(original_lines)
    proposed_counts = Counter(proposed_lines)
    original_positions = {
        line: index
        for index, line in enumerate(original_lines)
        if _REDACTED not in line and original_counts[line] == 1
    }
    return [
        (proposed_index, original_positions[line])
        for proposed_index, line in enumerate(proposed_lines)
        if _REDACTED not in line
        and proposed_counts[line] == 1
        and line in original_positions
    ]


def _context_candidate_indices(
    proposed_index: int,
    anchor_pairs: list[tuple[int, int]],
    proposed_anchor_indices: list[int],
    *,
    original_line_count: int,
) -> set[int]:
    if not anchor_pairs:
        return set()
    insertion = bisect_left(proposed_anchor_indices, proposed_index)
    nearby = []
    if insertion:
        nearby.append(anchor_pairs[insertion - 1])
    if insertion < len(anchor_pairs):
        nearby.append(anchor_pairs[insertion])
    return {
        candidate
        for proposed_anchor, original_anchor in nearby
        for candidate in (original_anchor + (proposed_index - proposed_anchor),)
        if 0 <= candidate < original_line_count
    }


def _restore_redacted_line_values(
    original_line: str,
    masked_line: str,
    proposed_line: str,
) -> str:
    original_body = _line_without_ending(original_line)
    masked_body = _line_without_ending(masked_line)
    proposed_body = _line_without_ending(proposed_line)
    pieces = masked_body.split(_REDACTED)
    expression = "^" + r"([^\r\n]+?)".join(re.escape(piece) for piece in pieces) + "$"
    match = re.fullmatch(expression, original_body)
    if match is None or redact_secret_text(original_body) != masked_body:
        raise RedactedSecretResolutionError(
            "The corresponding source line no longer matches its redacted form."
        )
    values = list(match.groups())
    proposed_pieces = proposed_body.split(_REDACTED)
    source_anchors = _redacted_marker_anchors(masked_body)
    proposed_anchors = _redacted_marker_anchors(proposed_body)
    if any(anchor is None for anchor in proposed_anchors):
        if proposed_anchors != source_anchors:
            raise RedactedSecretResolutionError(
                "A redacted value lacks an unambiguous secret-field anchor."
            )
        value_indices = list(range(len(values)))
    else:
        value_indices = []
        used: set[int] = set()
        for anchor in proposed_anchors:
            matching = [
                index
                for index, source_anchor in enumerate(source_anchors)
                if source_anchor == anchor and index not in used
            ]
            if len(matching) != 1:
                raise RedactedSecretResolutionError(
                    f"Secret field {anchor!r} is missing or ambiguous on its source line."
                )
            value_index = matching[0]
            used.add(value_index)
            value_indices.append(value_index)

    resolved = proposed_pieces[0]
    for value_index, suffix in zip(value_indices, proposed_pieces[1:], strict=True):
        value = values[value_index]
        if resolved.endswith((" ", "\t")):
            value = value.lstrip(" \t")
        resolved += value + suffix
    return resolved + _line_ending(proposed_line)
