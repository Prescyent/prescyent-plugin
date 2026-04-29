# Page type: Concept

A Concept page defines an idea, model, or pattern the company reasons about — something that shapes conversations and decisions but isn't itself a process, system, or role. Examples: "our pricing tiers," "the ICP definition," "the 3-tier incident severity model," "Tier 0 / Tier 1 / Tier 2 support." If you would struggle to onboard someone without explaining this idea first, it deserves a Concept page.

Concept pages live under `00-meta/concepts/` or alongside the domain they anchor (e.g., sales-concepts under `04-gtm/concepts/`).

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.concept.ideal-customer-profile
title: Ideal Customer Profile (ICP)
type: Concept
owner: head-of-marketing@acme.com
confidence: high
source_artifacts:
  - gdrive://Marketing/ICP-v3.pdf
  - https://acme.com/about/who-we-serve
last_verified: 2026-04-24
review_cycle_days: 180
status: published
created_by: marketing-ops@acme.com
last_edited_by: head-of-marketing@acme.com
classification: internal
audience: [marketing, sales, leadership]
redactions_applied: []
classification_decided_by: kb-classifier

aliases:
  - ICP
  - target customer
  - our fit profile
related_concepts:
  - company.concept.buyer-personas
  - company.concept.tam-definition
  - company.concept.disqualification-rules
examples:
  - "Mid-market B2B SaaS, 200-2000 employees, Series C+, North America, CRO or VP Sales as champion"
  - "See the 2026 ICP one-pager: [link]"
supersedes: null
superseded_by: null
---
```

## Required fields

Envelope plus:

- `aliases` (list — other names this concept goes by, especially informal ones)
- `related_concepts` (list of page ids)
- `examples` (list — concrete instances or illustrative descriptions)

## Body conventions

Prose sections in order:

1. **One-line definition** — the single sentence you'd use to explain this to a new hire in a hallway.
2. **Extended definition** — the paragraph. Include the distinctions that matter (what this is NOT is often as important as what it is).
3. **Why it matters** — what decisions get made differently once someone understands this concept. One or two sentences.
4. **Examples** — concrete instances. Prefer real, anonymized examples over hypothetical ones.
5. **Common confusions** — phrases, ideas, or adjacent concepts people conflate with this one. Link the adjacent Concept pages via `related_concepts`.
6. **Where it shows up** — processes, decisions, or systems this concept drives. Link them.

Keep Concept pages short. A Concept page that runs past 300 words is usually hiding a Process or a Decision inside it — split it out.

## Example of a good page

```markdown
---
id: company.concept.tier-1-support
title: Tier 1 support
type: Concept
owner: head-of-cx@acme.com
confidence: high
source_artifacts: [gdrive://CX/support-tiers-2026.pdf]
last_verified: 2026-04-24
review_cycle_days: 180
status: published
created_by: cx-ops@acme.com
last_edited_by: cx-ops@acme.com
classification: internal
audience: [cx, product, engineering]
redactions_applied: []
classification_decided_by: kb-classifier
aliases: ["T1", "front-line support", "first-touch"]
related_concepts:
  - company.concept.tier-2-support
  - company.concept.tier-3-engineering-escalation
  - company.concept.sla-tiers
examples:
  - "Password reset, billing question, 'how do I export my data'"
  - "Staffed 6am-10pm PT by CX specialists; median response time ~8 min"
supersedes: null
superseded_by: null
---

## One-line definition
The front-line human reply for any customer question that doesn't need engineering.

## Extended definition
Tier 1 is staffed by CX specialists. They handle ~80% of all tickets end-to-end using the runbook library under `11-playbooks/cx/`. Anything that requires account-level data access beyond what Zendesk exposes, or any bug suspected to be live, escalates to Tier 2.

## Why it matters
The Tier 1 / Tier 2 split is the reason our CX headcount scales sublinearly with customer count...
```
