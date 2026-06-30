# Token, Owner, Sandbox Auto-Setup Design

Date: 2026-06-30

## Summary

OpenSquilla should make sandboxed use the default low-friction path for remote
users while preserving owner-only full host access. The gateway will derive the
initial run mode from the current principal:

- Owner users start in Full Host Access when they have no saved preference.
- Token-authenticated non-owner users start in Trusted-Sandbox.
- No-token non-owner users also start in Trusted-Sandbox.

The mode choice is still enforced by the backend. The UI only reflects the
policy; it must not be the source of authority.

Sandbox setup should also stop depending on the first WebUI visit. The gateway
will attempt sandbox setup automatically by default. On Linux and macOS this is
currently a ready/no-op path. On Windows it may perform host-level setup and can
require administrator rights, so failures must be reported clearly and only the
owner can retry setup from the UI.

This design follows Codex's product model: sandboxing is the technical boundary,
approval is the boundary-crossing decision, and routine work inside the sandbox
should continue without repeated prompts.

## Definitions

`owner` means the gateway principal with local owner authority. In the current
gateway, token authentication alone does not imply owner; owner is reserved for
the local loopback owner case.

`token user` means a request authenticated with a configured access token but
not marked as owner.

`no-token user` means a remote or unauthenticated principal when the gateway is
running in no-auth mode. This principal can still be allowed to operate within
the sandbox, but it must not receive full host access.

`Trusted-Sandbox` means the sandbox remains enabled while common low-risk
workspace and public-network actions are expected to proceed with minimal
approval friction.

`Full Host Access` means the sandbox boundary is disabled for the session's
commands and file operations. It remains owner-only.

`sandbox setup` means preparing host capabilities needed by the sandbox backend.
On Linux and macOS this currently returns ready without mutation. On Windows it
may create or repair the Windows sandbox marker, offline user, filesystem and
network boundary, and managed-proxy allowlist.

## Goals

- Let token and no-token non-owner users use Standard-Sandbox and
  Trusted-Sandbox.
- Keep Full Host Access owner-only in both frontend and backend.
- Choose the initial run mode from the current principal when no saved user
  choice exists.
- Make sandbox setup automatic by default, so normal deployments do not require
  the first user to click Establish sandbox.
- Keep Windows host-level setup guarded by owner/admin authority when automatic
  setup cannot complete.
- Keep Trusted-Sandbox low-friction by auto-allowing routine session-scoped
  sandbox grants.
- Keep persistent, global, or host-widening grants owner-only.
- Provide localized UI messaging when Full Host Access is unavailable or setup
  requires an owner/admin.

## Non-Goals

- Do not let token authentication imply owner.
- Do not allow non-owner users to select Full Host Access.
- Do not reintroduce `host_once` approvals.
- Do not move approval decisions back into individual tool implementations.
- Do not silently fall back from a requested sandbox mode to Full Host Access.
- Do not require remote non-owner users to perform host-level sandbox setup.
- Do not solve every Windows multi-instance proxy limitation in this change;
  the initial change should avoid making it worse and should expose clear
  diagnostics.

## Current Behavior

The gateway currently exposes `sandbox.setup.status` and `sandbox.setup.ensure`.
The ensure path is owner-guarded. The WebUI shows an Establish sandbox prompt
when setup is not ready.

Gateway boot intentionally does not run setup. The existing boot helper returns
without calling the setup routine, and tests assert that boot does not prepare
the sandbox.

Linux and macOS setup currently returns ready without mutation. Windows setup is
the meaningful host mutation path. It writes a marker under the current user's
OpenSquilla home, prepares the Windows default sandbox network boundary, and
may launch an elevated helper when the current process is not admin.

The current frontend defaults to Full Host Access in several places, and it
does not receive enough principal information to disable Full Host Access for
non-owner users.

## Desired Behavior

### Initial Run Mode

The backend returns a principal-aware run-mode policy in the bootstrap payload:

```text
isOwner
authenticated
allowedRunModes
defaultRunMode
sandboxSetupStatus
```

When no explicit saved preference exists:

```text
owner -> full
token non-owner -> trusted
no-token non-owner -> trusted
```

If a saved preference exists, it may be reused only when it is still allowed for
the current principal. If the saved value is not allowed, the frontend and
backend both normalize it to the principal's default mode.

Allowed modes:

```text
owner -> standard, trusted, full
non-owner -> standard, trusted
```

The backend must reject any non-owner attempt to set or use Full Host Access,
even if a stale frontend or direct RPC request sends it.

### Automatic Sandbox Setup

Add a sandbox auto-setup policy with this effective default:

```text
sandbox.auto_setup = true
```

On gateway startup, if auto setup is enabled, the gateway starts a background
setup task. This task must be idempotent:

- If setup is already ready, it returns ready.
- If the platform setup is a no-op, it returns ready.
- If setup needs admin authority and the process cannot complete it, it records
  a failed or not-ready status with a clear message.
- It must not block the gateway from serving the UI.

The UI should therefore usually see either ready or preparing. Only exceptional
cases, mainly native Windows without completed elevated setup, should show a
manual owner/admin action.

### Windows Setup

Windows automatic setup should try the existing setup routine. If the process
has enough authority, setup can complete during gateway startup. If not, the
gateway records that elevated setup is required.

