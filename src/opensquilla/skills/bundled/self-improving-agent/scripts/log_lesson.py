"""Append a timestamped lesson entry to a `.learnings/*.md` file."""

from __future__ import annotations

import argparse
from datetime import UTC, datetime
from pathlib import Path

CATEGORIES: dict[str, str] = {
    "correction": "LEARNINGS.md",
    "knowledge_gap": "LEARNINGS.md",
    "best_practice": "LEARNINGS.md",
    "error": "ERRORS.md",
    "feature": "FEATURE_REQUESTS.md",
}


def append_entry(root: Path, category: str, text: str) -> Path:
    if category not in CATEGORIES:
        raise ValueError(
            f"unknown category {category!r}; pick one of {sorted(CATEGORIES)}"
        )
    learnings_dir = root / ".learnings"
    learnings_dir.mkdir(parents=True, exist_ok=True)
    target = learnings_dir / CATEGORIES[category]
    if not target.exists():
        target.write_text(f"# {target.stem}\n\n---\n", encoding="utf-8")

    stamp = datetime.now(UTC).isoformat()
    body = text.strip()
    entry = f"\n## [{stamp}] {category}\n\n{body}\n"
    with target.open("a", encoding="utf-8") as fh:
        fh.write(entry)
    return target


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Append a lesson to .learnings/.")
    parser.add_argument(
        "--root",
        type=Path,
        default=Path.cwd(),
        help="Workspace root (defaults to cwd)",
    )
    parser.add_argument(
        "--category",
        required=True,
        choices=sorted(CATEGORIES),
        help="One of: correction, knowledge_gap, best_practice, error, feature",
    )
    parser.add_argument("--text", required=True, help="Body of the lesson, plain markdown")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    target = append_entry(args.root, args.category, args.text)
    import json
    print(json.dumps({"file": str(target), "category": args.category}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
