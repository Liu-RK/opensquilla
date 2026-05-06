"""Cron scheduler CLI commands backed by OpenSquilla gateway RPCs."""

from __future__ import annotations

from typing import Any

import typer
from rich.table import Table

from opensquilla.cli.gateway_rpc import confirm_or_exit, run_gateway_sync
from opensquilla.cli.output import print_json
from opensquilla.cli.ui import console

cron_app = typer.Typer(help="Inspect and manage scheduled OpenSquilla runs.")

_SESSION_TARGETS = {"isolated", "main", "current", "session"}


def _validate_session_target(value: str) -> str:
    normalized = value.strip().lower()
    if normalized not in _SESSION_TARGETS:
        raise typer.BadParameter(
            "--session-target must be one of isolated, main, current, session"
        )
    return normalized


def _job_rows(payload: Any) -> list[dict[str, Any]]:
    if isinstance(payload, list):
        return [row for row in payload if isinstance(row, dict)]
    if isinstance(payload, dict):
        rows = payload.get("jobs", [])
        if isinstance(rows, list):
            return [row for row in rows if isinstance(row, dict)]
    return []


def _render_jobs(rows: list[dict[str, Any]], *, title: str = "Cron jobs") -> None:
    if not rows:
        typer.echo("No cron jobs.")
        return
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("ID")
    table.add_column("Name")
    table.add_column("Enabled")
    table.add_column("Expression")
    table.add_column("Agent")
    table.add_column("Next run")
    table.add_column("Last run")
    table.add_column("Errors", justify="right")
    for row in rows:
        table.add_row(
            str(row.get("id") or ""),
            str(row.get("name") or ""),
            str(row.get("enabled") or False),
            str(row.get("expression") or row.get("schedule_raw") or ""),
            str(row.get("agentId") or row.get("agent_id") or ""),
            str(row.get("next_run") or ""),
            str(row.get("last_run") or ""),
            str(row.get("error_count") or row.get("consecutive_errors") or 0),
        )
    console.print(table)


def _render_mapping(payload: dict[str, Any], *, title: str) -> None:
    table = Table(title=title, show_header=True, header_style="bold cyan")
    table.add_column("Field")
    table.add_column("Value")
    for key, value in payload.items():
        table.add_row(str(key), str(value))
    console.print(table)


def _render_runs(rows: list[dict[str, Any]]) -> None:
    if not rows:
        typer.echo("No cron runs.")
        return
    table = Table(title="Cron runs", show_header=True, header_style="bold cyan")
    table.add_column("ID")
    table.add_column("Started")
    table.add_column("Finished")
    table.add_column("Status")
    table.add_column("Duration ms", justify="right")
    table.add_column("Error")
    for row in rows:
        table.add_row(
            str(row.get("id") or ""),
            str(row.get("started_at") or ""),
            str(row.get("finished_at") or ""),
            str(row.get("status") or ("ok" if row.get("success") else "error")),
            str(row.get("duration_ms") or ""),
            str(row.get("error") or ""),
        )
    console.print(table)


def _emit_success(payload: Any, *, json_output: bool, title: str) -> None:
    if json_output:
        print_json(payload)
    elif isinstance(payload, dict):
        _render_mapping(payload, title=title)
    else:
        typer.echo(str(payload))


