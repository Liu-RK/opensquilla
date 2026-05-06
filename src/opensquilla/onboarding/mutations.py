"""Mutations for provider/channel onboarding configuration."""

from __future__ import annotations

import os
from dataclasses import dataclass, field
from typing import Any, Literal, cast

from pydantic import ValidationError

from opensquilla.channels.registry import discover_all, parse_channel_entry
from opensquilla.gateway.config import (
    ChannelsConfig,
    GatewayConfig,
    LlmProviderConfig,
    MemoryEmbeddingConfig,
)
from opensquilla.onboarding.image_generation_specs import (
    get_image_generation_provider_setup_spec,
)
from opensquilla.onboarding.provider_specs import get_provider_setup_spec
from opensquilla.onboarding.redaction import (
    redact_channel_entry,
    redact_image_generation_payload,
    redact_memory_embedding_payload,
    redact_provider_payload,
    redact_search_payload,
)
from opensquilla.onboarding.search_specs import get_search_provider_setup_spec

SearchFallbackPolicy = Literal["off", "network"]
_REMOTE_MEMORY_EMBEDDING_PROVIDERS = {"openai", "openai-compatible"}
_DEFAULT_REMOTE_EMBEDDING_BASE_URL = "https://api.openai.com/v1"
_DEFAULT_OLLAMA_EMBEDDING_BASE_URL = "http://localhost:11434"


@dataclass(frozen=True)
class MutationResult:
    config: GatewayConfig
    changed: bool
    restart_required: bool
    warnings: list[str] = field(default_factory=list)
    public_payload: dict[str, Any] = field(default_factory=dict)


def _clone(cfg: GatewayConfig) -> GatewayConfig:
    new_cfg = cfg.model_copy(deep=True)
    new_cfg.inherit_runtime_secrets(cfg)
    return new_cfg


def _clean_optional_str(value: str | None) -> str:
    if value is None:
        return ""
    return value.strip()


def upsert_llm_provider(
    config: GatewayConfig,
    *,
    provider_id: str,
    model: str,
    api_key: str = "",
    base_url: str = "",
    proxy: str = "",
    provider_routing: dict[str, str] | None = None,
) -> MutationResult:
    spec = get_provider_setup_spec(provider_id)
    if not spec.runtime_supported:
        raise ValueError(
            f"provider {provider_id!r} is not runtime-supported and cannot be configured"
        )
    if not model:
        raise ValueError("model is required")
    # When the operator omits an api_key while reconfiguring the same
    # provider that already has one stored, treat that as "leave key
    # unchanged" — matches the WebUI's "leave blank to keep current"
    # password-field affordance.
    effective_api_key = api_key
    if (
        not effective_api_key
        and spec.requires_api_key
        and config.llm.provider == provider_id
        and config.llm.api_key
    ):
        effective_api_key = config.llm.api_key
    if spec.requires_api_key and not effective_api_key:
        raise ValueError(f"provider {provider_id!r} requires an api_key")
    effective_base_url = base_url or spec.default_base_url
    if spec.requires_base_url and not effective_base_url:
        raise ValueError(f"provider {provider_id!r} requires a base_url")

    new_cfg = _clone(config)
    new_cfg.llm = LlmProviderConfig(
        provider=provider_id,
        model=model,
        api_key=effective_api_key,
        base_url=effective_base_url,
        proxy=proxy,
        provider_routing=dict(provider_routing or {}),
    )
    if api_key:
        new_cfg.clear_runtime_secret("llm.api_key")

    payload = {
        "provider": provider_id,
        "model": model,
        "api_key": effective_api_key,
        "base_url": effective_base_url,
        "proxy": proxy,
        "provider_routing": dict(provider_routing or {}),
    }
    return MutationResult(
        config=new_cfg,
        changed=True,
        restart_required=False,
        warnings=[],
        public_payload=redact_provider_payload(payload),
    )


def upsert_search_provider(
    config: GatewayConfig,
    *,
    provider_id: str,
    api_key: str = "",
    max_results: int = 5,
    proxy: str = "",
    use_env_proxy: bool = False,
    fallback_policy: str = "off",
    diagnostics: bool = False,
) -> MutationResult:
    spec = get_search_provider_setup_spec(provider_id)
    if not spec.runtime_supported:
        raise ValueError(
            f"search provider {provider_id!r} is not runtime-supported and cannot be configured"
        )
    if max_results < 1:
        raise ValueError("max_results must be >= 1")
    if fallback_policy not in {"off", "network"}:
        raise ValueError("fallback_policy must be 'off' or 'network'")
    fallback_policy_value = cast(SearchFallbackPolicy, fallback_policy)

    effective_api_key = api_key
    if (
        not effective_api_key
        and spec.requires_api_key
        and config.search_provider == provider_id
        and config.search_api_key
    ):
        effective_api_key = config.search_api_key
    if spec.requires_api_key and not effective_api_key:
        raise ValueError(f"search provider {provider_id!r} requires an api_key")

    new_cfg = _clone(config)
    new_cfg.search_provider = provider_id
    new_cfg.search_api_key = effective_api_key
    new_cfg.search_max_results = max_results
    new_cfg.search_proxy = proxy
    new_cfg.search_use_env_proxy = bool(use_env_proxy)
    new_cfg.search_fallback_policy = fallback_policy_value
    new_cfg.search_diagnostics = bool(diagnostics)
    if api_key:
        new_cfg.clear_runtime_secret("search_api_key")

    payload = {
        "provider": provider_id,
        "api_key": effective_api_key,
        "max_results": max_results,
        "proxy": proxy,
        "use_env_proxy": bool(use_env_proxy),
        "fallback_policy": fallback_policy_value,
        "diagnostics": bool(diagnostics),
    }
    return MutationResult(
        config=new_cfg,
        changed=True,
        restart_required=False,
        warnings=[],
        public_payload=redact_search_payload(payload),
    )


