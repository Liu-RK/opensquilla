# Third-party notices for `website-builder` skill

Inspired by the `website` skill on the ClawHub registry
(<https://clawhub.ai/website>, MIT-0). The OpenSquilla version is
independently authored: SKILL.md instructional text, the generator and
preview scripts, and the SEO reference document were written for
OpenSquilla's existing Jinja2 dependency and the standard Python
http.server interface, not copied from the upstream package.

## Runtime dependencies

Reuses `jinja2` (already in OpenSquilla default dependencies, BSD-3-Clause
license, <https://github.com/pallets/jinja>). The preview script invokes
the standard library's `http.server` via subprocess; no other
dependencies required.

## License

This skill, as part of OpenSquilla, is licensed under the project's MIT
license.
