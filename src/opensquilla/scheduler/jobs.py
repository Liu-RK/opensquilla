"""Job execution: timeout, backoff, and post-execution state machine."""

from __future__ import annotations

import asyncio
import logging
from collections.abc import Awaitable, Callable
from datetime import UTC, datetime, timedelta

from .parser import parse_cron
from .persistence import JobStore
from .types import CronJob, HandlerResult, JobExecution, JobStatus, ScheduleKind, clear_reservation

logger = logging.getLogger(__name__)

# Exponential backoff schedule for retryable jobs.
BACKOFF_SCHEDULE: list[int] = [30, 60, 300, 900, 3600]  # 30s, 1m, 5m, 15m, 60m
MAX_CONSECUTIVE_ERRORS: int = 5
_ONE_SHOT_MAX_RETRIES: int = 3

HandlerFn = Callable[[CronJob], Awaitable[HandlerResult | str | tuple | None]]


def compute_backoff(consecutive_errors: int) -> float:
    """Return backoff delay in seconds for the given consecutive error count.

    Returns 0.0 for zero errors, otherwise indexes into BACKOFF_SCHEDULE
    (capped at the last entry).
    """
    if consecutive_errors <= 0:
        return 0.0
    idx = min(consecutive_errors - 1, len(BACKOFF_SCHEDULE) - 1)
    return float(BACKOFF_SCHEDULE[idx])


async def execute_with_timeout(job: CronJob, handler: HandlerFn) -> JobExecution:
    """Wrap a handler call with asyncio timeout, returning a JobExecution record.

    The handler may return:
    - str: treated as summary text
    - (str, str): treated as (summary, session_key)
    - None: no summary
    """
    execution = JobExecution(job_id=job.id, started_at=datetime.now(UTC))
    try:
        task = handler(job)
        if job.timeout_seconds <= 0:
            result = await task
        else:
            result = await asyncio.wait_for(task, timeout=job.timeout_seconds)
        execution.success = True
        if isinstance(result, HandlerResult):
            execution.summary = result.summary[:500] if result.summary else None
            execution.session_key = result.session_key
            execution.delivery_status = result.delivery_status
        elif isinstance(result, tuple) and len(result) >= 2:
            execution.summary = result[0][:500] if isinstance(result[0], str) else None
            execution.session_key = result[1] or ""
            if len(result) >= 3:
                execution.delivery_status = result[2] or ""
        elif isinstance(result, str):
            execution.summary = result[:500]
        else:
            execution.summary = None
    except TimeoutError:
        execution.success = False
        execution.error = f"Timeout after {job.timeout_seconds}s"
        logger.warning("job_timeout id=%s timeout=%.1f", job.id, job.timeout_seconds)
    except Exception as exc:
        execution.success = False
        execution.error = str(exc)
        logger.exception("job_error id=%s", job.id)
    finally:
        execution.finished_at = datetime.now(UTC)
    return execution


def _next_run(job: CronJob, after: datetime) -> datetime:
    """Compute the next execution time for a recurring job after *after*."""
    if job.schedule_kind == ScheduleKind.EVERY and job.cron_expr.isdigit():
        # Anchor-based interval: add interval_seconds to after
        interval_seconds = int(job.cron_expr)
        return after + timedelta(seconds=interval_seconds)

    # Standard cron: scan forward minute-by-minute
    expr = parse_cron(job.cron_expr)
    candidate = after.replace(second=0, microsecond=0) + timedelta(minutes=1)
    for _ in range(2_102_400):
        if expr.matches(candidate):
            return candidate + timedelta(seconds=job.jitter_seconds)
        candidate += timedelta(minutes=1)
    raise ValueError(f"No valid next run found for expression '{job.cron_expr}'")


