"""Resource directory support for skills — scripts, references, assets."""

from __future__ import annotations

from pathlib import Path


class SkillResources:
    """Access skill resource directories: scripts/, references/, assets/."""

    def __init__(self, skill_dir: Path) -> None:
        self._dir = skill_dir

    @property
    def scripts_dir(self) -> Path:
        return self._dir / "scripts"

    @property
    def references_dir(self) -> Path:
        return self._dir / "references"

    @property
    def assets_dir(self) -> Path:
        return self._dir / "assets"

    def has_scripts(self) -> bool:
        return self.scripts_dir.is_dir() and any(self.scripts_dir.iterdir())

    def has_references(self) -> bool:
        return self.references_dir.is_dir() and any(self.references_dir.iterdir())

    def has_assets(self) -> bool:
        return self.assets_dir.is_dir() and any(self.assets_dir.iterdir())

    def list_scripts(self) -> list[Path]:
        if not self.scripts_dir.is_dir():
            return []
        return sorted(p for p in self.scripts_dir.iterdir() if p.is_file())

    def list_references(self) -> list[Path]:
        if not self.references_dir.is_dir():
            return []
        return sorted(p for p in self.references_dir.iterdir() if p.is_file())

    def list_assets(self) -> list[Path]:
        if not self.assets_dir.is_dir():
            return []
        return sorted(p for p in self.assets_dir.iterdir() if p.is_file())

    def read_reference(self, name: str) -> str | None:
        """Read a reference file by name. Returns None if not found."""
        path = self.references_dir / name
        if path.is_file():
            # Security: ensure resolved path is within references_dir
            try:
                path.resolve().relative_to(self.references_dir.resolve())
            except ValueError:
                return None
            return path.read_text(encoding="utf-8")
        return None

    def read_script(self, name: str) -> str | None:
        """Read a script file by name. Returns None if not found."""
        path = self.scripts_dir / name
        if path.is_file():
            try:
                path.resolve().relative_to(self.scripts_dir.resolve())
            except ValueError:
                return None
            return path.read_text(encoding="utf-8")
        return None
