from __future__ import annotations

import asyncio
from types import SimpleNamespace
from typing import Any

import pytest


def test_parse_raw_fallback_entries_preserves_multiline_message_body():
    from opensquilla.gateway.memory_repair_service import parse_raw_fallback_entries

    entries = parse_raw_fallback_entries(
        "# Raw flush (timeout)\n\n"
        "user: [opensquilla-message: date=2026-05-22 message=1 anchor=raw1]\n"
        "# Keep this heading as raw user content\n"
        "Wei: Yesterday the public synthetic alpha project selected gamma mode. "
        "[dia_id: raw1]\n"
        "assistant: acknowledged\n"
    )

    assert [entry.role for entry in entries] == ["user", "assistant"]
    assert "# Keep this heading" in entries[0].content
    assert "Wei: Yesterday" in entries[0].content
    assert entries[1].content == "acknowledged"


class _RepairSessionManager:
    def __init__(self) -> None:
        self.summary = SimpleNamespace(
            id=17,
            session_id="session-17",
            session_key="agent:main:repair-service",
            compaction_id="cmp-17",
            trigger_reason="preflight",
            flush_receipt_status="degraded_forensic",
            removed_count=2,
            covered_through_id=9,
            created_at=123,
        )
        self.entries = [
            SimpleNamespace(
                id=3,
                message_id="m3",
                role="user",
                content="preimage service marker",
                token_count=3,
                created_at=111,
            )
        ]
        self.status_updates: list[tuple[int | None, str]] = []

    async def list_degraded_compactions(
        self,
        *,
        agent_id: str | None = None,
        limit: int = 50,
    ) -> list[Any]:
        assert agent_id == "main"
        assert limit > 0
        if self.status_updates:
            return []
        return [self.summary]

    async def get_compaction_preimage(self, summary: Any) -> list[Any]:
        assert summary is self.summary
        return list(self.entries)

    async def mark_compaction_repair_status(self, summary: Any, status: str) -> None:
        self.status_updates.append((getattr(summary, "id", None), status))


class _FlushService:
    def __init__(self) -> None:
        self.calls: list[tuple[list[Any], str, dict[str, Any]]] = []

    async def execute(self, transcript: list[Any], session_key: str, **kwargs: Any) -> Any:
        self.calls.append((list(transcript), session_key, dict(kwargs)))
        return SimpleNamespace(
            mode="llm",
            indexed_chunk_count=1,
            integrity_status="ok",
            output_coverage_status="ok",
            invalid_candidate_count=0,
            candidate_missing_ids=[],
            obligation_status="ok",
            obligation_missing_ids=[],
            to_dict=lambda: {"mode": "llm"},
        )


@pytest.mark.asyncio
async def test_memory_repair_service_run_once_repairs_preimage_and_raw_fallback(tmp_path):
    try:
        from opensquilla.gateway.memory_repair_service import MemoryRepairService
    except ModuleNotFoundError:
        pytest.fail("MemoryRepairService is not implemented")

    raw_dir = tmp_path / "memory" / ".raw_fallbacks"
    raw_dir.mkdir(parents=True)
    (raw_dir / "raw.md").write_text(
        "# Raw flush (llm_error)\n\nuser: raw service marker\n",
        encoding="utf-8",
    )
    session_manager = _RepairSessionManager()
    flush_service = _FlushService()
    service = MemoryRepairService(
        session_manager=session_manager,
        flush_service=flush_service,
        memory_roots={"main": tmp_path},
        agent_ids=("main",),
        interval_seconds=60.0,
        max_items_per_tick=5,
    )

    results = await service.run_once()

    assert [result["sourceType"] for result in results] == [
        "compaction_preimage",
        "raw_fallback",
    ]
    assert [result["status"] for result in results] == ["repaired", "repaired"]
    assert session_manager.status_updates == [(17, "repaired")]
    assert flush_service.calls[0][1] == "agent:main:repair-service"
    assert flush_service.calls[1][0][0].content == "raw service marker"


@pytest.mark.asyncio
async def test_memory_repair_service_background_loop_runs_repair_tick(tmp_path):
    try:
        from opensquilla.gateway.memory_repair_service import MemoryRepairService
    except ModuleNotFoundError:
        pytest.fail("MemoryRepairService is not implemented")

    raw_dir = tmp_path / "memory" / ".raw_fallbacks"
    raw_dir.mkdir(parents=True)
    (raw_dir / "raw.md").write_text(
        "# Raw flush (timeout)\n\nuser: background raw marker\n",
        encoding="utf-8",
    )
    flush_service = _FlushService()
    service = MemoryRepairService(
        session_manager=_RepairSessionManager(),
        flush_service=flush_service,
        memory_roots={"main": tmp_path},
        agent_ids=("main",),
        interval_seconds=0.01,
        max_items_per_tick=5,
    )

    service.start()
    try:
        for _ in range(50):
            if flush_service.calls:
                break
            await asyncio.sleep(0.01)
    finally:
        await service.stop()

    assert flush_service.calls
