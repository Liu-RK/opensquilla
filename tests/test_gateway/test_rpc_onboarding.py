"""RPC tests for onboarding handlers."""

from __future__ import annotations

import tomllib

import pytest

import opensquilla.gateway.rpc_onboarding  # noqa: F401  ensures registration
from opensquilla.gateway.auth import Principal
from opensquilla.gateway.rpc import RpcContext, get_dispatcher


def _admin_ctx() -> RpcContext:
    return RpcContext(
        conn_id="t",
        principal=Principal(
            role="operator",
            scopes=frozenset({"operator.admin"}),
            is_owner=True,
            authenticated=True,
        ),
    )


def _read_ctx() -> RpcContext:
    return RpcContext(
        conn_id="t",
        principal=Principal(
            role="operator",
            scopes=frozenset({"operator.read"}),
            is_owner=False,
            authenticated=True,
        ),
    )


@pytest.mark.asyncio
async def test_onboarding_status_works_with_read_scope(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch("r1", "onboarding.status", {}, _read_ctx())
    assert res.error is None, res.error
    assert "needsOnboarding" in res.payload
    assert "configPath" in res.payload


@pytest.mark.asyncio
async def test_onboarding_catalog_returns_providers_and_channels(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch("r1", "onboarding.catalog", {}, _read_ctx())
    assert res.error is None, res.error
    payload = res.payload
    assert "providers" in payload
    assert "channels" in payload
    assert "searchProviders" in payload
    assert "imageGenerationProviders" in payload
    assert "memoryEmbeddingProviders" in payload
    types = {c["type"] for c in payload["channels"]}
    assert {"slack", "telegram", "matrix", "discord"} <= types
    search_provider_ids = {p["providerId"] for p in payload["searchProviders"]}
    assert {"brave", "duckduckgo"} <= search_provider_ids
    image_provider_ids = {p["providerId"] for p in payload["imageGenerationProviders"]}
    assert {"openai", "openrouter"} <= image_provider_ids
    memory_provider_ids = {p["providerId"] for p in payload["memoryEmbeddingProviders"]}
    assert {
        "auto",
        "local",
        "openai",
        "openai-compatible",
        "ollama",
        "none",
    } <= memory_provider_ids


@pytest.mark.asyncio
async def test_provider_configure_redacts_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.provider.configure",
        {"providerId": "openrouter", "model": "x", "apiKey": "sk-test"},
        _admin_ctx(),
    )
    assert res.error is None, res.error
    assert res.payload["changed"] is True
    assert res.payload["entry"]["api_key"] == "***"
    assert res.payload["restartRequired"] is False


@pytest.mark.asyncio
async def test_channel_upsert_redacts_secrets(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.channel.upsert",
        {"entry": {"type": "slack", "name": "w", "token": "supersecret"}},
        _admin_ctx(),
    )
    assert res.error is None, res.error
    assert res.payload["changed"] is True
    assert res.payload["restartRequired"] is True
    assert res.payload["entry"]["token"] == "***"


@pytest.mark.asyncio
async def test_search_configure_redacts_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.search.configure",
        {"providerId": "brave", "apiKey": "brave-secret", "maxResults": 3},
        _admin_ctx(),
    )
    assert res.error is None, res.error
    assert res.payload["changed"] is True
    assert res.payload["entry"]["api_key"] == "***"


@pytest.mark.asyncio
async def test_image_generation_configure_redacts_api_key(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.imageGeneration.configure",
        {
            "providerId": "openrouter",
            "primary": "openrouter/google/gemini-3.1-flash-image-preview",
            "apiKey": "sk-or",
        },
        _admin_ctx(),
    )
    assert res.error is None, res.error
    assert res.payload["changed"] is True
    assert res.payload["restartRequired"] is False
    assert res.payload["entry"]["api_key"] == "***"

    data = tomllib.loads(target.read_text())
    assert data["image_generation"]["enabled"] is True
    assert (
        data["image_generation"]["primary"]
        == "openrouter/google/gemini-3.1-flash-image-preview"
    )
    assert data["image_generation"]["providers"]["openrouter"]["api_key"] == "sk-or"


@pytest.mark.asyncio
async def test_onboarding_status_requires_image_generation_enable_for_llm_fallback(
    tmp_path,
    monkeypatch,
):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    from opensquilla.gateway.config import GatewayConfig

    ctx = _read_ctx()
    ctx.config = GatewayConfig()
    ctx.config.llm.provider = "openrouter"
    ctx.config.llm.api_key = "sk-or"

    res = await get_dispatcher().dispatch("r1", "onboarding.status", {}, ctx)

    assert res.error is None, res.error
    assert res.payload["imageGenerationConfigured"] is False
    assert res.payload["imageGenerationEnabled"] is False
    assert res.payload["imageGenerationSource"] == "none"
    assert res.payload["imageGenerationProvider"] == ""


@pytest.mark.asyncio
async def test_image_generation_configure_can_enable_llm_fallback(tmp_path, monkeypatch):
    target = tmp_path / "c.toml"
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(target))
    from opensquilla.gateway.config import GatewayConfig

    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.llm.provider = "openrouter"
    ctx.config.llm.api_key = "sk-or"

    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.imageGeneration.configure",
        {"providerId": "openrouter"},
        ctx,
    )

    assert res.error is None, res.error
    assert res.payload["entry"]["enabled"] is True
    assert res.payload["entry"]["api_key_source"] == "llm_fallback"

    data = tomllib.loads(target.read_text())
    assert data["image_generation"]["enabled"] is True
    assert data["image_generation"]["providers"]["openrouter"]["api_key"] == ""


