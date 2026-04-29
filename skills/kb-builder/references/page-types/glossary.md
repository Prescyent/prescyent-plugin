# Page type: Glossary

A Glossary page preserves a single term-of-art the company uses — captured with the exact wording the team actually says, not a sanitized definition. Glossary pages exist so the KB stays faithful to the company's language: when an agent or a new hire sees "PSAT," they find the page that says "Primary Supplier Agreement Template, pronounced pee-sat, called 'the PSAT doc' internally, not to be confused with 'PSAT scores' which is the customer satisfaction metric that unfortunately shares the acronym."

Glossary pages are about preserving the company's dialect. If a team says "roll the numbers" to mean "reconcile the monthly figures," the glossary captures that — the definition never replaces the phrase. Company language is the signal; translation is a footnote.

Glossary pages live under `10-glossary/`.

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.glossary.psat
title: PSAT
type: Glossary
owner: legal-ops@acme.com
confidence: high
source_artifacts:
  - gdrive://Legal/templates/PSAT-v12.docx
  - slack://legal-ops/thread-archive
last_verified: 2026-04-24
review_cycle_days: 180
status: published
created_by: legal-ops@acme.com
last_edited_by: legal-ops@acme.com
classification: internal
audience: [legal, procurement, finance, sales]
redactions_applied: []
classification_decided_by: kb-classifier

term: PSAT
definition: "Primary Supplier Agreement Template — the standard contract we send net-new suppliers. Pronounced 'pee-sat'."
aliases:
  - "the PSAT doc"
  - "primary supplier template"
  - "supplier MSA"
do_not_confuse_with:
  - "PSAT (customer satisfaction metric)"
  - "NDA (different artifact, different flow)"
  - "Supplier Addendum (attaches to an existing PSAT; not a replacement)"
customer_facing_equivalent: "Our Supplier Agreement"
preferred_phrasing: "PSAT"
usage_examples:
  - "Can you send them the PSAT?"
  - "The PSAT has a 30-day payment-term clause; legal won't redline it."
  - "Roll the PSAT and the supplier addendum together."
supersedes: null
superseded_by: null
---
```

## Required fields

Envelope plus:

- `term` (the literal string the company uses — preserve casing, hyphens, spaces)
- `definition` (one or two sentences — what it means, with pronunciation if non-obvious)
- `aliases` (list — every variant the team uses, formal and informal)
- `do_not_confuse_with` (list — phrases or terms that sound similar or overlap but are different)
- `customer_facing_equivalent` (string — what this term is called in customer-facing materials, or "n/a" if internal-only)
- `preferred_phrasing` (string — the canonical form the team should use when precision matters)
- `usage_examples` (list — sentences pulled verbatim from transcripts, Slack, or docs that show the term in use)

## Body conventions

Glossary pages are terse on purpose. Prose sections in order:

1. **Term** — repeat the title, with pronunciation if non-obvious.
2. **Definition** — one or two sentences. No more.
3. **How it's used** — the `usage_examples` list, with light context for each. Pull from real transcripts when you can.
4. **Do not confuse with** — the list, expanded with a sentence each on the distinction. This is the most valuable section — it's why the page exists.
5. **Customer-facing equivalent** — if the external term differs, name the external term and when to switch.
6. **History** (optional) — where the term came from. Sometimes useful ("coined by the legal team in 2022 when we migrated from DocuSign templates to Ironclad").

**Never paraphrase the term itself.** If the team says "PSAT," the page title is `PSAT`. If the team says "the lead-to-cash motion," the term is `"the lead-to-cash motion"`, not `"lead to cash"`. The whole point is that the company's phrasing is preserved.

Agents reading the KB should treat Glossary pages as the authoritative dictionary — if a term appears in another page's body, link to the Glossary entry via `[[company.glossary.<term-slug>]]`.

## Example of a good page

```markdown
---
id: company.glossary.roll-the-numbers
title: Roll the numbers
type: Glossary
owner: controller@acme.com
confidence: high
source_artifacts: [slack://finance/close-week-threads]
last_verified: 2026-04-24
review_cycle_days: 365
status: published
created_by: finance-ops@acme.com
last_edited_by: controller@acme.com
classification: internal
audience: [finance, accounting]
redactions_applied: []
classification_decided_by: kb-classifier
term: "roll the numbers"
definition: "Run the month-end close reconciliation: pull GL, match subledger balances, post adjustments, produce the draft P&L."
aliases:
  - "rolling the close"
  - "rolling"
  - "the monthly roll"
do_not_confuse_with:
  - "rolling forecast (different artifact; 13-week view, not a close)"
  - "roll-forward schedule (specific to fixed-asset accounting; subset of the close)"
customer_facing_equivalent: "n/a — internal only"
preferred_phrasing: "roll the numbers"
usage_examples:
  - "I'm rolling the numbers this week — ping me after Thursday."
  - "Did accounting finish rolling? Need the draft P&L for the board deck."
  - "We rolled on day 3; fastest close this year."
supersedes: null
superseded_by: null
---

## Term
Roll the numbers.

## Definition
Run the month-end close reconciliation...
```
