"""Usage domain RPC handlers — wired to session manager."""

from __future__ import annotations

import time
from collections.abc import Mapping
from typing import Any

from opensquilla.gateway.rpc import RpcContext, get_dispatcher
from opensquilla.session.cost_rollup import rollup_cost_source

_d = get_dispatcher()


def _now_ms() -> int:
    return int(time.time() * 1000)


def _field(source: Any, name: str, default: Any = None) -> Any:
    if isinstance(source, Mapping):
        return source.get(name, default)
    return getattr(source, name, default)


def _first_field(source: Any, *names: str, default: Any = None) -> Any:
    for name in names:
        value = _field(source, name)
        if value is not None:
            return value
    return default


def _resolved_session_cost_fields(
    source: Any,
    *,
    input_tokens: int = 0,
    output_tokens: int = 0,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    ephemeral: bool = False,
) -> dict[str, Any]:
    legacy_total = _field(source, "estimated_cost_usd")
    total_cost = _field(source, "total_cost_usd")

    billed_cost = _field(source, "billed_cost_usd")
    if billed_cost is None:
        billed_cost = _field(source, "billed_cost", 0.0) or 0.0

    estimated_component = _field(source, "estimated_cost_component_usd")
    if estimated_component is None:
        source_name = _field(source, "cost_source")
        estimated_component = (
            float(total_cost or 0.0)
            if source_name in {None, "", "none", "opensquilla_estimate"}
            and not billed_cost
            else 0.0
        )

    missing_entries = _field(source, "missing_cost_entries", 0) or 0
    cost_source = _field(source, "cost_source")
    if total_cost is None:
        total_cost = legacy_total
    if (
        legacy_total
        and not billed_cost
        and not estimated_component
        and not missing_entries
        and cost_source in {None, "", "none", "opensquilla_estimate"}
    ):
        if not total_cost:
            total_cost = legacy_total
        estimated_component = legacy_total
    if total_cost is None:
        total_cost = 0.0

    if not cost_source or cost_source == "none":
        if billed_cost or estimated_component or missing_entries:
            cost_source = rollup_cost_source(
                billed_cost_usd=float(billed_cost or 0.0),
                estimated_cost_component_usd=float(estimated_component or 0.0),
                missing_cost_entries=int(missing_entries or 0),
            )
        elif input_tokens or output_tokens or cache_read_tokens or cache_write_tokens:
            cost_source = "unavailable"
        else:
            cost_source = "none"

    return {
        "cost_usd": float(total_cost or 0.0),
        "billed_cost_usd": float(billed_cost or 0.0),
        "estimated_cost_usd": float(estimated_component or 0.0),
        "cost_source": cost_source,
        "missing_cost_entries": int(missing_entries or 0),
        "cost_ephemeral": bool(ephemeral),
    }


def _usage_row(
    *,
    session_key: str,
    model: str | None,
    input_tokens: int,
    output_tokens: int,
    cost_usd: float,
    billed_cost_usd: float = 0.0,
    estimated_cost_usd: float = 0.0,
    cost_source: str = "none",
    missing_cost_entries: int = 0,
    cost_ephemeral: bool = False,
    cache_read_tokens: int = 0,
    cache_write_tokens: int = 0,
    created_at: int | None = None,
    updated_at: int | None = None,
    started_at: int | None = None,
    ended_at: int | None = None,
) -> dict[str, Any]:
    cost = round(cost_usd, 6)
    billed_cost = round(billed_cost_usd, 6)
    estimated_cost = round(estimated_cost_usd, 6)
    return {
        # Canonical keys used by newer RPC consumers.
        "sessionKey": session_key,
        "inputTokens": input_tokens,
        "outputTokens": output_tokens,
        "costUsd": cost,
        "billedCostUsd": billed_cost,
        "estimatedCostUsd": estimated_cost,
        "costSource": cost_source,
        "missingCostEntries": missing_cost_entries,
        "costEphemeral": cost_ephemeral,
        "cacheReadTokens": cache_read_tokens,
        "cacheWriteTokens": cache_write_tokens,
        "createdAt": created_at,
        "updatedAt": updated_at,
        "startedAt": started_at,
        "endedAt": ended_at,
        "model": model,
        # Compatibility aliases used by the shipped web UI.
        "session": session_key,
        "key": session_key,
        "input_tokens": input_tokens,
        "output_tokens": output_tokens,
        "cost_usd": cost,
        "billed_cost_usd": billed_cost,
        "estimated_cost_usd": estimated_cost,
        "cost_source": cost_source,
        "missing_cost_entries": missing_cost_entries,
        "cost_ephemeral": cost_ephemeral,
        "cache_read_tokens": cache_read_tokens,
        "cache_write_tokens": cache_write_tokens,
        "created_at": created_at,
        "updated_at": updated_at,
        "started_at": started_at,
        "ended_at": ended_at,
    }


