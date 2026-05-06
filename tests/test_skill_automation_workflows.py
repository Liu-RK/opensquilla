"""automation-workflows skill — load + references shipped (no scripts)."""

from __future__ import annotations

from pathlib import Path

import pytest

from opensquilla.skills.eligibility import EligibilityContext, check_eligibility
from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"


def _spec() -> object:
    return SkillLoader(bundled_dir=BUNDLED).get_by_name("automation-workflows")


def test_skill_loads() -> None:
    spec = _spec()
    assert spec is not None
    assert spec.name == "automation-workflows"


def test_eligibility_unconditional(monkeypatch: pytest.MonkeyPatch) -> None:
    """Pure-instruction skill has no requires; eligibility passes unconditionally."""
    monkeypatch.setattr("opensquilla.skills.eligibility.shutil.which", lambda name: None)
    spec = _spec()
    assert spec is not None
    assert check_eligibility(spec, EligibilityContext.auto())


def test_three_vendor_references_present() -> None:
    refs = BUNDLED / "automation-workflows" / "references"
    assert (refs / "zapier.md").is_file()
    assert (refs / "make.md").is_file()
    assert (refs / "n8n.md").is_file()


def test_no_scripts_directory() -> None:
    """The skill is intentionally pure-instruction; no scripts dir should ship."""
    scripts = BUNDLED / "automation-workflows" / "scripts"
    assert not scripts.exists() or not any(scripts.iterdir())
