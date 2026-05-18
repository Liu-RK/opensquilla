from __future__ import annotations

import pytest

from opensquilla.provider.request_proof import (
    ProviderRequestBudgetExceeded,
    prove_or_compact_provider_payload,
    prove_provider_payload,
)


def test_provider_request_proof_allows_payload_within_budget() -> None:
    proof = prove_provider_payload(
        {"messages": [{"role": "user", "content": "small"}]},
        projection_adapter="openai",
        proof_budget=10_000,
    )

    assert proof["fits"] is True
    assert proof["projection_adapter"] == "openai"
    assert proof["estimated_chars"] < 10_000


def test_provider_request_proof_blocks_oversized_payload() -> None:
    with pytest.raises(ProviderRequestBudgetExceeded) as exc_info:
        prove_provider_payload(
            {"messages": [{"role": "user", "content": "x" * 5000}]},
            projection_adapter="openai",
            proof_budget=1000,
        )

    assert exc_info.value.proof["fits"] is False
    assert exc_info.value.proof["fallback_reason"] == "provider_request_budget_exhausted"
    assert exc_info.value.proof["top_contributors"][0]["chars"] == 5000


def test_provider_request_proof_excludes_native_image_payload_from_text_budget() -> None:
    proof = prove_provider_payload(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "describe this"},
                        {
                            "type": "image_url",
                            "image_url": {
                                "url": "data:image/png;base64," + ("a" * 5000),
                            },
                        },
                    ],
                }
            ]
        },
        projection_adapter="openrouter",
        proof_budget=1000,
        status_projection_mode="content_envelope",
    )

    assert proof["fits"] is True
    assert proof["media_blocks_excluded"] == 1
    assert proof["media_chars_excluded"] > 5000
    assert proof["top_contributors"][0]["chars"] < 5000


def test_provider_request_proof_excludes_anthropic_base64_media_from_text_budget() -> None:
    proof = prove_provider_payload(
        {
            "messages": [
                {
                    "role": "user",
                    "content": [
                        {"type": "text", "text": "summarize this"},
                        {
                            "type": "image",
                            "source": {
                                "type": "base64",
                                "media_type": "image/png",
                                "data": "a" * 5000,
                            },
                        },
                    ],
                }
            ]
        },
        projection_adapter="anthropic",
        proof_budget=1000,
        status_projection_mode="content_envelope",
    )

    assert proof["fits"] is True
    assert proof["media_blocks_excluded"] == 1
    assert proof["media_chars_excluded"] == 5000
    assert proof["top_contributors"][0]["chars"] < 5000


def test_provider_request_proof_still_blocks_large_text_next_to_native_media() -> None:
    payload = {
        "messages": [
            {
                "role": "user",
                "content": [
                    {"type": "text", "text": "x" * 5000},
                    {
                        "type": "image_url",
                        "image_url": {
                            "url": "data:image/png;base64," + ("a" * 5000),
                        },
                    },
                ],
            }
        ]
    }

    with pytest.raises(ProviderRequestBudgetExceeded) as exc_info:
        prove_provider_payload(
            payload,
            projection_adapter="openrouter",
            proof_budget=1000,
            status_projection_mode="content_envelope",
        )

    proof = exc_info.value.proof
    assert proof["fits"] is False
    assert proof["media_blocks_excluded"] == 1
    assert proof["top_contributors"][0]["chars"] == 5000


def test_provider_request_proof_compacts_tool_payload_once() -> None:
    payload = {
        "messages": [
            {"role": "user", "content": "hi"},
            {"role": "tool", "content": "x" * 5000},
        ]
    }

    compacted, proof = prove_or_compact_provider_payload(
        payload,
        projection_adapter="openai",
        proof_budget=2000,
        status_projection_mode="content_envelope",
    )

    assert proof is not None
    assert proof["fits"] is True
    assert proof["retry_count"] == 1
    assert len(compacted["messages"][1]["content"]) < 2000


def test_provider_request_proof_blocks_after_one_retry_when_still_oversized() -> None:
    payload = {"messages": [{"role": "tool", "content": "x" * 5000}]}

    with pytest.raises(ProviderRequestBudgetExceeded) as exc_info:
        prove_or_compact_provider_payload(
            payload,
            projection_adapter="openai",
            proof_budget=100,
            status_projection_mode="content_envelope",
        )

    assert exc_info.value.proof["fits"] is False
    assert exc_info.value.proof["retry_count"] == 1
