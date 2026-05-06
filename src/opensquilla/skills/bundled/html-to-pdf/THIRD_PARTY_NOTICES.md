# Third-party notices for `html-to-pdf` skill

Inspired by `generate-pdf` on the ClawHub registry
(<https://clawhub.ai/generate-pdf>, MIT-0). The OpenSquilla version is
independently authored: SKILL.md instructional text, the render script,
and the WeasyPrint reference were written from the WeasyPrint
documentation (<https://doc.courtbouillon.org/weasyprint/>) and the CSS
Paged Media specification, not copied from the upstream package.

## Runtime dependency

This skill requires `weasyprint` (BSD-3-Clause license,
<https://weasyprint.org/>). Because WeasyPrint pulls in native libraries
(Pango, Cairo, GDK-PixBuf, fontconfig), it ships in OpenSquilla's
`[document-extras]` optional-dependencies group rather than the default
install.

## License

This skill, as part of OpenSquilla, is licensed under the project's MIT
license. The WeasyPrint runtime carries its own BSD-3-Clause license.
