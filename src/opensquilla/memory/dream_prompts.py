"""Prompt builders for Dream Phase 1 (analysis) and Phase 2 (edit)."""

from __future__ import annotations

from pathlib import Path


def phase1_prompt_from_contents(
    current_memory_md: str,
    new_files: list[tuple[str, str]],
) -> str:
    """Build Phase 1 prompt from pre-budgeted file contents."""
    header = (
        "You are reviewing new session memory files to decide what should "
        "be promoted to MEMORY.md (the long-term curated tier) and what "
        "should be discarded as session-specific noise.\n\n"
        "Rules:\n"
        "- Only promote durable facts: preferences, decisions, recurring "
        "context. Skip one-off task details.\n"
        "- If a fact is already in MEMORY.md, note whether it needs an "
        "update or can be skipped.\n"
        "- Keep the output concise (bullet list, <= 300 words).\n"
        "- Do NOT modify MEMORY.md yet — Phase 2 will apply edits.\n\n"
    )
    md_block = f"Current MEMORY.md:\n<<<\n{current_memory_md}\n>>>\n\n"
    files_block = "New session files:\n"
    for name, content in new_files:
        files_block += f"\n-- {name} --\n{content}\n"
    return header + md_block + files_block + "\n\nYour analysis:"


def phase1_prompt(current_memory_md: str, new_files: list[Path]) -> str:
    """Build the Phase 1 analysis prompt.

    Inputs: current ``MEMORY.md`` content + N new session-flush files.
    Output (from LLM): plain text rationale listing which facts to
    promote, update, or drop.
    """
    return phase1_prompt_from_contents(
        current_memory_md,
        [(p.name, p.read_text(encoding="utf-8", errors="replace")) for p in new_files],
    )


def phase2_prompt(phase1_output: str) -> str:
    """Ask the LLM to emit a JSON edit plan for ``MEMORY.md``.

    The LLM returns ``{"edits": [...], "done": true}`` plus the
    ``<<dream_complete>>`` marker. Dream validates and applies.
    """
    return (
        "Based on the Phase 1 analysis below, produce a JSON edit plan for "
        "MEMORY.md. Emit JSON ONLY, then the marker <<dream_complete>>.\n\n"
        "Schema:\n"
        "{\n"
        '  "edits": [\n'
        '    {"op": "append", "text": "...content to append..."},\n'
        '    {"op": "replace", "find": "old string", "with": "new string"}\n'
        "  ],\n"
        '  "done": true\n'
        "}\n\n"
        "Rules:\n"
        "- Only add high-value, durable facts.\n"
        "- Use `replace` for updates (find must be unique).\n"
        "- Use `append` for net-new content.\n"
        "- Leave `edits` empty if nothing is worth changing.\n\n"
        f"Phase 1 analysis:\n{phase1_output}\n"
    )