Only owner users see a retry or Establish sandbox action. Non-owner users see a
read-only message explaining that the owner/admin must prepare the sandbox.

For packaged desktop builds, the installer or first local owner launch should
run the same setup routine. The remote WebUI should not become the primary way
to perform host-level Windows setup.

### Multi-Instance Server Deployment

For multiple OpenSquilla gateways on one server, each instance should use its
own config, state, and workspace roots. The public WebUI/API port is separate
from the sandbox managed-proxy port.

Current Windows managed networking uses a fixed internal proxy allowlist port.
That is acceptable for a first compatibility pass only if setup remains
diagnostic and fail-closed. A later Windows multi-instance improvement should
either provide a shared managed proxy service or make the internal proxy ports
instance-aware and update the Windows marker accordingly.

## Approval Policy

The unified sandbox approval layer remains the only place that grants or denies
sandbox boundary changes.

Trusted-Sandbox should automatically approve routine session-scoped grants when
the request is low risk and remains inside the sandbox design. Examples include
ordinary workspace file access and public network access through the managed
network path.

Owner-only approvals:

- Full Host Access.
- Persistent grants that affect future sessions.
- Global or workspace-wide grants that materially widen the boundary.
- Host-level setup or repair operations.
- Sensitive path access.
- Any destructive or security-weakening action that the existing unified
  approval policy classifies as owner-only.

Non-owner users may reject approvals they are shown, but they cannot approve
owner-only grants.

## UI Behavior

The run-mode selector should use the backend policy payload.

For owner:

- Standard-Sandbox enabled.
- Trusted-Sandbox enabled.
- Full Host Access enabled.
- Initial default is Full Host Access unless the owner has a valid saved
  preference.

For token and no-token non-owner:

- Standard-Sandbox enabled.
- Trusted-Sandbox enabled.
- Full Host Access disabled.
- Initial default is Trusted-Sandbox unless the user has a valid saved
  Standard-Sandbox or Trusted-Sandbox preference.

Localized hint when Full Host Access is disabled:

```text
zh: 当前账号不是 owner，不能选择 Full Host Access。你可以使用 Standard-Sandbox 或 Trusted-Sandbox。
en: This account is not the owner, so Full Host Access is unavailable. You can use Standard-Sandbox or Trusted-Sandbox.
```

Sandbox setup status:

- `ready`: no setup prompt.
- `setting_up`: show a passive preparing state.
- `not_setup` or `failed` for owner: show a setup/retry action.
- `not_setup` or `failed` for non-owner: show a read-only owner/admin required
  message.
- `unavailable`: show a clear unavailable state and prevent starting sandboxed
  modes that cannot run.

## Data Flow

Startup:

```text
load config
build services
start background sandbox auto-setup task if enabled
serve gateway
```

Bootstrap:

```text
request principal
compute allowed run modes
compute default run mode
read setup status
return policy payload to UI
```

Run-mode set:

```text
request principal
validate requested mode against allowed modes
for standard/trusted, require sandbox setup ready or return SANDBOX_SETUP_REQUIRED
for full, require owner
persist or apply session run context
```

Approval resolution:

```text
request principal
load pending approval
if approval widens owner-only boundary, require owner
if approval is routine trusted sandbox session grant, allow authenticated or no-token operator according to operator scopes
record decision
```

## Error Handling

Auto setup failures must not crash the gateway. They should be observable in
setup status, logs, and UI messages.

If sandbox setup is required for Standard-Sandbox or Trusted-Sandbox and is not
ready, the backend returns `SANDBOX_SETUP_REQUIRED` rather than silently
changing modes.

If a non-owner selects Full Host Access through a stale UI or direct RPC, the
backend returns a permission error.

If Windows setup needs elevation, the status should include `requiresAdmin` so
the UI can distinguish owner-action-needed from unsupported host behavior.

## Testing

Backend tests:

- Owner principal defaults to Full Host Access.
- Token non-owner defaults to Trusted-Sandbox.
- No-token non-owner defaults to Trusted-Sandbox.
- Non-owner cannot set Full Host Access.
- Owner can set Full Host Access.
- Saved preferences are reused only when allowed for the current principal.
- Boot auto setup calls setup when enabled.
- Boot auto setup does not block startup.
- Boot auto setup can be disabled.
- Setup failures are captured in status rather than raised through gateway
  startup.
- Non-owner cannot approve owner-only sandbox grants.
- Trusted-Sandbox routine session grants can auto-approve for non-owner users.

Frontend tests:

- Run-mode selector enables two modes and disables Full Host Access for
  non-owner principals.
- Disabled Full Host Access shows localized English and Chinese hints.
- Owner sees all three modes enabled.
- Initial mode follows backend default.
- Setup status renders ready, preparing, owner retry, non-owner blocked, and
  unavailable states.

Platform tests:

- Linux/macOS setup remains ready/no-op.
- Windows setup ready marker reports ready.
- Windows setup requiring admin reports `requiresAdmin`.
- Windows managed-network marker diagnostics remain fail-closed.

## Rollout

Implement this behind the new setup policy while making the default enabled.
Keep an explicit opt-out for operators:

```text
sandbox.auto_setup = false
```

Update documentation and UI copy so users understand that Standard-Sandbox and
Trusted-Sandbox are available to non-owner users, while Full Host Access and
host-level setup remain owner/admin responsibilities.
