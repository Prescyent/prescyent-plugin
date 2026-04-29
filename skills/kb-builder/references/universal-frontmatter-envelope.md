# Universal Frontmatter Envelope

Every page written into a Prescyent knowledge base — regardless of page type — opens with a YAML frontmatter block containing this envelope. The envelope is the single source of truth for provenance, access control, lifecycle, and cross-framework tagging. Page-type schemas (see `page-types/`) extend the envelope with type-specific fields; they never replace it.

The validator at `scripts/validate-frontmatter.py` treats the envelope fields listed below as required on every page. Type-specific required fields stack on top.

## Required envelope fields

```yaml
id: company.process.lead-to-cash    # immutable, namespace-prefixed kebab-slug; never reused
title: Lead to cash                 # human-readable page title
type: Process                       # one of: Process | System | Role | Decision | Concept | Playbook | Glossary
owner: sales-ops@acme.com           # email of the responsible human, or a role name like "Sales Ops Lead"
confidence: high                    # high | medium | low — how sure the author is of this page's accuracy
source_artifacts:                   # list of paths/URLs the page was derived from
  - gdrive://.../SOP-LeadToCash.docx
  - https://salesforce.com/reports/12345
last_verified: 2026-04-24           # ISO date (YYYY-MM-DD) — last time a human confirmed this page
review_cycle_days: 90               # integer — days until the next review is due
status: draft                       # draft | published | superseded
created_by: tyler@acme.com          # email of the person (or agent) that first wrote the page
last_edited_by: tyler@acme.com      # email of the last editor
classification: internal            # public | internal | department-only | exec-only | confidential
audience:                           # groups, departments, or individual emails the page is meant for
  - sales
  - sales-ops
  - revenue-ops@acme.com
redactions_applied: []              # list of redaction categories applied by kb-pii-redactor (e.g., ["ssn", "dob"])
classification_decided_by: kb-classifier  # agent name (e.g., "kb-classifier") or human email
```

## Optional orthogonal framework indexes

These are optional on every page. Populate them where the mapping is obvious; the `kb-graph` subagent fills the rest after the corpus is written. Each field accepts a single string or an array of strings. Stick to the reference tables shipped in this skill (`apqc-pcf-reference.md`, `bian-reference.md`, `togaf-reference.md`, `zachman-reference.md`).

```yaml
pcf: ["3.5.1", "6.2.3"]            # APQC Process Classification Framework tags
bian: "Customer Offer"              # BIAN service domain — banking only
togaf: "Application"                # TOGAF architecture domain: Business | Application | Data | Technology
zachman: "How/Business"             # Zachman cell — {What,How,Where,Who,When,Why} / {Scope,Business,System,Tech,Detailed,Functioning}
dmbok: "Data Governance"            # DAMA DMBOK knowledge area (for data-heavy pages)
```

Keep them as `null` or omit them when there is no obvious mapping. Never guess; a blank tag is better than a wrong one.

## Supersedes / superseded_by chain

Pages are immutable at the `id` level — a page that is wrong or stale is replaced by a new page with a new `id`, and both ends of the chain point at each other. This makes history auditable and lets readers follow the thread forward or back.

```yaml
supersedes: company.process.lead-to-cash-v2     # the id this page replaces, or omit if none
superseded_by: null                              # set when a newer page takes over; otherwise null
```

Rules:
- When a page's `status` is set to `superseded`, its `superseded_by` field MUST name the successor page.
- The successor page's `supersedes` field MUST name this page.
- Never edit a superseded page's body; readers depend on it staying frozen.
- The `kb-graph` subagent verifies the chain is bidirectional and flags breaks in `_meta/gap-reports/`.

## Validator behavior

The validator treats the envelope as a strict schema:
- Missing required field -> error, exit 1.
- `classification` not in the allowed set -> error, exit 1.
- `type` not in the allowed set -> error, exit 1.
- Unknown fields -> warning (not an error) — page-type schemas may add fields the envelope doesn't know about, and that's fine.
- `supersedes` or `superseded_by` pointing at a non-existent page id -> warning (the graph subagent does the full cross-check).

See `scripts/validate-frontmatter.py --test` for the canary fixtures that exercise each rule.
