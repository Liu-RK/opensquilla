# AI-writing patterns

A working taxonomy of patterns the scanner detects and the rewriter
either fixes or flags. Pure heuristics; expect false positives, especially
in formal genres where some patterns are appropriate.

## High-severity patterns (rewrite or flag)

### ai_vocab

A small set of words that are statistically over-represented in
LLM-generated English: `delve`, `tapestry`, `landscape`, `realm`,
`journey`, `embark`, `navigate`, `unleash`, `unlock`, `unveil`,
`pivotal`, `multifaceted`, `nuanced`, `seamless`, `robust`, `harness`,
`foster`, `paradigm`, `transformative`, `cutting-edge`, `state-of-the-art`.

Trivial substitutions (rewriter does these automatically):

| Stock phrase | Better |
|---|---|
| `delve into` | `look at`, `examine`, `study` |
| `harness the power of` | `use` |
| `unlock the potential of` | `use`, `enable` |
| `leverage` | `use` |
| `facilitate` | `help` |
| `cutting-edge` | `modern` |
| `state-of-the-art` | `current` |

Non-trivial substitutions (flagged for the LLM): replace metaphors that
require understanding the surrounding sentence — for example, `tapestry of
ideas` cannot be mechanically swapped for `set of ideas` without breaking
the cadence.

## Medium-severity patterns

### em_dash_overuse

Em-dashes (`—`) and double-hyphens (`--`) appearing more than ~1 per 50
words is an AI tell. The scanner flags paragraphs over the threshold; the
rewriter does not auto-fix because em-dashes are sometimes appropriate.

### inflated_symbolism

Stock metaphor patterns: `tapestry of ...`, `landscape of ...`, `journey
of ...`, `fabric of ...`, `odyssey of ...`. These almost always replace a
concrete noun with an abstract one for no reason. Flag for human review.

### vague_attribution

`many experts say`, `it is widely believed`, `studies have shown`,
`research has shown`, `experts agree`. These are placeholders for actual
citations. Either replace with a concrete citation or remove the claim.

### promotional

`cutting-edge`, `world-class`, `best-in-class`, `industry-leading`,
`groundbreaking`. Marketing language masquerading as analysis. The
rewriter handles a few; the rest are flagged for human judgment.

## Low-severity patterns

### rule_of_three

Three-item lists (`A, B, and C`) where the count is decorative rather
than meaningful. AI text leans on these heavily because they sound
balanced. The rewriter does not auto-fix; humans should ask whether two
or four items would convey the substance better.

### negative_parallelism

`Not just X, but Y` and its variants. Used reflexively in AI text to
inject false stakes. Flag for review; rewrite by dropping the `not just`
clause if the second half stands on its own.

### conjunctive_overuse

`Furthermore`, `Moreover`, `Additionally`, `Subsequently`, `Ultimately`,
`Consequently`. Three or more chained transitions across consecutive
paragraphs is a tell. AI text uses these as filler; human writers more
often start sentences with the actual point.

## Patterns deliberately not detected

- **Sentence rhythm**: detecting bad rhythm requires syntactic analysis
  the scanner does not attempt. Read aloud as a human review pass.
- **Paragraph length monotony**: AI text often produces paragraphs of
  near-identical length. Detection requires whole-document statistics;
  out of scope for a per-line scanner.
- **False precision**: e.g., "approximately 73% of users". A heuristic
  for "is this number suspiciously specific" is brittle; flag for
  human review separately.

## Severity assignment

`severity` reflects the strength of the AI signal, not the editing
priority. A `high`-severity match (AI vocab) is mechanically fixable; a
`low`-severity match (rule of three) often requires more thought. Sort by
severity for triage, but do not treat low-severity as "safe to ignore" —
several lows in a paragraph add up.

## Adding voice (post-cleanup)

After running this skill, the prose is cleaner but may now feel
voiceless. Counter-checklist:

- Does any sentence reveal an opinion or judgment?
- Is there at least one concrete detail per paragraph?
- Does the writer acknowledge uncertainty when it exists?
- Do sentence lengths vary?
- Is there one striking sentence the reader will remember?

If "no" to most: add voice. The skill won't do this for you.