def _tracker_rows(ctx: RpcContext, *, now_ms: int) -> list[dict[str, Any]]:
    if ctx.usage_tracker is None:
        return []
    all_sessions = ctx.usage_tracker.all_sessions()
    if not all_sessions:
        return []

    config_model = getattr(ctx.config, "llm", None) and ctx.config.llm.model or None
    rows = []
    for session_key, usage in all_sessions.items():
        cost_fields = _resolved_session_cost_fields(
            usage,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
            ephemeral=True,
        )
        cost_fields["cost_usd"] = usage.cost
        cost_fields["estimated_cost_usd"] = usage.cost
        cost_fields["cost_source"] = "opensquilla_estimate"
        row = _usage_row(
            session_key=session_key,
            model=usage.model_id or config_model,
            input_tokens=usage.input_tokens,
            output_tokens=usage.output_tokens,
            **cost_fields,
            cache_read_tokens=getattr(usage, "cache_read_tokens", 0) or 0,
            cache_write_tokens=getattr(usage, "cache_write_tokens", 0) or 0,
            created_at=now_ms,
            updated_at=now_ms,
        )
        row["modelBreakdown"] = getattr(usage, "model_breakdown", [])
        rows.append(row)
    return rows


def _append_tracker_only_rows(
    rows: list[dict[str, Any]],
    tracker_rows: list[dict[str, Any]],
) -> list[dict[str, Any]]:
    """Merge tracker rows into disk-loaded rows.

    Disk persistence (cost-rollup pipeline) records the final per-session model
    but no per-model breakdown. The in-memory tracker accumulates breakdown via
    ``SessionUsage._per_model`` while the session is alive. Without this merge,
    sessions that hit the billing path lose their breakdown on the next status
    fetch — the "auto · N models" UI never surfaces for auto-routed sessions
    even though the data is still in memory.
    """
    tracker_by_key = {tr["session"]: tr for tr in tracker_rows}
    seen = set()
    for row in rows:
        seen.add(row["session"])
        tracker_row = tracker_by_key.get(row["session"])
        if (
            tracker_row
            and tracker_row.get("modelBreakdown")
            and not row.get("modelBreakdown")
        ):
            row["modelBreakdown"] = tracker_row["modelBreakdown"]
    return rows + [row for row in tracker_rows if row["session"] not in seen]


def _usage_totals(rows: list[dict[str, Any]]) -> dict[str, int | float]:
    total_in = sum(int(row["input_tokens"] or 0) for row in rows)
    total_out = sum(int(row["output_tokens"] or 0) for row in rows)
    total_cost = sum(float(row["cost_usd"] or 0.0) for row in rows)
    return {
        "input": total_in,
        "output": total_out,
        "cost": total_cost,
        "cache_read": sum(int(row["cache_read_tokens"] or 0) for row in rows),
        "cache_write": sum(int(row["cache_write_tokens"] or 0) for row in rows),
    }


