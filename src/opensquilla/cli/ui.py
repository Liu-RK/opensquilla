"""Shared CLI presentation helpers."""

from __future__ import annotations

from rich.console import Console
from rich.panel import Panel

console = Console(highlight=False)

ACCENT = "#1fb6aa"
ACCENT_SOFT = "#5eead4"


def error_panel(message: str, *, title: str = "Error") -> Panel:
    """Return a compact operator-facing error panel."""
    return Panel(f"[red]{message}[/red]", title=title, border_style="red")
