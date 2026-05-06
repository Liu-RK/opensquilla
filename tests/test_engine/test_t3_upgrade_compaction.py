"""Tests for TurnRunner._maybe_compact_on_t3_upgrade()."""

from __future__ import annotations

from dataclasses import dataclass, field
from types import SimpleNamespace
from typing import Any

import pytest

from opensquilla.engine.pipeline import TurnContext
from opensquilla.engine.runtime import TurnRunner
from opensquilla.session.models import TranscriptEntry

# ---------------------------------------------------------------------------
# Fakes
# ---------------------------------------------------------------------------


class _FakeSessionManager:
    def __init__(self, transcript: list[TranscriptEntry] | None = None) -> None:
        self._transcript = transcript or []
        self.compact_calls: list[tuple[str, int]] = []

    async def get_transcript(self, session_key: str, **kwargs: Any) -> list[TranscriptEntry]:
        return list(self._transcript)

    async def compact(self, session_key: str, context_window_tokens: int, **kwargs: Any) -> str:
        self.compact_calls.append((session_key, context_window_tokens))
        return "summary"


@dataclass(frozen=True)
class _FakeFlushReceipt:
    mode: str = "llm"
    flushed_paths: list[str] = field(default_factory=list)
    slug: str | None = None
    message_count: int = 1
    duration_ms: int = 10
    raw_reason: str | None = None
    error: str | None = None


class _FakeFlushService:
    def __init__(
        self,
        receipt: _FakeFlushReceipt | None = None,
        raise_exc: Exception | None = None,
    ) -> None:
        self._receipt = receipt or _FakeFlushReceipt()
        self._raise_exc = raise_exc
        self.execute_calls: list[dict[str, Any]] = []

    async def execute(self, transcript: Any, session_key: str, **kwargs: Any) -> _FakeFlushReceipt:
        self.execute_calls.append({"session_key": session_key, **kwargs})
        if self._raise_exc is not None:
            raise self._raise_exc
        return self._receipt


# ---------------------------------------------------------------------------
# Helpers
# ---------------------------------------------------------------------------

def _sample_transcript() -> list[TranscriptEntry]:
    return [
        TranscriptEntry(
            session_id="s1",
            session_key="agent:main:webchat:default",
            role="user",
            content="hello",
        ),
        TranscriptEntry(
            session_id="s1",
            session_key="agent:main:webchat:default",
            role="assistant",
            content="hi there",
        ),
    ]


def _make_turn(
    routed_tier: str = "t3",
    previous_tier: str | None = "t2",
    base_tier: str | None = None,
    final_tier: str | None = None,
    routing_applied: bool = True,
) -> TurnContext:
    routing_extra: dict[str, Any] = {}
    if previous_tier is not None:
        routing_extra["previous_tier"] = previous_tier
    if base_tier is not None:
        routing_extra["base_tier"] = base_tier
    if final_tier is not None:
        routing_extra["final_tier"] = final_tier

    return TurnContext(
        message="test",
        session_key="agent:main:webchat:default",
        config=None,
        provider=None,
        model="anthropic/claude-opus-4.7",
        tool_defs=[],
        system_prompt="you are helpful",
        metadata={
            "routed_tier": routed_tier,
            "routing_applied": routing_applied,
            "routing_extra": routing_extra,
        },
    )


def _make_runner(
    session_manager: Any = None,
    flush_service: Any = None,
    enabled: bool = True,
) -> TurnRunner:
    config = SimpleNamespace(
        squilla_router=SimpleNamespace(upgrade_to_t3_compaction_enabled=enabled),
    )
    return TurnRunner(
        provider_selector=SimpleNamespace(clone=lambda: SimpleNamespace()),
        session_manager=session_manager,
        config=config,
        session_flush_service=flush_service,
    )


# ---------------------------------------------------------------------------
# Tests
# ---------------------------------------------------------------------------


@pytest.mark.asyncio
async def test_t2_to_t3_triggers_flush_then_compact() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService()
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t3", previous_tier="t2")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is True
    assert len(fs.execute_calls) == 1
    assert len(sm.compact_calls) == 1
    assert sm.compact_calls[0] == ("agent:main:webchat:default", 100_000)


@pytest.mark.asyncio
async def test_t0_t1_to_t3_triggers() -> None:
    for prev in ("t0", "t1"):
        sm = _FakeSessionManager(_sample_transcript())
        fs = _FakeFlushService()
        runner = _make_runner(session_manager=sm, flush_service=fs)

        turn = _make_turn(routed_tier="t3", previous_tier=prev)
        result = await runner._maybe_compact_on_t3_upgrade(
            "agent:main:webchat:default", turn, 100_000
        )

        assert result is True, f"failed for previous_tier={prev}"
        assert len(fs.execute_calls) == 1
        assert len(sm.compact_calls) == 1


@pytest.mark.asyncio
async def test_t3_to_t3_skips() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService()
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t3", previous_tier="t3")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is False
    assert len(fs.execute_calls) == 0
    assert len(sm.compact_calls) == 0


@pytest.mark.asyncio
async def test_non_t3_route_skips() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService()
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t1", previous_tier="t0")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is False
    assert len(fs.execute_calls) == 0
    assert len(sm.compact_calls) == 0


@pytest.mark.asyncio
async def test_config_disabled_skips() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService()
    runner = _make_runner(session_manager=sm, flush_service=fs, enabled=False)

    turn = _make_turn(routed_tier="t3", previous_tier="t2")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is False
    assert len(fs.execute_calls) == 0
    assert len(sm.compact_calls) == 0


@pytest.mark.asyncio
async def test_observe_mode_skips() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService()
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t3", previous_tier="t2", routing_applied=False)
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is False
    assert len(fs.execute_calls) == 0
    assert len(sm.compact_calls) == 0


@pytest.mark.asyncio
async def test_flush_raises_skips_compact() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService(raise_exc=RuntimeError("flush boom"))
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t3", previous_tier="t2")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is True
    assert len(fs.execute_calls) == 1
    assert len(sm.compact_calls) == 0


@pytest.mark.asyncio
async def test_flush_error_receipt_skips_compact() -> None:
    sm = _FakeSessionManager(_sample_transcript())
    fs = _FakeFlushService(receipt=_FakeFlushReceipt(mode="error", error="provider down"))
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t3", previous_tier="t2")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is True
    assert len(fs.execute_calls) == 1
    assert len(sm.compact_calls) == 0


@pytest.mark.asyncio
async def test_compact_raises_continues() -> None:
    sm = _FakeSessionManager(_sample_transcript())

    async def _boom(session_key: str, context_window_tokens: int, **kw: Any) -> str:
        raise RuntimeError("compact boom")

    sm.compact = _boom  # type: ignore[assignment]
    fs = _FakeFlushService()
    runner = _make_runner(session_manager=sm, flush_service=fs)

    turn = _make_turn(routed_tier="t3", previous_tier="t2")
    result = await runner._maybe_compact_on_t3_upgrade(
        "agent:main:webchat:default", turn, 100_000
    )

    assert result is True
    assert len(fs.execute_calls) == 1
