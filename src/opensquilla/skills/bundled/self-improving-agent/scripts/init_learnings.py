"""Idempotently create the workspace `.learnings/` directory and seed files."""

from __future__ import annotations

import argparse
from pathlib import Path

LEARNINGS_HEADER = (
    "# Learnings\n\n"
    "Corrections, insights, and knowledge gaps captured during development.\n\n"
    "**Categories**: correction | error | feature | knowledge_gap | best_practice\n\n"
    "---\n"
)

ERRORS_HEADER = (
    "# Errors\n\n"
    "Command failures and integration errors, redacted.\n\n"
    "---\n"
)

FEATURES_HEADER = (
    "# Feature requests\n\n"
    "Capabilities the user has asked for that do not yet exist.\n\n"
    "---\n"
)


def init(root: Path) -> dict[str, bool]:
    """Create `.learnings/` and seed files. Returns a per-file `created` flag."""
    learnings_dir = root / ".learnings"
    learnings_dir.mkdir(parents=True, exist_ok=True)

    targets = {
        "LEARNINGS.md": LEARNINGS_HEADER,
        "ERRORS.md": ERRORS_HEADER,
        "FEATURE_REQUESTS.md": FEATURES_HEADER,
    }

    created: dict[str, bool] = {}
    for name, header in targets.items():
        path = learnings_dir / name
        if path.exists():
            created[name] = False
            continue
        path.write_text(header, encoding="utf-8")
        created[name] = True
    return created


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Seed workspace .learnings/ files.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Workspace root (defaults to cwd)",
    )
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    created = init(args.root)
    import json
    print(json.dumps({"root": str(args.root), "created": created}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
