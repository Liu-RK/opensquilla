from __future__ import annotations

import asyncio
import base64
import json
from types import SimpleNamespace

import pytest

from opensquilla.channels.stream_policy import resolve_channel_stream_policy
from opensquilla.channels.types import Attachment, IncomingMessage, OutgoingMessage
from opensquilla.engine.types import DoneEvent, TextDeltaEvent
from opensquilla.gateway.attachment_ingest import (
    MAX_STAGED_PDF_BYTES,
    MAX_TOTAL_ATTACHMENT_BYTES,
    AttachmentTotalTooLargeError,
)
from opensquilla.gateway.channel_dispatch import (
    _dispatch_combined_message_after_debounce,
    _ingest_channel_message_attachments,
    _run_turn_batch_path,
    _run_turn_with_streaming,
)
from opensquilla.gateway.config import AgentEntryConfig, GatewayConfig


class _FakeChannel:
    def __init__(self) -> None:
        self.sent: list[OutgoingMessage] = []

    async def send(self, message: OutgoingMessage) -> None:
        self.sent.append(message)


class _FakeEventBridge:
    def __init__(self) -> None:
        self.events: list[tuple[str, str, dict]] = []

    async def emit(self, session_key: str, event_name: str, payload: dict) -> None:
        self.events.append((session_key, event_name, payload))


def _message() -> IncomingMessage:
    return IncomingMessage(sender_id="u1", channel_id="c1", content="hello")


def _tool_ctx(agent_id: str = "main") -> SimpleNamespace:
    return SimpleNamespace(agent_id=agent_id)


def _exact_pdf(size: int) -> bytes:
    header = b"%PDF-1.4\n"
    return header + b"a" * (size - len(header))


def test_channel_stream_policy_prefers_adapter_stream_updates() -> None:
    class StreamingChannel:
        async def send_streaming(self, chunks):
            async for _ in chunks:
                pass

    policy = resolve_channel_stream_policy(StreamingChannel())

    assert policy.mode == "adapter_stream"
    assert policy.relay_stream is True
    assert policy.typing_keepalive is False


def test_channel_stream_policy_uses_typing_placeholder_without_stream_editing() -> None:
    class TypingOnlyChannel:
        async def send_typing(self) -> None:
            pass

        async def send(self, message: OutgoingMessage) -> None:
            pass

    policy = resolve_channel_stream_policy(TypingOnlyChannel())

    assert policy.mode == "typing_final"
    assert policy.relay_stream is False
    assert policy.typing_keepalive is True


def test_channel_stream_policy_allows_adapter_final_only_override() -> None:
    class FinalOnlyChannel:
        stream_update_strategy = "final_only"

        async def send_streaming(self, chunks):
            async for _ in chunks:
                pass

    policy = resolve_channel_stream_policy(FinalOnlyChannel())

    assert policy.mode == "final_only"
    assert policy.relay_stream is False
    assert policy.typing_keepalive is False


@pytest.mark.asyncio
async def test_direct_channel_turn_emits_run_heartbeat_while_stream_is_quiet() -> None:
    class FakeTurnRunner:
        async def run(self, message: str, session_key: str, **kwargs):
            await asyncio.sleep(0.03)
            yield TextDeltaEvent(text="ok")
            yield DoneEvent()

    channel = _FakeChannel()
    bridge = _FakeEventBridge()
    config = SimpleNamespace(
        agent_stream_heartbeat_interval_seconds=0.01,
        agent_stream_idle_timeout_seconds=1.0,
    )

    await _run_turn_batch_path(
        channel,
        FakeTurnRunner(),
        _message(),
        "agent:main:channel-test",
        _tool_ctx(),
        bridge,
        None,
        config,
    )

    assert any(event_name == "session.event.run_heartbeat" for _, event_name, _ in bridge.events)
    assert channel.sent[-1].content == "ok"


