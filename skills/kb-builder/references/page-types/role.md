# Page type: Role

A Role page describes a seat in the company — formal reporting, what that seat owns, and (most importantly) what people informally rely on the holder of that seat for. Use Role pages for both formal positions ("VP Engineering") and informal but load-bearing roles ("the person everyone asks about the Stripe migration").

Role pages capture the knowledge that org charts miss. The `informal_goto_for` field is the reason this page type exists: it surfaces the real decision surface of the company, not the org-chart fiction.

Role pages live under `06-people/`.

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.role.vp-engineering
title: VP Engineering
type: Role
owner: ceo@acme.com
confidence: high
source_artifacts:
  - gdrive://HR/org-chart-2026-Q2.pdf
  - notion://handbook/leadership-team
last_verified: 2026-04-24
review_cycle_days: 90
status: published
created_by: people-ops@acme.com
last_edited_by: people-ops@acme.com
classification: internal
audience: [all-hands]
redactions_applied: []
classification_decided_by: kb-classifier
pcf: ["6.1.1"]

reports_to: ceo@acme.com
direct_reports:
  - eng-manager-platform@acme.com
  - eng-manager-product@acme.com
  - staff-architect@acme.com
informal_goto_for:
  - "sizing engineering work during deal reviews"
  - "vendor security review escalations"
  - "historical context on the 2024 infra migration"
processes_owned:
  - company.process.eng-hiring
  - company.process.incident-response
systems_owned:
  - company.system.pagerduty
  - company.system.github-org
tenure_at_company: "4.2 years"
domain_expertise:
  - distributed systems
  - SOC2 audit prep
  - acquisition due diligence
supersedes: null
superseded_by: null
---
```

## Required fields

Envelope plus:

- `reports_to` (single email or role id)
- `direct_reports` (list)
- `informal_goto_for` (list — the subjects people actually come to this person about, even when it's not their formal job; this is the critical field and often differs from `processes_owned`)
- `processes_owned` (list of page ids)
- `systems_owned` (list of page ids)
- `tenure_at_company` (short string, e.g., "4.2 years", "6 months")
- `domain_expertise` (list of tags)

## Body conventions

Prose sections in order:

1. **Seat summary** — one sentence: what this person is accountable for.
2. **Formal scope** — a few bullets on the stated job description. Link processes and systems they own.
3. **Informal scope** — the `informal_goto_for` list, expanded. For each item, name why this person ended up being the go-to (history, expertise, who they replaced). This section is the one new hires will read twice.
4. **Collaborators** — the 3-5 people this role works with most, with a sentence each on the interface.
5. **Escalation patterns** — who escalates to this role, and who this role escalates to.
6. **History** (optional) — prior holders and what they moved to. Useful when context lives in "ask the person who had this seat before."

The separation between `informal_goto_for` and `processes_owned` is deliberate. A VP Engineering's org chart says they own `eng-hiring`; in practice people also come to them for vendor security questions because they ran the last SOC2. Capture both.

Role pages are confidential-leaning — the `informal_goto_for` data is derived from communication patterns and should be reviewed by the named person before `status: published`. Default to `status: draft` until a human says otherwise.

## Example of a good page

```markdown
---
id: company.role.dba-lead
title: DBA Lead
type: Role
owner: cto@acme.com
confidence: medium
source_artifacts: [gdrive://HR/titles.xlsx]
last_verified: 2026-04-24
review_cycle_days: 180
status: draft
created_by: kb-company
last_edited_by: kb-company
classification: internal
audience: [engineering, data]
redactions_applied: []
classification_decided_by: kb-classifier
reports_to: cto@acme.com
direct_reports: []
informal_goto_for:
  - "why the prod replica lags at 3am Sundays"
  - "running a one-off pg_restore without paging the team"
  - "cross-region failover drill history"
processes_owned:
  - company.process.db-backup-rotation
systems_owned:
  - company.system.postgres-prod
  - company.system.pgbouncer
tenure_at_company: "5.5 years"
domain_expertise: [postgres, replication, pitr]
supersedes: null
superseded_by: null
---

## Seat summary
Keeps the production Postgres fleet healthy.

## Formal scope
- Owns backup + PITR policy
- Owns prod schema migrations
- On-call rotation L2

## Informal scope
- **Sunday 3am replica lag** — history: wrote the original replication setup in 2020; the lag window is a known quirk of the cross-AZ network link and doesn't page unless it exceeds 10 min.
- **One-off pg_restore** — history: people default to asking because the runbook was written by them and they know the edge cases.
...
```