@pytest.mark.asyncio
async def test_memory_embedding_configure_redacts_remote_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.memory_embedding.configure",
        {
            "providerId": "openai",
            "model": "text-embedding-3-small",
            "apiKey": "mem-secret",
            "baseUrl": "https://api.openai.com/v1",
        },
        _admin_ctx(),
    )
    assert res.error is None, res.error
    assert res.payload["changed"] is True
    assert res.payload["restartRequired"] is True
    assert res.payload["entry"]["remote"]["api_key"] == "***"


@pytest.mark.asyncio
async def test_memory_embedding_configure_updates_ctx_config(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    from opensquilla.gateway.config import GatewayConfig

    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.config_path = str(tmp_path / "c.toml")

    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.memory_embedding.configure",
        {"providerId": "local", "onnxDir": "models/bge"},
        ctx,
    )
    assert res.error is None, res.error
    assert ctx.config.memory.embedding.requested_provider == "local"
    assert ctx.config.memory.embedding.local.onnx_dir == "models/bge"


@pytest.mark.asyncio
async def test_memory_embedding_configure_auto_can_store_remote_fallback(
    tmp_path, monkeypatch
):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    from opensquilla.gateway.config import GatewayConfig

    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.config_path = str(tmp_path / "c.toml")

    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.memory_embedding.configure",
        {
            "providerId": "auto",
            "model": "text-embedding-3-small",
            "apiKey": "mem-secret",
            "baseUrl": "https://embeddings.example/v1",
        },
        ctx,
    )

    assert res.error is None, res.error
    assert ctx.config.memory.embedding.requested_provider == "auto"
    assert ctx.config.memory.embedding.remote.api_key == "mem-secret"
    assert ctx.config.memory.embedding.remote.base_url == "https://embeddings.example/v1"
    assert res.payload["entry"]["remote"]["api_key"] == "***"


@pytest.mark.asyncio
async def test_admin_required_for_mutations(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.provider.configure",
        {"providerId": "openrouter", "model": "x", "apiKey": "k"},
        _read_ctx(),
    )
    assert res.error is not None
    assert res.error.code == "UNAUTHORIZED"


@pytest.mark.asyncio
async def test_provider_configure_writes_to_active_config_path(tmp_path, monkeypatch):
    # Gateway booted from ./opensquilla.toml — RPC must respect ctx.config.config_path.
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "wrong.toml"))
    project_config = tmp_path / "project.toml"

    from opensquilla.gateway.config import GatewayConfig

    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.config_path = str(project_config)

    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.provider.configure",
        {"providerId": "openrouter", "model": "x", "apiKey": "sk-test"},
        ctx,
    )
    assert res.error is None, res.error
    assert project_config.exists()
    assert not (tmp_path / "wrong.toml").exists()
    assert res.payload["configPath"] == str(project_config)


@pytest.mark.asyncio
async def test_provider_configure_updates_ctx_config_in_place(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    from opensquilla.gateway.config import GatewayConfig

    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.config_path = str(tmp_path / "c.toml")

    await get_dispatcher().dispatch(
        "r1",
        "onboarding.provider.configure",
        {"providerId": "openrouter", "model": "deepseek/x", "apiKey": "sk-new"},
        ctx,
    )
    # The running gateway's config should now reflect the change.
    assert ctx.config.llm.provider == "openrouter"
    assert ctx.config.llm.model == "deepseek/x"
    assert ctx.config.llm.api_key == "sk-new"


@pytest.mark.asyncio
async def test_provider_configure_does_not_persist_runtime_api_key(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    from opensquilla.gateway.config import GatewayConfig

    target = tmp_path / "c.toml"
    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.config_path = str(target)
    ctx.config.llm.provider = "openrouter"
    ctx.config.llm.model = "m1"
    ctx.config.llm.api_key = "from-env"
    ctx.config.mark_runtime_secret("llm.api_key")

    res = await get_dispatcher().dispatch(
        "r1",
        "onboarding.provider.configure",
        {"providerId": "openrouter", "model": "m2"},
        ctx,
    )

    assert res.error is None, res.error
    data = tomllib.loads(target.read_text())
    assert "api_key" not in data["llm"]
    assert ctx.config.llm.api_key == "from-env"


@pytest.mark.asyncio
async def test_provider_configure_calls_provider_selector_sync(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    from opensquilla.gateway.config import GatewayConfig

    sync_calls: list[object] = []

    class FakeSelector:
        def sync_primary(self, provider_config):
            sync_calls.append(provider_config)

    ctx = _admin_ctx()
    ctx.config = GatewayConfig()
    ctx.config.config_path = str(tmp_path / "c.toml")
    ctx.provider_selector = FakeSelector()

    await get_dispatcher().dispatch(
        "r1",
        "onboarding.provider.configure",
        {"providerId": "openrouter", "model": "m", "apiKey": "k"},
        ctx,
    )
    assert len(sync_calls) == 1
    assert sync_calls[0].provider == "openrouter"
    assert sync_calls[0].model == "m"
    assert sync_calls[0].api_key == "k"


@pytest.mark.asyncio
async def test_channel_disable_then_remove(tmp_path, monkeypatch):
    monkeypatch.setenv("OPENSQUILLA_GATEWAY_CONFIG_PATH", str(tmp_path / "c.toml"))
    d = get_dispatcher()
    await d.dispatch(
        "r1",
        "onboarding.channel.upsert",
        {"entry": {"type": "slack", "name": "w", "token": "t"}},
        _admin_ctx(),
    )
    res = await d.dispatch("r2", "onboarding.channel.disable", {"name": "w"}, _admin_ctx())
    assert res.error is None
    assert res.payload["enabled"] is False
    res2 = await d.dispatch("r3", "onboarding.channel.remove", {"name": "w"}, _admin_ctx())
    assert res2.error is None
    assert res2.payload["changed"] is True
