"""Canvas and node helper functions for deployments with a node runtime."""

from __future__ import annotations

import json

from opensquilla.tools.types import ToolError

_CANVAS_ACTIONS = ("present", "hide", "eval", "snapshot")
_NODES_ACTIONS = ("list", "describe", "invoke")


async def canvas(
    action: str,
    node_id: str,
    content: str | None = None,
) -> str:
    if action not in _CANVAS_ACTIONS:
        raise ToolError(f"Invalid action: {action}. Must be present|hide|eval|snapshot")
    raise ToolError("Canvas requires a configured node runtime.")


async def nodes(
    action: str,
    node_id: str | None = None,
    tool_name: str | None = None,
    arguments: dict | None = None,
) -> str:
    if action not in _NODES_ACTIONS:
        raise ToolError(f"Invalid action: {action}. Must be list|describe|invoke")

    if action in ("describe", "invoke") and not node_id:
        raise ToolError(f"'node_id' required for {action}")

    if action == "invoke" and not tool_name:
        raise ToolError("'tool_name' required for invoke")

    if action == "list":
        return json.dumps({"nodes": []})

    raise ToolError("Node actions require a configured node runtime.")
