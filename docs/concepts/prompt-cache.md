# Prompt Cache

OpenSquilla splits prompt material into a cacheable base and an uncached dynamic
suffix.

The base contains identity, tool policy, runtime facts that are stable for the
session, and other prompt text that should not churn between turns. The dynamic
suffix contains per-turn or frequently changing context such as workspace file
payloads, daily notes, skills injection, subagent grounding, and channel
rendering hints.

Decision logs record both sides of the split:

- `cache_base_hash` and `cache_base_chars` identify the cacheable prefix.
- `cache_dynamic_hash` and `cache_dynamic_chars` identify the uncached suffix.
- `cache_read_input_tokens` is the provider-reported cache read token count.
- `cache_creation_input_tokens` is the provider-reported cache write token count.
- `resolved_model`, `alias_resolution_chain`, and `provider_after_rewrite`
  describe the routed model/provider shape used for cache analysis.
- `cache_legacy_hash` hashes the migration-period key tuple
  `(agent_id, resolved_model)`.
- `cache_shadow_final_hash` hashes the comparison key tuple
  `(agent_id, resolved_model, provider_after_rewrite, channel_pinned?)`.
- `cache_key_collision` is true when the same legacy hash maps to multiple
  comparison hashes in the current process.

OpenSquilla keeps the existing cache key behavior. The legacy/comparison fields
are diagnostics for cache analysis, not an automatic migration path.
