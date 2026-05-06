from __future__ import annotations

import json

import pytest

from opensquilla.engine.types import ToolCall
from opensquilla.tools.dispatch import build_tool_handler
from opensquilla.tools.registry import ToolRegistry
from opensquilla.tools.types import (
    CallerKind,
    InteractionMode,
    ToolContext,
    ToolSpec,
    current_tool_context,
)


def _build_registry() -> ToolRegistry:
    registry = ToolRegistry()

    async def boom() -> str:
        raise ValueError("bad argument")

    async def pending() -> str:
        return json.dumps(
            {
                "status": "approval_required",
                "approval_id": "abc123",
                "command": "rm secret",
                "warning": "destructive",
                "message": "Resolve this approval via exec.approval.resolve",
            }
        )

    registry.register(ToolSpec(name="boom", description="boom", parameters={}), boom)
    registry.register(ToolSpec(name="pending", description="pending", parameters={}), pending)
    return registry


@pytest.mark.asyncio
async def test_dispatch_missing_tool_returns_five_field_error_envelope() -> None:
    handler = build_tool_handler(_build_registry())

    result = await handler(
        ToolCall(
            tool_use_id="tc-1",
            tool_name="nope",
            arguments={},
        )
    )

    assert result.is_error is True
    payload = json.loads(result.content)
    assert set(payload.keys()) == {
        "status",
        "tool",
        "error_class",
        "user_message",
        "retry_allowed",
    }
    assert payload["status"] == "error"
    assert payload["tool"] == "nope"
    assert payload["error_class"] == "ToolNotFound"


@pytest.mark.asyncio
async def test_dispatch_tool_exception_envelope_is_canonical_five_key_shape() -> None:
    handler = build_tool_handler(_build_registry())

    result = await handler(
        ToolCall(
            tool_use_id="tc-2",
            tool_name="boom",
            arguments={},
        )
    )

    assert result.is_error is True
    payload = json.loads(result.content)
    assert payload["tool"] == "boom"
    assert payload["error_class"] == "ValueError"
    assert set(payload.keys()) == {
        "status",
        "tool",
        "error_class",
        "user_message",
        "retry_allowed",
    }


@pytest.mark.asyncio
async def test_dispatch_unsupported_surface_approval_payload_is_error_envelope() -> None:
    handler = build_tool_handler(_build_registry())
    token = current_tool_context.set(
        ToolContext(
            is_owner=True,
            caller_kind=CallerKind.CHANNEL,
            interaction_mode=InteractionMode.UNATTENDED,
            session_key="agent:main:demo",
            agent_id="main",
        )
    )
    try:
        result = await handler(
            ToolCall(
                tool_use_id="tc-3",
                tool_name="pending",
                arguments={},
            )
        )
    finally:
        current_tool_context.reset(token)

    assert result.is_error is True
    payload = json.loads(result.content)
    assert payload["status"] == "error"
    assert payload["tool"] == "pending"
    assert payload["error_class"] == "UnsupportedSurface"
    assert payload["retry_allowed"] is False


@pytest.mark.asyncio
async def test_dispatch_unattended_cli_approval_payload_is_error_envelope() -> None:
    handler = build_tool_handler(_build_registry())
    token = current_tool_context.set(
        ToolContext(
            is_owner=True,
            caller_kind=CallerKind.CLI,
            interaction_mode=InteractionMode.UNATTENDED,
            session_key="agent:main:demo",
            agent_id="main",
        )
    )
    try:
        result = await handler(
            ToolCall(
                tool_use_id="tc-4",
                tool_name="pending",
                arguments={},
            )
        )
    finally:
        current_tool_context.reset(token)

    assert result.is_error is True
    payload = json.loads(result.content)
    assert set(payload.keys()) == {
        "status",
        "tool",
        "error_class",
        "user_message",
        "retry_allowed",
    }
    assert payload["status"] == "error"
    assert payload["tool"] == "pending"
    assert payload["error_class"] == "UnsupportedSurface"
    assert payload["retry_allowed"] is False


@pytest.mark.asyncio
async def test_dispatch_unknown_tool_in_skill_name_context_raises_unsupported_surface() -> None:
    known_skill_names = {"shell"}
    handler = build_tool_handler(_build_registry(), known_skill_names=known_skill_names)

    result = await handler(
        ToolCall(
            tool_use_id="tc-4",
            tool_name="shell",
            arguments={},
        )
    )

    payload = json.loads(result.content)
    assert result.is_error is True
    assert payload["error_class"] == "UnsupportedSurface"
    assert payload["tool"] == "shell"
    assert "skill" in payload["user_message"].lower()
