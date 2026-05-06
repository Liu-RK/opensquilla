<p align="center">
  <img src="assets/opensquilla-mark.png" alt="OpenSquilla logo" width="260">
</p>

<h1 align="center">OpenSquilla</h1>

<p align="center">
  Cross-platform Python agent runtime with a built-in gateway, Web UI, memory, tools, scheduling, and provider routing.
</p>

<p align="center">
  <strong>Python 3.12+</strong> · <strong>uv</strong> · <strong>OpenRouter-compatible LLMs</strong> · <strong>Brave/DuckDuckGo search</strong>
</p>

---

## Install

Clone with Git LFS enabled so bundled model assets are hydrated:

```sh
git lfs install
git clone https://github.com/Token-Rhythm/opensquilla.git
cd opensquilla
git lfs pull --include="src/opensquilla/contrib/squilla_router/models/**"
```

Install the full recommended local runtime:

```sh
uv sync --extra recommended
```

The `recommended` extra is enough for hybrid skill retrieval: it includes
`onnxruntime` and `transformers` (tokenizer only, no torch), which together
drive the bundled BGE INT8 ONNX export at
`src/opensquilla/contrib/squilla_router/models/v4.2_phase3_inference/bge_onnx/`.
The local SquillaRouter assets also include LightGBM, ONNX, and
scikit-learn/joblib training artifacts. Use assets shipped with a trusted
OpenSquilla release or assets whose checksums match
`src/opensquilla/contrib/squilla_router/models/v4.2_phase3_inference/artifact_manifest.json`;
do not replace `.pkl` or `.joblib` files from untrusted sources.

The `recommended` profile carries the local SquillaRouter runtime and assets.
Use the `core` profile when you want a smaller artifact without local router
model dependencies. Third-party notices live in `THIRD_PARTY_NOTICES.md`, and
router bundle provenance lives next to the model assets in `PROVENANCE.md`.

### Release Zips

OpenSquilla's first release channel is GitHub Release zip artifacts. Ordinary
users should download the portable zip; it bundles Python and starts from the
extracted folder:

```sh
python3.12 scripts/build_wheelhouse_zip.py --profile recommended --bundle-python-runtime
```

Advanced users who already manage Python 3.12 can use the smaller wheelhouse
zip instead:

```sh
python3.12 scripts/build_wheelhouse_zip.py --profile recommended
```

Release artifacts are published with per-file and aggregate checksums:

```text
OpenSquilla-<version>-<platform>-py312-recommended-portable.zip
OpenSquilla-<version>-<platform>-py312-recommended-portable.zip.sha256
OpenSquilla-<version>-<platform>-py312-recommended-wheelhouse.zip
OpenSquilla-<version>-<platform>-py312-recommended-wheelhouse.zip.sha256
SHA256SUMS
```

Portable users extract the zip and run:

```sh
bash start.sh
```

