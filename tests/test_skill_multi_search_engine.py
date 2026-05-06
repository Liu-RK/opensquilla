"""multi-search-engine skill — load + missing-key engines fail soft."""

from __future__ import annotations

import sys
from pathlib import Path

import pytest

from opensquilla.skills.eligibility import EligibilityContext, check_eligibility
from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"
SCRIPTS = BUNDLED / "multi-search-engine" / "scripts"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("multi-search-engine")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "multi-search-engine"


def test_eligibility_with_python(monkeypatch: pytest.MonkeyPatch) -> None:
    monkeypatch.setattr(
        "opensquilla.skills.eligibility.shutil.which",
        lambda name: "/usr/bin/python3" if name in {"python", "python3"} else None,
    )
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def test_brave_without_key_fails_soft(monkeypatch: pytest.MonkeyPatch) -> None:
    """Engine missing its API key must not crash the run; record an error and continue."""
    monkeypatch.delenv("BRAVE_API_KEY", raising=False)
    sys.path.insert(0, str(SCRIPTS))
    try:
        import search  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    payload = search.search_all(
        query="anything",
        engines=["brave"],
        limit=3,
        strict=False,
    )
    assert payload["query"] == "anything"
    assert payload["results"] == []
    assert any("BRAVE_API_KEY" in e["reason"] for e in payload["errors"])


def test_unknown_engine_recorded() -> None:
    sys.path.insert(0, str(SCRIPTS))
    try:
        import search  # type: ignore[import-not-found]
    finally:
        sys.path.pop(0)

    payload = search.search_all(
        query="x",
        engines=["bogus-engine-name"],
        limit=1,
        strict=False,
    )
    assert payload["results"] == []
    assert any("unknown engine" in e["reason"] for e in payload["errors"])
