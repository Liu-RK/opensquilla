from __future__ import annotations

import json
from dataclasses import dataclass

import pytest
import structlog.testing

from opensquilla.tools.builtin import shell
from opensquilla.tools.types import CallerKind, ToolContext, ToolError, current_tool_context


class _FakeStdin:
    def __init__(self) -> None:
        self.closed = False
        self.writes: list[bytes] = []

    def is_closing(self) -> bool:
        return self.closed

    def write(self, data: bytes) -> None:
        self.writes.append(data)

    async def drain(self) -> None:
        return None

    def close(self) -> None:
        self.closed = True

    async def wait_closed(self) -> None:
        return None


@dataclass
class _FakeProcess:
    returncode: int | None = None
    stdin: _FakeStdin | None = None

    def __post_init__(self) -> None:
        if self.stdin is None:
            self.stdin = _FakeStdin()


def _ctx(
    session_key: str,
    *,
    is_owner: bool = False,
    agent_id: str = "agent",
    caller_kind: CallerKind = CallerKind.AGENT,
) -> ToolContext:
    return ToolContext(
        is_owner=is_owner,
        caller_kind=caller_kind,
        session_key=session_key,
        agent_id=agent_id,
    )


@pytest.fixture(autouse=True)
def _reset_bg_sessions():
    previous = dict(shell._bg_sessions)
    shell._bg_sessions.clear()
    yield
    shell._bg_sessions.clear()
    shell._bg_sessions.update(previous)


def _session(
    session_id: str,
    session_key: str | None,
    *,
    agent_id: str | None = "agent",
    done: bool = False,
) -> shell._BgSession:
    return shell._BgSession(
        session_id=session_id,
        command=f"cmd {session_id}",
        process=_FakeProcess(returncode=0 if done else None),  # type: ignore[arg-type]
        session_key=session_key,
        agent_id=agent_id,
        done=done,
        returncode=0 if done else None,
    )


@pytest.mark.asyncio
async def test_process_list_filters_to_current_session_and_warns_for_untagged() -> None:
    shell._bg_sessions["own"] = _session("own", "agent:main:one")
    shell._bg_sessions["other"] = _session("other", "agent:main:two")
    shell._bg_sessions["legacy"] = _session("legacy", None)

    token = current_tool_context.set(_ctx("agent:main:one"))
    try:
        with structlog.testing.capture_logs() as captured:
            payload = json.loads(await shell.process("list"))
    finally:
        current_tool_context.reset(token)

    assert [session["session_id"] for session in payload["sessions"]] == ["own"]
    assert any(event["event"] == "shell.bg_session_untagged" for event in captured)


@pytest.mark.asyncio
async def test_process_owner_context_can_list_all_sessions() -> None:
    shell._bg_sessions["own"] = _session("own", "agent:main:one")
    shell._bg_sessions["other"] = _session("other", "agent:main:two")

    token = current_tool_context.set(
        _ctx("agent:main:ops", is_owner=True, caller_kind=CallerKind.CLI)
    )
    try:
        payload = json.loads(await shell.process("list"))
    finally:
        current_tool_context.reset(token)

    assert {session["session_id"] for session in payload["sessions"]} == {"own", "other"}


@pytest.mark.asyncio
@pytest.mark.parametrize("action", ["poll", "log", "kill", "remove", "write", "submit", "eof"])
async def test_process_cross_context_operations_are_denied(action: str) -> None:
    shell._bg_sessions["owned-by-other"] = _session(
        "owned-by-other",
        "agent:main:other",
        done=action == "remove",
    )

    token = current_tool_context.set(_ctx("agent:main:one"))
    kwargs = {"data": "hello"} if action in {"write", "submit"} else {}
    try:
        with pytest.raises(ToolError, match="not accessible"):
            await shell.process(action, session_id="owned-by-other", **kwargs)
    finally:
        current_tool_context.reset(token)


@pytest.mark.asyncio
async def test_process_owner_context_can_poll_other_sessions() -> None:
    shell._bg_sessions["other"] = _session("other", "agent:main:two")

    token = current_tool_context.set(
        _ctx("agent:main:ops", is_owner=True, caller_kind=CallerKind.CLI)
    )
    try:
        payload = json.loads(await shell.process("poll", session_id="other"))
    finally:
        current_tool_context.reset(token)

    assert payload["status"] == "ok"
    assert payload["session"]["session_id"] == "other"


@pytest.mark.asyncio
async def test_process_subagent_owner_context_is_not_admin_bypass() -> None:
    shell._bg_sessions["own"] = _session("own", "subagent:agent:main:one")
    shell._bg_sessions["other"] = _session("other", "agent:main:two")

    token = current_tool_context.set(
        _ctx("subagent:agent:main:one", is_owner=True, caller_kind=CallerKind.SUBAGENT)
    )
    try:
        payload = json.loads(await shell.process("list"))
        with pytest.raises(ToolError, match="not accessible"):
            await shell.process("poll", session_id="other")
    finally:
        current_tool_context.reset(token)

    assert [session["session_id"] for session in payload["sessions"]] == ["own"]
