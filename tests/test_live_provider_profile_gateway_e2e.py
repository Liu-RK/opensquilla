from __future__ import annotations

import importlib.util
import sys
from pathlib import Path


def _load_e2e_module():
    script_path = (
        Path(__file__).resolve().parents[1] / "scripts" / "live_provider_profile_gateway_e2e.py"
    )
    spec = importlib.util.spec_from_file_location("live_provider_profile_gateway_e2e", script_path)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    sys.modules[spec.name] = module
    spec.loader.exec_module(module)
    return module


e2e = _load_e2e_module()


def test_gateway_e2e_defaults_cover_all_router_profiles() -> None:
    assert e2e.DEFAULT_PROVIDERS == [
        "openrouter",
        "dashscope",
        "deepseek",
        "gemini",
        "volcengine",
        "openai",
        "zhipu",
        "moonshot",
    ]


def test_profile_slot_targets_cover_slots_not_unique_models() -> None:
    tiers = {
        "t0": {"provider": "deepseek", "model": "deepseek-v4-flash"},
        "t1": {
            "provider": "deepseek",
            "model": "deepseek-v4-flash",
            "thinking_level": "low",
        },
        "t2": {"provider": "deepseek", "model": "deepseek-v4-pro"},
        "t3": {
            "provider": "deepseek",
            "model": "deepseek-v4-pro",
            "thinking_level": "high",
        },
        "image_model": {"provider": "openrouter", "model": "vision", "image_only": True},
    }

    targets = e2e._profile_slot_targets(tiers)

    assert list(targets) == ["t0", "t1", "t2", "t3"]
    assert targets["t0"]["model"] == targets["t1"]["model"]
    assert targets["t1"]["thinking_level"] == "low"


def test_forced_tier_overrides_make_only_target_slot_text_routable() -> None:
    tiers = {
        "t0": {"provider": "deepseek", "model": "deepseek-v4-flash"},
        "t1": {"provider": "deepseek", "model": "deepseek-v4-flash"},
        "t2": {"provider": "deepseek", "model": "deepseek-v4-pro"},
        "t3": {"provider": "deepseek", "model": "deepseek-v4-pro"},
    }

    overrides = e2e._forced_tier_overrides_for_slot(tiers, "t2")

    assert overrides["t2"]["image_only"] is False
    assert overrides["t2"]["model"] == "deepseek-v4-pro"
    assert overrides["t0"]["image_only"] is True
    assert overrides["t1"]["image_only"] is True
    assert overrides["t3"]["image_only"] is True


def test_missing_profile_slots_are_computed_by_slot() -> None:
    tiers = {
        "t0": {"provider": "deepseek", "model": "deepseek-v4-flash"},
        "t1": {"provider": "deepseek", "model": "deepseek-v4-flash"},
        "t2": {"provider": "deepseek", "model": "deepseek-v4-pro"},
        "t3": {"provider": "deepseek", "model": "deepseek-v4-pro"},
    }
    rows = [
        {
            "ok": True,
            "expected_slot": "t0",
            "actual_slot_covered": "t0",
            "expected_model": "deepseek-v4-flash",
            "actual_request_model": "deepseek-v4-flash",
        },
        {
            "ok": True,
            "expected_slot": "t2",
            "actual_slot_covered": "t2",
            "expected_model": "deepseek-v4-pro",
            "actual_request_model": "deepseek-v4-pro",
        },
    ]

    assert e2e._missing_profile_slots(tiers, rows) == ["t1", "t3"]


def test_cost_summary_never_promotes_gateway_placeholder_to_provider_bill() -> None:
    cost = e2e._estimate_cost(
        "glm-5.1",
        {"input_tokens": 1000, "output_tokens": 2000, "billed_cost": 0.0},
    )

    assert cost["provider_billed_cost_usd"] is None
    assert cost["raw_gateway_usage_billed_cost_usd"] == 0.0
    assert cost["cost_source"] == "opensquilla_static_estimate"
    assert cost["opensquilla_estimated_cost_usd"] > 0


def test_openrouter_nonzero_billed_cost_is_recorded_as_provider_bill() -> None:
    cost = e2e._estimate_cost(
        "z-ai/glm-5.1",
        {"input_tokens": 1000, "output_tokens": 2000, "billed_cost": 0.0123},
        provider="openrouter",
    )

    assert cost["provider_billed_cost_usd"] == 0.0123
    assert cost["raw_gateway_usage_billed_cost_usd"] == 0.0123
    assert cost["cost_source"] == "provider_billed"
    assert cost["billing_scope"] == "provider_response"
    assert cost["opensquilla_estimated_cost_usd"] > 0


def test_router_step_is_extracted_from_decision_log() -> None:
    decision = {
        "pipeline_steps": [
            {"step_name": "resolve_model", "routed_tier": None},
            {
                "step_name": "apply_squilla_router",
                "routed_tier": "t2",
                "routing_source": "v4_phase3",
                "confidence": 0.91,
            },
        ]
    }

    step = e2e._router_step_from_decision(decision)

    assert step["routed_tier"] == "t2"
    assert step["routing_source"] == "v4_phase3"
    assert step["confidence"] == 0.91
