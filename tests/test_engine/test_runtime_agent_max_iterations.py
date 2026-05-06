from __future__ import annotations

from types import SimpleNamespace

import pytest

from opensquilla.engine.runtime import TurnRunner
from opensquilla.engine.types import AgentConfig
from opensquilla.gateway.config import GatewayConfig


class _SessionConfigManager:
    def __init__(self, config: object | None) -> None:
        self.config = config

    def get_session_config(self, session_key: str) -> object | None:
        return self.config


def test_resolve_agent_max_iterations_prefers_explicit_value(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENSQUILLA_AGENT_MAX_ITERATIONS", "222")
    runner = TurnRunner(
        provider_selector=None,
        session_manager=_SessionConfigManager(SimpleNamespace(agent_max_iterations=111)),
        config=GatewayConfig(agent_max_iterations=333),
    )

    assert runner._resolve_agent_max_iterations("agent:main:test", 444) == 444


def test_resolve_agent_max_iterations_prefers_session_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENSQUILLA_AGENT_MAX_ITERATIONS", "222")
    runner = TurnRunner(
        provider_selector=None,
        session_manager=_SessionConfigManager(SimpleNamespace(agent_max_iterations=111)),
        config=GatewayConfig(agent_max_iterations=333),
    )

    assert runner._resolve_agent_max_iterations("agent:main:test") == 111


def test_resolve_agent_max_iterations_prefers_env_over_gateway_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENSQUILLA_AGENT_MAX_ITERATIONS", "222")
    runner = TurnRunner(
        provider_selector=None,
        session_manager=_SessionConfigManager(None),
        config=GatewayConfig(agent_max_iterations=333),
    )

    assert runner._resolve_agent_max_iterations("agent:main:test") == 222


def test_resolve_agent_max_iterations_uses_gateway_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENSQUILLA_AGENT_MAX_ITERATIONS", raising=False)
    runner = TurnRunner(provider_selector=None, config=GatewayConfig(agent_max_iterations=333))

    assert runner._resolve_agent_max_iterations("agent:main:test") == 333


def test_resolve_agent_max_iterations_uses_agent_default_without_config(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.delenv("OPENSQUILLA_AGENT_MAX_ITERATIONS", raising=False)
    runner = TurnRunner(provider_selector=None, config=None)

    assert runner._resolve_agent_max_iterations("agent:main:test") == AgentConfig().max_iterations


def test_resolve_agent_max_iterations_invalid_env_falls_through(
    monkeypatch: pytest.MonkeyPatch,
) -> None:
    monkeypatch.setenv("OPENSQUILLA_AGENT_MAX_ITERATIONS", "not-an-int")
    runner = TurnRunner(
        provider_selector=None,
        session_manager=_SessionConfigManager(None),
        config=GatewayConfig(agent_max_iterations=333),
    )

    assert runner._resolve_agent_max_iterations("agent:main:test") == 333


def test_resolve_agent_max_iterations_rejects_invalid_explicit_value() -> None:
    runner = TurnRunner(provider_selector=None, config=GatewayConfig())

    with pytest.raises(ValueError, match="max_iterations"):
        runner._resolve_agent_max_iterations("agent:main:test", 0)