@_d.method("usage.status", scope="operator.read")
async def _handle_usage_status(params: dict | None, ctx: RpcContext) -> dict[str, Any]:
    now_ms = _now_ms()
    tracker_rows = _tracker_rows(ctx, now_ms=now_ms)

    if ctx.session_manager is None:
        totals = _usage_totals(tracker_rows)
        return {
            "totalSessions": len(tracker_rows),
            "activeSessions": len(tracker_rows),
            "totalInputTokens": totals["input"],
            "totalOutputTokens": totals["output"],
            "totalTokens": totals["input"] + totals["output"],
            "totalCostUsd": round(float(totals["cost"]), 6),
            "totalCacheReadTokens": totals["cache_read"],
            "totalCacheWriteTokens": totals["cache_write"],
            "sessions": tracker_rows,
        }
    try:
        sessions = await ctx.session_manager.list_sessions()
        rows = []
        active = sum(1 for s in sessions if _field(s, "status", "") == "running")
        for s in sessions:
            input_tokens = _first_field(s, "input_tokens", "total_input_tokens", default=0) or 0
            output_tokens = _first_field(s, "output_tokens", "total_output_tokens", default=0) or 0
            cache_read = _field(s, "cache_read", 0) or 0
            cache_write = _field(s, "cache_write", 0) or 0
            cost_fields = _resolved_session_cost_fields(
                s,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            )

            # Resolve model: session record > model_override > config default
            session_model = _field(s, "model") or _field(s, "model_override")
            if not session_model and ctx.config:
                session_model = getattr(ctx.config.llm, "model", None)
            rows.append(
                _usage_row(
                    session_key=_field(s, "session_key", "unknown"),
                    model=session_model,
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    **cost_fields,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                    created_at=_field(s, "created_at"),
                    updated_at=_field(s, "updated_at"),
                    started_at=_field(s, "started_at"),
                    ended_at=_field(s, "ended_at"),
                )
            )
        rows = _append_tracker_only_rows(rows, tracker_rows)
        totals = _usage_totals(rows)
        tracker_only_count = len(rows) - len(sessions)
        return {
            "totalSessions": len(rows),
            "activeSessions": active + tracker_only_count,
            "totalInputTokens": totals["input"],
            "totalOutputTokens": totals["output"],
            "totalTokens": totals["input"] + totals["output"],
            "totalCostUsd": round(float(totals["cost"]), 6),
            "totalCacheReadTokens": totals["cache_read"],
            "totalCacheWriteTokens": totals["cache_write"],
            "sessions": rows,
        }
    except (AttributeError, NotImplementedError):
        totals = _usage_totals(tracker_rows)
        return {
            "totalSessions": len(tracker_rows),
            "activeSessions": len(tracker_rows),
            "totalInputTokens": totals["input"],
            "totalOutputTokens": totals["output"],
            "totalTokens": totals["input"] + totals["output"],
            "totalCostUsd": round(float(totals["cost"]), 6),
            "totalCacheReadTokens": totals["cache_read"],
            "totalCacheWriteTokens": totals["cache_write"],
            "sessions": tracker_rows,
        }


@_d.method("usage.cost", scope="operator.read")
async def _handle_usage_cost(params: dict | None, ctx: RpcContext) -> dict[str, Any]:
    now_ms = _now_ms()
    tracker_rows = _tracker_rows(ctx, now_ms=now_ms)

    if ctx.session_manager is None:
        return {
            "breakdown": tracker_rows,
            "totalCostUsd": round(float(_usage_totals(tracker_rows)["cost"]), 6),
        }
    try:
        sessions = await ctx.session_manager.list_sessions()
        breakdown = []
        for s in sessions:
            input_tokens = _first_field(s, "input_tokens", "total_input_tokens", default=0) or 0
            output_tokens = _first_field(s, "output_tokens", "total_output_tokens", default=0) or 0
            cache_read = _field(s, "cache_read", 0) or 0
            cache_write = _field(s, "cache_write", 0) or 0
            cost_fields = _resolved_session_cost_fields(
                s,
                input_tokens=input_tokens,
                output_tokens=output_tokens,
                cache_read_tokens=cache_read,
                cache_write_tokens=cache_write,
            )
            breakdown.append(
                _usage_row(
                    session_key=_field(s, "session_key", "unknown"),
                    model=_field(s, "model", "unknown"),
                    input_tokens=input_tokens,
                    output_tokens=output_tokens,
                    **cost_fields,
                    cache_read_tokens=cache_read,
                    cache_write_tokens=cache_write,
                    created_at=_field(s, "created_at"),
                    updated_at=_field(s, "updated_at"),
                    started_at=_field(s, "started_at"),
                    ended_at=_field(s, "ended_at"),
                )
            )
        breakdown = _append_tracker_only_rows(breakdown, tracker_rows)
        return {
            "breakdown": breakdown,
            "totalCostUsd": round(float(_usage_totals(breakdown)["cost"]), 6),
        }
    except (AttributeError, NotImplementedError):
        return {
            "breakdown": tracker_rows,
            "totalCostUsd": round(float(_usage_totals(tracker_rows)["cost"]), 6),
        }
