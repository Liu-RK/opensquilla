from unittest.mock import patch

import pytest

from opensquilla.cli.repl.stream import StreamingRenderer, WaitingIndicator


def test_verb_cycles_by_dwell_seconds() -> None:
    ind = WaitingIndicator(started_at=100.0)
    assert ind._verb(0.0) == "Pondering"
    assert ind._verb(2.6) == "Synthesizing"
    assert ind._verb(5.1) == "Cooking"
    n = len(WaitingIndicator._verbs)
    assert ind._verb(n * 2.5 + 0.1) == ind._verb(0.1)


def test_render_contains_verb_and_elapsed_seconds() -> None:
    started = 100.0
    ind = WaitingIndicator(started_at=started)
    with patch("opensquilla.cli.repl.stream.time.monotonic", return_value=started + 3.0):
        plain = ind.__rich__().plain
    # 3.0 / 2.5 = 1 → _verbs[1] == "Synthesizing"
    assert "Synthesizing" in plain
    assert "3.0s" in plain
    assert "Ctrl+C cancels" in plain


def test_pulse_restart_preserves_monotonic_elapsed() -> None:
    started = 100.0
    first = WaitingIndicator(started_at=started)
    second = WaitingIndicator(started_at=started)  # mirrors pulse() re-init
    with patch("opensquilla.cli.repl.stream.time.monotonic", return_value=started + 4.0):
        e1 = first._elapsed()
    with patch("opensquilla.cli.repl.stream.time.monotonic", return_value=started + 5.0):
        e2 = second._elapsed()
    assert e2 >= e1


class _RecordingLive:
    instances: list["_RecordingLive"] = []

    def __init__(self, renderable=None, **kwargs):
        self.renderable = renderable
        self.kwargs = kwargs
        self.updates: list[dict] = []
        self.started = 0
        self.stopped = 0
        _RecordingLive.instances.append(self)

    def start(self) -> None:
        self.started += 1

    def stop(self) -> None:
        self.stopped += 1

    def update(self, renderable, *, refresh: bool = False) -> None:
        self.renderable = renderable
        self.updates.append({"refresh": refresh})


@pytest.fixture
def recording_live(monkeypatch):
    _RecordingLive.instances = []
    monkeypatch.setattr("opensquilla.cli.repl.stream.Live", _RecordingLive)
    yield _RecordingLive
    _RecordingLive.instances = []


def test_main_live_uses_manual_refresh(recording_live) -> None:
    """Lock down the race-free Live config: auto_refresh=False + refresh=True per update.

    The streaming Markdown panel duplicated itself on PowerShell/CJK terminals
    when Rich's background refresh thread used a stale render height. Every
    paint must be driven from the asyncio thread immediately after a buffer
    mutation, with no concurrent painter.
    """
    with StreamingRenderer() as renderer:
        renderer.append_text("foo")
        renderer.append_text("bar")
        renderer.pulse()

    assert len(recording_live.instances) >= 2, (
        "expected a waiting Live and a main Live to be constructed"
    )
    waiting_live, main_live = recording_live.instances[0], recording_live.instances[1]

    assert waiting_live.kwargs.get("transient") is True
    # Waiting indicator must keep auto-refresh so its elapsed-seconds counter
    # animates without external ticks. Locked down so a future refactor can't
    # silently mirror the main-Live config and freeze the timer.
    assert waiting_live.kwargs.get("auto_refresh", True) is not False

    assert main_live.kwargs.get("auto_refresh") is False, (
        "main Live must disable auto_refresh to avoid the cursor-up race"
    )
    assert all(call["refresh"] is True for call in main_live.updates), (
        "every main Live update must force an immediate paint"
    )
    assert len(main_live.updates) >= 3, (
        "two text_deltas + one pulse should each drive their own paint"
    )
