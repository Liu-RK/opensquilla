"""Factory helpers for constructing Dream runners from gateway config."""

from __future__ import annotations

import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from opensquilla.agents.scope import resolve_agent_workspace_dir
from opensquilla.memory.dream import Dream


def build_dream_provider_selector(config: Any) -> Any | None:
    """Build a ModelSelector using the gateway's LLM config precedence."""
    llm_cfg = getattr(config, "llm", None)
    if llm_cfg is None:
        return None

    api_key = os.environ.get("OPENROUTER_API_KEY", "") or getattr(llm_cfg, "api_key", "")
    if not api_key:
        return None

    from opensquilla.provider.selector import ModelSelector, ProviderConfig, SelectorConfig

    base_url = os.environ.get("OPENROUTER_BASE_URL", "") or getattr(llm_cfg, "base_url", "")
    if base_url.endswith("/v1"):
        base_url = base_url[:-3]
    proxy = os.environ.get("OPENSQUILLA_LLM_PROXY", "") or getattr(llm_cfg, "proxy", "")

    return ModelSelector(
        SelectorConfig(
            primary=ProviderConfig(
                provider=getattr(llm_cfg, "provider", "openrouter"),
                model=getattr(llm_cfg, "model", ""),
                api_key=api_key,
                base_url=base_url,
                proxy=proxy,
                provider_routing=getattr(llm_cfg, "provider_routing", {}),
            )
        )
    )


def _clone_selector(provider_selector: Any) -> Any:
    clone = getattr(provider_selector, "clone", None)
    if callable(clone):
        return clone()
    return provider_selector


def _resolve_provider(
    *,
    provider_selector: Any | None,
    config: Any,
    model_override: str | None,
    need_provider: bool,
) -> Any | None:
    if not need_provider:
        return None

    selector = provider_selector or build_dream_provider_selector(config)
    if selector is None:
        raise RuntimeError("no provider configured for Dream")

    selector = _clone_selector(selector)
    if model_override:
        override_model = getattr(selector, "override_model", None)
        if callable(override_model):
            override_model(model_override)

    resolve = getattr(selector, "resolve", None)
    if not callable(resolve):
        raise RuntimeError("provider selector cannot resolve a provider")
    return resolve()


def _session_lock_for(turn_runner: Any | None, agent_id: str) -> Any | None:
    if turn_runner is None:
        return None
    get_lock = getattr(turn_runner, "get_session_lock", None)
    if not callable(get_lock):
        get_lock = getattr(turn_runner, "_get_session_lock", None)
    if not callable(get_lock):
        return None
    return get_lock(f"memory_dream:{agent_id}")


def build_dream_factory(
    *,
    config: Any,
    provider_selector: Any | None = None,
    tool_registry: Any | None = None,
    turn_runner: Any | None = None,
    workspace_for_agent: Callable[[str], Path] | None = None,
    need_provider: bool = True,
) -> Callable[[str], Dream]:
    """Return ``build_dream(agent_id)`` wired to gateway/CLI dependencies."""
    dream_cfg = getattr(getattr(config, "memory", None), "dream", None)
    if dream_cfg is None:
        raise RuntimeError("memory.dream config is missing")

    model_override = getattr(dream_cfg, "model_override", None)
    default_model = getattr(getattr(config, "llm", None), "model", "")

    def build_dream(agent_id: str) -> Dream:
        workspace = (
            workspace_for_agent(agent_id)
            if workspace_for_agent is not None
            else resolve_agent_workspace_dir(agent_id, config)
        )
        workspace.mkdir(parents=True, exist_ok=True)
        (workspace / "memory").mkdir(parents=True, exist_ok=True)
        model = model_override or default_model
        provider = _resolve_provider(
            provider_selector=provider_selector,
            config=config,
            model_override=model_override,
            need_provider=need_provider,
        )
        return Dream(
            workspace=workspace,
            provider=provider,
            model=model,
            tool_registry=tool_registry,
            session_lock=_session_lock_for(turn_runner, agent_id),
            config=dream_cfg,
            agent_id=agent_id,
        )

    return build_dream
