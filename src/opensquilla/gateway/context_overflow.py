"""Context-overflow policy enforcement.

Helpers consulted by the gateway's chat entry-point before the turn is
handed off to the engine. The policy layer is deliberately small and
synchronous where possible — it either:

* returns :data:`PROCEED_NORMALLY` → the caller continues as today, or
* returns :class:`OverflowOutcome` carrying an error envelope (for REFUSE)
  or bookkeeping counters (for HARD_TRUNCATE / AUTO_SUMMARIZE) that the
  caller can use to shape the downstream turn.

The three policies:

* ``auto_summarize`` — call ``session_manager.compact()`` once, then let
  the normal turn proceed (the compaction collapses older history into a
  summary so the next call fits).
* ``hard_truncate`` — drop oldest transcript entries from the in-memory
  history list until the estimated token count is under budget. The
  caller uses the shortened list.
* ``refuse`` — short-circuit with a stable error envelope; the caller
  must not invoke the provider.
"""

from __future__ import annotations

from dataclasses import dataclass, field
from typing import Any

import structlog

from opensquilla.gateway.config import ContextOverflowPolicy, GatewayConfig
from opensquilla.session.compaction import call_compact_with_optional_config
from opensquilla.session.tokenizer import estimate_tokens

log = structlog.get_logger(__name__)


@dataclass
class OverflowOutcome:
    """Result of applying a context-overflow policy for one turn."""

    policy: ContextOverflowPolicy
    over_budget: bool = False
    estimated_tokens: int = 0
    budget_tokens: int = 0
    # Only populated for REFUSE: stable error envelope shaped like the
    # tool-failure envelope so UI code has one rendering path.
    refusal: dict[str, Any] | None = None
    # Only populated for HARD_TRUNCATE: how many transcript entries were
    # dropped to fit under budget.
    truncated_entries: int = 0
    # Only populated for AUTO_SUMMARIZE: whether compaction was triggered.
    summarized: bool = False
    retried: bool = False
    # Possibly mutated history. HARD_TRUNCATE shortens this list in place.
    trimmed_history: list[Any] = field(default_factory=list)


def _estimate_payload_tokens(message: str, transcript: list[Any]) -> int:
    """Estimate the token cost of (history + new message).

    Uses the shared :func:`opensquilla.session.tokenizer.estimate_tokens` so
    the budget comparison is apples-to-apples with on-disk bookkeeping.
    """

    total = estimate_tokens(message or "")
    for entry in transcript or []:
        content = getattr(entry, "content", None)
        if isinstance(content, str):
            total += estimate_tokens(content)
        elif content is not None:
            total += estimate_tokens(str(content))
    return total


def _build_refusal_envelope(estimated: int, budget: int) -> dict[str, Any]:
    """Shape the REFUSE error payload the way UI/tool-error callers expect."""

    return {
        "status": "error",
        "error_class": "context_overflow",
        "user_message": (
            "Your conversation is too long for the model. "
            "Please start a new session or remove some earlier messages."
        ),
        "retry_allowed": False,
        "estimated_tokens": estimated,
        "budget_tokens": budget,
    }

# Envelope shape note:
# This UI-facing refusal shares the common tool-failure fields, but it
# intentionally carries overflow-specific metadata as extra keys.


async def apply_context_overflow_policy(
    *,
    config: GatewayConfig,
    message: str,
    transcript: list[Any],
    session_key: str,
    session_manager: Any | None = None,
    compaction_config: Any | None = None,
    policy_override: ContextOverflowPolicy | None = None,
    budget_override: int | None = None,
) -> OverflowOutcome:
    """Apply the gateway's overflow policy to the upcoming turn.

    Parameters
    ----------
    config:
        The gateway config. ``config.context_overflow_policy`` and
        ``config.context_budget_tokens`` provide defaults.
    message:
        The new user message.
    transcript:
        The existing session transcript (list of ``TranscriptEntry``-like
        objects with a ``content`` attribute).
    session_key:
        Used for logging and as the handle passed to
        ``session_manager.compact`` for the AUTO_SUMMARIZE branch.
    session_manager:
        Optional session manager used to run compaction when the policy
        is AUTO_SUMMARIZE. When None (e.g. in unit tests) the AUTO
        branch degrades to a best-effort "drop oldest, retry" proxy so
        the turn can still proceed.
    compaction_config:
        Optional provider-backed config passed through to
        ``session_manager.compact`` for AUTO_SUMMARIZE.
    policy_override / budget_override:
        Test + per-session knobs.

    Returns
    -------
    OverflowOutcome
        ``over_budget=False`` means the caller can proceed unchanged.
        For REFUSE, the caller must return ``outcome.refusal``; for
        HARD_TRUNCATE, the caller should use ``outcome.trimmed_history``
        instead of the original transcript.
    """

    policy = policy_override or config.context_overflow_policy
    budget = budget_override if budget_override is not None else config.context_budget_tokens
    estimated = _estimate_payload_tokens(message, transcript)

    outcome = OverflowOutcome(
        policy=policy,
        estimated_tokens=estimated,
        budget_tokens=budget,
        trimmed_history=list(transcript or []),
    )

    if estimated <= budget:
        return outcome

    outcome.over_budget = True
    log.info(
        "context_overflow.triggered",
        session_key=session_key,
        policy=policy.value,
        estimated_tokens=estimated,
        budget_tokens=budget,
    )

    if policy == ContextOverflowPolicy.REFUSE:
        outcome.refusal = _build_refusal_envelope(estimated, budget)
        return outcome

    if policy == ContextOverflowPolicy.HARD_TRUNCATE:
        # Drop oldest transcript entries until estimated tokens fit.
        trimmed = list(transcript or [])
        while trimmed and _estimate_payload_tokens(message, trimmed) > budget:
            trimmed.pop(0)
            outcome.truncated_entries += 1
        outcome.trimmed_history = trimmed
        log.info(
            "context_overflow.hard_truncate",
            session_key=session_key,
            dropped=outcome.truncated_entries,
            remaining=len(trimmed),
        )
        return outcome

    # ContextOverflowPolicy.AUTO_SUMMARIZE
    if session_manager is not None:
        try:
            await call_compact_with_optional_config(
                session_manager.compact,
                session_key,
                budget,
                compaction_config,
            )
            outcome.summarized = True
            outcome.retried = True
            log.info("context_overflow.auto_summarize_ok", session_key=session_key)
        except Exception as exc:  # noqa: BLE001 — best-effort
            log.warning(
                "context_overflow.auto_summarize_failed",
                session_key=session_key,
                error=str(exc),
            )
    else:
        # No session manager wired in — degrade to drop-oldest proxy so
        # the turn still fits. This path is exercised by unit tests; the
        # production gateway always wires a real session manager.
        trimmed = list(transcript or [])
        while trimmed and _estimate_payload_tokens(message, trimmed) > budget:
            trimmed.pop(0)
            outcome.truncated_entries += 1
        outcome.trimmed_history = trimmed
        outcome.summarized = False
        outcome.retried = True
        log.info(
            "context_overflow.auto_summarize_proxy",
            session_key=session_key,
            dropped=outcome.truncated_entries,
        )

    return outcome