@cron_app.command("list")
def cron_list(
    agent: str | None = typer.Option(None, "--agent", help="Filter by agent id"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """List scheduled cron jobs."""

    async def _run(client):
        params: dict[str, Any] = {}
        if agent:
            params["agentId"] = agent
        return await client.call("cron.list", params)

    payload = run_gateway_sync(_run, json_output=json_output)
    if json_output:
        print_json(payload)
        return
    _render_jobs(_job_rows(payload))


@cron_app.command("status")
def cron_status(
    job_id: str = typer.Argument(..., help="Cron job id"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Show one cron job."""

    async def _run(client):
        return await client.call("cron.status", {"id": job_id})

    payload = run_gateway_sync(_run, json_output=json_output)
    _emit_success(payload, json_output=json_output, title=f"Cron job {job_id}")


@cron_app.command("add")
def cron_add(
    expression: str = typer.Option(..., "--expression", help="Cron expression"),
    text: str = typer.Option(..., "--text", help="Prompt text to run"),
    name: str | None = typer.Option(None, "--name", help="Display name"),
    agent: str | None = typer.Option(None, "--agent", help="Agent id"),
    session_target: str = typer.Option(
        "isolated",
        "--session-target",
        help="Target session mode: isolated, main, current, or session",
    ),
    timeout: float | None = typer.Option(None, "--timeout", help="Run timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Add a scheduled cron job."""

    target = _validate_session_target(session_target)
    params: dict[str, Any] = {"expression": expression, "text": text, "sessionTarget": target}
    if name:
        params["name"] = name
    if agent:
        params["agentId"] = agent
    if timeout is not None:
        params["timeout"] = timeout

    async def _run(client):
        return await client.call("cron.add", params)

    payload = run_gateway_sync(_run, json_output=json_output)
    _emit_success(payload, json_output=json_output, title="Cron job added")


@cron_app.command("update")
def cron_update(
    job_id: str = typer.Argument(..., help="Cron job id"),
    expression: str | None = typer.Option(None, "--expression", help="Cron expression"),
    text: str | None = typer.Option(None, "--text", help="Prompt text to run"),
    name: str | None = typer.Option(None, "--name", help="Display name"),
    enabled: bool | None = typer.Option(None, "--enabled/--disabled", help="Enable/disable job"),
    timeout: float | None = typer.Option(None, "--timeout", help="Run timeout in seconds"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Update a scheduled cron job."""

    params: dict[str, Any] = {"id": job_id}
    if expression is not None:
        params["expression"] = expression
    if text is not None:
        params["text"] = text
    if name is not None:
        params["name"] = name
    if enabled is not None:
        params["enabled"] = enabled
    if timeout is not None:
        params["timeout"] = timeout
    if len(params) == 1:
        raise typer.BadParameter("provide at least one field to update")

    async def _run(client):
        return await client.call("cron.update", params)

    payload = run_gateway_sync(_run, json_output=json_output)
    _emit_success(payload, json_output=json_output, title="Cron job updated")


@cron_app.command("remove")
def cron_remove(
    job_id: str = typer.Argument(..., help="Cron job id"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Remove a scheduled cron job."""

    confirm_or_exit(f"Remove cron job {job_id!r}?", yes=yes, json_output=json_output)

    async def _run(client):
        await client.call("cron.remove", {"id": job_id})
        return {"id": job_id, "removed": True}

    payload = run_gateway_sync(_run, json_output=json_output)
    _emit_success(payload, json_output=json_output, title="Cron job removed")


@cron_app.command("run")
def cron_run(
    job_id: str = typer.Argument(..., help="Cron job id"),
    yes: bool = typer.Option(False, "--yes", "-y", help="Skip confirmation prompt"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """Run a scheduled cron job now."""

    confirm_or_exit(
        f"Run cron job {job_id!r} now? This may post into a live session or channel.",
        yes=yes,
        json_output=json_output,
    )

    async def _run(client):
        return await client.call("cron.run", {"id": job_id})

    payload = run_gateway_sync(_run, json_output=json_output)
    _emit_success(payload, json_output=json_output, title="Cron run result")


@cron_app.command("runs")
def cron_runs(
    job_id: str = typer.Argument(..., help="Cron job id"),
    limit: int = typer.Option(20, "--limit", "-n", help="Maximum rows"),
    json_output: bool = typer.Option(False, "--json", help="Emit machine-readable JSON"),
) -> None:
    """List recent runs for a cron job."""

    async def _run(client):
        return await client.call("cron.runs", {"id": job_id, "limit": limit})

    payload = run_gateway_sync(_run, json_output=json_output)
    if json_output:
        print_json(payload)
        return
    _render_runs(_job_rows(payload))
