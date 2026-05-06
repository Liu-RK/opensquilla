---
name: humanizer
description: "Detect and rewrite signs of AI-generated text — em-dash overuse, inflated symbolism, vague attributions, rule-of-three lists, formulaic '-ing analyses', superficial conjunctive phrases, and generic AI-tell vocabulary. Trigger when editing or reviewing prose, especially after an LLM drafted it: emails, blog posts, PR descriptions, marketing copy, documentation. Two-step pipeline: `scan.py` enumerates pattern matches as JSON; `rewrite.py` applies trivial substitutions and outputs a rewrite plan for the host LLM to handle non-trivial cases. Pure regex/heuristic, no LLM calls inside the scripts."
homepage: ""
provenance:
  origin: clawhub-mit0
  license: MIT-0
  upstream_url: https://clawhub.ai/humanizer
  maintained_by: OpenSquilla
metadata:
  {
    "platform":
      {
        "emoji": "✍️",
      },
  }
---

# humanizer

Identify the patterns that mark text as AI-generated and rewrite or flag
them. The skill ships a regex/heuristic scanner and a deterministic
rewriter; non-trivial rewrites are escalated to the host LLM with explicit
guidance.

## When to use

- Polishing an LLM-drafted email, post, or memo before sending
- Editing AI-generated documentation that "reads off"
- Pre-publish review on a blog post, marketing copy, or release notes
- Code-review a PR description that sounds AI-generated

## When NOT to use

- Translating between languages (different rules apply)
- Editing technical specs where formality is appropriate
- Editing dialog or quoted material — preserve the source voice
- Editing creative fiction — many "AI tells" are also legitimate stylistic
  choices in fiction

## Pipeline

```
input.md → scan.py → patterns.json → rewrite.py → output.md (+ todo plan)
```

## Stage 1: Scan

```bash
python {baseDir}/scripts/scan.py --in draft.md --json > patterns.json
```

Output:

```json
{
  "matches": [
    {"pattern": "em_dash_overuse", "line": 3, "snippet": "...", "severity": "medium"},
    {"pattern": "rule_of_three", "line": 12, "snippet": "...", "severity": "low"},
    {"pattern": "ai_vocab", "line": 18, "snippet": "...", "severity": "high",
     "matched_terms": ["delve", "tapestry"]}
  ],
  "summary": {
    "total": 5,
    "by_severity": {"high": 1, "medium": 2, "low": 2}
  }
}
```

## Stage 2: Rewrite

```bash
python {baseDir}/scripts/rewrite.py --in draft.md --report patterns.json --out clean.md
```

The rewriter:

1. Applies trivial substitutions (e.g., `delve into` → `look at`,
   ` — ` em-dash → ` — ` only where not narratively justified).
2. Outputs a "manual review" stub for high-severity patterns the rewriter
   cannot mechanically fix (e.g., a rule-of-three list demanding
   reorganization, a vague attribution requiring concrete evidence).
3. Writes a TODO comment block at the bottom of the output file listing
   each unhandled pattern with line numbers, so the host LLM can finish
   the work in a focused pass.

## What it catches

See [references/ai_patterns.md](references/ai_patterns.md) for the full
24-pattern taxonomy. Common categories:

- **Em-dash overuse**: more than one em-dash per ~150 words
- **AI vocabulary**: `delve`, `tapestry`, `landscape`, `realm`, `journey`,
  `embark`, `navigate`, `unleash`, `unlock`, `unveil`, `pivotal`,
  `multifaceted`, `nuanced`, `crucial role`, `seamless`, `robust`
- **Rule of three**: triplet lists with no semantic reason for the count
- **Inflated symbolism**: stock comparisons (`tapestry of...`,
  `landscape of...`)
- **Vague attribution**: `many experts say`, `it is widely believed`
- **Promotional language**: `cutting-edge`, `state-of-the-art`,
  `revolutionary`
- **Superficial -ing analyses**: `revealing`, `highlighting`, `showcasing`
  without subject
- **Negative parallelism**: "not just X, but Y" used reflexively
- **Excessive conjunctive phrases**: `furthermore`, `moreover`,
  `additionally` chained

## Adding voice

The skill flags AI tells; it does **not** add personality. After cleaning,
the human (or the host LLM with explicit instruction) should:

- Add an opinion where the original was neutral
- Acknowledge uncertainty or mixed feelings instead of the false confidence
  AI text tends to have
- Use one striking concrete detail over three abstract ones
- Vary sentence length

A clean-but-soulless draft is just as obvious as an AI-tell-laden one.

## Boundaries

- Pure regex/heuristic. No semantic understanding. False positives are
  expected; reviewers should accept or reject each match.
- Fiction and dialog: skip this skill or scope to specific paragraphs.
- Languages other than English: patterns are English-tuned. Translation
  artifacts in other languages need a different rulebook.
- Whole-document restructuring (paragraph order, headings) is out of
  scope. The skill operates within paragraphs.
