from __future__ import annotations

import pytest

from opensquilla.agents.registry import AgentRegistry
from opensquilla.gateway.config import GatewayConfig
from opensquilla.gateway.rpc import RpcContext, get_dispatcher


class _FailingModelSelector:
    async def list_models(self) -> list[dict]:
        raise RuntimeError("provider unavailable")


def _ctx(config: GatewayConfig, registry: AgentRegistry) -> RpcContext:
    return RpcContext(conn_id="test", config=config, agent_registry=registry)


@pytest.mark.asyncio
async def test_agents_rpc_list_uses_config_backed_registry() -> None:
    cfg = GatewayConfig()
    registry = AgentRegistry(cfg, persist_changes=False)
    await registry.create_agent(agent_id="ops", model="openai/test")

    result = await get_dispatcher().dispatch("r1", "agents.list", {}, _ctx(cfg, registry))

    assert result.error is None, result.error
    assert [agent["id"] for agent in result.payload["agents"]] == ["main", "ops"]
    assert result.payload["agents"][1]["model"] == "openai/test"


@pytest.mark.asyncio
async def test_agents_rpc_list_without_registry_returns_empty() -> None:
    result = await get_dispatcher().dispatch(
        "r1",
        "agents.list",
        {},
        RpcContext(conn_id="test", config=GatewayConfig()),
    )

    assert result.error is None, result.error
    assert result.payload == {"agents": []}


@pytest.mark.asyncio
async def test_models_rpc_list_without_provider_selector_returns_empty() -> None:
    result = await get_dispatcher().dispatch(
        "r1",
        "models.list",
        {},
        RpcContext(conn_id="test"),
    )

    assert result.error is None, result.error
    assert result.payload == []


@pytest.mark.asyncio
async def test_models_rpc_list_provider_failure_returns_empty() -> None:
    result = await get_dispatcher().dispatch(
        "r1",
        "models.list",
        {},
        RpcContext(conn_id="test", provider_selector=_FailingModelSelector()),
    )

    assert result.error is None, result.error
    assert result.payload == []


@pytest.mark.asyncio
async def test_agents_rpc_create_accepts_explicit_id() -> None:
    cfg = GatewayConfig()
    registry = AgentRegistry(cfg, persist_changes=False)

    result = await get_dispatcher().dispatch(
        "r1",
        "agents.create",
        {"id": "ops", "name": "Operations", "model": "openai/test"},
        _ctx(cfg, registry),
    )

    assert result.error is None, result.error
    assert result.payload["id"] == "ops"
    assert result.payload["name"] == "Operations"
    assert cfg.agents[0].model == "openai/test"


@pytest.mark.asyncio
async def test_agents_rpc_delete_removes_config_entry() -> None:
    cfg = GatewayConfig()
    registry = AgentRegistry(cfg, persist_changes=False)
    await registry.create_agent(agent_id="ops")

    result = await get_dispatcher().dispatch(
        "r1",
        "agents.delete",
        {"id": "ops"},
        _ctx(cfg, registry),
    )

    assert result.error is None, result.error
    assert result.payload is None
    assert cfg.agents == []
