---
name: automation-workflows
description: "Design no-code or low-code automation workflows. Trigger when the user wants to connect two or more SaaS apps (Slack ↔ Notion, GitHub ↔ Linear, calendar ↔ CRM), schedule recurring jobs, automate handoffs, or replace a manual paste-and-forward step. Helps pick between Zapier, Make (Integromat), n8n, and direct webhook stitching by mapping the user's needs (volume, latency, branching, self-hosting, cost) onto each tool's strengths. Pure-instruction skill — no scripts; the value is the decision framework and workflow patterns in references/."
homepage: ""
provenance:
  origin: clawhub-mit0
  license: MIT-0
  upstream_url: https://clawhub.ai/automation-workflows
  maintained_by: OpenSquilla
metadata:
  {
    "platform":
      {
        "emoji": "⚙️",
      },
  }
---

# automation-workflows

A decision framework for picking and structuring an automation workflow,
plus reusable patterns for the most common use cases. This skill ships
references but no scripts — the work is choosing the right tool and
designing the trigger/action chain, not running it from this CLI.

## When to use

- "Whenever a customer signs up, post to Slack and add to a Notion DB"
- "Once a day at 9am, pull X from API Y and email a digest"
- "When a GitHub issue is labeled `bug`, create a Linear ticket"
- "When a calendar invite is booked, prep a brief in Notion"
- The user already named a tool ("can you set this up in Zapier?") and
  wants the chain designed cleanly

## When NOT to use

- The integration belongs in product code (already inside the user's
  application). Use proper API code, not a no-code tool.
- The volume is enterprise-scale (>100k events/day). No-code tools become
  expensive; consider event streaming (Kafka, Pub/Sub) plus serverless.
- The user is asking how to write the integration in code from scratch.
  This skill does not produce code; it produces workflow plans.

## Decision framework (1-2 minute version)

Walk through these in order:

1. **Volume**: <100 events/day → any tool works. >10k events/day → look
   at n8n self-hosted or move to product code.
2. **Latency**: <60s end-to-end? Make and direct webhooks are fastest.
   Zapier polls some triggers on 5-15 min intervals (free tier).
3. **Branching**: Need conditional paths, loops, error handlers? Make
   and n8n have first-class branching; Zapier has Filters and Paths but
   the UI gets unwieldy past 3 branches.
4. **Self-hosting**: Required (compliance, on-prem)? n8n is the only
   option. Zapier and Make are SaaS-only.
5. **Cost**: <$20/mo and <2k events → Zapier free/Starter or Make Core.
   Heavier → n8n Cloud or self-host. At scale, n8n self-host wins on
   cost but costs developer time.
6. **Team familiarity**: Picking the tool the team already uses beats
   the "objectively best" tool by a wide margin.

If the answer is unclear, default to **Zapier** (lowest setup cost) or
**n8n self-hosted** (lowest run cost, more flexible).

## Common patterns (see references/)

- **Linear handoff**: GitHub issue labeled X → create Linear issue,
  bidirectional sync — see [references/n8n.md](references/n8n.md).
- **Daily digest**: cron trigger → fetch sources → summarize → email/Slack
  — works in any tool; templates differ.
- **Customer onboarding**: signup webhook → CRM record → welcome email
  → Slack ping → Notion task — see [references/zapier.md](references/zapier.md).
- **Form-to-spreadsheet**: form submission → validate → append row →
  notify owner — see [references/make.md](references/make.md).
- **Long-running job with retries**: external API call may fail;
  exponential backoff and dead-letter queue — pattern for n8n + queue.

## Output shape

When designing a workflow with this skill, produce:

1. **Trigger**: what kicks it off (webhook, cron, polling)
2. **Steps in order**, numbered, each with the tool used, the inputs, and
   the outputs
3. **Branching points** with explicit conditions
4. **Error paths**: what happens on each step's failure
5. **Test plan**: how to verify the workflow without firing real customer
   events
6. **Rollout plan**: dry-run → small percentage → full

A workflow without an error path is half-built; do not skip step 4.

## Boundaries

- This skill does not deploy workflows for the user. It produces a plan
  the user pastes into the chosen tool.
- It does not store credentials. Each tool's credential management is
  the tool's problem.
- It does not benchmark per-tool latency in real time; the guidance is
  based on documented behavior as of the references' publication.
