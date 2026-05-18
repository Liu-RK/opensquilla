"""Context-overflow policy enforcement.

Helpers consulted by the gateway's chat entry-point before the turn is
handed off to the engine. The policy layer is deliberately small and
synchronous where possible — it either:

* returns :data:`PROCEED_NORMALLY` → the caller continues as today, or
* returns :class:`OverflowOutcome` carrying an error envelope (for REFUSE)
  or bookkeeping counters (for HARD_TRUNCATE / AUTO_SUMMARIZE) that the
  caller can use to shape the downstream turn.

The three policies:

* ``auto_summarize`` — require a qualified pre-compaction flush when
  configured, compact once, then proceed only if post-compaction token
  evidence proves the next call fits.
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
from opensquilla.session.compaction_lifecycle import (
    CompactionLifecycleResult,
    flush_receipt_allows_destructive_compaction,
    pre_compaction_flush_enabled,
)
from opensquilla.session.keys import parse_agent_id
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
    reason: str | None = None
    tokens_after: int | None = None
    remaining_budget_tokens: int | None = None
    removed_count: int = 0
    kept_count: int = 0
    summary_len: int = 0
    summary_source: str = "unknown"
    flush_receipt: Any = None
    lifecycle: CompactionLifecycleResult | None = None
    compacted_this_turn: bool = False
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


def _build_refusal_envelope(
    estimated: int, budget: int, reason: str = "context_overflow"
) -> dict[str, Any]:
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
        "reason": reason,
        "error": {
            "code": "context_overflow",
            "reason": reason,
        },
    }


async def _estimate_session_payload_tokens(
    message: str,
    transcript: list[Any],
    *,
    session_manager: Any | None = None,
    session_key: str = "",
    fallback_summary: str = "",
) -> int:
    total = _estimate_payload_tokens(message, transcript)
    get_summaries = getattr(session_manager, "get_summaries", None)
    if callable(get_summaries):
        summaries = await get_summaries(session_key)
        if summaries:
            for summary in summaries:
                total += estimate_tokens(str(getattr(summary, "summary_text", "") or ""))
            return total
    if fallback_summary:
        total += estimate_tokens(str(fallback_summary))
    return total


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
    flush_service: Any | None = None,
    compaction_marker: Any | None = None,
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
        outcome.reason = "context_overflow"
        outcome.refusal = _build_refusal_envelope(estimated, budget, outcome.reason)
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
            marker_has = getattr(compaction_marker, "has_compacted_this_turn", None)
            if callable(marker_has) and marker_has(session_key):
                compacted_transcript = await session_manager.get_transcript(session_key)
                post_estimate = await _estimate_session_payload_tokens(
                    message,
                    compacted_transcript,
                    session_manager=session_manager,
                    session_key=session_key,
                )
                outcome.tokens_after = post_estimate
                outcome.remaining_budget_tokens = max(budget - post_estimate, 0)
                if post_estimate <= budget and post_estimate < estimated:
                    outcome.summarized = True
                    outcome.retried = True
                    return outcome
                outcome.reason = "compaction_insufficient"
                outcome.refusal = _build_refusal_envelope(
                    post_estimate, budget, outcome.reason
                )
                return outcome

            flush_enabled = pre_compaction_flush_enabled(config)
            if flush_enabled and transcript and flush_service is None:
                outcome.reason = "compaction_flush_failed"
                outcome.refusal = _build_refusal_envelope(
                    estimated, budget, outcome.reason
                )
                outcome.lifecycle = CompactionLifecycleResult(
                    compacted=False,
                    refused=True,
                    reason=outcome.reason,
                    tokens_before=estimated,
                )
                log.warning(
                    "context_overflow.auto_summarize_refused",
                    session_key=session_key,
                    reason=outcome.reason,
                    error="flush_service_unavailable",
                )
                return outcome

            if flush_enabled and transcript:
                service = flush_service
                if service is None:
                    outcome.reason = "compaction_flush_failed"
                    outcome.refusal = _build_refusal_envelope(
                        estimated, budget, outcome.reason
                    )
                    return outcome
                try:
                    receipt = await service.execute(
                        transcript,
                        session_key,
                        agent_id=parse_agent_id(session_key),
                        timeout=30.0,
                        message_window=0,
                        segment_mode="auto",
                    )
                except Exception as exc:  # noqa: BLE001
                    outcome.reason = "compaction_flush_failed"
                    outcome.refusal = _build_refusal_envelope(
                        estimated, budget, outcome.reason
                    )
                    outcome.lifecycle = CompactionLifecycleResult(
                        compacted=False,
                        refused=True,
                        reason=outcome.reason,
                        tokens_before=estimated,
                    )
                    log.warning(
                        "context_overflow.auto_summarize_refused",
                        session_key=session_key,
                        reason=outcome.reason,
                        error=str(exc),
                    )
                    return outcome
                outcome.flush_receipt = receipt
                if not flush_receipt_allows_destructive_compaction(receipt):
                    outcome.reason = "compaction_flush_failed"
                    outcome.refusal = _build_refusal_envelope(
                        estimated, budget, outcome.reason
                    )
                    outcome.lifecycle = CompactionLifecycleResult(
                        compacted=False,
                        refused=True,
                        reason=outcome.reason,
                        tokens_before=estimated,
                        flush_receipt=receipt,
                    )
                    log.warning(
                        "context_overflow.auto_summarize_refused",
                        session_key=session_key,
                        reason=outcome.reason,
                    )
                    return outcome

            compact_with_result = getattr(session_manager, "compact_with_result", None)
            if callable(compact_with_result):
                result = await compact_with_result(session_key, budget, compaction_config)
                summary = getattr(result, "summary", "") or ""
                outcome.removed_count = int(getattr(result, "removed_count", 0) or 0)
                outcome.kept_count = len(getattr(result, "kept_entries", []) or [])
                outcome.summary_source = str(
                    getattr(result, "summary_source", "unknown") or "unknown"
                )
            else:
                summary = await call_compact_with_optional_config(
                    session_manager.compact,
                    session_key,
                    budget,
                    compaction_config,
                )
                outcome.removed_count = 1 if summary else 0
            compacted_transcript = await session_manager.get_transcript(session_key)
            post_estimate = await _estimate_session_payload_tokens(
                message,
                compacted_transcript,
                session_manager=session_manager,
                session_key=session_key,
                fallback_summary=str(summary or ""),
            )
            outcome.tokens_after = post_estimate
            outcome.remaining_budget_tokens = max(budget - post_estimate, 0)
            outcome.summary_len = len(str(summary or ""))

            if post_estimate > budget or post_estimate >= estimated:
                outcome.reason = "compaction_insufficient"
                outcome.refusal = _build_refusal_envelope(
                    post_estimate, budget, outcome.reason
                )
                outcome.lifecycle = CompactionLifecycleResult(
                    compacted=False,
                    refused=True,
                    reason=outcome.reason,
                    tokens_before=estimated,
                    tokens_after=post_estimate,
                    remaining_budget_tokens=outcome.remaining_budget_tokens,
                    removed_count=outcome.removed_count,
                    kept_count=outcome.kept_count,
                    summary_len=outcome.summary_len,
                    summary_source=outcome.summary_source,
                    flush_receipt=outcome.flush_receipt,
                )
                log.warning(
                    "context_overflow.auto_summarize_refused",
                    session_key=session_key,
                    reason=outcome.reason,
                    tokens_after=post_estimate,
                )
                return outcome

            outcome.summarized = True
            outcome.retried = True
            outcome.compacted_this_turn = True
            outcome.lifecycle = CompactionLifecycleResult(
                compacted=True,
                refused=False,
                tokens_before=estimated,
                tokens_after=post_estimate,
                remaining_budget_tokens=outcome.remaining_budget_tokens,
                removed_count=outcome.removed_count,
                kept_count=outcome.kept_count,
                summary_len=outcome.summary_len,
                summary_source=outcome.summary_source,
                flush_receipt=outcome.flush_receipt,
            )
            log.info(
                "context_overflow.auto_summarize_ok",
                session_key=session_key,
                tokens_before=estimated,
                tokens_after=post_estimate,
                remaining_budget_tokens=outcome.remaining_budget_tokens,
                summary_source=outcome.summary_source,
            )
        except Exception as exc:  # noqa: BLE001 — best-effort
            outcome.reason = "compaction_failed"
            outcome.refusal = _build_refusal_envelope(estimated, budget, outcome.reason)
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
