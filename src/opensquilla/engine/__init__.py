"""opensquilla.engine — Agent core state machine."""

from .agent import Agent, ToolHandler
from .context import ContextAssembly, ContextFiles
from .subagent import SubagentHandle, SubagentManager, SubagentRegistry, SubagentSpec
from .types import (
    THINKING_BUDGETS,
    AgentConfig,
    AgentEvent,
    AgentState,
    DoneEvent,
    ErrorEvent,
    RunHeartbeatEvent,
    StateChangeEvent,
    TextDeltaEvent,
    ThinkingEvent,
    ThinkingLevel,
    ToolCall,
    ToolResult,
    ToolResultEvent,
    ToolUseStartEvent,
    WarningEvent,
)

__all__ = [
    # Agent
    "Agent",
    "ToolHandler",
    # Context
    "ContextAssembly",
    "ContextFiles",
    # Subagent
    "SubagentSpec",
    "SubagentHandle",
    "SubagentManager",
    "SubagentRegistry",
    # Types
    "AgentState",
    "AgentEvent",
    "AgentConfig",
    "ThinkingLevel",
    "THINKING_BUDGETS",
    "ThinkingEvent",
    "TextDeltaEvent",
    "RunHeartbeatEvent",
    "ToolUseStartEvent",
    "ToolResultEvent",
    "StateChangeEvent",
    "ErrorEvent",
    "DoneEvent",
    "WarningEvent",
    "ToolCall",
    "ToolResult",
]