async def apply_result(job: CronJob, execution: JobExecution, store: JobStore) -> None:
    """Compatibility wrapper for tests and non-reserved state transitions.

    Production scheduler execution should use ``apply_reserved_result`` so the
    caller proves ownership of a persisted reservation token.
    """
    current = await store.get(job.id)
    if current is None:
        return
    if current.status in (JobStatus.PAUSED, JobStatus.DISABLED):
        return

    delete_job = _apply_result_state(current, execution, datetime.now(UTC))
    if delete_job:
        await store.delete(current.id)
    else:
        await store.save(current)


async def apply_reserved_result(
    job_id: str,
    reservation_token: str,
    execution: JobExecution,
    store: JobStore,
) -> bool:
    """Apply an execution result only when the reservation token still owns the job."""
    current = await store.get(job_id)
    if current is None:
        return False
    if current.reservation_token != reservation_token:
        return False
    if current.status in (JobStatus.PAUSED, JobStatus.DISABLED):
        clear_reservation(current)
        await store.save(current)
        return True

    delete_job = _apply_result_state(current, execution, datetime.now(UTC))
    if delete_job:
        await store.delete(current.id)
    else:
        await store.save(current)
    return True


def _apply_result_state(job: CronJob, execution: JobExecution, now: datetime) -> bool:
    """Post-execution state machine: update job state based on execution outcome.

    Handles:
    - Deleted/paused while running (no-op)
    - Success: reset error counters, reschedule or disable/delete
    - Failure: increment counters, backoff, mark FAILED or DISABLED at thresholds

    Returns True when the job should be deleted.
    """
    if execution.success:
        job.consecutive_errors = 0
        job.backoff_until = None
        job.last_error = None
        job.run_count += 1
        job.updated_at = now

        if job.schedule_kind == ScheduleKind.AT:
            clear_reservation(job)
            if job.delete_after_run:
                return True
            else:
                job.status = JobStatus.DISABLED
                job.enabled = False
        else:
            try:
                job.next_run_at = _next_run(job, now)
                job.status = JobStatus.PENDING
            except Exception as exc:
                _mark_schedule_compute_failed(job, exc, now, increment_error=True)
            else:
                clear_reservation(job)

    else:
        job.consecutive_errors += 1
        job.error_count += 1
        job.last_error = execution.error
        job.run_count += 1
        job.updated_at = now

        is_recurring = job.schedule_kind in (ScheduleKind.CRON, ScheduleKind.EVERY)
        if is_recurring:
            if job.consecutive_errors >= MAX_CONSECUTIVE_ERRORS:
                job.status = JobStatus.FAILED
                job.next_run_at = None
                job.backoff_until = None
                clear_reservation(job)
                logger.error(
                    "job_failed_permanently id=%s consecutive_errors=%d",
                    job.id,
                    job.consecutive_errors,
                )
            else:
                backoff_secs = compute_backoff(job.consecutive_errors)
                try:
                    job.next_run_at = _next_run(job, now)
                except Exception as exc:
                    _mark_schedule_compute_failed(job, exc, now, increment_error=False)
                else:
                    job.backoff_until = now + timedelta(seconds=backoff_secs)
                    job.status = JobStatus.PENDING
                    clear_reservation(job)
        else:
            # One-shot AT job
            if job.consecutive_errors >= _ONE_SHOT_MAX_RETRIES:
                job.status = JobStatus.DISABLED
                job.enabled = False
                clear_reservation(job)
                logger.error(
                    "job_one_shot_disabled id=%s consecutive_errors=%d",
                    job.id,
                    job.consecutive_errors,
                )
            else:
                backoff_secs = compute_backoff(job.consecutive_errors)
                job.backoff_until = now + timedelta(seconds=backoff_secs)
                job.status = JobStatus.PENDING
                clear_reservation(job)

    return False


def _mark_schedule_compute_failed(
    job: CronJob,
    exc: Exception,
    now: datetime,
    *,
    increment_error: bool,
) -> None:
    if increment_error:
        job.error_count += 1
        job.consecutive_errors += 1
    job.status = JobStatus.FAILED
    job.last_error = f"schedule compute failed: {exc}"
    job.updated_at = now
    job.backoff_until = None
    job.next_run_at = None
    clear_reservation(job)
