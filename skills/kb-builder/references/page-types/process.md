# Page type: Process

A Process page describes a repeatable sequence of work that takes defined inputs to defined outputs. Use it when the answer to "how do we do X?" is a series of steps owned by one or more people, touching one or more systems. Processes live under `05-operations/` or alongside the value stream they belong to (e.g., lead-to-cash Processes live under `04-gtm/` when that's where the team looks first).

Prefer Process pages over free-form how-to docs. A Process page is the page an onboarding employee reads on day one to learn how the work actually flows.

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.process.lead-to-cash
title: Lead to cash
type: Process
owner: sales-ops@acme.com
confidence: high
source_artifacts:
  - gdrive://SOPs/lead-to-cash-v4.docx
  - notion://sales-ops/playbooks/close-won-checklist
last_verified: 2026-04-24
review_cycle_days: 90
status: published
created_by: tyler@acme.com
last_edited_by: sales-ops@acme.com
classification: internal
audience: [sales, sales-ops, finance]
redactions_applied: []
classification_decided_by: kb-classifier
pcf: ["3.5.1"]
togaf: "Business"
zachman: "How/Business"

value_stream: lead-to-cash
inputs:
  - qualified lead record in HubSpot
  - signed MSA in Ironclad
outputs:
  - closed-won opportunity in HubSpot
  - invoice in NetSuite
  - handoff note in Slack #cs-handoff
actors:
  - role: Account Executive
  - role: Sales Engineer
  - role: Revenue Operations
  - role: Customer Success Lead
systems:
  - HubSpot
  - Ironclad
  - NetSuite
  - Slack
decision_points:
  - "Deal size >$50k triggers exec approval before MSA send"
  - "Net-new logo triggers security review"
failure_modes:
  - "AE forgets handoff note; CS has no context on day 1"
  - "Invoice generated before PO number is captured; AR chases"
supersedes: null
superseded_by: null
---
```

## Required fields

Envelope (see `universal-frontmatter-envelope.md`) plus:

- `value_stream`
- `inputs` (list)
- `outputs` (list)
- `actors` (list)
- `systems` (list)
- `decision_points` (list, may be empty)
- `failure_modes` (list, may be empty)

## Body conventions

The prose portion of the page uses these sections, in order:

1. **Purpose** — one sentence naming the outcome the process produces.
2. **Trigger** — what kicks it off.
3. **Steps** — numbered list. Each step names the actor, the system, and the action. Keep each step to one sentence.
4. **Inputs** — bullet list, mirrors frontmatter, with source-of-record pointer for each.
5. **Outputs** — bullet list, mirrors frontmatter, with destination system for each.
6. **Actors** — role and responsibility per actor. Link to Role pages when they exist.
7. **Systems** — list, linked to System pages.
8. **Decision points** — branch points where work splits. One bullet per branch, with the rule that decides it.
9. **Failure modes** — what breaks, how you spot it, and who fixes it.
10. **Metrics** (optional) — the 1-3 numbers that say whether this process is healthy.

Keep steps testable — a step that says "handle the customer well" is not a step, it's a wish.

## Example of a good page

```markdown
---
id: company.process.new-hire-onboarding
title: New-hire onboarding (week 1)
type: Process
owner: people-ops@acme.com
confidence: high
source_artifacts: [gdrive://HR/new-hire-week-1.pdf]
last_verified: 2026-04-24
review_cycle_days: 180
status: published
created_by: people-ops@acme.com
last_edited_by: people-ops@acme.com
classification: internal
audience: [people-ops, hiring-managers]
redactions_applied: []
classification_decided_by: kb-classifier
pcf: ["6.3.2"]
value_stream: hire-to-retire
inputs: ["signed offer letter", "start date confirmed"]
outputs: ["provisioned laptop", "Okta account", "first-week calendar", "buddy assigned"]
actors:
  - role: People Ops
  - role: IT
  - role: Hiring Manager
systems: [Rippling, Okta, Google Workspace]
decision_points:
  - "Remote hire triggers laptop shipment 7 days before start"
failure_modes:
  - "Okta account not ready day 1; new hire waits"
  - "No buddy assigned; new hire has no one to ask"
supersedes: null
superseded_by: null
---

## Purpose
Get a new hire productive by end of week 1.

## Trigger
Signed offer letter in Rippling.

## Steps
1. People Ops creates Rippling record (day -7).
2. IT provisions Okta + laptop (day -3).
3. Hiring Manager assigns a buddy (day -1).
...
```
