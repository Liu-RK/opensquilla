# Lesson categories

Five categories. Pick the one that best describes what happened — the choice
controls which file the entry lands in and how future agents grep for it.

## correction

The user disagreed with an action and explicitly redirected.

> Example: I generated a Python list comprehension; user said "Use a for-loop
> here for readability." Logged to LEARNINGS.md as `correction`.

Use when:

- The user typed "no", "not quite", "actually", "wrong", or similar
- The user supplied a counter-example or alternative
- The user changed scope mid-task to fix something already done

Do not use when the user is simply asking a follow-up question; that is
not a correction.

## knowledge_gap

You discovered a fact you held was wrong or outdated.

> Example: I claimed library X requires Python 3.10+; the actual minimum is
> 3.11. Logged to LEARNINGS.md as `knowledge_gap`.

Use when:

- A test or check disproved an assumption you stated as fact
- Documentation revealed your training-data knowledge was stale
- An API behaved differently than your model knew

Pair with a citation when possible (URL, version number, date).

## best_practice

You found a better approach for a recurring task.

> Example: For multi-file refactors in this repo, run ruff first to surface
> import-cycle issues before splitting modules. Logged to LEARNINGS.md as
> `best_practice`.

Use when:

- The new approach is reproducible across similar future tasks
- The lesson is generalizable — not specific to one quirk of this run

If the lesson is project-specific, it stays in `.learnings/`. If it
generalizes (e.g., a Python idiom), promote it to durable memory via the
`memory` skill's `memory_save` tool.

## error

A command or integration failed.

> Example: `git push` returned `403` because the token had expired. Logged
> to ERRORS.md as `error`.

Use when:

- A subprocess returned a non-zero exit code
- An external API returned an error response
- A network timeout, file-not-found, permission-denied, or similar

Always redact secrets before logging. Replace tokens, passwords, and
customer-identifying data with `<REDACTED>`.

## feature

The user requested a capability that does not exist.

> Example: User asked to "deploy this to Vercel from inside the chat";
> OpenSquilla has no Vercel skill. Logged to FEATURE_REQUESTS.md.

Use when:

- The user names a tool/integration not in the current bundle
- A workflow would benefit from a sub-step OpenSquilla cannot perform yet
- The host responded "I cannot do X here" and the user said "I wish you
  could"

Keep entries factual: what the user wanted + why it cannot be done now.
Avoid scope creep into "and we should also...". One feature request per
entry.

## Promotion to durable memory

Categories `correction`, `knowledge_gap`, and `best_practice` are
candidates for promotion via the `memory` skill's `memory_save` tool when
the lesson generalizes. `error` and `feature` stay in workspace
`.learnings/` because they are situational.

The `metadata.opensquilla.requires_tools = ["memory_save"]` declaration in
this skill's frontmatter ensures the loader only activates this skill when
the memory tools are available — guaranteeing the promotion path exists.
