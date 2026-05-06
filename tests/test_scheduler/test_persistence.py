from __future__ import annotations

import pytest

from opensquilla.scheduler.persistence import JobStore
from opensquilla.scheduler.types import CronJob


@pytest.mark.asyncio
async def test_scheduler_persistence_round_trips_tool_policy(tmp_path) -> None:
    store = JobStore(str(tmp_path / "scheduler.db"))
    await store.open()
    try:
        job = CronJob(
            id="policy",
            name="Policy",
            cron_expr="*/5 * * * *",
            schedule_raw="*/5 * * * *",
            handler_key="agent_run",
            tool_policy={
                "profile": "minimal",
                "also_allow": ["memory_search"],
                "deny": ["web_fetch"],
            },
        )

        await store.save(job)
        loaded = await store.get("policy")
    finally:
        await store.close()

    assert loaded is not None
    assert loaded.tool_policy == {
        "profile": "minimal",
        "also_allow": ["memory_search"],
        "deny": ["web_fetch"],
    }
