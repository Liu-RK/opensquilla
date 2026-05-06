"""humanizer skill — load, scan detects known patterns, rewrite is idempotent."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from opensquilla.skills.eligibility import EligibilityContext, check_eligibility
from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"
SCRIPTS = BUNDLED / "humanizer" / "scripts"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("humanizer")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "humanizer"


def test_eligibility_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("opensquilla.skills.eligibility.shutil.which", lambda name: None)
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def test_scan_detects_ai_vocab() -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import scan  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    text = "Let's delve into the multifaceted tapestry of modern systems."
    payload = scan.scan(text)
    pattern_names = {m["pattern"] for m in payload["matches"]}
    assert "ai_vocab" in pattern_names
    assert "inflated_symbolism" in pattern_names
    assert payload["summary"]["total"] >= 2


def test_scan_detects_negative_parallelism() -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import scan  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    text = "It's not just an editor, but a way of thinking."
    payload = scan.scan(text)
    pattern_names = {m["pattern"] for m in payload["matches"]}
    assert "negative_parallelism" in pattern_names


def test_scan_detects_vague_attribution() -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import scan  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    text = "Many experts say this is the future. Studies have shown it works."
    payload = scan.scan(text)
    pattern_names = {m["pattern"] for m in payload["matches"]}
    assert "vague_attribution" in pattern_names
    assert payload["summary"]["by_pattern"].get("vague_attribution", 0) >= 2


def test_rewrite_substitutes_trivial_terms(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import rewrite  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    src = "We will delve into how to leverage cutting-edge tools to facilitate growth."
    rewritten, applied = rewrite.apply_trivial(src)
    assert applied >= 4
    rewritten_lower = rewritten.lower()
    assert "delve into" not in rewritten_lower
    assert "leverage" not in rewritten_lower
    assert "cutting-edge" not in rewritten_lower
    assert "facilitate" not in rewritten_lower


def test_rewrite_emits_todo_block(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import rewrite  # type: ignore[import-not-found]
        import scan  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    src_path = tmp_path / "draft.md"
    src_path.write_text(
        "Our seamless tapestry of features will unlock the potential of users.",
        encoding="utf-8",
    )
    report_path = tmp_path / "report.json"
    report = scan.scan(src_path.read_text(encoding="utf-8"))
    report_path.write_text(json.dumps(report), encoding="utf-8")
    out_path = tmp_path / "out.md"

    text, _ = rewrite.apply_trivial(src_path.read_text(encoding="utf-8"))
    todo = rewrite.build_todo_block(report)
    out_path.write_text(text + "\n" + todo, encoding="utf-8")

    body = out_path.read_text(encoding="utf-8")
    assert "humanizer TODO" in body
    # Inflated symbolism was not auto-fixed, so it must appear in the TODO.
    assert "inflated_symbolism" in body
