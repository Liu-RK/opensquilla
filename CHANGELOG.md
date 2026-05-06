# Changelog

All notable changes to this project will be documented in this file.

The format is based on [Keep a Changelog](https://keepachangelog.com/en/1.0.0/).

## [Unreleased]

### Added

- PID file lock to prevent two gateway instances from sharing the same state directory.
- Core observability counters: `opensquilla_queue_depth`, `in_flight_turns_total`, `turn_cancellations_total`, `queue_full_errors_total`.
- CI matrix on `ubuntu-latest` and `windows-latest` × Python 3.11/3.12, including a metric-name drift check and a tracemalloc leak smoke step.
- Per-channel-adapter in-flight reply cap (`_ChannelInFlightSet`) so a single channel cannot exhaust the global concurrency budget.
- Cross-session fair queueing: sessions sharing an `agent_id` round-robin available slots by completion count.
- Session epoch counter so events from a pre-reset turn are discarded by the frontend after `session.reset`.
- Atomic write helper for transcript attachments (`_atomic_write_bytes`): tmp + fsync + `os.replace`.
- Concurrency env overrides — `OPENSQUILLA_TASK_MAX_CONCURRENCY` and `OPENSQUILLA_CHANNEL_INFLIGHT_CAP` — with invalid-value fallback and warning logs.

### Changed

- `TurnRunner` and `TaskRuntime` share a single per-session `asyncio.Lock` (injected via `session_lock_provider`), removing the two-layer lock dictionary and the reverse-acquire risk it created.

### Fixed

- Channel adapter ghost-turn bug: a `TaskQueueFullError` no longer leaves a dangling user message in the transcript.
- `TaskRuntime` terminal-state dictionary leak across `_tasks`, `_session_locks`, and `_pending_by_session`.