def _image_generation_provider_config(config: GatewayConfig, provider_id: str) -> Any:
    providers = config.image_generation.providers
    provider_config = getattr(providers, provider_id, None)
    if provider_config is None:
        raise KeyError(f"unknown image generation provider: {provider_id!r}")
    return provider_config


def _image_generation_api_key_source(
    config: GatewayConfig,
    *,
    provider_id: str,
    api_key: str,
    env_key: str,
) -> str:
    if api_key:
        return "explicit"
    if env_key and os.environ.get(env_key):
        return "env"
    if config.llm.provider == provider_id and config.llm.api_key:
        return "llm_fallback"
    return "none"


def upsert_image_generation_provider(
    config: GatewayConfig,
    *,
    provider_id: str,
    primary: str = "",
    api_key: str = "",
    base_url: str = "",
    enabled: bool = True,
) -> MutationResult:
    spec = get_image_generation_provider_setup_spec(provider_id)
    if not spec.runtime_supported:
        raise ValueError(
            f"image generation provider {provider_id!r} is not runtime-supported "
            "and cannot be configured"
        )
    primary_model = primary or spec.default_model
    primary_provider, sep, _model = primary_model.partition("/")
    if not sep or primary_provider != provider_id:
        raise ValueError(
            "primary must be a provider/model reference for "
            f"image generation provider {provider_id!r}"
        )

    current_provider_cfg = _image_generation_provider_config(config, provider_id)
    effective_api_key = api_key or getattr(current_provider_cfg, "api_key", "")
    env_key = getattr(current_provider_cfg, "api_key_env", spec.env_key) or spec.env_key
    api_key_source = _image_generation_api_key_source(
        config,
        provider_id=provider_id,
        api_key=effective_api_key,
        env_key=env_key,
    )
    if spec.requires_api_key and api_key_source == "none":
        raise ValueError(
            f"image generation provider {provider_id!r} requires an api_key, "
            f"{spec.env_key}, or a matching configured LLM provider"
        )

    effective_base_url = (
        base_url or getattr(current_provider_cfg, "base_url", "") or spec.default_base_url
    )

    new_cfg = _clone(config)
    new_cfg.image_generation.enabled = bool(enabled)
    new_cfg.image_generation.primary = primary_model
    next_provider_cfg = _image_generation_provider_config(new_cfg, provider_id)
    next_provider_cfg.api_key = effective_api_key
    next_provider_cfg.base_url = effective_base_url
    if api_key:
        new_cfg.clear_runtime_secret(f"image_generation.providers.{provider_id}.api_key")

    payload = {
        "provider": provider_id,
        "enabled": bool(enabled),
        "primary": primary_model,
        "api_key": effective_api_key,
        "api_key_env": env_key,
        "api_key_source": api_key_source,
        "base_url": effective_base_url,
    }
    return MutationResult(
        config=new_cfg,
        changed=True,
        restart_required=False,
        warnings=[],
        public_payload=redact_image_generation_payload(payload),
    )


