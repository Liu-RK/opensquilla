# n8n

Strengths, limits, and templates for designing workflows in n8n.

## When n8n is the right choice

- Self-hosting required (data privacy, on-prem, regulated industry)
- Cost matters at scale (self-hosted n8n is essentially free per
  execution after server cost)
- The workflow is sufficiently complex that visual + code coexistence
  helps (n8n has a Function/Code node and seamless code interop)
- The team has at least one developer comfortable with Node.js

## n8n vocabulary

| Term | Meaning |
|---|---|
| Workflow | A flow |
| Node | A step (trigger or action) |
| Item | A unit of data flowing through nodes |
| Execution | One run of a workflow (billing unit on n8n Cloud) |
| Sub-workflow | A workflow called as a node from another |
| Function node | Custom JS / Python code |
| Wait node | Pause for time or webhook callback |

## Trigger types

- **Webhook trigger**: instant.
- **Schedule trigger**: cron-style.
- **Polling**: per-app intervals, configurable.
- **Manual / test**: trigger the workflow yourself for development.
- **Sub-workflow trigger**: called from another workflow.

## Pattern: GitHub label → Linear with bidirectional sync

Workflow A — GitHub → Linear:

```
1. Webhook trigger (GitHub: issues.labeled)
2. IF node: payload.label.name == "bug"?
   true:
     3a. Linear node: create issue
     4a. Set node: build linear-id link
     5a. GitHub node: comment "Tracked as L-{id}"
   false:
     stop
```

Workflow B — Linear → GitHub status:

```
1. Webhook trigger (Linear: issue.update)
2. IF node: previous status was "in progress" and new is "done"?
   true:
     3a. GitHub node: close the issue identified by the linear-id link
     4a. GitHub node: comment "Closed via Linear-{id}"
```

n8n's IF node is a clean two-branch split; for >2 branches use Switch.

## Pattern: queue + retry for flaky external API

```
1. Schedule trigger (every 5 min)
2. Queue node: pop next batch from Redis list
3. Loop Over Items
   ├── HTTP Request to external API
   │   - Continue On Fail: yes
   ├── IF: success?
   │   true → DB write
   │   false → push back onto queue with attempt counter; abort on attempts > 5
4. Aggregator: collect results
5. Slack node: post summary if failures > 0
```

n8n's Continue On Fail + custom Function nodes for back-off math gives
fine control without extra services.

## Self-hosting

```bash
# Quick self-host with Docker
docker run -it --rm \
  --name n8n \
  -p 5678:5678 \
  -v ~/.n8n:/home/node/.n8n \
  n8nio/n8n
```

For production: docker-compose with a Postgres service, behind a reverse
proxy with TLS, mount workflow JSONs to a versioned volume. n8n exports
workflows as JSON; check them into git for review and rollback.

## Limits

- Self-hosted: only constrained by your infrastructure. Memory hits
  matter when handling large arrays — split into batches.
- n8n Cloud: paid plans by execution count and active workflows.
- Per-node timeouts vary; HTTP request default is 5 min.

## Anti-patterns

- **Using only Function nodes**: defeats the visual flow benefit. Reserve
  Function nodes for transformations no built-in node covers.
- **No environment separation**: a single n8n instance running prod and
  test workflows is fragile. Use n8n's environments feature (paid) or two
  instances.
- **Workflow files not in git**: at scale, untracked workflow drift is
  costly. Export JSON, commit, code-review changes.
