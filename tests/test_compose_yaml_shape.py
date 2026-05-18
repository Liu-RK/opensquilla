from __future__ import annotations

from pathlib import Path

import yaml

_ROOT = Path(__file__).parent.parent


def _load_compose() -> dict:
    return yaml.safe_load((_ROOT / "compose.yaml").read_text(encoding="utf-8"))


def test_compose_no_version_field() -> None:
    data = _load_compose()
    assert "version" not in data, (
        "compose.yaml must not have a top-level 'version:' field (use Compose v2 syntax)"
    )


def test_compose_gateway_port_is_loopback() -> None:
    data = _load_compose()
    ports = data["services"]["gateway"]["ports"]
    assert any(
        str(p) == "127.0.0.1:18791:18791" for p in ports
    ), f"Expected '127.0.0.1:18791:18791' in ports, got: {ports}"


def test_compose_gateway_healthcheck_exists() -> None:
    data = _load_compose()
    hc = data["services"]["gateway"].get("healthcheck")
    assert hc is not None, "services.gateway.healthcheck must be defined"


def test_compose_gateway_environment_has_openrouter_key() -> None:
    data = _load_compose()
    env = data["services"]["gateway"].get("environment", {})
    # environment can be a dict or a list of "KEY=VAL" strings
    if isinstance(env, dict):
        assert "OPENROUTER_API_KEY" in env, (
            f"OPENROUTER_API_KEY missing from environment dict: {env}"
        )
    else:
        keys = [item.split("=")[0] for item in env]
        assert "OPENROUTER_API_KEY" in keys, (
            f"OPENROUTER_API_KEY missing from environment list: {env}"
        )
