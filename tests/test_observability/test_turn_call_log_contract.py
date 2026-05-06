from __future__ import annotations

import json
from collections.abc import AsyncIterator
from types import SimpleNamespace
from typing import Any

import pytest

from opensquilla.engine.runtime import TurnRunner
from opensquilla.observability.turn_call_log import (
    TurnCallLogger,
    is_turn_call_log_enabled,
    resolve_turn_call_log_dir_with_source,
)
from opensquilla.provider import (
    ChatConfig,
    DoneEvent,
    Message,
    TextDeltaEvent,
    ToolUseEndEvent,
    ToolUseStartEvent,
)
from opensquilla.tools import ToolContext
from opensquilla.tools.registry import ToolRegistry
from opensquilla.tools.types import CallerKind, ToolSpec


class _ToolLoopProvider:
    provider_name = "fake"

    def __init__(self) -> None:
        self.calls = 0

    def chat(
        self,
        messages: list[Message],
        tools: list[Any] | None = None,
        config: ChatConfig | None = None,
    ) -> AsyncIterator[Any]:
        self.calls += 1
        return self._stream(self.calls)

    async def _stream(self, call_number: int) -> AsyncIterator[Any]:
        if call_number == 1:
            yield ToolUseStartEvent(tool_use_id="tool-1", tool_name="echo")
            yield ToolUseEndEvent(
                tool_use_id="tool-1",
                tool_name="echo",
                arguments={"value": "ok"},
            )
            yield DoneEvent(stop_reason="tool_use", input_tokens=3, output_tokens=1)
            return
        yield TextDeltaEvent(text="done")
        yield DoneEvent(stop_reason="end_turn", input_tokens=4, output_tokens=1)

    async def list_models(self) -> list[Any]:
        return []


class _FakeSelector:
    def __init__(self, provider: _ToolLoopProvider) -> None:
        self.provider = provider
        self.current_config = SimpleNamespace(model="fake-model")

    def clone(self) -> _FakeSelector:
        return self

    def resolve(self) -> _ToolLoopProvider:
        return self.provider

    def override_model(self, model: str) -> None:
        self.current_config.model = model


def test_turn_call_log_is_disabled_by_default(monkeypatch) -> None:
    monkeypatch.delenv("OPENSQUILLA_TURN_CALL_LOG", raising=False)

    assert is_turn_call_log_enabled() is False


def test_turn_call_log_enabled_values(monkeypatch) -> None:
    for value in ("1", "true", "yes", "on"):
        monkeypatch.setenv("OPENSQUILLA_TURN_CALL_LOG", value)
        assert is_turn_call_log_enabled() is True


def test_turn_call_log_directory_empty_specific_env_falls_back(monkeypatch, tmp_path) -> None:
    shared_log_dir = tmp_path / "logs"
    monkeypatch.setenv("OPENSQUILLA_TURN_CALL_LOG_DIR", "")
    monkeypatch.setenv("OPENSQUILLA_LOG_DIR", str(shared_log_dir))

    directory, source = resolve_turn_call_log_dir_with_source()

    assert directory == shared_log_dir
    assert source == "OPENSQUILLA_LOG_DIR"
    assert not shared_log_dir.exists()


def test_turn_call_log_writes_raw_trace_contract(tmp_path) -> None:
    logger = TurnCallLogger(
        trace_id="trace-1",
        turn_id="turn-1",
        session_key="agent:main:test",
        session_id="session-1",
        session_intent="chat",
        agent_id="main",
        provider="fake",
        model="fake-model",
        source={"kind": "test"},
        log_dir=tmp_path,
    )

    first_path = logger.write("turn_start", {"message": "raw user prompt"})
    second_path = logger.write("turn_end", {"final_text": "raw assistant text"})

    assert first_path == second_path
    assert first_path is not None
    records = [
        json.loads(line)
        for line in first_path.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]

    assert [record["kind"] for record in records] == ["turn_start", "turn_end"]
    assert [record["seq"] for record in records] == [1, 2]
    assert {record["schema_version"] for record in records} == {1}
    assert {record["privacy"] for record in records} == {"raw"}
    assert {record["trace_id"] for record in records} == {"trace-1"}
    assert {record["turn_id"] for record in records} == {"turn-1"}
    assert {record["session_key"] for record in records} == {"agent:main:test"}
    assert records[0]["payload"]["message"] == "raw user prompt"
    assert records[1]["payload"]["final_text"] == "raw assistant text"


@pytest.mark.asyncio
async def test_runtime_raw_turn_call_log_records_ordered_tool_turn(tmp_path, monkeypatch) -> None:
    monkeypatch.setenv("OPENSQUILLA_TURN_CALL_LOG", "1")
    monkeypatch.setenv("OPENSQUILLA_TURN_CALL_LOG_DIR", str(tmp_path))
    registry = ToolRegistry()

    async def echo(value: str) -> str:
        return f"echo:{value}"

    registry.register(
        ToolSpec(
            name="echo",
            description="Echo a value.",
            parameters={"value": {"type": "string"}},
            required=["value"],
        ),
        echo,
    )
    provider = _ToolLoopProvider()
    runner = TurnRunner(
        provider_selector=_FakeSelector(provider),
        tool_registry=registry,
    )

    events = [
        event
        async for event in runner.run(
            "use echo",
            "agent:main:turn-call-sequence",
            ToolContext(is_owner=True, caller_kind=CallerKind.AGENT),
        )
    ]

    assert any(event.kind == "done" for event in events)
    [log_file] = list(tmp_path.glob("turn-calls-*.jsonl"))
    records = [
        json.loads(line)
        for line in log_file.read_text(encoding="utf-8").splitlines()
        if line.strip()
    ]
    expected_kinds = {
        "prompt_report",
        "turn_start",
        "llm_request",
        "llm_response",
        "tool_request",
        "tool_response",
        "turn_end",
    }
    kinds = [record["kind"] for record in records if record["kind"] in expected_kinds]

    assert kinds == [
        "prompt_report",
        "turn_start",
        "llm_request",
        "llm_response",
        "tool_request",
        "tool_response",
        "llm_request",
        "llm_response",
        "turn_end",
    ]
    assert [record["seq"] for record in records] == list(range(1, len(records) + 1))
    assert {record["privacy"] for record in records} == {"raw"}
    assert len({record["trace_id"] for record in records}) == 1
