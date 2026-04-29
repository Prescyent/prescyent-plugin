# Subagent Output Contract

**contract_version: "2.0"**

Every subagent (`audit-systems`, `audit-knowledge`, `audit-comms`, `audit-stack`) MUST return output in this exact format. The master `audit` skill synthesizes by parsing this contract.

## What changed vs. v1.0

- Added top-level `contract_version` field.
- Added top-level `behavioral_trace_findings[]` (cap 10 per subagent) — patterns inferred from how data is used, not what's recorded.
- Added top-level `sor_pointers{}` — field → authoritative system map.
- Added per-finding `classification` (`public | internal | confidential | restricted`, default `internal`).
- Added per-finding `framework_indexes{}` with optional `pcf`, `bian`, `togaf`, `zachman` keys.
- `audit-stack` additionally emits a top-level `classification_surface{}` map: connector → classification tier.

## Contract

```json
{
  "contract_version": "2.0",
  "subagent": "audit-systems | audit-knowledge | audit-comms | audit-stack",
  "company_name": "string",
  "connectors_used": ["HubSpot", "OneDrive", "..."],
  "records_analyzed": {
    "total_records": 0,
    "total_documents": 0,
    "date_range": "YYYY-MM-DD to YYYY-MM-DD"
  },
  "sor_pointers": {
    "deal_count": "hubspot.deals",
    "owner_email": "hris.users"
  },
  "dimension_scores": {
    "data_accessibility": { "score": 0, "confidence": "High|Medium|Low", "rationale": "one-sentence" },
    "process_discipline": { "score": 0, "confidence": "High|Medium|Low", "rationale": "one-sentence" },
    "confidentiality_posture": { "score": null, "confidence": null, "rationale": "v0.2-beta dimension" }
  },
  "findings": [
    {
      "id": "SYS-01",
      "headline": "HubSpot has 412 deals with no close date",
      "detail": "Of 612 open deals, 412 (67%) have no close_date. Stage hygiene is breaking forecast accuracy.",
      "severity": "Critical | High | Medium | Low",
      "confidence": "High | Medium | Low",
      "data_source": "HubSpot deals API, pulled 2026-04-16",
      "recommendation": "Enforce close_date on stage change via HubSpot Workflow. 1-day fix.",
      "effort": "Low | Medium | High",
      "impact": "Low | Medium | High",
      "classification": "public | internal | confidential | restricted",
      "framework_indexes": {
        "pcf": "3.5.3 Manage sales orders",
        "bian": null,
        "togaf": "Business Architecture",
        "zachman": null
      }
    }
  ],
  "behavioral_trace_findings": [
    {
      "pattern": "Observed: 80% of close-won deals last quarter owned by 3 of 12 reps",
      "confidence": "Medium",
      "evidence": "HubSpot deals API, owner distribution over last 90d close_date"
    }
  ],
  "opportunities": [
    {
      "id": "OPP-01",
      "headline": "AI-draft post-meeting summaries to HubSpot deal",
      "why_now": "Fathom is connected. HubSpot deal notes are 80% empty. Template exists in the Prescyent gtm-wizards plugin.",
      "effort": "Low | Medium | High",
      "impact": "Low | Medium | High",
      "confidence": "High | Medium | Low"
    }
  ],
  "coverage_gaps": [
    {
      "gap": "No ~~wiki connector active",
      "impact": "Cannot score document_structure dimension",
      "fix": "Connect Notion or Confluence and re-run audit"
    }
  ],
  "open_questions": [
    {
      "question": "Are the 'Qualified' deals in HubSpot actually qualified, or is the stage being used as a placeholder?",
      "recommended_answer": "Spot-check 10 random 'Qualified' deals with the sales manager. If <70% have Budget+Authority notes, rename the stage 'Working' and add a distinct 'Qualified' stage gate."
    }
  ]
}
```

## Field Notes

- **`behavioral_trace_findings[]`** — each item: `{ pattern, confidence, evidence }`. Cap at 10 per subagent. Patterns are inferred — phrase as "observed" not "fact".
- **`sor_pointers{}`** — object mapping field name → authoritative system (e.g., `"deal_count": "hubspot.deals"`). The KB is a *derived* source-of-truth; HRIS/ERP/CRM are *authoritative*. Omit the key entirely if the subagent has no SOR claims.
- **`classification`** (per finding) — default `internal`. Synthesis drops `restricted` findings entirely and withholds `confidential` unless the user opts in.
- **`framework_indexes{}`** (per finding) — all four keys optional; default `null`. Only fill if obvious. The kb-graph subagent fills the rest downstream.

## audit-stack addendum

`audit-stack` additionally emits a top-level `classification_surface{}` map alongside the standard contract:

```json
{
  "classification_surface": {
    "HubSpot": "internal",
    "Gmail": "confidential",
    "git-private-repos": "restricted"
  }
}
```

This is the input to the kb-classifier subagent in v0.2.

## Rules

1. **Every finding must cite data.** No finding without a `data_source` field. No "generally speaking" language.
2. **Severity × Confidence.** A Critical finding with Low confidence is less urgent than a High finding with High confidence. The synthesis sorts by `(severity_weight × confidence_weight × impact_weight)`.
3. **Effort vs. Impact.** Every opportunity must score both. The synthesis ranks opportunities by `(impact - effort)` to surface low-lift wins first.
4. **No silent gaps.** If the subagent didn't analyze something, it goes in `coverage_gaps`. Do not omit.
5. **Open questions always carry a recommended answer.** Never leave ambiguity as a dead end. TribeAI convention — adopted here.
6. **Max 10 findings, max 5 opportunities, max 10 behavioral_trace_findings per subagent.** If more, surface the top N and note "and {M} additional findings" at the end. Keeps the synthesis tractable.
7. **Classification defaults to `internal`.** Findings tagged `restricted` never reach the HTML report; `confidential` requires user opt-in at synthesis.

## Markdown Rendering (what the master skill produces from the JSON)

The master `audit` skill renders the JSON into the final report structure. Subagents do not produce the final markdown — they produce the structured JSON. The master skill owns the voice + rendering.
