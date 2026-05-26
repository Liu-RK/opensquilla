"""Round-trip serialization tests for MetaPlan (PR2)."""

from __future__ import annotations

import json

from opensquilla.skills.meta.plan_serde import (
    PLAN_SERDE_VERSION,
    from_jsonable,
    to_jsonable,
)
from opensquilla.skills.meta.types import (
    MetaPlan,
    MetaStep,
    RouteCase,
)


def _example_plan() -> MetaPlan:
    return MetaPlan(
        name="example",
        triggers=("hello world",),
        priority=5,
        steps=(
            MetaStep(
                id="classify",
                skill="classify",
                kind="llm_classify",
                output_choices=("A", "B"),
                with_args={"text": "{{ inputs.user_message }}"},
            ),
            MetaStep(
                id="handle",
                skill="summarize",
                kind="agent",
                depends_on=("classify",),
                route=(RouteCase(when="outputs.classify == 'A'", to="writer"),),
                with_args={"request": "{{ inputs.user_message }}"},
            ),
        ),
        fallback_body="body",
        final_text_mode="step:handle",
    )


def test_to_jsonable_produces_versioned_envelope():
    payload = to_jsonable(_example_plan())
    assert payload["v"] == PLAN_SERDE_VERSION
    assert payload["v"] == 1
    assert "plan" in payload
    plan_obj = payload["plan"]
    assert plan_obj["name"] == "example"
    assert plan_obj["priority"] == 5
    assert len(plan_obj["steps"]) == 2
    assert plan_obj["steps"][0]["kind"] == "llm_classify"


def test_to_jsonable_is_json_dumpable():
    payload = to_jsonable(_example_plan())
    json.dumps(payload, sort_keys=True)


def test_from_jsonable_round_trip():
    original = _example_plan()
    payload = to_jsonable(original)
    restored = from_jsonable(payload)
    assert restored.name == original.name
    assert restored.triggers == original.triggers
    assert restored.priority == original.priority
    assert len(restored.steps) == len(original.steps)
    assert restored.fallback_body == original.fallback_body
    assert restored.final_text_mode == original.final_text_mode


def test_from_jsonable_tolerates_legacy_envelope():
    """Deserialize a pre-PR2 snapshot dict (no 'v' key)."""
    original = _example_plan()
    payload = to_jsonable(original)
    # Strip envelope to simulate legacy row
    legacy_dict = payload["plan"]
    restored = from_jsonable(legacy_dict)
    assert restored.name == original.name
    assert restored.priority == original.priority
