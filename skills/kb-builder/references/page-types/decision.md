# Page type: Decision

A Decision page is an ADR (Architectural Decision Record) — it captures a decision that was made, the options considered, the reasoning, and the tradeoffs the team knowingly accepted. Use Decision pages for any choice that future-you or future-hires will want to trace back: tool selections, architectural splits, policy calls, hiring model changes, pricing structure.

Decision pages are immutable. Once a decision is published, the page stays frozen. If the decision is later reversed or amended, a new Decision page is written, and the two are linked via `supersedes` / `superseded_by`. This is how the org's reasoning history stays intact.

Decision pages live under `08-decisions/` (or alongside the domain they affect — e.g., GTM decisions under `04-gtm/decisions/`).

## Full frontmatter (envelope + type-specific)

```yaml
---
id: company.decision.choose-snowflake-over-databricks
title: Chose Snowflake over Databricks for primary warehouse
type: Decision
owner: cto@acme.com
confidence: high
source_artifacts:
  - gdrive://Data/warehouse-evaluation-2024.pdf
  - slack://data-platform/archived-thread-12345
last_verified: 2026-04-24
review_cycle_days: 365
status: published
created_by: data-platform-lead@acme.com
last_edited_by: data-platform-lead@acme.com
classification: internal
audience: [engineering, data, leadership]
redactions_applied: []
classification_decided_by: kb-classifier
togaf: "Data"

decision_date: 2024-03-15
alternatives_considered:
  - name: Databricks
    rejected_because: "team had deeper Snowflake experience; pricing model cheaper for our BI workload"
  - name: BigQuery
    rejected_because: "multi-cloud strategy required AWS-native option"
  - name: Redshift
    rejected_because: "concurrency scaling limitations vs. Snowflake multi-cluster warehouses"
rationale: "BI-heavy workload, not ML-heavy. Snowflake's per-second compute billing and zero-copy clones fit the analyst-ergonomics goal. The team had 2 engineers with prior Snowflake experience and none with Databricks."
expected_tradeoffs:
  - "Locked into Snowflake compute pricing; negotiate multi-year EA to mitigate"
  - "ML workloads will need a separate compute layer (deferred, acceptable)"
  - "Data engineers must learn Snowflake-specific optimization patterns"
outcome: "Migration completed 2024-Q4. BI query times dropped 4x. ML workload moved to SageMaker in 2025 as planned."
decision_maker: cto@acme.com
affected_teams: [data-platform, analytics, engineering]
supersedes: null
superseded_by: null
---
```

`outcome` may be the literal string `pending` when the decision is fresh and the results are not yet in. Update it (via a new page that `supersedes` this one) once enough time has passed to judge.

## Required fields

Envelope plus:

- `decision_date` (ISO date)
- `alternatives_considered` (list of `{name, rejected_because}` objects — can be empty if no formal alternatives were evaluated, but write a sentence in the body explaining why)
- `rationale` (paragraph — why this choice won)
- `expected_tradeoffs` (list — what the team knowingly gave up)
- `outcome` (string, or the literal `pending`)
- `decision_maker` (single email)
- `affected_teams` (list)

`supersedes` and `superseded_by` are already in the envelope and are especially load-bearing for this page type.

## Body conventions

The prose mirrors the classic ADR structure. Sections in order:

1. **Context** — what problem prompted this decision. Two or three sentences. Name the forces at play (growth stage, team size, existing commitments).
2. **Decision** — the one-line statement of what was chosen. Restate from the title, precisely.
3. **Alternatives considered** — expand on each `alternatives_considered` entry with one paragraph of what made it attractive and what ruled it out.
4. **Consequences** — the expected and known second-order effects. Split into "positive," "negative," and "uncertain."
5. **Tradeoffs accepted** — the `expected_tradeoffs` list, with a sentence each on how the team plans to mitigate or accept the downside.
6. **Outcome** — filled in once time has passed. When the decision is first written, this section may say "pending — review in 6 months." When a successor Decision page is written, link back here and summarize what actually happened.

Never rewrite a published Decision page. If the outcome changes the reasoning, write a new page that supersedes this one.

## Example of a good page

```markdown
---
id: company.decision.drop-jenkins-for-github-actions
title: Dropped Jenkins in favor of GitHub Actions
type: Decision
owner: platform-lead@acme.com
confidence: high
source_artifacts: [gdrive://Eng/ci-evaluation-2025.pdf]
last_verified: 2026-04-24
review_cycle_days: 365
status: published
created_by: platform-lead@acme.com
last_edited_by: platform-lead@acme.com
classification: internal
audience: [engineering]
redactions_applied: []
classification_decided_by: kb-classifier
decision_date: 2025-06-01
alternatives_considered:
  - name: CircleCI
    rejected_because: "another vendor to onboard; GitHub Actions already reachable via existing GitHub SSO"
  - name: Keep Jenkins
    rejected_because: "plugin ecosystem bit-rot; team spending ~15% of cycles on CI maintenance"
rationale: "Consolidate on the GitHub platform we already pay for. Accept the loss of some Jenkins-specific flexibility in exchange for removing a whole maintenance surface."
expected_tradeoffs:
  - "Matrix builds harder to express for our 12-target iOS pipeline"
  - "Self-hosted runner cost will grow as we move internal workloads"
outcome: "pending"
decision_maker: cto@acme.com
affected_teams: [engineering, platform]
supersedes: null
superseded_by: null
---

## Context
Jenkins had accrued 60+ plugins; two of our last four P0 incidents traced back to plugin version conflicts...
```
