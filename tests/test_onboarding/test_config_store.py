"""Tests for config_store persistence."""

from __future__ import annotations

import os
import stat
import tomllib

import pytest

from opensquilla.gateway.config import AgentEntryConfig, GatewayConfig
from opensquilla.onboarding.config_store import (
    PersistResult,
    default_config_path,
    load_config,
    persist_config,
    validate_config_payload,
)


def test_default_config_path_under_home(monkeypatch, tmp_path):
    monkeypatch.setenv("HOME", str(tmp_path))
    monkeypatch.delenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", raising=False)
    p = default_config_path()
    assert p == tmp_path / ".opensquilla" / "config.toml"


def test_persist_creates_file_with_mode_0600(tmp_path):
    cfg = GatewayConfig()
    target = tmp_path / "config.toml"
    result = persist_config(cfg, path=target)
    assert isinstance(result, PersistResult)
    assert target.exists()
    mode = stat.S_IMODE(os.stat(target).st_mode)
    if os.name == "nt":
        assert mode & stat.S_IWRITE
    else:
        assert mode == 0o600


def test_persist_creates_backup_when_target_exists(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("port = 18790\n")
    cfg = GatewayConfig()
    result = persist_config(cfg, path=target)
    assert result.backup_path is not None
    assert result.backup_path.exists()
    assert result.backup_path.name.startswith("config.toml.backup.")


def test_persist_atomic_no_leftover_tmp(tmp_path):
    target = tmp_path / "config.toml"
    cfg = GatewayConfig()
    persist_config(cfg, path=target)
    leftovers = [p for p in tmp_path.iterdir() if p.suffix == ".tmp"]
    assert leftovers == []


def test_persist_validates_before_writing():
    with pytest.raises(Exception):
        validate_config_payload({"port": "not-a-port"})


def test_load_returns_gateway_config(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("port = 18791\n")
    cfg = load_config(target)
    assert cfg.port == 18791


def test_load_sets_config_path_for_existing_config(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text("port = 18791\n")
    cfg = load_config(target)
    assert cfg.config_path == str(target)


def test_persist_round_trip_preserves_unrelated(tmp_path):
    target = tmp_path / "config.toml"
    target.write_text(
        '[llm]\nprovider = "openrouter"\n'
        'model = "deepseek/deepseek-v4-flash"\n'
        'base_url = "https://openrouter.ai/api/v1"\n'
    )
    cfg = load_config(target)
    cfg.port = 18792
    persist_config(cfg, path=target)
    text = target.read_text()
    assert "openrouter" in text
    assert "18792" in text


def test_persist_omits_runtime_secret_paths(tmp_path):
    cfg = GatewayConfig()
    cfg.llm.api_key = "from-env"
    cfg.mark_runtime_secret("llm.api_key")

    target = tmp_path / "config.toml"
    persist_config(cfg, path=target)

    data = tomllib.loads(target.read_text())
    assert "api_key" not in data["llm"]


def test_load_nonexistent_returns_default(tmp_path):
    cfg = load_config(tmp_path / "missing.toml")
    assert isinstance(cfg, GatewayConfig)
    assert cfg.port == 18790  # default


def test_persist_omits_empty_agents_table(tmp_path):
    target = tmp_path / "config.toml"

    persist_config(GatewayConfig(), path=target)

    data = tomllib.loads(target.read_text())
    assert "agents" not in data


def test_persist_round_trips_agents_list(tmp_path):
    target = tmp_path / "config.toml"
    cfg = GatewayConfig(agents=[AgentEntryConfig(id="ops", model="openai/test")])

    persist_config(cfg, path=target)
    loaded = load_config(target)

    assert len(loaded.agents) == 1
    assert loaded.agents[0].id == "ops"
    assert loaded.agents[0].model == "openai/test"
