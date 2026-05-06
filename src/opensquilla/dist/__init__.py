"""opensquilla.dist — distribution artefact builders.

S22 ships a single artefact today: ``workspace-state.json`` — a reproducible,
versioned inventory of what this opensquilla install ships (bundled channels,
bundled tools, gateway safety defaults, package + python-requires metadata).
"""

from opensquilla.dist.workspace_state import (
    BUNDLED_CHANNELS,
    BUNDLED_TOOLS,
    GATEWAY_DEFAULTS,
    SCHEMA_VERSION,
    build_workspace_state,
    to_json,
)

__all__ = [
    "BUNDLED_CHANNELS",
    "BUNDLED_TOOLS",
    "GATEWAY_DEFAULTS",
    "SCHEMA_VERSION",
    "build_workspace_state",
    "to_json",
]