@pytest.mark.asyncio
async def test_direct_channel_turn_idle_timeout_sends_error_reply() -> None:
    class SlowTurnRunner:
        async def run(self, message: str, session_key: str, **kwargs):
            await asyncio.sleep(1.0)
            yield TextDeltaEvent(text="late")

    channel = _FakeChannel()
    config = SimpleNamespace(
        agent_stream_heartbeat_interval_seconds=0.0,
        agent_stream_idle_timeout_seconds=0.01,
    )

    await _run_turn_batch_path(
        channel,
        SlowTurnRunner(),
        _message(),
        "agent:main:channel-timeout",
        _tool_ctx(),
        _FakeEventBridge(),
        None,
        config,
    )

    assert channel.sent
    assert channel.sent[-1].content.startswith("Error: Stream idle")


@pytest.mark.asyncio
async def test_direct_channel_turn_honors_final_only_stream_policy() -> None:
    class FinalOnlyStreamingChannel(_FakeChannel):
        stream_update_strategy = "final_only"

        def __init__(self) -> None:
            super().__init__()
            self.streamed = False

        async def send_streaming(self, chunks):
            self.streamed = True
            text = ""
            async for chunk in chunks:
                text += chunk
            self.sent.append(OutgoingMessage(content=text))

    class FakeTurnRunner:
        async def run(self, message: str, session_key: str, **kwargs):
            yield TextDeltaEvent(text="final only")
            yield DoneEvent()

    channel = FinalOnlyStreamingChannel()
    config = SimpleNamespace(
        agent_stream_heartbeat_interval_seconds=0.0,
        agent_stream_idle_timeout_seconds=1.0,
    )

    await _run_turn_with_streaming(
        channel,
        FakeTurnRunner(),
        _message(),
        "agent:main:final-only",
        _FakeEventBridge(),
        None,
        config,
    )

    assert channel.streamed is False
    assert channel.sent[-1].content == "final only"


@pytest.mark.asyncio
async def test_channel_batch_turn_uses_agent_registry_model() -> None:
    class RecordingTurnRunner:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def run(self, message: str, session_key: str, **kwargs):
            self.calls.append(kwargs)
            yield DoneEvent()

    runner = RecordingTurnRunner()
    config = GatewayConfig(
        agents=[AgentEntryConfig(id="ops", model="agent/default")],
        agent_stream_heartbeat_interval_seconds=0.0,
        agent_stream_idle_timeout_seconds=1.0,
    )

    await _run_turn_batch_path(
        _FakeChannel(),
        runner,
        _message(),
        "agent:ops:channel-test",
        _tool_ctx("ops"),
        _FakeEventBridge(),
        None,
        config,
    )

    assert runner.calls[0]["model"] == "agent/default"


@pytest.mark.asyncio
async def test_channel_ingest_resolves_adapter_bytes_to_engine_attachment() -> None:
    class ResolvingChannel(_FakeChannel):
        channel_id = "test"

        async def resolve_inbound_attachment(self, attachment: Attachment) -> Attachment:
            return Attachment(
                name=attachment.name,
                mime_type=attachment.mime_type,
                data=b"hello",
                size=5,
            )

    msg = IncomingMessage(
        sender_id="u1",
        channel_id="c1",
        content="read",
        attachments=[
            Attachment(
                name="note.txt",
                mime_type="text/plain",
                url="https://example.test/note.txt",
            )
        ],
    )

    result = await _ingest_channel_message_attachments(channel=ResolvingChannel(), msg=msg)

    assert result.text == "read"
    assert result.failures == []
    assert result.attachments == [
        {
            "name": "note.txt",
            "type": "text/plain",
            "data": base64.b64encode(b"hello").decode("ascii"),
            "_was_staged": True,
        }
    ]


