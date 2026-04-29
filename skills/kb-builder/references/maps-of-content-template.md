# Maps of Content (MOCs)

A **Map of Content** is a navigation page for a value stream — a one-screen index that points at every page across the KB touching a named end-to-end flow. MOCs are not process documents. They do not describe steps. They link to the pages that do.

Owned by the `kb-graph` subagent. Do not edit by hand unless you know what you are doing — the next `/kb-build` rewrites every MOC from the corpus.

## Why MOCs exist

The 12-folder Karpathy structure groups pages by noun (company, products, operations). Real work crosses folders — a lead-to-cash process touches 04-gtm, 05-operations, 07-systems, and 06-people pages all at once. MOCs give the reader a verb-shaped view on top of the noun-shaped taxonomy.

## The 5 canonical value streams

| MOC file | Stream | Primary folders |
|---|---|---|
| `moc-lead-to-cash.md` | Lead capture through invoice collection | 04-gtm, 03-customers, 02-products, 05-operations |
| `moc-hire-to-retire.md` | Open req through offboarding | 06-people, 01-company |
| `moc-procure-to-pay.md` | Vendor request through payment | 05-operations, 07-systems |
| `moc-idea-to-launch.md` | Problem statement through general availability | 02-products, 08-projects, 09-decisions |
| `moc-incident-to-resolution.md` | Detection through postmortem | 11-playbooks, 05-operations, 07-systems |

All MOCs live at `{KB_ROOT}/public/00-meta/moc-*.md`.

## Page structure

```markdown
---
id: meta.moc.lead-to-cash
title: Lead to cash
type: Concept
owner: kb-graph
confidence: medium
source_artifacts: ["derived://corpus-scan"]
last_verified: 2026-04-24
review_cycle_days: 30
status: draft
created_by: kb-graph
last_edited_by: kb-graph
classification: internal
audience: ["company"]
redactions_applied: []
classification_decided_by: kb-writer-opus
---

# Lead to cash

How a lead becomes revenue in your company.

## Stages

1. **Lead capture** — inbound form, outbound sequence, or event scan.
   - [[gtm.process.lead-qualification|Lead qualification]] (Process)
   - [[gtm.system.crm-hubspot|HubSpot]] (System)
2. **Opportunity** — qualified lead moves to a pipeline stage.
   - [[gtm.process.deal-stages|Deal stages]] (Process)
   - [[gtm.role.account-executive|Account Executive]] (Role)
3. **Proposal** — pricing + scope document issued.
   - [[gtm.concept.pricing-model|Pricing model]] (Concept)
4. **Closed-won** — signed contract.
   - [[ops.process.order-to-cash|Order to cash]] (Process)
5. **Invoice + collection** — AR hands off to finance ops.
   - [[ops.process.ar-collection|AR collection]] (Process)

## Owners

- Overall stream: [[company.role.vp-revenue|VP Revenue]]
- Lead capture: [[company.role.head-of-marketing|Head of Marketing]]
- Proposal: [[company.role.sales-engineer|Sales Engineer]]
- Invoice + collection: [[company.role.controller|Controller]]

## Related concepts

- [[gtm.concept.icp|Ideal Customer Profile]]
- [[gtm.concept.personas|Personas]]
```

## Rules

1. **Stages are ordered.** Always a numbered list. Always left-to-right through the value stream.
2. **Every stage links to at least one page.** An empty stage means the MOC shouldn't be written yet.
3. **Each link is typed.** `(Process)`, `(Role)`, `(System)`, `(Concept)`, `(Playbook)` — so readers can scan for the type of page they need.
4. **Owners section is mandatory.** Even if most stages have "unassigned" — the unassigned flag is itself a useful gap signal.
5. **No prose paragraphs between stages.** Readers scan MOCs; they read the linked pages for depth.

## When NOT to write a MOC

- Fewer than 3 pages map to the stream. Log the skip in `kb-graph` return JSON (`mocs_skipped`). The MOC gets regenerated on the next `/kb-build` once more pages exist.
- The stream does not apply to the customer's business. `moc-procure-to-pay.md` makes no sense for a solo consultant with no vendor program; skip it.

`kb-graph` decides to skip based on the 3-page threshold. Customers never ask to skip an MOC by hand.

## Maintenance

- **Do not edit by hand.** Every `/kb-build` run rewrites every MOC from the current corpus.
- **Broken wikilinks** in an MOC signal a renamed or deleted page. `kb-graph` rewrites the MOC on the next run; if the link is still broken, the target page got deleted and the MOC gap entry captures it.
- **New value stream?** Add it to `kb-graph.md` Phase 3, not here. This template lists the canonical 5 — changing the canonical set is a product decision, not a kb-graph internals tweak.

## Classification

MOCs default to `classification: internal` and `audience: ["company"]`. The classifier in `kb-writer.py` may bump to `department-only` if the MOC's linked pages are heavily department-specific. The classifier never runs on MOCs with `--skip-classifier`; always let the funnel decide the final tier.
