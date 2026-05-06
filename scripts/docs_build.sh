#!/usr/bin/env bash
# opensquilla docs-site build wrapper (S24)
#
# Default invocation runs `uv run --extra docs mkdocs build --strict`,
# which produces the static site under ./site/ and fails on any broken
# internal link (mkdocs.yml declares strict: true).
#
# Pass --deploy to invoke `mkdocs gh-deploy --force` instead. This is
# operator-invoked only; CI deployment should be wired deliberately with
# repository credentials rather than as a side effect of local builds.
#
# Exit codes:
#   0 — build (or deploy) succeeded
#   1 — build failed (broken link, config error, etc.)
#   2 — docs extra not synced (`uv sync --extra docs` not yet run)
#
# Usage:
#   scripts/docs_build.sh             # local build → ./site/
#   scripts/docs_build.sh --deploy    # gh-deploy (operator opt-in)

set -euo pipefail

mode="build"
if [[ "${1:-}" == "--deploy" ]]; then
  mode="deploy"
fi

if ! command -v uv >/dev/null 2>&1; then
  printf 'scripts/docs_build.sh: `uv` not on PATH — install uv first.\n' >&2
  exit 2
fi

# Sanity probe: is the docs extra available? If not, emit a helpful
# error rather than let mkdocs fail with a cryptic ModuleNotFoundError.
if ! uv run --extra docs python -c "import mkdocs" >/dev/null 2>&1; then
  printf 'scripts/docs_build.sh: docs extra not synced.\n' >&2
  printf 'Run: uv sync --extra docs\n' >&2
  exit 2
fi

case "$mode" in
  build)
    exec uv run --extra docs mkdocs build --strict
    ;;
  deploy)
    exec uv run --extra docs mkdocs gh-deploy --force
    ;;
esac
