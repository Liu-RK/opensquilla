"""deep-research skill — load, plan→iterate→compile round-trip."""

from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

from opensquilla.skills.eligibility import EligibilityContext, check_eligibility
from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"
SCRIPTS = BUNDLED / "deep-research" / "scripts"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("deep-research")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "deep-research"
    description = spec.description.lower()
    # Must explicitly distinguish from sibling summarize skill.
    assert "summarize" in description


def test_eligibility_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    """Skill has no requires block; eligibility should pass unconditionally."""
    monkeypatch.setattr("opensquilla.skills.eligibility.shutil.which", lambda name: None)
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def test_full_pipeline(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import compile as compile_mod  # type: ignore[import-not-found]
        import iterate  # type: ignore[import-not-found]
        import plan as plan_mod  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    plan_path = tmp_path / "plan.json"
    plan = plan_mod.Plan(
        question="What changed in agent runtimes between 2024 and 2026?",
        depth="overview",
        created_at="2026-05-06T00:00:00+00:00",
        subquestions=plan_mod.make_subquestions("test", "overview"),
    )
    # Fill in subquestion text — host LLM normally does this.
    for idx, sq in enumerate(plan.subquestions):
        sq.question = f"Sub-question {idx + 1} text."
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")

    fetch_payload = iterate.under_target(plan)
    assert len(fetch_payload) == len(plan.subquestions)

    # Record one source per sub-question to drive coverage to 100%.
    evidence = [
        {
            "subquestion_id": sq.id,
            "url": f"https://example.com/{sq.id}",
            "title": f"Article for {sq.id}",
            "excerpt": f"Excerpt for {sq.id}.",
            "relevance": 0.85,
            "fetched_at": "2026-05-06T01:00:00+00:00",
        }
        for sq in plan.subquestions
    ]
    added = iterate.record_evidence(plan, evidence)
    assert added == len(plan.subquestions)
    assert plan.done is True
    assert plan.overall_coverage() == pytest.approx(1.0)

    # Persist and recompile.
    plan_path.write_text(plan.model_dump_json(indent=2), encoding="utf-8")
    out_md = tmp_path / "report.md"
    out_md.write_text(compile_mod.render(plan), encoding="utf-8")
    text = out_md.read_text(encoding="utf-8")
    assert "Research report" in text
    assert "References" in text
    # Each subquestion's URL must appear as a citation.
    for sq in plan.subquestions:
        assert f"https://example.com/{sq.id}" in text


def test_plan_persistence_round_trip(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import plan as plan_mod  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    p = plan_mod.Plan(
        question="Q",
        depth="thorough",
        created_at="now",
        subquestions=plan_mod.make_subquestions("Q", "thorough"),
    )
    raw = p.model_dump_json()
    p2 = plan_mod.Plan.model_validate_json(raw)
    assert len(p2.subquestions) == len(p.subquestions)
    assert all(sq.target_sources == 3 for sq in p2.subquestions)
    # JSON-serializable end-to-end.
    json.loads(raw)
