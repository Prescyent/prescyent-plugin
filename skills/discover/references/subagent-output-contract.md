# Subagent Output Contract

**contract_version: "2.2"**

Two contracts live in this file:

1. **Audit subagent contract** — what each `audit-*` subagent returns to the master `discover` skill.
2. **Synthesizer output contract** (new in 2.2) — the structured JSON the master skill produces for the renderers. Both renderers (`render_deck.py` for buyer HTML, `render_markdown.py` for analyst markdown) consume the same JSON. No markdown→HTML middleman.

---

## What changed vs. v2.1

- Added the **Synthesizer output contract** below.
- Subagent contract is unchanged in shape but the master skill now inlines the contract spec into each subagent prompt at dispatch time (Phase 3) instead of passing a path reference. Subagents no longer need to read this file at runtime.
- Phase 4 input shifts from `open_questions[]` to the synthesizer's draft contestable answer + Top 3 (strategic clarifications, not tactical triage). Subagent `open_questions[]` flow to the analyst markdown's Open Questions appendix.

---

## What changed vs. v2.0

- Added per-finding `surprise_factor` (`Low | Medium | High`).
- Added per-opportunity `surprise_factor`.

## What changed vs. v1.0 (still applies)

- Top-level `contract_version` field.
- Top-level `behavioral_trace_findings[]` (cap 10 per subagent).
- Top-level `sor_pointers{}`.
- Per-finding `classification` (`public | internal | confidential | restricted`, default `internal`).
- Per-finding `framework_indexes{}`.
- `audit-stack` additionally emits `classification_surface{}`.

---

## Audit subagent contract (every audit-* subagent returns this)

