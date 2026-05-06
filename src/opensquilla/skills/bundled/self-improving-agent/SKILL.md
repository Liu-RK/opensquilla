---
name: self-improving-agent
description: "Capture lessons, errors, and corrections in a workspace `.learnings/` directory so future iterations avoid past mistakes. Trigger when: (1) a command or operation fails unexpectedly, (2) the user corrects you (`No, that's wrong`, `Actually...`), (3) the user requests a capability that does not exist, (4) an external API or tool fails, (5) you discover a better approach for a recurring task. This is a learn/reflect/improve loop, distinct from the `memory` skill which manages passive remember/recall/forget operations on durable storage. The two coexist: this skill writes outcome-driven post-mortems; the memory skill stores arbitrary facts and recalls them later."
homepage: ""
provenance:
  origin: clawhub-mit0
  license: MIT-0
  upstream_url: https://clawhub.ai/self-improving-agent
  maintained_by: OpenSquilla
metadata:
  {
    "opensquilla":
      {
        "emoji": "🪞",
        "requires_tools": ["memory_save"],
      },
  }
---

# self-improving-agent

A learning-loop skill. After failures, corrections, or insights, write a
short post-mortem entry to a workspace `.learnings/` directory. The next
agent run can read those files and avoid the same mistake.

## When to log

| Situation | Target file |
|---|---|
| Command or operation fails unexpectedly | `.learnings/ERRORS.md` |
| User corrects you | `.learnings/LEARNINGS.md` (category: `correction`) |
| User requests a capability that does not exist | `.learnings/FEATURE_REQUESTS.md` |
| External API/tool fails | `.learnings/ERRORS.md` (with integration details) |
| You realize knowledge is outdated | `.learnings/LEARNINGS.md` (category: `knowledge_gap`) |
| You discover a better approach | `.learnings/LEARNINGS.md` (category: `best_practice`) |

## What NOT to log

- Secrets, tokens, private keys, environment variable values
- Full source files or full configuration files
- Long transcripts or raw command output dumps
- Anything the user has not consented to record

Prefer short, redacted summaries over verbatim excerpts. If a credential
appears in an error message, replace it with `<REDACTED>` before logging.

## First-use init

Before logging anything, ensure `.learnings/` exists in the workspace root:

```bash
python {baseDir}/scripts/init_learnings.py [--root .]
```

The script is idempotent: it creates `.learnings/`, `LEARNINGS.md`,
`ERRORS.md`, and `FEATURE_REQUESTS.md` only when missing. Existing files
are never overwritten.

## Logging an entry

```bash
python {baseDir}/scripts/log_lesson.py \
    --category correction \
    --text "I assumed X, but the user pointed out Y. Going forward, prefer Y because Z."
```

Categories on the `--category` flag:

- `correction` — user disagreed with an action; explicit redirect
- `error` — command/integration failed
- `feature` — capability gap the user wants filled
- `knowledge_gap` — discovered training-data is stale or wrong
- `best_practice` — found a better approach worth keeping

The script writes the entry with a UTC ISO timestamp. Files use plain
markdown so they are readable by humans and grep-able by future agents.

## Reading lessons before major tasks

Before starting a sizeable task, scan `.learnings/`:

```bash
cat .learnings/LEARNINGS.md   # check for relevant priors
cat .learnings/ERRORS.md      # check for known integration failures
```

The OpenSquilla `memory` skill exposes `memory_save` and `memory_search`
tools. When `memory_save` is available, also use it to persist
broadly-applicable lessons across sessions, not just the workspace —
`.learnings/` is workspace-local; `memory_save` can promote a lesson to
durable cross-session storage.

## Promotion criteria

A `.learnings/` entry deserves promotion to durable memory (via
`memory_save`) when:

- The lesson applies beyond this workspace (general technique, not
  project-specific code path)
- The mistake is plausible to repeat next session
- The fix is not obvious from the source code or docs alone

Workspace-local lessons stay in `.learnings/`. Cross-cutting lessons get
promoted via `memory_save`.

## Boundary with `memory` skill

| skill | role | trigger words |
|---|---|---|
| `memory` (already bundled) | Passive store: remember, recall, forget, search, update | "remember that...", "what did I save about X", "forget X" |
| `self-improving-agent` (this skill) | Active learning loop: errors, corrections, post-mortems | "that didn't work", "user corrected me", "I should have known", "next time" |

Trigger-word sets are intentionally disjoint. If a request fits both, the
host should pick `memory` for storage tasks and this skill for "what should
I learn from this" reflection.

## Boundaries

- This skill writes markdown files. It does not propose code fixes.
- It does not run tests or replicate the failure — that is the host's job.
- The `.learnings/` directory is intentionally workspace-local. For
  cross-workspace knowledge, promote to `memory_save`.
- Do not overwrite existing entries; always append. The history of past
  lessons matters as much as the current one.
