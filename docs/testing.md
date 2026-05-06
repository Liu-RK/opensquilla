# Testing

OpenSquilla uses layered tests so public contributors get a stable default suite while maintainers can still run live release checks.

## Public Default Gate

Run this gate for ordinary pull requests:

```powershell
uv run ruff check src tests
uv run pytest -q
uv build --wheel
```

The default suite must remain offline, deterministic, credential-free, and safe for forks. It must not require provider keys, channel accounts, private prompts, local transcripts, or network access.

## Opt-In Live Gates

Browser and live provider tests are explicit maintainer checks:

```powershell
$env:OPENSQUILLA_WEBUI_BROWSER_E2E="1"; uv run pytest tests/functional/test_webui_browser_e2e.py -q -s
$env:OPENSQUILLA_WEBUI_BROWSER_CHAT_E2E="1"; uv run pytest tests/functional/test_webui_browser_chat_e2e.py -q -s
$env:OPENROUTER_API_KEY="<set locally>"; uv run pytest tests/functional/test_llm_smoke.py -q -s
$env:OPENSQUILLA_GATEWAY_LLM_E2E="1"; $env:OPENROUTER_API_KEY="<set locally>"; uv run pytest tests/functional/test_gateway_llm_e2e.py -q -s
```

The GitHub `Live Release E2E` workflow runs the maintainer release gate with repository secrets. The Telegram channel smoke sends a real message only when the workflow input explicitly enables it.

## Private Test Boundary

Private release tests may use local fixtures, historical leak markers, real prompts, real logs, or account-specific channel identifiers. Those materials must not be committed.

Allowed private locations:

```text
tests/_private/
.omx/private-golden/
```

These paths are ignored by git and excluded from default pytest collection. Public tests may assert that the private boundary exists, but they must not embed private prompt text, real credentials, historical artifact names, local machine paths, or AI session records.
