from __future__ import annotations

import base64
from types import SimpleNamespace
from typing import Any

import pytest
from typer.testing import CliRunner

from opensquilla.cli.agent_cmd import run_agent_once
from opensquilla.engine.types import DoneEvent
from opensquilla.gateway.config import AgentEntryConfig, GatewayConfig
from opensquilla.tools.types import CallerKind, InteractionMode


class _FakeSessionManager:
    def __init__(self) -> None:
        self.messages: list[tuple[str, str, str]] = []

    async def get_or_create(self, session_key: str, agent_id: str = "main") -> object:
        return SimpleNamespace(session_key=session_key, agent_id=agent_id)

    async def append_message(self, session_key: str, role: str, content: str) -> None:
        self.messages.append((session_key, role, content))
        return None


class _FakeServices:
    def __init__(self, config: GatewayConfig) -> None:
        self.memory_sync_managers = {"main": object()}
        self.memory_retrievers = {"main": object()}
        self.turn_capture_services = {"main": object()}
        self.flush_service = object()
        self.model_catalog = object()
        self.provider_selector = object()
        self.tool_registry = None
        self.session_manager = _FakeSessionManager()
        self.skill_loader = None
        self.usage_tracker = None
        self.config = config

    async def close(self) -> None:
        return None


@pytest.mark.asyncio
async def test_run_agent_once_uses_agent_registry_model_when_model_not_explicit(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            captured["runner_config_model"] = kwargs["config"].llm.model

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["run_model"] = kwargs.get("model")
            captured["tool_context"] = kwargs.get("tool_context")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        captured["service_config_model"] = config.llm.model
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    root = tmp_path / "root"
    agent_workspace = tmp_path / "ops-workspace"
    cfg = GatewayConfig(
        workspace_dir=str(root),
        agents=[
            AgentEntryConfig(
                id="ops",
                model="agent/default",
                workspace=str(agent_workspace),
            )
        ],
    )
    result = await run_agent_once(message="hello", agent_id="ops", config=cfg)

    assert result.text == "ok"
    assert captured["service_config_model"] == "agent/default"
    assert captured["runner_config_model"] == "agent/default"
    assert captured["run_model"] == "agent/default"
    assert captured["tool_context"].workspace_dir == str(agent_workspace)


@pytest.mark.asyncio
async def test_run_agent_once_explicit_model_overrides_agent_registry_model(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            captured["runner_config_model"] = kwargs["config"].llm.model

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["run_model"] = kwargs.get("model")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        captured["service_config_model"] = config.llm.model
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    cfg = GatewayConfig(agents=[AgentEntryConfig(id="ops", model="agent/default")])
    await run_agent_once(
        message="hello",
        agent_id="ops",
        model="explicit/model",
        config=cfg,
    )

    assert captured["service_config_model"] == "explicit/model"
    assert captured["runner_config_model"] == "explicit/model"
    assert captured["run_model"] == "explicit/model"


@pytest.mark.asyncio
async def test_run_agent_once_uses_configured_agent_workspace_without_global_workspace(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["tool_context"] = kwargs.get("tool_context")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    agent_workspace = tmp_path / "ops-workspace"
    cfg = GatewayConfig(
        agents=[
            AgentEntryConfig(
                id="ops",
                workspace=str(agent_workspace),
            )
        ],
    )

    result = await run_agent_once(message="hello", agent_id="ops", config=cfg)

    assert captured["tool_context"].workspace_dir == str(agent_workspace)
    assert result.workspace == str(agent_workspace)


@pytest.mark.asyncio
async def test_run_agent_once_wires_memory_services_into_turnrunner(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}
    services: _FakeServices | None = None

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            captured.update(kwargs)

        async def run(self, message: str, session_key: str, **kwargs: Any):
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        nonlocal services
        services = _FakeServices(config)
        return services

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    await run_agent_once(message="hello", agent_id="main", config=GatewayConfig())

    assert services is not None
    assert captured["memory_sync_managers"] is services.memory_sync_managers
    assert captured["memory_retrievers"] is services.memory_retrievers
    assert captured["turn_capture_services"] is services.turn_capture_services
    assert captured["session_flush_service"] is services.flush_service
    assert captured["model_catalog"] is services.model_catalog


@pytest.mark.asyncio
async def test_run_agent_once_forwards_max_iterations(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["max_iterations"] = kwargs.get("max_iterations")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    await run_agent_once(
        message="hello",
        agent_id="main",
        config=GatewayConfig(),
        max_iterations=321,
    )

    assert captured["max_iterations"] == 321


@pytest.mark.asyncio
async def test_run_agent_once_defaults_to_unattended_interaction_contract(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["tool_context"] = kwargs.get("tool_context")
            captured["bootstrap_context_mode"] = kwargs.get("bootstrap_context_mode")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    await run_agent_once(message="hello", agent_id="main", config=GatewayConfig())

    ctx = captured["tool_context"]
    assert ctx.caller_kind is CallerKind.CLI
    assert ctx.interaction_mode is InteractionMode.UNATTENDED
    assert ctx.elevated is None
    assert captured["bootstrap_context_mode"] == "unattended"


@pytest.mark.asyncio
async def test_run_agent_once_passes_bypass_permissions_to_tool_context(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["tool_context"] = kwargs.get("tool_context")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    await run_agent_once(
        message="hello",
        agent_id="main",
        config=GatewayConfig(),
        permissions="bypass",
    )

    ctx = captured["tool_context"]
    assert ctx.interaction_mode is InteractionMode.UNATTENDED
    assert ctx.elevated == "bypass"


@pytest.mark.asyncio
async def test_run_agent_once_uses_permissions_environment_default(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["tool_context"] = kwargs.get("tool_context")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setenv("OPENSQUILLA_AGENT_PERMISSIONS", "full")
    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    await run_agent_once(message="hello", agent_id="main", config=GatewayConfig())

    assert captured["tool_context"].elevated == "full"


@pytest.mark.asyncio
async def test_run_agent_once_rejects_invalid_permissions() -> None:
    with pytest.raises(ValueError, match="permissions must be one of"):
        await run_agent_once(
            message="hello",
            agent_id="main",
            config=GatewayConfig(),
            permissions="benchmark",
        )


@pytest.mark.asyncio
async def test_run_agent_once_can_opt_into_interactive_single_shot(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["tool_context"] = kwargs.get("tool_context")
            captured["bootstrap_context_mode"] = kwargs.get("bootstrap_context_mode")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    await run_agent_once(
        message="hello",
        agent_id="main",
        config=GatewayConfig(),
        unattended=False,
    )

    assert captured["tool_context"].interaction_mode is InteractionMode.INTERACTIVE
    assert captured["bootstrap_context_mode"] is None


@pytest.mark.asyncio
async def test_run_agent_once_rejects_invalid_max_iterations() -> None:
    with pytest.raises(ValueError, match="max_iterations"):
        await run_agent_once(
            message="hello",
            agent_id="main",
            config=GatewayConfig(),
            max_iterations=0,
        )


@pytest.mark.asyncio
async def test_run_agent_once_forwards_inline_attachments(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["attachments"] = kwargs.get("attachments")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    payload = base64.b64encode(b"hello").decode("ascii")
    await run_agent_once(
        message="summarize",
        agent_id="main",
        config=GatewayConfig(),
        attachments=[{"type": "text/plain", "data": payload, "name": "note.txt"}],
    )

    assert captured["attachments"] == [
        {"type": "text/plain", "data": payload, "name": "note.txt"}
    ]


@pytest.mark.asyncio
async def test_run_agent_once_builds_multiple_file_attachments(
    monkeypatch: pytest.MonkeyPatch,
    tmp_path,
) -> None:
    captured: dict[str, Any] = {}

    class FakeTurnRunner:
        def __init__(self, **kwargs: Any) -> None:
            pass

        async def run(self, message: str, session_key: str, **kwargs: Any):
            captured["attachments"] = kwargs.get("attachments")
            yield DoneEvent(text="ok", model=kwargs.get("model") or "")

    async def fake_build_services(*, config: GatewayConfig, **kwargs: Any) -> _FakeServices:
        return _FakeServices(config)

    monkeypatch.setattr("opensquilla.engine.runtime.TurnRunner", FakeTurnRunner)
    monkeypatch.setattr("opensquilla.gateway.build_services", fake_build_services)

    note = tmp_path / "note.txt"
    note.write_bytes(b"hello")
    data = tmp_path / "data.csv"
    data.write_bytes(b"a,b\n1,2\n")

    await run_agent_once(
        message="compare",
        agent_id="main",
        config=GatewayConfig(),
        attachment_paths=[str(note), str(data)],
    )

    attachments = captured["attachments"]
    assert len(attachments) == 2
    assert [item["type"] for item in attachments] == ["text/plain", "text/csv"]
    assert base64.b64decode(attachments[0]["data"]) == b"hello"
    assert base64.b64decode(attachments[1]["data"]) == b"a,b\n1,2\n"


@pytest.mark.asyncio
async def test_run_agent_once_rejects_agent_file_requiring_upload_bridge(tmp_path) -> None:
    big_pdf = tmp_path / "big.pdf"
    big_pdf.write_bytes(b"%PDF-1.4\n" + b"a" * 2_000_001)

    with pytest.raises(ValueError, match="gateway bridge upload"):
        await run_agent_once(
            message="read",
            agent_id="main",
            config=GatewayConfig(),
            attachment_paths=[str(big_pdf)],
        )


@pytest.mark.asyncio
async def test_run_agent_once_rejects_large_text_file_without_staging(tmp_path) -> None:
    big_csv = tmp_path / "big.csv"
    big_csv.write_bytes(b"a" * 2_000_001)

    with pytest.raises(ValueError, match=r"text-family|/path"):
        await run_agent_once(
            message="read",
            agent_id="main",
            config=GatewayConfig(),
            attachment_paths=[str(big_csv)],
        )


def test_top_level_agent_command_accepts_repeated_file_options(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opensquilla.cli.main import app

    captured: dict[str, Any] = {}

    def fake_run_agent_command(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("opensquilla.cli.main.run_agent_command", fake_run_agent_command)

    result = CliRunner().invoke(
        app,
        [
            "agent",
            "--message",
            "compare",
            "--file",
            "a.txt",
            "--file",
            "b.csv",
            "--json",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["message"] == "compare"
    assert captured["file_paths"] == ["a.txt", "b.csv"]
    assert captured["json_output"] is True
    assert captured["unattended"] is True
    assert captured["permissions"] is None


def test_top_level_agent_command_accepts_interactive_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opensquilla.cli.main import app

    captured: dict[str, Any] = {}

    def fake_run_agent_command(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("opensquilla.cli.main.run_agent_command", fake_run_agent_command)

    result = CliRunner().invoke(
        app,
        [
            "agent",
            "--message",
            "hello",
            "--interactive",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["unattended"] is False


def test_top_level_agent_command_accepts_permissions_option(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    from opensquilla.cli.main import app

    captured: dict[str, Any] = {}

    def fake_run_agent_command(**kwargs: Any) -> None:
        captured.update(kwargs)

    monkeypatch.setattr("opensquilla.cli.main.run_agent_command", fake_run_agent_command)

    result = CliRunner().invoke(
        app,
        [
            "agent",
            "--message",
            "hello",
            "--permissions",
            "bypass",
        ],
    )

    assert result.exit_code == 0, result.output
    assert captured["permissions"] == "bypass"
