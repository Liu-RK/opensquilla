"""Admin cron tool: strict structured-schedule contract.

Covers structured success path plus the four key field-named ``ToolError``
messages (flat string rejection, invalid cron expr, naive ISO ``at``, and
``every_seconds`` lower-bound).
"""

from __future__ import annotations

import json
from typing import Any

import pytest

import opensquilla.tools.builtin.admin as admin_mod
from opensquilla.tools.builtin.admin import cron as cron_tool
from opensquilla.tools.types import ToolError


class _ToolFakeScheduler:
    def __init__(self) -> None:
        self.added_kwargs: dict[str, Any] | None = None

    async def add_job(self, **kwargs):
        self.added_kwargs = kwargs
        from types import SimpleNamespace

        return SimpleNamespace(
            id="job-strict",
            delivery=SimpleNamespace(ws_topic=""),
        )

    async def update_job(self, *_, **__):
        return None


@pytest.mark.asyncio
async def test_admin_cron_accepts_structured_cron_schedule() -> None:
    fake = _ToolFakeScheduler()
    admin_mod.set_scheduler(fake)
    try:
        raw = await cron_tool(
            action="add",
            schedule={"kind": "cron", "expr": "*/5 * * * *"},
            task="ping",
            job_kind="agent_turn",
            session_target="isolated",
        )
    finally:
        admin_mod.set_scheduler(None)  # type: ignore[arg-type]

    assert fake.added_kwargs is not None
    assert fake.added_kwargs["schedule_value"] == "*/5 * * * *"
    assert json.loads(raw)["schedule_value"] == "*/5 * * * *"


@pytest.mark.asyncio
async def test_admin_cron_rejects_flat_string_schedule() -> None:
    """A bare 5-field cron string must NOT be accepted by the LLM tool."""
    admin_mod.set_scheduler(_ToolFakeScheduler())
    try:
        with pytest.raises(ToolError, match="schedule must be an object"):
            await cron_tool(
                action="add",
                schedule="每5分钟",  # type: ignore[arg-type]
                task="ping",
                job_kind="system_event",
                session_target="main",
            )
    finally:
        admin_mod.set_scheduler(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_admin_cron_rejects_invalid_cron_expr() -> None:
    admin_mod.set_scheduler(_ToolFakeScheduler())
    try:
        with pytest.raises(ToolError, match="schedule.expr invalid"):
            await cron_tool(
                action="add",
                schedule={"kind": "cron", "expr": "not-a-cron"},
                task="ping",
                job_kind="agent_turn",
                session_target="isolated",
            )
    finally:
        admin_mod.set_scheduler(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_admin_cron_rejects_naive_at_timestamp() -> None:
    admin_mod.set_scheduler(_ToolFakeScheduler())
    try:
        with pytest.raises(ToolError, match="must include a timezone"):
            await cron_tool(
                action="add",
                schedule={"kind": "at", "at": "2026-05-15T09:00:00"},
                task="ping",
                job_kind="agent_turn",
                session_target="isolated",
            )
    finally:
        admin_mod.set_scheduler(None)  # type: ignore[arg-type]


@pytest.mark.asyncio
async def test_admin_cron_rejects_zero_every_seconds() -> None:
    admin_mod.set_scheduler(_ToolFakeScheduler())
    try:
        with pytest.raises(ToolError, match="every_seconds"):
            await cron_tool(
                action="add",
                schedule={"kind": "every", "every_seconds": 0},
                task="ping",
                job_kind="agent_turn",
                session_target="isolated",
            )
    finally:
        admin_mod.set_scheduler(None)  # type: ignore[arg-type]
