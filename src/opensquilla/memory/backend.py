"""Minimal memory backend protocol.

The protocol documents the behavior a future backend must satisfy without
changing the current production backend, which remains ``LongTermMemoryStore``.
"""

from __future__ import annotations

from typing import Any, Protocol, runtime_checkable

from opensquilla.memory.types import MemorySearchResult, MemorySource, SearchMode


@runtime_checkable
class MemoryBackend(Protocol):
    async def initialize(self) -> None: ...

    async def index_file(
        self,
        path: str,
        content: str,
        source: MemorySource = MemorySource.memory,
        *,
        mtime: float | None = None,
        chunk_tokens: int = 400,
        chunk_overlap: int = 50,
    ) -> int: ...

    async def search(
        self,
        query: str,
        max_results: int = 10,
        min_score: float = 0.0,
        vector_weight: float = 0.7,
        text_weight: float = 0.3,
    ) -> tuple[list[MemorySearchResult], SearchMode]: ...

    async def remove_file(self, path: str) -> None: ...

    async def rebuild(self) -> None: ...

    async def health(self) -> dict[str, Any]: ...

    async def close(self) -> None: ...
