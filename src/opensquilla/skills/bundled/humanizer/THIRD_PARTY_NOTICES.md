# Third-party notices for `humanizer` skill

Inspired by the `humanizer` skill on the ClawHub registry
(<https://clawhub.ai/humanizer>, MIT-0), which itself draws on Wikipedia's
WikiProject AI Cleanup "Signs of AI writing" guide. The OpenSquilla version
is independently authored: SKILL.md instructional text, the regex/heuristic
scanner, the rewriter substitution list, and the pattern taxonomy in
`references/` were rewritten from scratch to integrate with OpenSquilla's
two-stage scan/rewrite pipeline.

## Methodology source

The pattern taxonomy is informed by the publicly-edited Wikipedia article
"Wikipedia:Signs of AI writing"
(<https://en.wikipedia.org/wiki/Wikipedia:WikiProject_AI_Cleanup/Signs_of_AI_writing>).
That source is licensed CC BY-SA; only the high-level pattern names and
categories are reused, not verbatim text. The detection regexes and
substitution lists in this skill are original.

## Runtime dependencies

Pure Python, stdlib only.

## License

This skill, as part of OpenSquilla, is licensed under the project's MIT
license.
