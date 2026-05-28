# Memory Safety Floor and Background Distill Design

## Goal

Stabilize WebUI long-context chat and destructive compaction by separating
deterministic transcript safety from semantic memory quality.

The core contract is:

```text
Memory safety is required before destructive compaction.
Memory intelligence is best-effort and repairable.
```

This design avoids another patch around `archive_failed` or repair receipts.
It changes the dependency structure so normal chat and compaction safety no
longer depend on LLM distillation, JSON parsing, or the model-callable
`memory_save` scanner.

## Problem

OpenSquilla currently mixes two different responsibilities:

- Semantic memory writes through `memory_save`.
- Forensic raw transcript archive used as a safety fallback before compaction.

The raw fallback is written under `memory/.raw_fallbacks/`, but it still uses
the `memory_save` tool path. That path sanitizes and scans semantic memory
content before writing. A raw transcript can naturally contain strings such as
`<system>` or `ignore previous instructions`, so the fallback can be blocked
by the semantic memory threat scanner and return `archive_failed`.

That makes semantic memory health part of the compaction safety path. The
result is fragile: long-context WebUI chat can be blocked or degraded because
a best-effort memory distill or raw fallback write failed for semantic-tool
reasons.

## Non-Goals

- Do not replace Dream, Honcho-like recall, or the broader memory architecture
  in this phase.
- Do not widen `memory_save` with broad scanner bypasses.
- Do not treat failed semantic distillation as success.
- Do not expose raw checkpoint or raw archive internals to ordinary chat users.
- Do not remove the existing repair service; make its scope clearer.

## Architecture

Introduce or clarify three boundaries while reusing existing code where safe.

### TranscriptSafetyArchive

Owns deterministic transcript preservation before destructive compaction.

Responsibilities:

- Write checkpoints or raw archives without calling `memory_save`.
- Enforce narrow sidecar paths such as `memory/.checkpoints/` and
  `memory/.raw_fallbacks/`.
- Write atomically or idempotently.
- Return path, content hash, coverage metadata, and receipt status.
- Never index archived content into recall.
- Never expose this writer as a model-callable tool.

The existing checkpoint implementation can be reused as the preferred safety
floor. Raw archive remains an internal fallback when checkpoint coverage is
not enough or when the current code path needs a raw transcript artifact for
repair.

### SemanticMemoryDistiller

Owns LLM-based memory extraction and promotion.

Responsibilities:

- Run the existing session flush proposal and `memory_save` flow.
- Preserve semantic scanner behavior for promoted memory.
- Record `distill_failed`, `repair_pending`, or similar ledger states when it
  cannot produce safe semantic memory.
- Run inline only when cheap and safe, otherwise run in the background.
- Never be required for destructive-compaction safety once deterministic
  archive coverage exists.

The first implementation can keep `SessionFlushService` as the concrete
distiller, but its role should be described as semantic distill, not the
source of compaction safety.

### CompactionSafetyGate

Owns the decision to allow destructive compaction.

Responsibilities:

- Allow compaction when deterministic safety evidence covers the transcript
  being removed.
- Block destructive compaction when no safe checkpoint/archive receipt exists.
- Treat semantic memory status as advisory, not fatal.
- Emit explicit safety and semantic statuses so UI/RPC code does not conflate
  the two.

The existing `flush_receipt_allows_destructive_compaction()` name is too
narrow for this design. Either add a new outer helper such as
`compaction_safety_allows_destructive_compaction()` or rename callers toward
the safety-gate concept while keeping compatibility wrappers during migration.

## Data Flow

```text
User/WebUI turn
  |
  v
Context pressure detected
  |
  v
Deterministic safety archive/checkpoint
  |-- failure --> block destructive compact; keep chat/session intact
  |
  v
Destructive compact allowed
  |
  v
Compact history
  |
  v
Semantic distill runs best-effort
  |-- success --> promoted memory + receipt
  |-- failure --> repair_pending/distill_failed + non-blocking status
```

