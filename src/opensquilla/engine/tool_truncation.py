"""Tool result truncation — token-budget-aware, head+tail strategy."""

from __future__ import annotations


def estimate_tokens(text: str) -> int:
    """Rough token estimate: ~4 chars per token."""
    return max(0, len(text) // 4)


def truncate_result(
    text: str,
    context_window_tokens: int,
    max_share: float = 0.25,
) -> str:
    """Truncate tool result if it exceeds max_share of context window.

    Strategy: keep head 70% + tail 20% of budget, insert truncation marker.
    Returns original text if within budget.
    """
    budget_tokens = int(context_window_tokens * max_share)
    text_tokens = estimate_tokens(text)

    if text_tokens <= budget_tokens:
        return text

    # Convert token budget to char budget (4 chars per token)
    budget_chars = budget_tokens * 4
    head_chars = int(budget_chars * 0.70)
    tail_chars = int(budget_chars * 0.20)

    if head_chars + tail_chars >= len(text):
        return text

    omitted = len(text) - head_chars - tail_chars
    marker = f"\n[...truncated {omitted} chars...]\n"
    return text[:head_chars] + marker + text[-tail_chars:]
