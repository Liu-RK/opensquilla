"""prompt-toolkit backed input for the chat REPL."""

from __future__ import annotations

import asyncio
import sys
from dataclasses import dataclass

from prompt_toolkit import PromptSession
from prompt_toolkit.completion import WordCompleter
from prompt_toolkit.history import FileHistory
from prompt_toolkit.key_binding import KeyBindings
from prompt_toolkit.patch_stdout import patch_stdout

from opensquilla.cli.repl.commands import slash_words
from opensquilla.engine.commands import Surface, parse_surface
from opensquilla.paths import state_dir


@dataclass(frozen=True)
class PromptConfig:
    force_plain: bool = False


_session: PromptSession[str] | None = None
_sessions: dict[Surface, PromptSession[str]] = {}


def _key_bindings() -> KeyBindings:
    bindings = KeyBindings()

    @bindings.add("c-c")
    def _clear_input(event) -> None:
        event.app.current_buffer.reset()

    return bindings


def _history_path() -> str:
    path = state_dir("history", "chat")
    path.parent.mkdir(parents=True, exist_ok=True)
    return str(path)


def _prompt_session(surface: Surface | str = Surface.CLI_GATEWAY) -> PromptSession[str]:
    global _session
    parsed = parse_surface(surface) if isinstance(surface, str) else surface
    if parsed not in _sessions:
        _sessions[parsed] = PromptSession(
            history=FileHistory(_history_path()),
            completer=WordCompleter(slash_words(parsed), ignore_case=True),
            enable_history_search=True,
            key_bindings=_key_bindings(),
        )
    if parsed == Surface.CLI_GATEWAY:
        _session = _sessions[parsed]
    return _sessions[parsed]


async def prompt_user(
    prefix: str = "[you] ",
    *,
    config: PromptConfig | None = None,
    surface: Surface | str = Surface.CLI_GATEWAY,
) -> str | None:
    """Read one prompt line, using prompt-toolkit for real terminals."""
    cfg = config or PromptConfig()
    if cfg.force_plain or not sys.stdin.isatty() or not sys.stdout.isatty():
        loop = asyncio.get_running_loop()

        def _readline() -> str | None:
            sys.stdout.write(prefix)
            sys.stdout.flush()
            line = sys.stdin.readline()
            if line == "":
                return None
            return line.rstrip("\n")

        return await loop.run_in_executor(None, _readline)

    try:
        with patch_stdout():
            return await _prompt_session(surface).prompt_async(prefix)
    except EOFError:
        return None


async def prompt_approval(prefix: str = "Decision [o/a/b/d]: ") -> str:
    """Read an approval decision without exposing prompt-toolkit details."""
    try:
        value = await prompt_user(prefix)
    except KeyboardInterrupt:
        return "d"
    if value is None:
        return "d"
    return value.strip().lower()
