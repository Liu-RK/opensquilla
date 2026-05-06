from __future__ import annotations

from opensquilla.provider.model_catalog import ModelCatalog


def test_deepseek_provider_profile_enables_deepseek_reasoning_format() -> None:
    caps = ModelCatalog().get_capabilities(
        "deepseek-chat",
        provider_name="deepseek",
        base_url="https://api.deepseek.com",
    )

    assert caps.supports_reasoning is True
    assert caps.supports_tools is True
    assert caps.reasoning_format == "deepseek"


def test_gemini_reasoning_model_uses_gemini_reasoning_format() -> None:
    caps = ModelCatalog().get_capabilities(
        "gemini-2.5-flash",
        provider_name="gemini",
        base_url="https://generativelanguage.googleapis.com/v1beta/openai",
    )

    assert caps.supports_reasoning is True
    assert caps.reasoning_format == "gemini"


def test_direct_openai_gpt_5_models_use_openai_reasoning_effort_format() -> None:
    catalog = ModelCatalog()

    for model in ("gpt-5.4-nano", "gpt-5.4-mini", "gpt-5.5"):
        caps = catalog.get_capabilities(
            model,
            provider_name="openai",
            base_url="https://api.openai.com/v1",
        )

        assert caps.supports_reasoning is True
        assert caps.supports_tools is True
        assert caps.reasoning_format == "openai"


def test_zai_glm5_models_use_zai_reasoning_format() -> None:
    catalog = ModelCatalog()

    for model in ("glm-4.7-flashx", "glm-5", "glm-5.1"):
        caps = catalog.get_capabilities(
            model,
            provider_name="zhipu",
            base_url="https://open.bigmodel.cn/api/paas/v4",
        )

        assert caps.supports_reasoning is True
        assert caps.supports_tools is True
        assert caps.reasoning_format == "zai"


def test_dashscope_qwen_thinking_models_use_dashscope_reasoning_format() -> None:
    catalog = ModelCatalog()

    for model in ("qwen3.6-flash", "qwen3.6-plus", "qwen3-max"):
        caps = catalog.get_capabilities(
            model,
            provider_name="dashscope",
            base_url="https://dashscope.aliyuncs.com/compatible-mode/v1",
        )

        assert caps.supports_reasoning is True
        assert caps.supports_tools is True
        assert caps.reasoning_format == "dashscope"


def test_moonshot_distinguishes_kimi_thinking_from_moonshot_v1() -> None:
    catalog = ModelCatalog()

    kimi_caps = catalog.get_capabilities(
        "kimi-k2.5",
        provider_name="moonshot",
        base_url="https://api.moonshot.cn/v1",
    )
    v1_caps = catalog.get_capabilities(
        "moonshot-v1-128k",
        provider_name="moonshot",
        base_url="https://api.moonshot.cn/v1",
    )

    assert kimi_caps.supports_reasoning is True
    assert kimi_caps.reasoning_format == "moonshot"
    assert v1_caps.supports_reasoning is False
    assert v1_caps.reasoning_format == "none"


def test_volcengine_doubao_thinking_models_use_volcengine_reasoning_format() -> None:
    catalog = ModelCatalog()

    thinking_caps = catalog.get_capabilities(
        "doubao-seed-1-6-thinking-250715",
        provider_name="volcengine",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )
    plain_caps = catalog.get_capabilities(
        "doubao-seed-1-6-251015",
        provider_name="volcengine",
        base_url="https://ark.cn-beijing.volces.com/api/v3",
    )

    assert thinking_caps.supports_reasoning is True
    assert thinking_caps.reasoning_format == "volcengine"
    assert plain_caps.supports_reasoning is False
    assert plain_caps.reasoning_format == "none"


def test_unknown_compatible_model_degrades_to_tools_only() -> None:
    caps = ModelCatalog().get_capabilities(
        "unknown-model",
        provider_name="moonshot",
        base_url="https://api.moonshot.ai/v1",
    )

    assert caps.supports_reasoning is False
    assert caps.supports_tools is True
    assert caps.reasoning_format == "none"
