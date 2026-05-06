# Zapier

Strengths, limits, and templates for designing workflows in Zapier.

## When Zapier is the right choice

- Volume is moderate (<5k events/month on a free or Starter plan)
- Linear flows: trigger → 2-6 actions, no deep branching
- The user already has accounts and apps connected
- You want the lowest setup cost, even if monthly cost is higher

## Zapier vocabulary

| Term | Meaning |
|---|---|
| Zap | A workflow |
| Trigger | The event that starts a Zap |
| Action | A step that runs after the trigger |
| Filter | Conditional that passes/blocks the rest of the Zap |
| Path | Branching with multiple parallel action chains |
| Task | One execution of a step (Zapier's billing unit) |

## Trigger types

- **Polling triggers** (most): check the source every 1-15 minutes
  depending on plan. Free tier polls every 15 min, paid every 1 min.
- **Instant triggers** (webhooks): the source app sends Zapier a webhook,
  Zap runs in seconds.
- **Schedule trigger**: cron-style daily/weekly/monthly.

For latency-sensitive workflows, prefer instant triggers (webhooks) or
move to Make / n8n.

## Pattern: customer onboarding

Trigger: webhook from `/signup` endpoint with `{email, plan}`.

```
1. Webhook trigger
2. Filter: continue only if plan != "trial"
3. Action: HubSpot — create or update contact
4. Action: Notion — create page in "Active customers" DB
5. Action: Slack — post to #signups: "{name} on {plan}"
6. Action: SendGrid — send welcome email (template ID)
```

Error path: if step 3 fails (HubSpot API down), Zapier retries 3 times
with exponential backoff, then moves to error queue. Configure email
notification on errors in account settings.

Test plan: Zapier UI has "Test trigger" + "Test action" per step. Run
each step against fixture webhook payloads before publishing.

Rollout: turn on, fire one real test signup, then watch the History tab.

## Pattern: GitHub bug → Linear

Trigger: New labeled issue (bug) in GitHub repo.

```
1. GitHub trigger: New labeled issue
2. Filter: label name == "bug"
3. Code action (Zapier Code): build Linear issue title from
   "{issue.title} ({issue.number})"
4. Linear action: create issue in team X, project Y, priority urgent
5. GitHub action: comment on issue: "Tracked as Linear-{linear.id}"
```

The Code action is JavaScript or Python; useful when you need a small
transformation a built-in action does not cover.

## Limits

- Free tier: 100 tasks/month, 5 Zaps, 15-min polling.
- Paid tiers go up to unlimited Zaps and 1-min polling.
- Zapier Code timeout: 10s; payload size: 6MB; output: 100KB.
- No first-class loops. Use iterators or pre-process arrays in Code.

## Anti-patterns

- **One mega-Zap with 20 steps**: hard to debug, every change tests
  everything. Split into chained Zaps, each <8 steps.
- **Putting credentials in plain Code**: use Zapier's connections instead.
- **Using Filter to drop 90%+ of events**: the events still cost tasks.
  Move filtering upstream to the trigger app when possible.
