# Third-party notices for `self-improving-agent` skill

Inspired by `self-improving-agent` on the ClawHub registry
(<https://clawhub.ai/self-improving-agent>, MIT-0). The OpenSquilla version
is independently authored: SKILL.md instructional text, the `init_learnings`
and `log_lesson` scripts, and the categories rubric were rewritten to match
OpenSquilla's existing `memory` skill boundaries and the conditional-tool
activation fields the OpenSquilla skill loader already supports.

The OpenClaw-specific onboarding section in the upstream version (which
referenced an OpenClaw setup flow and OpenClaw-only file paths) was
deliberately omitted; the OpenSquilla version is workspace-portable and
relies only on standard pathlib + the host's existing `memory_save` tool.

## Runtime dependencies

Pure Python, stdlib only.

## License

This skill, as part of OpenSquilla, is licensed under the project's MIT
license.
