# Third-party notices for `multi-search-engine` skill

Inspired by `multi-search-engine` on the ClawHub registry
(<https://clawhub.ai/multi-search-engine>, MIT-0). The OpenSquilla version
is independently authored: SKILL.md instructional text, the search script,
and the engine selection guide were written for OpenSquilla's existing
`httpx` + `beautifulsoup4` stack and were not copied from the upstream
package.

## Runtime dependencies

Reuses `httpx` and `beautifulsoup4`, both in OpenSquilla default
dependencies. No additional packages needed.

## Engine API terms

Brave, Tavily, and SerpAPI each have their own terms of service. Users
must comply with those terms when using their respective API keys. The
HTML-scraping engines (DuckDuckGo, Bing, Baidu, Sogou, 360) are subject
to those sites' robots.txt and terms — the skill respects rate limiting
hints but does not enforce per-site policies.

## License

This skill, as part of OpenSquilla, is licensed under the project's MIT
license.
