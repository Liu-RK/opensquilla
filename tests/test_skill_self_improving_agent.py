"""self-improving-agent skill — load, init idempotency, log appends."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from opensquilla.skills.eligibility import EligibilityContext, check_eligibility
from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"
SCRIPTS = BUNDLED / "self-improving-agent" / "scripts"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("self-improving-agent")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "self-improving-agent"


def test_hermes_requires_memory_save() -> None:
    spec = _spec()
    assert spec is not None
    assert "memory_save" in spec.requires_tools, (
        "self-improving-agent should be Hermes-gated on memory_save tool availability"
    )


def test_description_disjoint_from_memory() -> None:
    spec = _spec()
    assert spec is not None
    desc_lower = spec.description.lower()
    # The skill must distinguish from the existing `memory` skill in retrieval.
    # Disjoint trigger words: the description must mention "learn" semantics
    # while explicitly contrasting with memory's "remember/recall" semantics.
    assert "learn" in desc_lower or "lesson" in desc_lower or "post-mortem" in desc_lower
    assert "remember" not in desc_lower or "memory" in desc_lower, (
        "if 'remember' appears, the description must explicitly contrast with the memory skill"
    )


def test_eligibility_passes(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr("opensquilla.skills.eligibility.shutil.which", lambda name: None)
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def test_init_learnings_idempotent(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import init_learnings  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    first = init_learnings.init(tmp_path)
    assert first == {
        "LEARNINGS.md": True,
        "ERRORS.md": True,
        "FEATURE_REQUESTS.md": True,
    }
    learnings_path = tmp_path / ".learnings" / "LEARNINGS.md"
    initial_content = learnings_path.read_text(encoding="utf-8")

    second = init_learnings.init(tmp_path)
    assert second == {
        "LEARNINGS.md": False,
        "ERRORS.md": False,
        "FEATURE_REQUESTS.md": False,
    }
    after_content = learnings_path.read_text(encoding="utf-8")
    assert initial_content == after_content


def test_log_lesson_appends(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import init_learnings  # type: ignore[import-not-found]
        import log_lesson  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    init_learnings.init(tmp_path)
    target = log_lesson.append_entry(tmp_path, "correction", "User pointed out X.")
    assert target.name == "LEARNINGS.md"

    text = target.read_text(encoding="utf-8")
    assert "correction" in text
    assert "User pointed out X." in text

    # Log a second time; both entries should be present.
    log_lesson.append_entry(tmp_path, "correction", "Another lesson.")
    text = target.read_text(encoding="utf-8")
    assert text.count("correction") >= 2
    assert "User pointed out X." in text
    assert "Another lesson." in text


def test_log_lesson_routes_by_category(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import init_learnings  # type: ignore[import-not-found]
        import log_lesson  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    init_learnings.init(tmp_path)
    err = log_lesson.append_entry(tmp_path, "error", "git push failed (auth).")
    feat = log_lesson.append_entry(tmp_path, "feature", "User wanted Vercel deploy.")
    assert err.name == "ERRORS.md"
    assert feat.name == "FEATURE_REQUESTS.md"


def test_log_lesson_unknown_category_raises(tmp_path: Path) -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import log_lesson  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    with pytest.raises(ValueError):
        log_lesson.append_entry(tmp_path, "bogus", "noop")