@pytest.mark.asyncio
async def test_channel_ingest_hard_rejects_aggregate_attachment_cap() -> None:
    one_pdf = _exact_pdf(MAX_TOTAL_ATTACHMENT_BYTES // 3 + 1)
    assert len(one_pdf) < MAX_STAGED_PDF_BYTES

    class ResolvingChannel(_FakeChannel):
        channel_id = "test"

        async def resolve_inbound_attachment(self, attachment: Attachment) -> Attachment:
            return Attachment(
                name=attachment.name,
                mime_type="application/pdf",
                data=one_pdf,
                size=len(one_pdf),
            )

    msg = IncomingMessage(
        sender_id="u1",
        channel_id="c1",
        content="read",
        attachments=[
            Attachment(
                name=f"{index}.pdf",
                mime_type="application/pdf",
                url=f"https://example.test/{index}.pdf",
            )
            for index in range(3)
        ],
    )

    with pytest.raises(AttachmentTotalTooLargeError, match="total raw bytes"):
        await _ingest_channel_message_attachments(channel=ResolvingChannel(), msg=msg)


@pytest.mark.asyncio
async def test_channel_batch_turn_passes_normalized_attachments() -> None:
    class RecordingTurnRunner:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def run(self, message: str, session_key: str, **kwargs):
            self.calls.append(kwargs)
            yield DoneEvent()

    runner = RecordingTurnRunner()
    attachment = {
        "type": "text/plain",
        "name": "note.txt",
        "data": base64.b64encode(b"hello").decode("ascii"),
    }

    await _run_turn_batch_path(
        _FakeChannel(),
        runner,
        _message(),
        "agent:main:channel-attachment",
        _tool_ctx(),
        _FakeEventBridge(),
        None,
        SimpleNamespace(
            agent_stream_heartbeat_interval_seconds=0.0,
            agent_stream_idle_timeout_seconds=1.0,
        ),
        [attachment],
    )

    assert runner.calls[0]["attachments"] == [attachment]


@pytest.mark.asyncio
async def test_debounce_channel_turn_rejects_aggregate_cap_before_runtime_start() -> None:
    one_pdf = _exact_pdf(MAX_TOTAL_ATTACHMENT_BYTES // 3 + 1)
    assert len(one_pdf) < MAX_STAGED_PDF_BYTES

    class ResolvingChannel(_FakeChannel):
        channel_id = "test"

        async def resolve_inbound_attachment(self, attachment: Attachment) -> Attachment:
            return Attachment(
                name=attachment.name,
                mime_type="application/pdf",
                data=one_pdf,
                size=len(one_pdf),
            )

    class FakeSessionManager:
        def __init__(self) -> None:
            self.delivery_contexts: list[tuple[str, str]] = []
            self.entries: list[dict[str, str]] = []

        async def get_or_create(self, key: str, **kwargs):
            return SimpleNamespace(session_key=key, **kwargs), True

        async def update(self, key: str, **kwargs) -> None:
            self.delivery_contexts.append((key, kwargs.get("last_channel") or ""))

        async def append_message(self, key: str, role: str, content: str):
            self.entries.append({"role": role, "content": content})
            return SimpleNamespace(content=content)

        async def read_transcript(self, key: str):
            return list(self.entries)

    class FakeTaskRuntime:
        def __init__(self) -> None:
            self.enqueue_calls: list[dict] = []

        async def enqueue(self, envelope, message: str, **kwargs):
            self.enqueue_calls.append({"message": message, **kwargs})
            return SimpleNamespace(task_id="t1")

    msg = IncomingMessage(
        sender_id="u1",
        channel_id="c1",
        content="read",
        attachments=[
            Attachment(
                name=f"{index}.pdf",
                mime_type="application/pdf",
                url=f"https://example.test/{index}.pdf",
            )
            for index in range(3)
        ],
    )
    runtime = FakeTaskRuntime()
    manager = FakeSessionManager()

    with pytest.raises(AttachmentTotalTooLargeError):
        await _dispatch_combined_message_after_debounce(
            ResolvingChannel(),
            SimpleNamespace(message=msg, raw_content="read", coalesced_count=1),
            SimpleNamespace(),
            manager,
            "agent:main:matrix:direct:u1",
            "matrix",
            runtime,
            SimpleNamespace(),
        )

    assert runtime.enqueue_calls == []
    assert manager.entries == []


@pytest.mark.asyncio
async def test_channel_streaming_turn_uses_agent_registry_model() -> None:
    class StreamingChannel(_FakeChannel):
        async def send_streaming(self, chunks, **kwargs):
            async for _ in chunks:
                pass

    class RecordingTurnRunner:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def run(self, message: str, session_key: str, **kwargs):
            self.calls.append(kwargs)
            yield DoneEvent()

    runner = RecordingTurnRunner()
    config = GatewayConfig(
        agents=[AgentEntryConfig(id="ops", model="agent/default")],
        agent_stream_heartbeat_interval_seconds=0.0,
        agent_stream_idle_timeout_seconds=1.0,
    )

    await _run_turn_with_streaming(
        StreamingChannel(),
        runner,
        _message(),
        "agent:ops:channel-test",
        _FakeEventBridge(),
        None,
        config,
    )

    assert runner.calls[0]["model"] == "agent/default"


@pytest.mark.asyncio
async def test_channel_streaming_turn_passes_normalized_attachments() -> None:
    class StreamingChannel(_FakeChannel):
        async def send_streaming(self, chunks, **kwargs):
            async for _ in chunks:
                pass

    class RecordingTurnRunner:
        def __init__(self) -> None:
            self.calls: list[dict] = []

        async def run(self, message: str, session_key: str, **kwargs):
            self.calls.append(kwargs)
            yield DoneEvent()

    runner = RecordingTurnRunner()
    attachment = {
        "type": "text/plain",
        "name": "note.txt",
        "data": base64.b64encode(b"hello").decode("ascii"),
    }

    await _run_turn_with_streaming(
        StreamingChannel(),
        runner,
        _message(),
        "agent:main:channel-stream-attachment",
        _FakeEventBridge(),
        None,
        SimpleNamespace(
            agent_stream_heartbeat_interval_seconds=0.0,
            agent_stream_idle_timeout_seconds=1.0,
        ),
        attachments=[attachment],
    )

    assert runner.calls[0]["attachments"] == [attachment]


@pytest.mark.asyncio
async def test_debounce_channel_turn_honors_attachment_persistence_config(tmp_path) -> None:
    class RecordingLock:
        def __init__(self) -> None:
            self.in_lock = False

        def locked(self) -> bool:
            return self.in_lock

        async def __aenter__(self):
            self.in_lock = True

        async def __aexit__(self, exc_type, exc, tb) -> None:
            self.in_lock = False

    lock = RecordingLock()

    class ResolvingChannel(_FakeChannel):
        channel_id = "test"

        async def resolve_inbound_attachment(self, attachment: Attachment) -> Attachment:
            assert lock.in_lock is False
            return Attachment(
                name=attachment.name,
                mime_type=attachment.mime_type,
                data=b"%PDF-1.4\nbody\n",
            )

    class FakeSessionManager:
        def __init__(self) -> None:
            self.entries: list[dict[str, str]] = []

        async def get_or_create(self, key: str, **kwargs):
            return SimpleNamespace(session_key=key, **kwargs), True

        async def update(self, key: str, **kwargs) -> None:
            pass

        async def append_message(self, key: str, role: str, content: str):
            entry = {"role": role, "content": content}
            self.entries.append(entry)
            return SimpleNamespace(content=content)

        async def read_transcript(self, key: str):
            return list(self.entries)

    class FakeTaskRuntime:
        def __init__(self) -> None:
            self.enqueue_calls: list[dict] = []

        async def enqueue(self, envelope, message: str, **kwargs):
            self.enqueue_calls.append({"message": message, **kwargs})
            return SimpleNamespace(task_id="t1")

        async def wait(self, task_id: str):
            return SimpleNamespace(status="succeeded")

    class FakeTurnRunner:
        def _get_session_lock(self, key: str):
            return lock

    msg = IncomingMessage(
        sender_id="u1",
        channel_id="c1",
        content="read this",
        attachments=[Attachment(name="doc.pdf", mime_type="application/pdf", url="mxc://doc")],
    )
    runtime = FakeTaskRuntime()
    session_manager = FakeSessionManager()
    config = SimpleNamespace(
        attachments=SimpleNamespace(
            persist_transcripts=False,
            media_root=str(tmp_path),
            transcript_disk_budget_bytes=1024,
        )
    )

    await _dispatch_combined_message_after_debounce(
        ResolvingChannel(),
        SimpleNamespace(message=msg, raw_content="read this", coalesced_count=1),
        FakeTurnRunner(),
        session_manager,
        "agent:main:matrix:direct:u1",
        "matrix",
        runtime,
        config,
    )

    persisted = json.loads(session_manager.entries[-1]["content"])
    assert persisted["attachments"][0]["data"] == base64.b64encode(b"%PDF-1.4\nbody\n").decode(
        "ascii"
    )
    assert "sha256_ref" not in persisted["attachments"][0]
    assert not (tmp_path / "transcripts").exists()
    assert runtime.enqueue_calls[0]["attachments"][0]["_was_staged"] is True
