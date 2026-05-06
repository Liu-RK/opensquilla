# OpenSquilla Module Contract

This document records the current package-level import contract used by the
Tier A architecture guard. It is intentionally conservative: the first guard
captures the current baseline and prevents new top-level package edges or new
packages joining the existing import cycle without an explicit review.

## Layer intent

- `compat`, `persistence`, `observability`, `safety`, `search`, and `dist` are
  foundation packages. They should stay side-effect-light and should not import
  runtime orchestration packages.
- `provider`, `session`, `memory`, `tools`, `scheduler`, and `skills` are service
  packages. They may depend on foundation packages and stable public contracts,
  but new imports back into `gateway` or deep `engine` internals should be
  treated as boundary-expansion work.
- `engine` owns turn orchestration and agent execution.
- `gateway`, `channels`, and `cli` are entrypoint/integration packages. They may
  compose services, but service packages should not add new dependencies back
  into entrypoints.
- `contrib` hosts bundled optional router assets and should not become a general
  dependency target outside documented runtime integration points.

## Current cycle baseline

The current package graph has one known strongly connected component containing:

`agents`, `channels`, `engine`, `gateway`, `identity`, `mcp`, `memory`,
`onboarding`, `provider`, `sandbox`, `scheduler`, `session`, `skills`, `tools`.

That set is a shrink target, not a design goal. New packages must not join it
silently, and new top-level import edges must update the guard with a rationale.

## Guard

`tests/test_ci/test_architecture_import_contracts.py` parses imports under
`src/opensquilla` and checks two invariants:

1. Actual top-level `opensquilla.<package>` import edges are a subset of the
   approved baseline.
2. Packages participating in multi-package import cycles are a subset of the
   approved cycle baseline.

When refactoring removes imports, keep the smaller graph. When a new import edge
is truly necessary, update both this document and the test in the same commit,
with a commit-message `Constraint:` explaining the boundary reason.