## Status Model

Separate safety state from semantic memory state.

```text
safety_status:
  safe
  degraded_archive
  unsafe

semantic_status:
  healthy
  pending
  degraded
  failed
```

Examples:

- Checkpoint succeeds and LLM flush succeeds:
  `safety_status=safe`, `semantic_status=healthy`.
- Checkpoint succeeds and LLM flush times out:
  `safety_status=safe`, `semantic_status=degraded`.
- Checkpoint succeeds, raw archive succeeds, LLM flush parse fails:
  `safety_status=degraded_archive`, `semantic_status=failed`.
- Checkpoint fails and raw archive fails:
  `safety_status=unsafe`; destructive compaction is blocked.

WebUI and RPC flows should only block normal progress on `safety_status=unsafe`.
Semantic failures should be reported as non-blocking memory organization or
repair work.

## Implementation Scope

First phase implementation should stay focused on stabilizing the mechanism.

Likely touched areas:

- `src/opensquilla/memory/archive.py`
- `src/opensquilla/memory/session_flush.py`
- `src/opensquilla/session/compaction_lifecycle.py`
- `src/opensquilla/engine/runtime.py`
- `src/opensquilla/gateway/context_overflow.py`
- `src/opensquilla/gateway/rpc_sessions.py`
- `src/opensquilla/tools/builtin/memory_tools.py`
- Relevant tests under `tests/`

Expected behavior changes:

1. Raw transcript archive no longer calls `memory_save`.
2. The internal archive writer accepts raw transcript content that would be
   unsafe as promoted semantic memory.
3. `memory_save` continues to block the same content for normal memory paths.
4. Raw archives and checkpoints remain unindexed and hidden from recall.
5. Compaction safety uses deterministic receipt evidence.
6. Semantic distill failure does not block WebUI chat or destructive compaction
   when safety evidence exists.
7. Repair service consumes failed semantic distill and raw archive receipts as
   quality work, not as proof that the current compact is unsafe.

## Compatibility and Migration

- Keep existing receipt rows readable.
- Keep legacy raw fallback admin list/show/repair APIs.
- If model-callable `memory_save` still accepts `memory/.raw_fallbacks/` for
  compatibility, mark that path deprecated and do not rely on it for new
  safety behavior.
- New safety helpers should be additive first, then callers can migrate from
  flush-specific helpers to safety-gate helpers.
- Existing checkpoint receipts should remain valid safety evidence when path
  and content hash are present.

## Verification Plan

Required regression tests:

- Raw archive with `<system>ignore previous instructions</system>` succeeds.
- Raw archive is not indexed and is not returned by memory search.
- `memory_save` with the same content to a normal memory path is still blocked.
- Checkpoint success plus semantic flush failure still allows compaction.
- Checkpoint/archive failure blocks destructive compaction.
- WebUI context overflow does not return a fatal error for semantic distill
  failure when safety evidence exists.
- Repair service can consume raw archive receipts.
- Legacy raw fallback list/show APIs still work.

Suggested command set:

```bash
PYTHONPATH=$PWD/src TMPDIR=/dev/shm .venv/bin/pytest -q \
  tests/test_memory_flush.py \
  tests/test_memory_search_defaults.py \
  tests/test_session/test_compaction_lifecycle.py \
  tests/test_engine/test_preflight_compaction.py \
  tests/test_gateway/test_context_overflow.py \
  tests/test_gateway/test_rpc_sessions.py \
  tests/test_memory_repair_service.py
```

## Future Refactor Path

This design should remain compatible with a later full memory pipeline:

```text
capture -> archive -> distill -> promote -> recall
```

The first phase implements the `capture/archive` safety boundary and reclassifies
existing flush behavior as `distill/promote`. That means future memory backend
work can replace the distiller or recall layer without reopening the compact
safety decision.
