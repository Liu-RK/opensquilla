"""Tests for non-interactive onboarding flow halves."""

from __future__ import annotations


def test_noninteractive_provider_configure_writes_config(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    from opensquilla.onboarding.flow import run_noninteractive_provider_configure

    result = run_noninteractive_provider_configure(
        "openrouter",
        {"model": "deepseek/deepseek-v4-flash", "api_key": "sk"},
    )
    assert result.path == target
    assert "openrouter" in target.read_text()


def test_noninteractive_channel_add_writes_config(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    from opensquilla.onboarding.flow import run_noninteractive_channel_add

    result = run_noninteractive_channel_add("slack", {"name": "w", "token": "x"})
    assert result.path == target
    assert "slack" in target.read_text()


def test_interactive_configure_without_tty_does_not_create_config(
    tmp_path, monkeypatch
):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    from opensquilla.onboarding import flow

    monkeypatch.setattr(flow, "_is_tty", lambda: False)
    result = flow.run_interactive_configure("providers")

    assert result is None
    assert not target.exists()
