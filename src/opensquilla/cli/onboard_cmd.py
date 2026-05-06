"""CLI: opensquilla onboard / configure."""

from __future__ import annotations

import typer

from opensquilla.onboarding.config_store import load_config
from opensquilla.onboarding.flow import (
    OnboardOptions,
    run_interactive_configure,
    run_interactive_onboard,
    run_noninteractive_provider_configure,
)
from opensquilla.onboarding.status import get_onboarding_status


def onboard_command(
    provider: str = typer.Option("", "--provider"),
    model: str = typer.Option("", "--model"),
    api_key: str = typer.Option("", "--api-key"),
    base_url: str = typer.Option("", "--base-url"),
    skip_channels: bool = typer.Option(False, "--skip-channels"),
    skip_search: bool = typer.Option(False, "--skip-search"),
    if_needed: bool = typer.Option(False, "--if-needed"),
) -> None:
    """Run first-run onboarding (interactive or non-interactive)."""
    if if_needed:
        cfg = load_config()
        if get_onboarding_status(cfg).llm_configured:
            typer.echo("Onboarding already complete; nothing to do.")
            raise typer.Exit(code=0)

    if provider and model:
        result = run_noninteractive_provider_configure(
            provider,
            {"model": model, "api_key": api_key, "base_url": base_url},
        )
        typer.echo(f"Provider configured: {provider}")
        typer.echo(f"Config: {result.path}")
        return

    options = OnboardOptions(
        skip_channels=skip_channels,
        skip_search=skip_search,
        if_needed=if_needed,
        provider_id=provider or None,
        model=model or None,
        api_key=api_key or None,
        base_url=base_url or None,
    )
    result = run_interactive_onboard(options)
    if "tty_required" in result.warnings:
        raise typer.Exit(code=2)
    typer.echo(f"Onboarding complete. Config: {result.path}")


def configure_command(
    section: str = typer.Option(
        "", "--section",
        help="providers | channels | search | image-generation",
    ),
) -> None:
    """Reconfigure a section (providers/channels/search/image-generation)."""
    result = run_interactive_configure(section or None)
    if result is not None:
        typer.echo(f"Saved: {result.path}")