```json
{
  "contract_version": "2.2",
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
      "surprise_factor": "Low | Medium | High",
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
      "confidence": "High | Medium | Low",
      "surprise_factor": "Low | Medium | High"
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

### Field notes

- **`behavioral_trace_findings[]`** — each item: `{ pattern, confidence, evidence }`. Cap at 10 per subagent. Patterns are inferred — phrase as "observed" not "fact".
- **`sor_pointers{}`** — object mapping field name → authoritative system. Omit the key entirely if the subagent has no SOR claims.
- **`classification`** (per finding) — default `internal`. Synthesis drops `restricted` findings entirely. Synthesis withholds `confidential` findings as Coverage Gaps with a one-line note (no opt-in flag in v0.5 — buyer never sees confidential signal regardless).
- **`framework_indexes{}`** (per finding) — all four keys optional; default `null`.
- **`surprise_factor`** (per finding + per opportunity) — required.
  - **High** = required cross-source synthesis or contradicts a stated position. User almost certainly does NOT know this.
  - **Medium** = volume-driven discovery — counts, percentages, stale-records the user might know exist but hasn't quantified.
  - **Low** = obvious / known patterns. Synthesis demotes to appendix.

### audit-stack addendum

`audit-stack` additionally emits `classification_surface{}` alongside the standard contract:

```json
{
  "classification_surface": {
    "HubSpot": "internal",
    "Gmail": "confidential",
    "git-private-repos": "restricted"
  }
}
```

### Rules

1. **Every finding must cite data.** No finding without a `data_source` field.
2. **Severity × Confidence.** Synthesis sorts by `(severity_weight × confidence_weight × impact_weight)`.
3. **Effort vs. Impact.** Every opportunity scores both. Synthesis ranks by `(impact - effort)`.
4. **No silent gaps.** If subagent didn't analyze something, it goes in `coverage_gaps`.
5. **Open questions always carry a recommended answer.**
6. **Max 10 findings, max 5 opportunities, max 10 behavioral_trace_findings per subagent.**
7. **Classification defaults to `internal`.** `restricted` never reaches the report; `confidential` surfaces as Coverage Gap only.

---

## Synthesizer output contract (new in 2.2)

The master `discover` skill produces this structured JSON at Phase 5a. Both renderers consume it:

```json
{
  "contract_version": "2.2",
  "plugin_version": "0.5.0",

  "company_name": "Baseline Payments",
  "company_slug": "baseline-payments",
  "audit_date": "2026-05-01",
  "depth": "Deep",
  "user_role": "founder",
  "user_email": "tyler@baselinepayments.com",
  "unconnected_tools": "Koncert, Trumpet",

  "the_answer": "Your AI stack is already an A-grade. The bullshit you want eliminated isn't a tooling problem; it's an integration problem you happen to be the only person solving.",

  "scores": {
    "stack": 8,
    "workflow_integration": 4,
    "overall": 62,
    "interpretation": "Tools present, plumbing missing."
  },

  "wins_top_3": [
    {
      "rank": 1,
      "headline": "Disconnect the JetPay zombie sign-up feed.",
      "one_liner": "815 of your 1,149 open deals (71%) sit in pipelines explicitly labeled DO NOT USE. Live HubSpot workflow still feeding them.",
      "ai_mechanism": "One-hour HubSpot Workflows audit. Zero code.",
      "impact_metric": "~3 hrs/week back",
      "effort": "Low",
      "impact": "High",
      "confidence": "High",
      "surprise": "High",
      "evidence": "142 of 200 sampled open deals sit in pipelines named Jetpay Registration New - DO NOT USE."
    },
    {
      "rank": 2,
      "headline": "Build the Granola → Gmail-draft + HubSpot-note loop.",
      "one_liner": "You wrote email-patterns.md from a manually iterated re-engagement play. The wiki has the playbook; the connectors are wired; only the trigger is missing.",
      "ai_mechanism": "A Claude skill triggered by Fathom recap → drafts the email + writes the CRM note.",
      "impact_metric": "~1.5 hrs/week back",
      "effort": "Low",
      "impact": "High",
      "confidence": "High",
      "surprise": "Medium",
      "evidence": "26 Fathom recordings in 30 days, zero CRM writebacks, four manual post-call recap emails authored within 7 minutes of recap."
    },
    {
      "rank": 3,
      "headline": "Replace the calendar-invite-email factory with a one-line generator.",
      "one_liner": "38 calendar-admin email threads in 30 days, all authored manually, all structurally identical.",
      "ai_mechanism": "A Claude skill that generates the right batch of internal vs external invites from one line of input.",
      "impact_metric": "~2.5 hrs/week back",
      "effort": "Low",
      "impact": "High",
      "confidence": "High",
      "surprise": "High",
      "evidence": "38% of sampled email volume is calendar admin. Michael & Son thread shows the pattern."
    }
  ],

  "why_now": "May 2026 is the inflection moment. Companies are splitting into two AI plays — use AI to do the same things slightly cheaper, or use AI to do things that were impossible last quarter. The companies pulling ahead aren't cutting headcount. They're running outbound motions no human team could sustain, building knowledge layers that compound, shipping product before competitors notice. Baseline has the connector surface to play that game. What's missing is the wiring.",

  "losing_time": [
    {
      "headline": "You author every external calendar invite by hand.",
      "one_liner": "38 invite-cancel-reschedule threads in 30 days. Michael & Son alone produced nine emails for one 30-minute call.",
      "time_cost": "2.5 hrs/week",
      "ai_fix": "a Claude skill that drafts the right batch from one line of input"
    },
    {
      "headline": "You re-author post-call emails Fathom already wrote you.",
      "one_liner": "Fathom recap arrives at 21:34, your manual external email goes at 21:41. Same content, different voice.",
      "time_cost": "1.5 hrs/week",
      "ai_fix": "a scheduled task that drafts the follow-up the moment Fathom recap lands"
    },
    {
      "headline": "Your Esker pipeline report is a 90-minute biweekly task that's already a deterministic query.",
      "one_liner": "Pull HubSpot Esker pipeline, filter to Needs Analysis+, format as ranked list, email.",
      "time_cost": "1.5 hrs/week",
      "ai_fix": "a Cowork scheduled task that runs Monday 8am and drops the formatted draft in your inbox"
    }
  ],

  "roadmap": [
    {
      "window": "Now → 3 months",
      "title": "Quick wins",
      "body": "Ship the 3 wins above. Plus: a knowledge base on the Drive that every AI tool reads from. Replace stale Notion doctrine with the canonical wiki.",
      "accent": "green"
    },
    {
      "window": "3 → 6 months",
      "title": "Skills layer",
      "body": "Custom skills for your top 5 recurring workflows: pipeline reports, post-call recap drafts, calendar admin, ticket intake, weekly research digests. Your personal cookbook.",
      "accent": "cyan"
    },
    {
      "window": "6 → 12 months",
      "title": "Scheduled tasks",
      "body": "Skills run on cron. Esker report drafts arrive Monday 8am. Daily competitive scan in your inbox at 7am. Weekly pipeline hygiene check. You wake up to drafts, not work.",
      "accent": "purple"
    },
    {
      "window": "12 months+",
      "title": "Durable agents",
      "body": "Cloud-deployed agents triggered by real-world events. New ticket → AI-drafted response in 30 seconds. New deal stage → CRM enrichment + research brief. Work happens before you sit down.",
      "accent": "brass"
    }
  ],

  "lanes": [
    {
      "name": "DIY",
      "headline": "Run /kb-build now",
      "body": "Free, ~20 min. Mining subagents read your connectors and scaffold the wiki. You own everything.",
      "cta_label": "Free path"
    },
    {
      "name": "Light-touch",
      "headline": "Have Tyler build your KB",
      "body": "Skip the learning curve. Tyler builds the foundation, hands it back, supports your team through the first month.",
      "cta_label": "Talk to Tyler"
    },
    {
      "name": "Full",
      "headline": "Engage Prescyent for the complete discovery",
      "body": "Two-layer audit. Voice-agent interviews with your team. Custom plugin built around your workflows.",
      "cta_label": "Talk to Tyler"
    }
  ],

  "path_forward": "The audit findings point at one structural pattern: every AI tool at {company} operates without a persistent context layer accessible to the team. The fix is finishing what you started — a single wiki on the Drive that every AI tool reads from, mined from your connectors, kept current automatically.",

  "tyler_brief": "Baseline Payments has a v5.0.0 structured wiki on the Drive that almost no founder builds. Their AI stack is A-grade. The bottleneck is that every workflow runs through Tyler personally instead of through deterministic automation. Three immediate wins (zombie pipeline disconnect, Granola→Gmail loop, calendar-invite generator) free up ~7 hrs/week. The bigger move is finishing the KB so Marc, JS, and Matt operate from the same canonical source. Founder, ready for Phase 1 plugins.",

  "coverage": [
    {"category": "GTM & Systems", "platforms": "HubSpot", "records_analyzed": "200 deals · 100 contacts · 10 tickets · 101 owners", "confidence": "High"},
    {"category": "Knowledge & Docs", "platforms": "Google Drive · Notion", "records_analyzed": "127 Drive files · 47 Notion pages · 11 deep reads", "confidence": "Medium"},
    {"category": "Communications", "platforms": "Gmail · Calendar · Chat · Fathom · Granola", "records_analyzed": "100+ threads · 41 meetings · 82 chat spaces · 26 Fathom recordings · 20 Granola notes", "confidence": "High"},
    {"category": "Stack", "platforms": "11 connectors visible", "records_analyzed": "Catalog scored across rubric · 2 unconnected adjacencies", "confidence": "High"}
  ],

  "dimensions": [
    {
      "title": "GTM & Systems Readiness",
      "score": 4,
      "findings": [
        {
          "severity": "Critical",
          "surprise": "High",
          "headline": "Two pipelines labeled DO NOT USE hold ~815 of 1,149 open deals (71%).",
          "recommendation": "Audit HubSpot Workflows for any create-deal action targeting pipeline IDs 10112334 or 2123176. Disable. Migrate any real records to a clean Onboarding pipeline."
        }
      ]
    }
  ],

  "conflicts": [
    {
      "topic": "Doctrine source-of-truth",
      "summary": "Drive wiki says Sandler/NEPQ. Notion superseded pages still surface Challenger framing in search.",
      "recommendation": "Adopt Drive as canonical; add hard-redirect banners on Notion.",
      "needed_decision": "30-min /wiki:review session this week."
    }
  ],

  "coverage_gaps": [
    {"gap": "Koncert (out of scope)", "impact": "SDR call activity siloed.", "fix": "Configure Koncert native HubSpot sync."},
    {"gap": "Trumpet (out of scope)", "impact": "Buyer engagement signal siloed.", "fix": "Configure Trumpet native HubSpot integration."}
  ],

  "open_questions": [
    {
      "question": "Are the HubSpot email nurture sequences actually live, or documented intent only?",
      "recommended_answer": "Spend five minutes in HubSpot > Sequences. If documented but not deployed, this is a one-step deployment of an already-written automation.",
      "needed_decision": "Confirm and either deploy or formally retire the documented sequences."
    }
  ],

  "next_steps_role_aware": "Review the Top 3 wins with your senior team this week. The zombie-pipeline fix is the single highest-surprise finding — disconnect before the next pipeline review.",

  "next_steps_connector_aware": "Connect Trumpet to HubSpot via the native integration. Buyer engagement data is the highest-intent signal in B2B payments and it's currently siloed.",

  "tan_attribution_footnote": "The zero-sum vs positive-sum framing comes from Garry Tan's February 2026 essay on AI strategy bifurcation."
}
```

### Synthesizer field notes

- **`the_answer`** — Minto Level 1. ONE contestable sentence. ≤60 words. Specific enough that someone could disagree. No hedging.
- **`scores`** — split scoring (v0.5 change). `stack` = 1-10 grade of the AI tool surface; `workflow_integration` = 1-10 grade of how those tools wire into deterministic workflows; `overall` = 0-100 weighted (`stack × 4 + workflow_integration × 6`). The split scoring resolves the v0.4 "A-grade stack + 62/100" contradiction.
- **`wins_top_3`** — exactly 3 entries. Each ≤50 words combined across `headline` + `one_liner` + `ai_mechanism`. The `ai_mechanism` field is mandatory and must name a concrete Prescyent ladder rung (skill / scheduled task / custom plugin / durable agent).
- **`losing_time`** — 3-5 entries. Each ≤40 words combined. The `ai_fix` field is mandatory.
- **`roadmap`** — exactly 4 entries (now-3mo / 3-6mo / 6-12mo / 12mo+). Each ≤50 words. Foaster-style ladder.
- **`lanes`** — exactly 3 entries (DIY / Light-touch / Full). No pricing in body copy. `cta_label` drives the button text.
- **`tyler_brief`** — 100-word executive brief that lands at the top of the analyst markdown. Buyer can copy/paste into a lead email.
- **`dimensions`** — 4 entries, one per audit category. Each finding has `severity` + `surprise` + `headline` + `recommendation`.
- **`tan_attribution_footnote`** — appears ONLY in the analyst markdown's footnote. Never named in the buyer deck. Buyer copy uses the zero-sum vs positive-sum idea without the attribution.

### Renderer responsibilities

`render_deck.py` (buyer HTML):

- Hero with `the_answer` blockquote + split-score display.
- "The 3 wins" cards built from `wins_top_3` (compressed shape).
- Mid-page CTA after the 3 wins.
- "Why this matters now" from `why_now` (no Tan name in buyer copy).
- "Where you're losing time" from `losing_time` with explicit `ai_fix` lines.
- "The path from here to AI-native" timeline from `roadmap`.
- Three lanes from `lanes`.
- Collapsed `<details>` appendix with `dimensions` + `conflicts` + `coverage_gaps` + `open_questions`.
- Canonical Prescyent footer with mailto + booking link.

`render_markdown.py` (analyst MD):

- YAML frontmatter (company, slug, dates, scores, plugin_version, contract_version).
- Top section: `tyler_brief` (100-word executive brief).
- Full report: contestable answer, top 3, why now (with Tan footnote), losing time, path forward, full per-dimension findings, conflicts, gaps, open questions, next steps.
- Plain markdown — no HTML. Suitable for `/kb-build` ingestion.
