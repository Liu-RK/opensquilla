from __future__ import annotations

from pathlib import Path

from opensquilla.identity.prompt import assemble_system_prompt
from opensquilla.identity.types import AgentProfile


def test_default_user_template_names_profile_fields() -> None:
    template = Path("src/opensquilla/identity/templates/bootstrap/USER.md").read_text(
        encoding="utf-8"
    )

    assert "Name:" in template
    assert "What to call them:" in template
    assert "Pronouns:" in template
    assert "Timezone:" in template
    assert "Notes:" in template
    assert "## Context" in template
    assert "Do not put secrets" in template
    assert "one-off task notes" in template


def test_system_prompt_routes_profile_to_user_md() -> None:
    prompt = assemble_system_prompt(
        AgentProfile(agent_id="main", prompt_mode="full"),
        tools=["memory_search", "memory_get", "write_file", "edit_file", "apply_patch"],
    )

    assert "USER.md" in prompt
    assert "name, preferred address, pronouns, timezone" in prompt
    assert "Do not use `memory_save` for `USER.md`" in prompt
    assert "MEMORY.md` for durable non-profile facts" in prompt
    assert "decisions, dates, people, preferences, or todos" not in prompt
    assert "prior work, decisions, dated history, todos" in prompt


def test_system_prompt_only_documents_canonical_tool_names() -> None:
    prompt = assemble_system_prompt(
        AgentProfile(agent_id="main", prompt_mode="full"),
        tools=["image_generate", "sessions_spawn", "sessions_send", "subagents"],
    )

    assert "`image_generate`" in prompt
    assert "generate_image" not in prompt
    assert "spawn_subagent" not in prompt
    assert "send_message" not in prompt


def test_system_prompt_disambiguates_session_send_from_channel_message() -> None:
    prompt = assemble_system_prompt(
        AgentProfile(agent_id="main", prompt_mode="full"),
        tools=["sessions_send", "message"],
    )

    assert "agent-to-agent or session-to-session" in prompt
    assert "`sessions_send`" in prompt
    assert "`message` only for channel adapter delivery" in prompt
    assert "send_message" not in prompt


def test_legacy_image_alias_does_not_enable_image_generation_prompt() -> None:
    prompt = assemble_system_prompt(
        AgentProfile(agent_id="main", prompt_mode="full"),
        tools=["generate_image"],
    )

    assert "MUST call the `image_generate` tool" not in prompt
    assert "Image generation is not available in this session" in prompt


def test_template_no_longer_renders_duplicate_skills_section() -> None:
    prompt = assemble_system_prompt(
        AgentProfile(agent_id="main", prompt_mode="full"),
        tools=["memory_search"],
        skills=["memory"],
    )

    assert "## Skills (mandatory)" not in prompt
    assert "Available skills:" not in prompt