On Windows PowerShell:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\start.ps1
```

The command flow is consistent across platforms, and the portable zip bundles a
Python runtime. Release zips are still platform-specific because they include
native dependency wheels and a platform-specific Python runtime.

To publish a GitHub Release, push a version tag such as `v0.1.0` that matches
the version in `pyproject.toml`. The `Wheelhouse Zip Release` workflow then
builds Windows x64, macOS arm64, and Linux x64 artifacts with the same script
used locally, producing both portable and wheelhouse zips in the same run and
uploading them to a draft GitHub Release.

Maintainers can also run the `Wheelhouse Zip Release` workflow from the Actions
tab. Leave `tag` empty to create workflow artifacts only, or set `tag` to an
existing version tag to upload the artifacts to that draft GitHub Release.

Inputs:

- `profile`: `recommended` for the full runtime, or `core` for a smaller build.
- `python_runtime_release`: pinned python-build-standalone release, currently `20260414`.
- `python_runtime_version`: bundled CPython version, currently `3.12.13`.
- `tag`: optional existing git tag for manual runs. Leave empty to create workflow artifacts only.

For tag pushes and manual runs with `tag` set, the workflow uploads
`dist/*.zip`, `dist/*.zip.sha256`, and `dist/SHA256SUMS` to a draft GitHub
Release for that tag. The GitHub Release and Actions artifact hosting are
GitHub features; zip build, naming, checksum, manifest, runtime bundling, and
upload behavior are defined by this repository's script and workflow.

## Configure

OpenSquilla's normal user-level config file is:

```text
~/.opensquilla/config.toml
```

On Windows, that is usually:

```text
C:\Users\<you>\.opensquilla\config.toml
```

Minimal config:

```toml
search_provider = "brave"
search_api_key = "your-brave-key"

[llm]
provider = "openrouter"
model = "deepseek/deepseek-v4-flash"
api_key = "<your-openrouter-api-key>"
base_url = "https://openrouter.ai/api/v1"

[sandbox]
sandbox = true
security_grading = true
backend = "auto"

[squilla_router]
enabled = true
strategy = "v4_phase3"
rollout_phase = "full"
default_tier = "t1"
confidence_threshold = 0.5

[image_generation]
# Image generation is a separate agent capability. Keep this false unless you
# want the agent to receive the image_generate tool.
enabled = true
# Use "openai/gpt-image-1", "openrouter/google/gemini-3.1-flash-image-preview",
# or another provider/model supported by your configured image provider.
primary = "openrouter/google/gemini-3.1-flash-image-preview"

[image_generation.providers.openrouter]
# Optional when [llm].provider is "openrouter" and [llm].api_key is set, or
# OPENROUTER_API_KEY is present. Provider-specific image keys still win.
api_key = ""
base_url = "https://openrouter.ai/api/v1"
```

Image generation can also be configured from the WebUI setup page. If the
selected LLM provider is also an image provider, the image tool can reuse that
provider's API key unless a provider-specific image key is configured. Reusing
the key does not enable the capability by itself; `[image_generation].enabled`
or the WebUI image-provider toggle must be on before agents receive image
tools.

Run `opensquilla onboard` to write this file interactively. You can also set
secrets with environment variables instead of storing them in TOML.

PowerShell:

```powershell
setx OPENROUTER_API_KEY "<your-openrouter-api-key>"
setx BRAVE_SEARCH_API_KEY "your-brave-key"
```

macOS/Linux:

```sh
export OPENROUTER_API_KEY="<your-openrouter-api-key>"
export BRAVE_SEARCH_API_KEY="your-brave-key"
```

### LLM Provider Support

OpenRouter remains the default and best-tested route. The providers below are
covered by local mocked-contract tests only unless marked native; that means
request construction, payload shape, usage parsing, and failure classification
are verified without live vendor credentials. They are not live-verified.

| Provider | Config `provider` | Support Level | API Key Env | Default Base URL |
| --- | --- | --- | --- | --- |
| OpenRouter | `openrouter` | `compat_mock_verified` | `OPENROUTER_API_KEY` | `https://openrouter.ai/api/v1` |
| OpenAI | `openai` | `compat_mock_verified` | `OPENAI_API_KEY` | `https://api.openai.com/v1` |
| Anthropic | `anthropic` | `native` | `ANTHROPIC_API_KEY` | `https://api.anthropic.com` |
| Ollama | `ollama` | `native` | none | `http://localhost:11434` |
| DeepSeek | `deepseek` | `compat_mock_verified` | `DEEPSEEK_API_KEY` | `https://api.deepseek.com` |
| Gemini OpenAI-compatible | `gemini` | `compat_mock_verified` | `GEMINI_API_KEY` | `https://generativelanguage.googleapis.com/v1beta/openai` |
| DashScope/Qwen | `dashscope` | `compat_mock_verified` | `DASHSCOPE_API_KEY` | `https://dashscope.aliyuncs.com/compatible-mode/v1` |
| Bailian Coding | `bailian_coding` | `compat_configured` | `BAILIAN_API_KEY` | `https://coding-intl.dashscope.aliyuncs.com/v1` |
| Moonshot/Kimi | `moonshot` | `compat_mock_verified` | `MOONSHOT_API_KEY` | `https://api.moonshot.ai/v1` |
| Mistral | `mistral` | `compat_mock_verified` | `MISTRAL_API_KEY` | `https://api.mistral.ai/v1` |
| Groq | `groq` | `compat_mock_verified` | `GROQ_API_KEY` | `https://api.groq.com/openai/v1` |
| Zhipu/Z.AI | `zhipu` | `compat_mock_verified` | `ZAI_API_KEY` | `https://open.bigmodel.cn/api/paas/v4` |
| SiliconFlow | `siliconflow` | `compat_mock_verified` | `SILICONFLOW_API_KEY` | `https://api.siliconflow.cn/v1` |
| Volcengine Ark | `volcengine` | `compat_mock_verified` | `VOLCENGINE_API_KEY` | `https://ark.cn-beijing.volces.com/api/v3` |
| BytePlus ModelArk | `byteplus` | `compat_mock_verified` | `BYTEPLUS_API_KEY` | `https://ark.ap-southeast.bytepluses.com/api/v3` |
| vLLM | `vllm` | `compat_mock_verified` | none | explicit `base_url` required |
| LM Studio | `lm_studio` | `compat_mock_verified` | none | `http://localhost:1234/v1` |
| OVMS | `ovms` | `compat_mock_verified` | none | `http://localhost:8000/v3` |
| Qianfan | `qianfan` | `compat_configured` | `QIANFAN_API_KEY` | `https://qianfan.baidubce.com/v2` |
| AIHubMix | `aihubmix` | `compat_configured` | `AIHUBMIX_API_KEY` | `https://aihubmix.com/v1` |
| MiniMax | `minimax` | `compat_configured` | `MINIMAX_API_KEY` | `https://api.minimaxi.com/anthropic` |
| MiniMax OpenAI-compatible | `minimax_openai` | `compat_configured` | `MINIMAX_API_KEY` | `https://api.minimaxi.com/v1` |
| MiniMax Mainland | `minimax_cn` | `compat_configured` | `MINIMAX_CN_API_KEY` | `https://api.minimaxi.com/anthropic` |
| MiniMax Global | `minimax_global` | `compat_configured` | `MINIMAX_API_KEY` | `https://api.minimax.io/anthropic` |
| Azure OpenAI | `azure` | `unsupported_for_A` | provider-specific | explicit Azure design required |

Compatibility-mode providers vary by model. Tool calling, vision, reasoning,
prompt caching, model listing, and usage accounting should be treated as
provider/model-specific until live smoke tests prove the exact deployment.

Use `opensquilla config get squilla_router` to see all current tier settings.
Set `squilla_router.require_router_runtime = true` to fail fast if the bundled
v4 runtime cannot be initialized.

### Provider tier profiles

By default, Squilla Router keeps the OpenRouter tier table. To select a
provider-specific tier ladder, set `squilla_router.tier_profile` and make
`llm.provider` match the same provider:

```toml
[llm]
provider = "gemini"
model = "gemini-2.5-flash"

[squilla_router]
tier_profile = "gemini"
```

The router does not switch providers at runtime. A mismatched profile/provider
configuration fails during config validation. Leave `tier_profile` unset to
preserve legacy OpenRouter behavior. Provider-profile cost values are
OpenSquilla estimates derived from token usage; they are not provider billing
statements.

Config load order:

```text
1. OPENSQUILLA_GATEWAY_CONFIG_PATH
2. ./opensquilla.toml
3. ~/.opensquilla/config.toml
4. built-in defaults
```

## Concurrency Tuning

OpenSquilla uses two independent concurrency limits that can be set via environment variables:

| Environment Variable | Default | Description |
|---|---|---|
| `OPENSQUILLA_TASK_MAX_CONCURRENCY` | `4` | Max simultaneous tasks in `task_runtime` (controls the global semaphore in `task_runtime.py`) |
| `OPENSQUILLA_CHANNEL_INFLIGHT_CAP` | `8` | Max simultaneous in-flight channel adapter messages |

Invalid (non-integer) values fall back to the default and emit a `WARNING` log line.

### Sizing Formula

```
max_concurrency = min(memory_gb × 4, llm_api_rpm / 60)
```

Pick the smaller of your memory headroom and your LLM API rate limit to avoid OOM spikes and 429 errors simultaneously.

### Deployment Examples

**Local (laptop, free-tier API)**

```sh
# defaults — no env override needed
# memory: ~2 GB free → 2×4 = 8; API RPM: 20 → 20/60 ≈ 0 (capped at 1 by Field ge=1)
# practical: leave OPENSQUILLA_TASK_MAX_CONCURRENCY at default 4
OPENSQUILLA_TASK_MAX_CONCURRENCY=4
OPENSQUILLA_CHANNEL_INFLIGHT_CAP=8
```

**Production (8 GB RAM, 600 RPM API)**

```sh
# min(8×4=32, 600/60=10) = 10
OPENSQUILLA_TASK_MAX_CONCURRENCY=10
OPENSQUILLA_CHANNEL_INFLIGHT_CAP=16
```

**Constrained (2 GB VPS, 60 RPM API)**

```sh
# min(2×4=8, 60/60=1) = 1
OPENSQUILLA_TASK_MAX_CONCURRENCY=1
OPENSQUILLA_CHANNEL_INFLIGHT_CAP=2
```

## Run

Start the gateway:

```sh
uv run opensquilla gateway run
```

Use a custom port:

```sh
uv run opensquilla gateway run --port 18791
```

Open the Web UI:

```text
http://127.0.0.1:18790/control/
```

Interactive chat can analyze large local files without uploading bytes:

```text
/path <path> [prompt]
```

`/path` sends the path string and tool-use hints in the chat prompt with no
attachments; file bytes stay local and are read by filesystem tools on the same
machine. Because the path string is prompt text, it may be stored in the
conversation transcript. Remote gateways should use `/file <path> [prompt]`
when the file must be uploaded from the CLI machine. Standalone chat also
supports `--workspace <dir>` and `--workspace-strict` to constrain read-side
filesystem tools.

Verify:

```sh
curl http://127.0.0.1:18790/health
curl http://127.0.0.1:18790/ready
```

Expected:

```json
{"ok":true,"status":"live"}
```

## Testing

See [Testing](docs/testing.md) for the full public and maintainer-only test boundary.

Install development dependencies:

```sh
uv sync --extra dev --extra recommended
```

Run the default offline test suite:

```sh
uv run pytest tests -q
```

Run lint:

```sh
uv run ruff check src tests
```

The default suite is designed to avoid network calls and paid provider access.
Live and browser tests are opt-in:

```powershell
$env:OPENSQUILLA_WEBUI_BROWSER_E2E="1"; uv run pytest tests/functional/test_webui_browser_e2e.py -q -s
$env:OPENSQUILLA_WEBUI_BROWSER_CHAT_E2E="1"; uv run pytest tests/functional/test_webui_browser_chat_e2e.py -q -s
$env:OPENROUTER_API_KEY="<set locally>"; uv run pytest tests/functional/test_llm_smoke.py -q -s
$env:OPENSQUILLA_GATEWAY_LLM_E2E="1"; $env:OPENROUTER_API_KEY="<set locally>"; uv run pytest tests/functional/test_gateway_llm_e2e.py -q -s
```

The default GitHub CI runs on pull requests and pushes to `main`. It uses an
isolated test state directory and does not require provider credentials.
Maintainer-only live release checks are grouped in the manual
`Live Release E2E` workflow. The Telegram channel smoke additionally requires
`OPENSQUILLA_LIVE_TELEGRAM_BOT_TOKEN` and `OPENSQUILLA_LIVE_TELEGRAM_CHAT_ID`
secrets, and the workflow input must explicitly enable the real message send.

Release golden prompts are split into a public static suite and a maintainer
live runner:

```sh
uv run pytest tests/test_public_release_hygiene.py tests/test_public_tool_surface.py tests/test_public_release_golden_static.py -q
uv run python scripts/run_public_release_golden_prompts.py
```

The live runner expects a local gateway with a configured provider and writes
its report under `tests/functional/reports/`, which is ignored by git.

## Memory

OpenSquilla's memory lifecycle keeps user-authored memory files, derived
search state, and session transcripts separate, and flushes non-empty
transcripts before reset or compact operations.

The release memory scope is intentionally single-path: durable Markdown
memory, hybrid FTS/vector retrieval, bounded recall, session flush, and
opt-in Dream consolidation.

## Agents

Durable agents are stored in the same gateway config used by the CLI, RPC
gateway, channels, task runtime, memory, and Web UI. Manage them with:

```sh
uv run opensquilla agents list --json
uv run opensquilla agents add ops --model openai/gpt-5.1 --json
uv run opensquilla agents delete ops --force --json
```

`agents add` writes an `agents = [...]` entry to the config. Agent defaults are
used when a turn does not pass an explicit model; precedence is explicit CLI or
session model, then the agent's configured model, then the global `[llm]` model.
Agent workspaces default to `~/.opensquilla/workspace/agents/<id>` unless the
agent entry has its own `workspace`.

Restart a running gateway after `agents add` or `agents delete` so boot-time
memory, workspace, and channel routing state can pick up the new registry.

## Observability: Core Metrics

OpenSquilla emits four core metrics as structured log lines (via `structlog`).
No Prometheus endpoint is provided; metrics are extracted from log output.

**Counter names are locked** — do not rename without updating this section and
the corresponding CI grep check.

| Metric name | Kind | Description |
|---|---|---|
| `opensquilla_queue_depth` | gauge | Pending queue depth for a session after each enqueue. Emitted every time a task is added; value is the current depth. |
| `in_flight_turns_total` | counter | Cumulative turns that have acquired a concurrency slot and entered execution. Increments by 1 per turn; never decrements. |
| `turn_cancellations_total` | counter | Cumulative cancellations. Includes `reason` label: `interrupt` (asyncio cancel mid-run), `user_cancel` (cancelled before start), `timeout` (TimeoutError). |
| `queue_full_errors_total` | counter | Cumulative `TaskQueueFullError` raises. Emitted immediately before the error is raised. |

**Log format** (structlog key=value rendering):

```
event='opensquilla_queue_depth' metric='opensquilla_queue_depth' value=1 session_key='agent-1::sess-abc'
event='in_flight_turns_total' metric='in_flight_turns_total' value=1 session_key='agent-1::sess-abc'
event='turn_cancellations_total' metric='turn_cancellations_total' value=1 reason='interrupt' session_key='agent-1::sess-abc'
event='queue_full_errors_total' metric='queue_full_errors_total' value=1 session_key='agent-1::sess-abc'
```

**Extracting metrics from logs:**

PowerShell:
```powershell
Get-Content opensquilla.log | Select-String "metric='opensquilla_queue_depth'"
Get-Content opensquilla.log | Select-String "metric='in_flight_turns_total'"
Get-Content opensquilla.log | Select-String "metric='turn_cancellations_total'"
Get-Content opensquilla.log | Select-String "metric='queue_full_errors_total'"
```

bash:
```bash
grep "metric='opensquilla_queue_depth'" opensquilla.log
grep "metric='in_flight_turns_total'" opensquilla.log
grep "metric='turn_cancellations_total'" opensquilla.log
grep "metric='queue_full_errors_total'" opensquilla.log
```

## Credits

OpenSquilla is inspired by OpenClaw's architecture and lifecycle ideas. The
non-skill runtime implementation, docs, tests, and configuration are
OpenSquilla-authored work.

Bundled skill descriptor provenance is documented in `THIRD_PARTY_NOTICES.md`;
OpenClaw-derived and OpenSquilla-original skills are listed there.
