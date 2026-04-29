# Page type: Playbook

A Playbook page is a response runbook — the ordered set of steps someone runs when a specific trigger fires. Playbooks are for situations where speed matters and the team can't afford to reason from first principles. Examples: incident response, prospect re-engagement, churn save, quarterly close checklist.

The difference between a Playbook and a Process: a Process describes recurring work with known cadence ("here's how lead-to-cash flows"). A Playbook fires on a trigger and finishes ("here's what to do when a P0 alert pages the on-call"). Playbooks are shorter, sharper, and usually have a clock.

Playbook pages live under `11-playbooks/`.

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.playbook.p0-incident-response
title: P0 incident response
type: Playbook
owner: platform-lead@acme.com
confidence: high
source_artifacts:
  - gdrive://Eng/incident-runbook-v7.pdf
  - notion://on-call/p0-checklist
last_verified: 2026-04-24
review_cycle_days: 90
status: published
created_by: platform-lead@acme.com
last_edited_by: sre-lead@acme.com
classification: internal
audience: [engineering, platform, on-call]
redactions_applied: []
classification_decided_by: kb-classifier
pcf: ["4.4.2"]

trigger: "PagerDuty P0 alert fires OR customer reports full outage via status page"
objective: "Restore service within 30 min; communicate every 15 min"
steps:
  - 1. "Acknowledge page within 5 min; declare incident in #incidents"
  - 2. "Spin up incident Slack channel from /incident bot"
  - 3. "Page the on-call commander if not already on"
  - 4. "Open status page update within 10 min of trigger"
  - 5. "Diagnose via runbooks linked below; escalate if no progress in 15 min"
  - 6. "Restore service or failover; confirm with synthetic checks"
  - 7. "Post resolution on status page; schedule postmortem within 48h"
success_criteria: "Service restored; first status-page update within 10 min; postmortem scheduled"
failure_modes:
  - "Commander not paged; too many cooks, no decisions"
  - "Status page forgotten; customers learn via Twitter"
  - "Rollback attempted without capturing logs; RCA impossible"
time_to_execute: "30-60 min active; 48h to postmortem"
practiced_by:
  - on-call-rotation-sre
  - platform-team
supersedes: null
superseded_by: null
---
```

## Required fields

Envelope plus:

- `trigger` (string — the condition that starts this playbook)
- `objective` (string — the outcome the playbook is trying to produce)
- `steps` (ordered list — numbered, one-line each)
- `success_criteria` (string — how the runner knows the playbook worked)
- `failure_modes` (list — the traps people fall into)
- `time_to_execute` (string — wall-clock estimate, e.g., "15 min", "30-60 min active")
- `practiced_by` (list — which roles or rotations actually run this)

## Body conventions

Prose sections in order:

1. **When to run this** — the trigger, expanded. Name the edge cases (what LOOKS like the trigger but isn't).
2. **Objective** — what "done" looks like.
3. **Steps** — numbered, detailed. Each step names: who does it, what system, what action, what to check next. Include command snippets, shortcuts, or links to tools. This is the meat of the page.
4. **Communication checkpoints** — when and where to announce progress. For time-sensitive playbooks (incidents, churn saves), this section is as important as the steps.
5. **Success criteria** — how the runner confirms the playbook worked.
6. **Failure modes** — the common ways this playbook goes wrong, and how to recognize them mid-run.
7. **Post-run** — what to do after. For incidents, schedule the postmortem. For churn saves, log the outcome. For close-of-quarter, file the artifacts.
8. **Related** (optional) — linked Playbook, Process, or System pages.

Playbooks must be runnable under time pressure. Favor numbered steps over prose. Keep each step to one action and one check. If a step needs a branch, call it out: "If X, go to step 4; else continue."

## Example of a good page

```markdown
---
id: company.playbook.churn-save-at-risk-renewal
title: Churn save — at-risk renewal
type: Playbook
owner: head-of-cs@acme.com
confidence: high
source_artifacts: [gdrive://CS/renewal-playbook-v2.pdf]
last_verified: 2026-04-24
review_cycle_days: 180
status: published
created_by: cs-ops@acme.com
last_edited_by: head-of-cs@acme.com
classification: internal
audience: [customer-success, sales, revops]
redactions_applied: []
classification_decided_by: kb-classifier
trigger: "Renewal score <60 within 60 days of renewal date, OR CSM flags at-risk"
objective: "Secure a multi-year renewal OR a clean, dignified exit"
steps:
  - 1. "CSM files at-risk note in Gainsight within 24h of flag"
  - 2. "Pull usage + support trend in the at-risk dashboard"
  - 3. "Schedule exec-sponsor-to-exec-sponsor call within 7 days"
  - 4. "Run the discovery call using the 4-question exit script"
  - 5. "Decide: save path vs. graceful exit. Log decision in Gainsight"
  - 6. "If save: write a tailored renewal proposal in 5 business days"
  - 7. "If exit: offer transition help, ask for a testimonial / referral"
success_criteria: "Renewal closed OR formal churn logged with learnings captured"
failure_modes:
  - "Exec call never booked; CSM negotiates alone against a dissatisfied buyer"
  - "Save proposal generic; doesn't name the actual friction"
  - "Exit handled poorly; NPS damage ripples to their network"
time_to_execute: "14-30 days from trigger to resolution"
practiced_by: [cs-team, sales-ops]
supersedes: null
superseded_by: null
---

## When to run this
Renewal score flags at-risk in Gainsight, OR a CSM files a concern manually...
```
