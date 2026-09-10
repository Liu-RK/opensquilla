"""Shared diagnostics for exact text edits."""

from __future__ import annotations


def find_match_start_lines(
    content: str,
    old_text: str,
    limit: int = 20,
) -> tuple[int, list[int]]:
    """Return non-overlapping match count and bounded 1-based start lines."""

    if not old_text:
        return 0, []
    match_count = content.count(old_text)
    candidate_lines: list[int] = []
    search_from = 0
    previous_match_start = 0
    line_number = 1
    for _ in range(min(match_count, max(0, limit))):
        match_start = content.find(old_text, search_from)
        if match_start < 0:
            break
        line_number += content.count("\n", previous_match_start, match_start)
        candidate_lines.append(line_number)
        previous_match_start = match_start
        search_from = match_start + len(old_text)
    return match_count, candidate_lines


def ambiguous_edit_guidance(
    match_count: int,
    candidate_lines: list[int],
) -> str:
    """Explain how to disambiguate an exact edit without retrying blindly."""

    lines = ", ".join(str(line) for line in candidate_lines)
    guidance = [f"Candidate lines: {lines}."]
    omitted = match_count - len(candidate_lines)
    if omitted > 0:
        guidance.append(f"Additional matches omitted: {omitted}")
    guidance.extend(
        (
            "Use read_file around the intended line, then retry with a longer unique "
            "old_text.",
            "Do not include read_file line-number prefixes in old_text.",
        )
    )
    return "\n".join(guidance)


__all__ = ["ambiguous_edit_guidance", "find_match_start_lines"]
