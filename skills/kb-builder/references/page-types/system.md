# Page type: System

A System page describes a software tool, platform, or service the company depends on. Use it for CRMs, data warehouses, ticketing systems, internal services, vendor SaaS, auth providers — anything with a name, a login, and a role in daily work. System pages live under `07-systems/` (or the folder matching the team that owns the tool).

A good System page answers, in one screen: what this tool is, what facts it owns, what it sends where, and the two or three things that will bite you if you don't know them.

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.system.hubspot
title: HubSpot
type: System
owner: revops@acme.com
confidence: high
source_artifacts:
  - https://hubspot.com/docs
  - gdrive://IT/SaaS-inventory.xlsx
last_verified: 2026-04-24
review_cycle_days: 180
status: published
created_by: revops@acme.com
last_edited_by: revops@acme.com
classification: internal
audience: [sales, sales-ops, marketing, revops]
redactions_applied: []
classification_decided_by: kb-classifier
pcf: ["3.5.1", "3.5.2"]
togaf: "Application"

system_type: CRM
vendor: HubSpot, Inc.
sor_for:
  - deals
  - contacts
  - companies
  - pipeline_stage
consumes_from:
  - salesloft (activity sync)
  - zoominfo (contact enrichment)
feeds_into:
  - snowflake (nightly ETL)
  - netsuite (closed-won webhook)
  - slack (#deals-won alerts)
gotchas:
  - "Pipeline stage enum was renamed in 2025-Q4; old reports still reference legacy names"
  - "Contact dedupe runs nightly, not real-time — expect 24h lag"
auth_method: SSO via Okta; API keys rotate quarterly
mcp_available: true
supersedes: null
superseded_by: null
---
```

## Required fields

Envelope plus:

- `system_type` (e.g., CRM, ERP, Data Warehouse, Auth Provider, Ticketing)
- `vendor`
- `sor_for` (list — the fields/entities this system is the source of record for)
- `consumes_from` (list of upstream systems or integrations)
- `feeds_into` (list of downstream systems this writes to)
- `gotchas` (list — the lived-experience traps)
- `auth_method` (short string: "SSO via Okta", "API key + IP allowlist", etc.)
- `mcp_available` (boolean — whether an MCP server exists to read/write this system)

## Body conventions

Prose sections in order:

1. **What it is** — one sentence.
2. **Who owns it** — name the team or role; link the Role page.
3. **Source of record for** — the specific fields or entities. This is the most-read section; keep it precise.
4. **Data flow** — inputs from upstream systems, outputs to downstream systems. A Mermaid diagram is fine but not required.
5. **Auth** — how humans and services authenticate. Never paste secrets.
6. **Gotchas** — the real-world traps. One bullet per trap. Each bullet names the trigger and the fix.
7. **MCP / API notes** (optional) — what the MCP exposes, rate limits, known quirks.
8. **Runbook links** (optional) — link to Playbook pages that touch this system.

Do not recreate vendor documentation. Link to it. The System page is for the company-specific truth: what you use it for, what it owns, what's special about your setup.

## Example of a good page

```markdown
---
id: company.system.snowflake
title: Snowflake (prod warehouse)
type: System
owner: data-platform@acme.com
confidence: high
source_artifacts: [gdrive://Data/warehouse-arch-2026.pdf]
last_verified: 2026-04-24
review_cycle_days: 90
status: published
created_by: data-platform@acme.com
last_edited_by: data-platform@acme.com
classification: internal
audience: [data, analytics, engineering]
redactions_applied: []
classification_decided_by: kb-classifier
togaf: "Data"
system_type: Data Warehouse
vendor: Snowflake
sor_for: ["analytics events", "daily revenue snapshot"]
consumes_from: [hubspot, segment, netsuite, postgres-prod]
feeds_into: [looker, sigma, fivetran-reverse-etl]
gotchas:
  - "Warehouse auto-suspend is 60s; cold queries cost ~4s"
  - "PROD_ANALYTICS.CORE is the only schema business users should query"
auth_method: Okta SSO; service accounts via key-pair rotation
mcp_available: false
supersedes: null
superseded_by: null
---

## What it is
Primary analytics warehouse for Acme.

## Who owns it
Data Platform team ([[role:data-platform-lead]]).

## Source of record for
- Daily revenue snapshot (reconciled against NetSuite at T+1)
- Product analytics events (from Segment)
...
```
