from __future__ import annotations

import pytest

from opensquilla.provider.failures import ProviderFailureKind, classify_provider_error


@pytest.mark.parametrize(
    "provider",
    [
        "deepseek",
        "gemini",
        "dashscope",
        "bailian_coding",
        "moonshot",
        "mistral",
        "groq",
        "zhipu",
        "siliconflow",
        "volcengine",
        "byteplus",
        "qianfan",
        "aihubmix",
        "minimax_openai",
        "vllm",
        "lm_studio",
        "ovms",
    ],
)
def test_openai_compatible_providers_share_common_failure_classification(provider: str) -> None:
    assert (
        classify_provider_error(provider, 401, message="invalid api key")
        is ProviderFailureKind.AUTH_INVALID
    )
    assert (
        classify_provider_error(provider, 429, message="rate limit exceeded")
        is ProviderFailureKind.RATE_LIMITED
    )
    assert (
        classify_provider_error(provider, 404, message="model not found")
        is ProviderFailureKind.MODEL_NOT_FOUND
    )
    assert (
        classify_provider_error(provider, 400, message="unsupported parameter")
        is ProviderFailureKind.UNSUPPORTED_FEATURE
    )


@pytest.mark.parametrize("provider", ["minimax", "minimax_cn", "minimax_global"])
def test_minimax_region_profiles_use_anthropic_failure_classification(provider: str) -> None:
    assert (
        classify_provider_error(provider, 401, raw_code="authentication_error")
        is ProviderFailureKind.AUTH_INVALID
    )