def upsert_memory_embedding(
    config: GatewayConfig,
    *,
    provider: str,
    model: str | None = None,
    api_key: str | None = None,
    base_url: str | None = None,
    onnx_dir: str | None = None,
) -> MutationResult:
    if provider not in {"auto", "none", "local", "openai", "openai-compatible", "ollama"}:
        raise ValueError(f"unknown memory embedding provider: {provider!r}")

    new_cfg = _clone(config)
    old_memory = config.memory.model_dump(mode="python")
    current = config.memory.embedding
    model_value = _clean_optional_str(model)
    api_key_value = _clean_optional_str(api_key)
    base_url_value = _clean_optional_str(base_url)
    onnx_dir_value = _clean_optional_str(onnx_dir)
    payload: dict[str, Any] = {"provider": provider}

    if provider in _REMOTE_MEMORY_EMBEDDING_PROVIDERS:
        effective_api_key = api_key_value or current.remote.api_key or current.api_key or ""
        if not effective_api_key:
            raise ValueError("remote memory embedding provider requires an api_key")
        payload["remote"] = {
            "api_key": effective_api_key,
            "base_url": (
                base_url_value
                or current.remote.base_url
                or current.base_url
                or _DEFAULT_REMOTE_EMBEDDING_BASE_URL
            ),
        }
        remote_model = model_value or current.remote.model or current.model
        if remote_model:
            payload["remote"]["model"] = remote_model
    elif provider == "auto":
        remote_payload: dict[str, str] = {}
        effective_api_key = api_key_value or current.remote.api_key or current.api_key or ""
        if effective_api_key:
            remote_payload["api_key"] = effective_api_key
        remote_base_url = base_url_value or current.remote.base_url or current.base_url
        if remote_base_url:
            remote_payload["base_url"] = remote_base_url
        remote_model = model_value or current.remote.model or (
            current.model if effective_api_key else None
        )
        if remote_model:
            remote_payload["model"] = remote_model
        if remote_payload:
            payload["remote"] = remote_payload
    elif provider == "local":
        payload["local"] = {}
        local_onnx_dir = onnx_dir_value or (
            current.local.onnx_dir if current.requested_provider == "local" else ""
        )
        if local_onnx_dir:
            payload["local"]["onnx_dir"] = local_onnx_dir
    elif provider == "ollama":
        payload["ollama"] = {
            "base_url": (
                base_url_value
                or current.ollama.base_url
                or _DEFAULT_OLLAMA_EMBEDDING_BASE_URL
            ),
        }
        ollama_model = model_value or current.ollama.model
        if ollama_model:
            payload["ollama"]["model"] = ollama_model

    new_cfg.memory.embedding = MemoryEmbeddingConfig.model_validate(payload)
    changed = old_memory != new_cfg.memory.model_dump(mode="python")
    if api_key_value:
        new_cfg.clear_runtime_secret("memory.embedding.remote.api_key")
        new_cfg.clear_runtime_secret("memory.embedding.api_key")

    return MutationResult(
        config=new_cfg,
        changed=changed,
        restart_required=changed,
        warnings=[],
        public_payload=redact_memory_embedding_payload(payload),
    )


def _channel_entries_as_dicts(cfg: GatewayConfig) -> list[dict[str, Any]]:
    return [e.model_dump(mode="python") for e in cfg.channels.channels]


def list_channel_entries(config: GatewayConfig) -> list[dict[str, Any]]:
    return [redact_channel_entry(d.get("type", ""), d) for d in _channel_entries_as_dicts(config)]


def validate_channel_entry(payload: dict[str, Any]) -> dict[str, Any]:
    if not isinstance(payload, dict):
        raise TypeError("channel entry payload must be a dict")
    type_name = payload.get("type")
    if not isinstance(type_name, str) or not type_name:
        raise ValueError("channel entry requires non-empty 'type'")
    if type_name not in discover_all():
        raise ValueError(f"unknown channel type: {type_name!r}")
    full = {"agent_id": "main", "enabled": True, **payload}
    try:
        entry = parse_channel_entry(full)
    except ValidationError as exc:
        raise ValueError(str(exc)) from exc
    return entry.model_dump(mode="python")


def upsert_channel(
    config: GatewayConfig,
    *,
    entry_payload: dict[str, Any],
) -> MutationResult:
    normalized = validate_channel_entry(entry_payload)
    name = normalized["name"]
    new_cfg = _clone(config)
    raw = _channel_entries_as_dicts(new_cfg)
    replaced = False
    for idx, existing in enumerate(raw):
        if existing.get("name") == name:
            raw[idx] = normalized
            replaced = True
            break
    if not replaced:
        raw.append(normalized)
    new_cfg.channels = ChannelsConfig.model_validate({"channels": raw})

    return MutationResult(
        config=new_cfg,
        changed=True,
        restart_required=True,
        warnings=[],
        public_payload=redact_channel_entry(normalized["type"], normalized),
    )


def remove_channel(
    config: GatewayConfig,
    *,
    name: str,
) -> MutationResult:
    new_cfg = _clone(config)
    raw = _channel_entries_as_dicts(new_cfg)
    remaining = [e for e in raw if e.get("name") != name]
    if len(remaining) == len(raw):
        raise KeyError(f"no channel named {name!r}")
    new_cfg.channels = ChannelsConfig.model_validate({"channels": remaining})
    return MutationResult(
        config=new_cfg,
        changed=True,
        restart_required=True,
        public_payload={"name": name, "removed": True},
    )


def set_channel_enabled(
    config: GatewayConfig,
    *,
    name: str,
    enabled: bool,
) -> MutationResult:
    new_cfg = _clone(config)
    raw = _channel_entries_as_dicts(new_cfg)
    found = False
    for entry in raw:
        if entry.get("name") == name:
            entry["enabled"] = bool(enabled)
            found = True
            break
    if not found:
        raise KeyError(f"no channel named {name!r}")
    new_cfg.channels = ChannelsConfig.model_validate({"channels": raw})
    return MutationResult(
        config=new_cfg,
        changed=True,
        restart_required=True,
        public_payload={"name": name, "enabled": bool(enabled)},
    )
