"""CLI tests for `opensquilla channels`."""

from __future__ import annotations

from pathlib import Path

from typer.testing import CliRunner

from opensquilla.cli.main import app

runner = CliRunner()


def _setenv(monkeypatch, tmp_path: Path) -> Path:
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    return target


def test_channels_list_empty(tmp_path, monkeypatch):
    _setenv(monkeypatch, tmp_path)
    result = runner.invoke(app, ["channels", "list"])
    assert result.exit_code == 0
    assert "0 channels" in result.stdout.lower()


def test_channels_add_telegram_polling_minimal(tmp_path, monkeypatch):
    target = _setenv(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        ["channels", "add", "telegram", "--name", "tg", "--token", "abc"],
    )
    assert result.exit_code == 0, result.stdout
    text = target.read_text()
    assert "tg" in text
    assert "telegram" in text
    assert "abc" not in result.stdout
    assert "restart" in result.stdout.lower()


def test_channels_add_slack_missing_token_fails(tmp_path, monkeypatch):
    _setenv(monkeypatch, tmp_path)
    result = runner.invoke(app, ["channels", "add", "slack", "--name", "w"])
    assert result.exit_code != 0
    combined = (result.stdout + (result.stderr or "")).lower()
    assert "token" in combined


def test_channels_add_slack_succeeds_with_token(tmp_path, monkeypatch):
    target = _setenv(monkeypatch, tmp_path)
    result = runner.invoke(
        app,
        [
            "channels", "add", "slack",
            "--name", "w", "--token", "xoxb-x",
            "--field", "slack_channel_id=C123",
        ],
    )
    assert result.exit_code == 0, result.stdout
    text = target.read_text()
    assert "C123" in text
    assert "xoxb-x" not in result.stdout


def test_channels_remove(tmp_path, monkeypatch):
    target = _setenv(monkeypatch, tmp_path)
    runner.invoke(app, ["channels", "add", "slack",
                        "--name", "w", "--token", "x"])
    result = runner.invoke(app, ["channels", "remove", "w"])
    assert result.exit_code == 0
    # Either the channel is gone, or the [[channels.channels]] table is empty.
    text = target.read_text()
    assert 'name = "w"' not in text


def test_channels_disable_then_enable(tmp_path, monkeypatch):
    target = _setenv(monkeypatch, tmp_path)
    runner.invoke(app, ["channels", "add", "slack",
                        "--name", "w", "--token", "x"])
    r1 = runner.invoke(app, ["channels", "disable", "w"])
    assert r1.exit_code == 0
    assert "enabled = false" in target.read_text()
    r2 = runner.invoke(app, ["channels", "enable", "w"])
    assert r2.exit_code == 0
    assert "enabled = true" in target.read_text()


def test_channels_list_redacts_secrets(tmp_path, monkeypatch):
    _setenv(monkeypatch, tmp_path)
    runner.invoke(app, ["channels", "add", "slack",
                        "--name", "w", "--token", "supersecret"])
    result = runner.invoke(app, ["channels", "list"])
    assert "supersecret" not in result.stdout
    assert "***" in result.stdout
