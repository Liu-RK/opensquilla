# Make (formerly Integromat)

Strengths, limits, and templates for designing workflows in Make.

## When Make is the right choice

- Branching, error handling, or iteration is non-trivial
- Webhooks and instant triggers across many apps
- Visual scenario design with bundles flowing between modules
- Cost-conscious team that wants more "ops per minute" than Zapier

Make's per-operation pricing is typically cheaper than Zapier's per-task
for the same workflow.

## Make vocabulary

| Term | Meaning |
|---|---|
| Scenario | A workflow |
| Module | A step (trigger or action) |
| Bundle | One unit of data flowing between modules |
| Operation | One module execution (billing unit) |
| Router | Branching block; pure parallel paths with optional filters |
| Iterator / Aggregator | Loop helpers — split arrays / reassemble |
| Error handler route | Per-module error path |

## Trigger types

- **Instant triggers** (webhooks): preferred where supported.
- **Scheduled scenarios**: run on a cron (every minute, hour, day).
- **Polling triggers**: check the source on a configurable interval (1
  min minimum on paid tiers).

## Pattern: form to spreadsheet with validation

Trigger: webhook from web form `{name, email, message}`.

```
1. Webhook trigger
2. Tools: Set variables — normalize email casing
3. Filter: regex check for email format
4. Router: split into parallel paths
   ├── Path A — append row to Google Sheets
   └── Path B — send notification to #forms Slack channel
5. Each path has its own error handler:
   ├── Sheets error → log to error sheet, retry 3×
   └── Slack error → send fallback to email
```

Make's router runs branches independently; an error in one does not stop
the others.

## Pattern: long-running job with retries

Trigger: scheduled (every 30 min).

```
1. Schedule trigger
2. HTTP module: call external API
   - Error handler attached: route to "Break" with 5x exponential backoff
3. Iterator: split response into items
4. Per-item:
   - Validate, transform
   - Insert into DB module
5. Aggregator: collect insert results
6. Email summary of failures (if any) to ops@
```

Iterator + Aggregator is Make's idiom for "for each item, do X, then
combine results". Zapier has nothing as clean.

## Limits

- Free: 1k operations/month, 5 active scenarios.
- Core (paid): 10k ops/month, unlimited scenarios, 1-min execution.
- Per-execution timeout: 40 minutes.
- HTTP module: max 100 MB upload, 100 MB download.

## Anti-patterns

- **Using HTTP module for everything**: built-in app modules are usually
  faster and have better error semantics.
- **Routing everything through one Router**: routers are visual debt at
  scale. Split into multiple chained scenarios.
- **Missing error handlers on critical modules**: errors silently abort
  the bundle's path. Always attach an error handler on third-party API
  calls.
