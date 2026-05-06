"""Scan text for signs of AI-generated writing.

Pure regex/heuristic. No LLM calls. Reports JSON with per-pattern matches
and a severity summary the host can act on.
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from dataclasses import dataclass
from pathlib import Path
from typing import Any


@dataclass(frozen=True)
class PatternRule:
    name: str
    severity: str  # high | medium | low
    pattern: re.Pattern[str]


# AI vocabulary — the largest single source of "AI tell" signal.
AI_VOCAB = {
    "delve",
    "delves",
    "delving",
    "tapestry",
    "landscape",
    "realm",
    "journey",
    "embark",
    "navigate",
    "navigates",
    "unleash",
    "unlock",
    "unveil",
    "unveils",
    "pivotal",
    "multifaceted",
    "nuanced",
    "seamless",
    "seamlessly",
    "robust",
    "comprehensive",
    "intricate",
    "cutting-edge",
    "state-of-the-art",
    "revolutionary",
    "transformative",
    "paradigm",
    "paradigm-shifting",
    "leverage",
    "leverages",
    "elevate",
    "showcase",
    "harness",
    "foster",
    "fosters",
}

VAGUE_ATTRIBUTIONS = {
    "many experts say",
    "it is widely believed",
    "it is often said",
    "many believe",
    "studies have shown",
    "it is well known",
    "research has shown",
    "experts agree",
    "people often say",
}

PROMOTIONAL_PHRASES = {
    "cutting-edge",
    "state-of-the-art",
    "world-class",
    "best-in-class",
    "next-generation",
    "industry-leading",
    "groundbreaking",
}

CONJUNCTIVES = {
    "furthermore",
    "moreover",
    "additionally",
    "in addition",
    "consequently",
    "subsequently",
    "ultimately",
}

INFLATED_SYMBOLISM_PATTERNS = [
    re.compile(r"\b(tapestry|landscape|realm|fabric|journey|odyssey)\s+of\s+\w+", re.IGNORECASE),
]

NEGATIVE_PARALLELISM = re.compile(
    r"\bnot\s+(?:just|only|merely|simply)\s+[^,\n]+,\s+but\s+", re.IGNORECASE
)


def _word_token_pattern(words: set[str]) -> re.Pattern[str]:
    parts = [re.escape(w) for w in sorted(words, key=len, reverse=True)]
    return re.compile(r"\b(" + "|".join(parts) + r")\b", re.IGNORECASE)


AI_VOCAB_RE = _word_token_pattern(AI_VOCAB)
VAGUE_RE = re.compile(
    r"\b(" + "|".join(re.escape(p) for p in VAGUE_ATTRIBUTIONS) + r")\b",
    re.IGNORECASE,
)
PROMO_RE = _word_token_pattern(PROMOTIONAL_PHRASES)
CONJ_RE = _word_token_pattern(CONJUNCTIVES)


def detect_em_dash_overuse(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    paragraphs = text.split("\n\n")
    cursor_line = 1
    for para in paragraphs:
        words = len(para.split())
        em_dashes = para.count("—") + para.count(" -- ")
        if words >= 50 and em_dashes >= 2 and em_dashes / max(words, 1) * 1000 >= 15:
            out.append(
                {
                    "pattern": "em_dash_overuse",
                    "line": cursor_line,
                    "snippet": para[:120],
                    "severity": "medium",
                    "count": em_dashes,
                    "words": words,
                }
            )
        cursor_line += para.count("\n") + 2
    return out


def detect_rule_of_three(text: str) -> list[dict[str, Any]]:
    """Triplet lists with no obvious semantic justification (heuristic)."""
    pattern = re.compile(
        r"\b(\w+),\s+(\w+),?\s+and\s+(\w+)\b",
        re.IGNORECASE,
    )
    out: list[dict[str, Any]] = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        # Skip obvious technical lists (numeric, identifiers).
        for match in pattern.finditer(line):
            terms = [match.group(1), match.group(2), match.group(3)]
            # Filter false positives where one term is numeric or uppercase id.
            if any(t.isdigit() for t in terms) or any(t.isupper() for t in terms):
                continue
            if any(len(t) <= 2 for t in terms):
                continue
            out.append(
                {
                    "pattern": "rule_of_three",
                    "line": line_idx,
                    "snippet": match.group(0),
                    "severity": "low",
                    "matched_terms": terms,
                }
            )
    return out


def detect_word_set(
    text: str, regex: re.Pattern[str], pattern_name: str, severity: str
) -> list[dict[str, Any]]:
    """One entry per match so summary counts reflect occurrences, not lines."""
    out: list[dict[str, Any]] = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        for match in regex.finditer(line):
            out.append(
                {
                    "pattern": pattern_name,
                    "line": line_idx,
                    "snippet": line.strip()[:160],
                    "severity": severity,
                    "matched_terms": [match.group(0)],
                }
            )
    return out


def detect_inflated_symbolism(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        for regex in INFLATED_SYMBOLISM_PATTERNS:
            for match in regex.finditer(line):
                out.append(
                    {
                        "pattern": "inflated_symbolism",
                        "line": line_idx,
                        "snippet": match.group(0),
                        "severity": "medium",
                    }
                )
    return out


def detect_negative_parallelism(text: str) -> list[dict[str, Any]]:
    out: list[dict[str, Any]] = []
    for line_idx, line in enumerate(text.splitlines(), start=1):
        for match in NEGATIVE_PARALLELISM.finditer(line):
            out.append(
                {
                    "pattern": "negative_parallelism",
                    "line": line_idx,
                    "snippet": match.group(0),
                    "severity": "low",
                }
            )
    return out


def scan(text: str) -> dict[str, Any]:
    matches: list[dict[str, Any]] = []
    matches.extend(detect_em_dash_overuse(text))
    matches.extend(detect_rule_of_three(text))
    matches.extend(detect_inflated_symbolism(text))
    matches.extend(detect_negative_parallelism(text))
    matches.extend(detect_word_set(text, AI_VOCAB_RE, "ai_vocab", "high"))
    matches.extend(detect_word_set(text, VAGUE_RE, "vague_attribution", "medium"))
    matches.extend(detect_word_set(text, PROMO_RE, "promotional", "medium"))
    matches.extend(detect_word_set(text, CONJ_RE, "conjunctive_overuse", "low"))

    summary: dict[str, Any] = {
        "total": len(matches),
        "by_severity": {"high": 0, "medium": 0, "low": 0},
        "by_pattern": {},
    }
    for m in matches:
        sev = m["severity"]
        summary["by_severity"][sev] = summary["by_severity"].get(sev, 0) + 1
        pat = m["pattern"]
        summary["by_pattern"][pat] = summary["by_pattern"].get(pat, 0) + 1
    return {"matches": matches, "summary": summary}


def _parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="Scan text for AI-writing patterns.")
    parser.add_argument("--in", dest="input_path", type=Path, required=True)
    parser.add_argument("--out", type=Path, default=None)
    parser.add_argument("--json", action="store_true", help="(default; kept for clarity)")
    return parser.parse_args()


def main() -> int:
    args = _parse_args()
    if not args.input_path.is_file():
        print(f"error: {args.input_path} not found", file=sys.stderr)
        return 2
    text = args.input_path.read_text(encoding="utf-8")
    payload = scan(text)
    encoded = json.dumps(payload, ensure_ascii=False, indent=2)
    if args.out is not None:
        args.out.write_text(encoded, encoding="utf-8")
    else:
        print(encoded)
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
