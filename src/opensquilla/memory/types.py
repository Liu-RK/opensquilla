"""Core data types for the memory system."""

from __future__ import annotations

from dataclasses import dataclass, field
from enum import StrEnum


class MemorySource(StrEnum):
    memory = "memory"


class SearchMode(StrEnum):
    hybrid = "hybrid"
    fts_only = "fts-only"


class SearchIntent(StrEnum):
    """Intent label for a memory search, used for attribution and filtering."""

    TOOL = "tool"  # memory_search tool path
    PREFETCH = "prefetch"  # auto-prefetch in runtime
    ADMIN = "admin"  # CLI / admin queries


@dataclass
class MemorySearchResult:
    """A result from memory search."""

    chunk_id: str
    path: str
    source: MemorySource
    start_line: int
    end_line: int
    snippet: str
    score: float
    vector_score: float | None = None
    text_score: float | None = None
    text: str | None = None
    chunk_hash: str | None = None
    metadata: dict[str, str] = field(default_factory=dict)
    citation: str | None = None


@dataclass
class MemorySearchOpts:
    max_results: int = 10
    min_score: float = 0.0
