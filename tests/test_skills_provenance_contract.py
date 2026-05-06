from __future__ import annotations

from pathlib import Path

from opensquilla.skills.loader import SkillLoader

ROOT = Path(__file__).resolve().parents[1]
BUNDLED = ROOT / "src" / "opensquilla" / "skills" / "bundled"
DEFAULTS = {"skill-creator", "pptx", "memory", "cron", "github"}


def test_default_bundled_skills_have_release_provenance(tmp_path: Path) -> None:
    loader = SkillLoader(bundled_dir=BUNDLED, snapshot_path=tmp_path / "snapshot.json")
    skills = {skill.name: skill for skill in loader.load_all()}

    for name in DEFAULTS:
        provenance = skills[name].provenance
        assert provenance.origin in {"opensquilla-original", "openclaw-derived"}
        assert provenance.license in {"MIT", "MIT-0"}
        assert provenance.maintained_by == "OpenSquilla"
        if provenance.origin == "openclaw-derived":
            assert provenance.upstream_url.startswith("https://")


def test_provenance_survives_snapshot_roundtrip(tmp_path: Path) -> None:
    snapshot = tmp_path / "snapshot.json"
    loader = SkillLoader(bundled_dir=BUNDLED, snapshot_path=snapshot)
    first = {skill.name: skill.provenance for skill in loader.load_all()}
    loader.save_snapshot()

    reloaded = SkillLoader(bundled_dir=BUNDLED, snapshot_path=snapshot)
    second = {skill.name: skill.provenance for skill in reloaded.load_all()}

    for name in DEFAULTS:
        assert second[name] == first[name]
