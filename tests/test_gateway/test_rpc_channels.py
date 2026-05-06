"""RPC tests for channel status payloads."""

from __future__ import annotations

import pytest

import opensquilla.gateway.rpc_channels  # noqa: F401  ensures registration
from opensquilla.gateway.auth import Principal
from opensquilla.gateway.config import GatewayConfig
from opensquilla.gateway.rpc import RpcContext, get_dispatcher
from opensquilla.onboarding.mutations import upsert_channel


def _read_ctx() -> RpcContext:
    return RpcContext(
        conn_id="t",
        principal=Principal(
            role="operator",
            scopes=frozenset({"operator.read"}),
            is_owner=False,
            authenticated=True,
        ),
    )


@pytest.mark.asyncio
async def test_channels_status_includes_configured_channels_without_manager():
    ctx = _read_ctx()
    res = upsert_channel(
        GatewayConfig(),
        entry_payload={"type": "slack", "name": "work", "token": "xoxb-secret"},
    )
    ctx.config = res.config

    rpc_res = await get_dispatcher().dispatch("r1", "channels.status", {}, ctx)

    assert rpc_res.error is None, rpc_res.error
    assert rpc_res.payload["channels"] == [
        {
            "name": "work",
            "connected": False,
            "status": "stopped",
            "bot_user_id": None,
            "connected_since": None,
            "restart_attempts": 0,
            "type": "slack",
            "enabled": True,
            "configured": True,
        }
    ]
