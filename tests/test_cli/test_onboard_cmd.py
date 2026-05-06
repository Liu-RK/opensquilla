"""CLI tests for `opensquilla onboard` and `configure`."""

from __future__ import annotations

from typer.testing import CliRunner

from opensquilla.cli.main import app

runner = CliRunner()


def test_onboard_noninteractive_provider(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    result = runner.invoke(
        app,
        [
            "onboard",
            "--provider", "openrouter",
            "--model", "deepseek/deepseek-v4-flash",
            "--api-key", "sk",
            "--skip-channels", "--skip-search",
        ],
    )
    assert result.exit_code == 0, result.stdout
    assert "openrouter" in target.read_text()
    assert "sk" not in result.stdout


def test_onboard_if_needed_skips_when_configured(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    runner.invoke(
        app,
        [
            "onboard",
            "--provider", "openrouter",
            "--model", "x", "--api-key", "k",
            "--skip-channels", "--skip-search",
        ],
    )
    mtime_before = target.stat().st_mtime
    result = runner.invoke(app, ["onboard", "--if-needed"])
    assert result.exit_code == 0
    assert "already complete" in result.stdout.lower()
    assert target.stat().st_mtime == mtime_before


def test_onboard_without_tty_prints_hint_without_writing_config(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))

    result = runner.invoke(app, ["onboard"])

    assert result.exit_code == 2
    assert "requires a TTY" in result.stdout
    assert not target.exists()


def test_init_help_mentions_onboard():
    result = runner.invoke(app, ["init", "--help"])
    assert "onboard" in result.stdout.lower()
