# Third-party notices for `pdf-toolkit` skill

Inspired by the `pdf` skill on the ClawHub registry
(<https://clawhub.ai/pdf>, MIT-0). The OpenSquilla version is independently
authored: SKILL.md instructional text and helper scripts here were written
from the pypdf, pdfplumber, and reportlab documentation, not copied from the
upstream package.

## Runtime dependencies

This skill requires:

- `pypdf` (BSD-3-Clause license,
  <https://github.com/py-pdf/pypdf>) for structural reads and writes
- `pdfplumber` (MIT license, <https://github.com/jsvine/pdfplumber>) for
  text and table extraction (already in OpenSquilla default dependencies)
- `reportlab` (BSD-3-Clause license,
  <https://www.reportlab.com/>) for PDF generation

## Scope vs `nano-pdf`

This skill ships alongside the existing `nano-pdf` bundled skill but does
not replace it. `nano-pdf` wraps a natural-language LLM rewriter; this skill
wraps deterministic structural operations. Trigger words and descriptions
were chosen to keep the two from competing in skill retrieval.

## License

This skill, as part of OpenSquilla, is licensed under the project's MIT
license. The runtime dependencies carry their own permissive licenses
(BSD-3-Clause and MIT respectively).
