from pathlib import Path

from opensquilla.memory.checkpoint import (
    CheckpointEvent,
    checkpoint_event_hash,
    checkpoint_relative_path,
)


def test_checkpoint_event_serializes_required_fields() -> None:
    event = CheckpointEvent(
        schema_version=1,
        event_id="evt-1",
        session_key="agent:main:webchat:abc",
        session_id="session-1",
        turn_id="turn-1",
        sequence=1,
        timestamp_ms=123,
        role="tool_result",
        content_type="json",
        content='{"ok": true}',
        summary="tool succeeded",
        tool_name="memory_save",
        tool_call_id="call-1",
        status="ok",
        token_estimate=3,
        source="tool_runtime",
        attachments=[],
        content_hash="",
    )

    payload = event.to_json_dict()

    assert payload["schema_version"] == 1
    assert payload["session_key"] == "agent:main:webchat:abc"
    assert payload["role"] == "tool_result"
    assert payload["tool_name"] == "memory_save"
    assert payload["status"] == "ok"


def test_checkpoint_hash_is_stable_for_normalized_content() -> None:
    first = checkpoint_event_hash(" user message\n")
    second = checkpoint_event_hash("user message")

    assert first == second
    assert len(first) == 64


def test_checkpoint_relative_path_is_sidecar_only() -> None:
    path = checkpoint_relative_path(
        session_key="agent:main:webchat:abc",
        turn_id="turn-1",
    )

    assert path == Path("memory/.checkpoints/agent-main-webchat-abc/turn-1.jsonl")
