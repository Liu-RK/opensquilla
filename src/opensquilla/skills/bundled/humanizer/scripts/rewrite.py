"""Apply trivial AI-tell substitutions and emit a TODO list for the rest.

Trivial substitutions: vocabulary swaps that almost always read better.
Non-trivial cases (rule-of-three reorganization, paragraph restructuring,
adding voice) are emitted as a TODO block at the end of the output for the
host LLM to handle in a follow-up pass.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path
from typing import Any

# Conservative substitutions — only swap when the replacement reads
# correctly in nearly all sentence positions. Aggressive swaps belong in
# the TODO list, not here.
TRIVIAL_SUBSTITUTIONS: list[tuple[re.Pattern[str], str]] = [
    (re.compile(r"\bdelve into\b", re.IGNORECASE), "look at"),
    (re.compile(r"\bdelve\b", re.IGNORECASE), "examine"),
    (re.compile(r"\bdelving into\b", re.IGNORECASE), "looking at"),
    (re.compile(r"\bin today's\s+(?:fast-paced|rapidly-evolving)\s+\w+,?\s*", re.IGNORECASE), ""),
    (re.compile(r"\bcutting-edge\b", re.IGNORECASE), "modern"),
    (re.compile(r"\bstate-of-the-art\b", re.IGNORECASE), "current"),
    (re.compile(r"\bharness the power of\b", re.IGNORECASE), "use"),
    (re.compile(r"\bunlock the potential of\b", re.IGNORECASE), "use"),
    (re.compile(r"\bleverage\b", re.IGNORECASE), "use"),
    (re.compile(r"\bfacilitate\b", re.IGNORECASE), "help"),
    (re.compile(r"\butilize\b", re.IGNORECASE), "use"),
    (re.compile(r"\bin order to\b", re.IGNORECASE), "to"),
    (re.compile(r"\bplethora of\b", re.IGNORECASE), "many"),
    (re.compile(r"\bmyriad of\b", re.IGNORECASE), "many"),
]


def apply_trivial(text: str) -> tuple[str, int]:
    """Apply substitutions; return (rewritten_text, count_applied)."""
    count = 0
    new_text = text
    for pattern, replacement in TRIVIAL_SUBSTITUTIONS:
        new_text, n = pattern.subn(replacement, new_text)
        count += n
    # Collapse double spaces left behind by deletions.
    new_text = re.sub(r"  +", " ", new_text)
    new_text = re.sub(r" \n", "\n", new_text)
    return new_text, count


def build_todo_block(report: dict[str, Any]) -> str:
    """Emit a markdown TODO block listing patterns the host LLM should fix."""
    matches = report.get("matches", [])
    if not matches:
        return ""
    by_pattern: dict[str, list[dict[str, Any]]] = {}
    for match in matches:
        by_pattern.setdefault(match["pattern"], []).append(match)

    # Patterns that need human/LLM rewriting (the trivial path didn't fix).
    leaves = [
        "rule_of_three",
        "inflated_symbolism",
        "negative_parallelism",
        "vague_attribution",
        "em_dash_overuse",
        "conjunctive_overuse",
        "promotional",
        "ai_vocab",
    ]
    lines = ["", "<!--", "## humanizer TODO", ""]
    any_emitted = False
    for pattern in leaves:
        bucket = by_pattern.get(pattern, [])
        if not bucket:
            continue
        any_emitted = True
        lines.append(f"### {pattern} ({len(bucket)} occurrence(s))")
        for entry in bucket[:8]:
            snippet = entry.get("snippet", "")
            line_no = entry.get("line", "?")
            lines.append(f"- L{line_no}: {snippet}")
        if len(bucket) > 8:
            lines.append(f"- (+{len(bucket) - 8} more)")
        lines.append("")
    lines.append("-->")
    return "\n".join(lines) if any_emitted else ""


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Apply trivial humanizer rewrites.")
    parser.add_argument("--in", dest="input_path", type=Path, required=True)
    parser.add_argument(
        "--report",
        type=Path,
        default=None,
        help="Optional patterns.json from scan.py; emits a TODO block when supplied",
    )
    parser.add_argument("--out", type=Path, required=True)
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.input_path.is_file():
        print(f"error: {args.input_path} not found", file=sys.stderr)
        return 2
    text = args.input_path.read_text(encoding="utf-8")
    rewritten, count = apply_trivial(text)
    todo_block = ""
    if args.report is not None:
        if not args.report.is_file():
            print(f"error: report {args.report} not found", file=sys.stderr)
            return 2
        report = json.loads(args.report.read_text(encoding="utf-8"))
        todo_block = build_todo_block(report)
    args.out.parent.mkdir(parents=True, exist_ok=True)
    args.out.write_text(rewritten + ("\n" + todo_block if todo_block else ""), encoding="utf-8")
    print(json.dumps({"applied": count, "todo": bool(todo_block)}, ensure_ascii=False))
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
