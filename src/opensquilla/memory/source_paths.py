"""Canonical predicates for searchable curated memory source files."""

from __future__ import annotations

from pathlib import Path


def is_memory_source_path(path: str) -> bool:
    """Return True for OpenSquilla curated memory source files."""
    rel = Path(path)
    if rel.is_absolute() or any(part in {"", ".", ".."} for part in rel.parts):
        return False
    if rel.parts == ("MEMORY.md",):
        return True
    return (
        len(rel.parts) >= 2
        and rel.parts[0] == "memory"
        and rel.suffix == ".md"
        and not any(part.startswith(".") for part in rel.parts[1:])
    )
