# Subagent Output Contract

**contract_version: "3.0"**

Two contracts live in this file:

1. **Audit subagent contract** — what each `audit-*` subagent returns to the master `discover` skill.
2. **Synthesizer output contract** — the structured JSON the master skill produces for the renderers. Both renderers (`render_deck.py` for buyer HTML, `render_markdown.py` for analyst markdown) consume the same JSON. No markdown→HTML middleman.

---

## What changed vs. v2.3

- **9 audit lanes total** (was 5). Three new dedicated lanes — `audit-drive`, `audit-email`, `audit-meeting-transcripts` — split out of the v2.3 `audit-knowledge` and `audit-comms` scope. Plus a new `audit-web-search` that goes wide on the buyer's company across the open web.
- **`_trace[]` requirement on every subagent return.** Each subagent prepends a self-trace array of `{tool, args_summary, result_summary, ms, tokens_est}` rows so the orchestrator + Tyler can post-hoc-audit what every lane actually did.
- **All subagents run on Opus 4.7 by default.** Per-Task model override remains; Sonnet fallback documented in README + reachable via single sed-pass before alpha distribution.
- **3-tier depth** drives audit-meeting-transcripts mode + master resumption cap + per-lane time window:
  - Standard: 90-day window, audit-meeting-transcripts skipped or `summary_count: 10`, 1 master follow-up per subagent.
  - Medium: 12-month window, audit-meeting-transcripts summary-wide (`summary_count: 80`), 3 master follow-ups per subagent.
  - Very-deep: 12-month window, audit-meeting-transcripts summary-wide + transcript-deep (`summary_count: 120, transcript_count: 12`), 6 master follow-ups per subagent.
- **Resumption-based gap-detection pass.** After Wave 1 (all 9 subagents return), master scores each subagent for thin spots and resumes specific subagents with targeted follow-ups via `query({prompt: "Resume agent {agentId} and dig into {Q}", options: {resume: sessionId}})`. Adaptive cap by depth (above). Resume calls land in the synthesizer's new `resume_trace[]` field.
- **New synthesizer fields:** `entity_map[]` (audit-web-search), `vocabulary_primer{}`, `voice_pattern{}` (audit-email), `voice_samples[]` (audit-email + audit-drive), `email_matrix{}` (audit-email), `drive_taxonomy{}` (audit-drive), `comms_patterns{}` (audit-comms), `meeting_inventory{}` + `transcript_deep_reads[]` (audit-meeting-transcripts), `web_research{}` (audit-web-search), `citations[]` (audit-web-search + per-finding source URLs), `resume_trace[]`, `raw_subagent_dumps{}` (the full per-lane JSON, load-bearing for `/kb-build --from-discover`).
- **Markdown report becomes THE deliverable.** Target 50-100 KB / 15-25K tokens (was 15 KB / 3K tokens). Two AI consumers: Prescyent's deal-context ingestion + `/kb-build --from-discover` seed.
- **Email body inline-embeds the artifact bundle.** No more "attached" claim — Gmail MCP `create_draft` doesn't accept attachments. Markdown + HTML + JSON concatenated below the signoff with separator banners.

Backward-compat: 2.3 fixtures still parse (renderers tolerate missing v3.0 fields). New fixtures should ship at 3.0.

---

## What changed vs. v2.2

- New `audit-sessions` lane added to the audit subagent set (5th lane in v0.7). Same JSON shape; lane-specific notes in the audit-sessions addendum.
- Synthesizer contract gained `behavioral_history_findings[]` (analyst-markdown-only) and `cowork_observed: bool`.

## What changed vs. v2.1

- Added the **Synthesizer output contract** below.
- Subagent contract is unchanged in shape but the master skill inlines the contract spec into each subagent prompt at dispatch time.

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
  "_trace": [
    {"tool": "search_crm_objects", "args_summary": "deals limit:100 props:8 q1-2026", "result_summary": "612 deals, 412 with no close_date", "ms": 2300, "tokens_est": 18400},
    {"tool": "search_crm_objects", "args_summary": "deals limit:100 props:8 q2-2026", "result_summary": "489 deals, 321 with no close_date", "ms": 2100, "tokens_est": 17200}
  ],
  "contract_version": "3.0",
  "subagent": "audit-systems | audit-knowledge | audit-drive | audit-email | audit-comms | audit-meeting-transcripts | audit-stack | audit-sessions | audit-web-search",
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
      "why_now": "Fathom is connected. HubSpot deal notes are 80% empty. Template exists in the gtm-wizards plugin.",
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

- **`_trace[]`** (v3.0, REQUIRED) — array of `{tool, args_summary, result_summary, ms, tokens_est}` rows. One row per tool call the subagent makes. Adds ~1-2K tokens to the return; gains post-hoc traceability. Tyler greps `_trace[]` from the synthesizer JSON to see what each subagent actually did.
- **`behavioral_trace_findings[]`** — each item: `{ pattern, confidence, evidence }`. Cap at 10 per subagent. Patterns are inferred — phrase as "observed" not "fact".
- **`sor_pointers{}`** — object mapping field name → authoritative system. Omit the key entirely if the subagent has no SOR claims.
- **`classification`** (per finding) — default `internal`. Synthesis drops `restricted` findings entirely. Synthesis withholds `confidential` findings as Coverage Gaps with a one-line note.
- **`framework_indexes{}`** (per finding) — all four keys optional; default `null`.
- **`surprise_factor`** (per finding + per opportunity) — required.
  - **High** = required cross-source synthesis or contradicts a stated position. User almost certainly does NOT know this.
  - **Medium** = volume-driven discovery — counts, percentages, stale-records the user might know exist but hasn't quantified.
  - **Low** = obvious / known patterns. Synthesis demotes to appendix.

### audit-sessions addendum

`audit-sessions` is the v0.7 5th audit lane that sources its evidence from `mcp__session_info__list_sessions` + `mcp__session_info__read_transcript` rather than connected systems.

Lane-specific rules:

- `dimension_scores` → omit. audit-sessions does NOT score dimensions.
- `connectors_used` → use the literal string `"Cowork session history"`.
- `records_analyzed` → `{total_sessions: <int>, deep_reads: <int>, date_range: "YYYY-MM-DD to YYYY-MM-DD"}`.
- Findings describe **workflow patterns + recurrence**, not connected-system inventory. Verbatim user content is forbidden — see the audit-sessions agent file for privacy rules.
- `data_source` field on every finding reads `"Cowork session history, N matching sessions sampled at last-30-message tail"` or similar.
- Conditional dispatch: this subagent is included in Phase 3 fan-out ONLY when `mcp__session_info__list_sessions` is in the master skill's tool list. Otherwise the audit runs without this lane.

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

### audit-drive addendum (v3.0, NEW lane)

`audit-drive` is the dedicated cloud-storage lane (Google Drive / OneDrive / Dropbox / SharePoint / Box — provider-agnostic per the connected MCP). Returns the standard contract plus:

```json
{
  "drive_taxonomy": {
    "root_label": "Tyler @ Hernando Capital",
    "top_folders": [
      {"path": "/Wiki", "file_count": 47, "depth": 3, "authority_score": 9, "last_modified": "2026-04-30"},
      {"path": "/Decks", "file_count": 22, "depth": 2, "authority_score": 7, "last_modified": "2026-05-01"}
    ],
    "authority_clusters": [
      {"name": "Playbooks", "patterns": ["playbook", "doctrine", "SOP"], "page_count": 14},
      {"name": "Templates", "patterns": ["template", "draft"], "page_count": 9}
    ],
    "stale_pages": [
      {"path": "/Wiki/2024-q1-strategy.md", "last_modified": "2024-03-15", "still_referenced": false}
    ],
    "doctrine_pages": [
      {"path": "/Wiki/sales-playbook.md", "owner": "tyler@", "last_modified": "2026-04-22", "promote_to_canonical": true}
    ]
  },
  "voice_samples": [
    {"source_path": "/Drafts/2026-04-q1-recap.md", "excerpt": "5-10 sentence verbatim text excerpt that demonstrates tone"}
  ]
}
```

### audit-email addendum (v3.0, NEW lane)

`audit-email` is the dedicated email lane (Gmail / Outlook). Returns the standard contract plus:

```json
{
  "voice_pattern": {
    "formality": "casual / neutral / formal",
    "median_length_words": 87,
    "em_dash_density_per_100w": 0.4,
    "sign_off_pattern": "first-name-only",
    "lead_pattern": "lead-with-the-thing",
    "common_greetings": []
  },
  "voice_samples": [
    {"thread_id": "...", "to_domain": "...", "excerpt": "verbatim sent-thread text"}
  ],
  "email_matrix": {
    "top_inbound_senders": [
      {"sender": "alice@company.com", "volume_12mo": 312, "domain_type": "internal"},
      {"sender": "bob@partner.io", "volume_12mo": 198, "domain_type": "external_partner"}
    ],
    "top_outbound_domains": [
      {"domain": "@company.com", "volume_12mo": 2104, "dominant_thread_type": "internal-coord"}
    ],
    "sent_received_ratios": {
      "alice@company.com": {"sent": 198, "received": 312, "ratio": 0.63}
    },
    "response_time_medians": {
      "alice@company.com": "1.5h",
      "bob@partner.io": "8h"
    },
    "recurring_workflows": [
      {"pattern": "Weekly pipeline digest", "subject_template": "Pipeline week of {date}", "frequency": "weekly", "recipients": ["team@"]}
    ],
    "attachment_patterns": [
      {"to_domain": "@partner.io", "file_type": ".pdf", "volume": 22, "common_subject_pattern": "Statement of Work"}
    ]
  }
}
```

### audit-meeting-transcripts addendum (v3.0, NEW lane)

`audit-meeting-transcripts` is the dedicated meeting-transcript lane (Fathom / Granola / etc). Depth-adaptive:

- **Standard mode:** lane skipped OR `summary_count: 10` cap on most-recent meetings, no transcript deep-read.
- **Medium mode:** `summary_count: 80`, no transcript deep-read.
- **Very-deep mode:** `summary_count: 120`, `transcript_count: 12` (12 high-signal meetings get full transcripts pulled).

Returns the standard contract plus:

```json
{
  "meeting_inventory": {
    "total_meetings_12mo": 142,
    "by_counterparty": [
      {"counterparty": "Esker", "meeting_count": 8, "cadence": "monthly", "first_seen": "2025-09-12", "last_seen": "2026-04-22"},
      {"counterparty": "Internal — leadership", "meeting_count": 22, "cadence": "weekly"}
    ],
    "by_type": [
      {"type": "discovery", "count": 18},
      {"type": "review", "count": 24},
      {"type": "kickoff", "count": 6}
    ],
    "cadence_patterns": [
      {"pattern": "Every Tuesday with Esker partner team", "frequency": "weekly", "first_observed": "2025-11"}
    ]
  },
  "transcript_deep_reads": [
    {
      "recording_id": "fathom-12345",
      "title": "Esker Q1 review",
      "date": "2026-03-15",
      "duration_min": 47,
      "why_selected": "Decision: Esker partner team committed to Q2 deployment timeline",
      "key_extract": "Verbatim or near-verbatim 200-500 word excerpt of the load-bearing dialogue",
      "counterparty": "Esker"
    }
  ],
  "recurring_workflow_candidates": [
    {"workflow": "Pre-Esker-meeting prep flow", "evidence": "Same Q1 financials opener observed across 8 Esker meetings", "automation_path": "Custom skill triggered by upcoming-Esker-meeting calendar entry"}
  ],
  "voice_pattern_meeting": {
    "tone": "direct, data-led",
    "opener_pattern": "Always opens with Q1 financials",
    "closer_pattern": "Recap + next-step ownership question",
    "uncertainty_markers": ["I think we're saying...", "let me reframe that"]
  }
}
```

### audit-comms addendum (v3.0, MODIFIED — chat + calendar only; email removed; meeting-intel removed)

`audit-comms` returns the standard contract plus:

```json
{
  "comms_patterns": {
    "calendar_meeting_density": {
      "weekly_avg_meetings": 18,
      "weekly_avg_meeting_hours": 14,
      "by_quarter": {"2025-q4": 16, "2026-q1": 19, "2026-q2": 18}
    },
    "recurring_meeting_cadences": [
      {"title_pattern": "Weekly leadership", "frequency": "weekly", "attendee_count": 5}
    ],
    "chat_top_spaces": [
      {"space": "team-leadership", "30d_message_volume": 412, "active_participants": 5}
    ],
    "cross_channel_decision_flow": "Decisions surface in chat (40%), get formalized in calendar invites (30%), confirmed in meeting summaries (30%)."
  }
}
```

### audit-web-search addendum (v3.0, NEW lane)

`audit-web-search` goes wide on the buyer's company across the open web. Returns the standard contract plus:

```json
{
  "entity_map": [
    {"name": "Baseline Payments", "type": "primary", "domain": "baselinepayments.com", "description": "B2B payments processor"},
    {"name": "JetPay", "type": "product_line", "parent": "Baseline Payments", "domain": "jetpay.com"},
    {"name": "Hernando Capital Ltd.", "type": "operating_company", "relationship": "holding entity"}
  ],
  "web_research": {
    "per_entity_summaries": [
      {
        "entity": "Baseline Payments",
        "description": "B2B payments processor with merchant services + AP/AR automation reseller positioning",
        "customer_segments": ["mid-market merchants", "Esker AP/AR customers"],
        "products": ["JetPay merchant onboarding", "Esker partnership", "Direct merchant services"],
        "recent_moves": [{"date": "2026-03-15", "headline": "Esker partnership formalized", "tier": 3}],
        "team_signals": ["VP BD: Tyler Massey (LinkedIn)"],
        "risk_signals": []
      }
    ],
    "individual_operator_flag": false
  },
  "citations": [
    {"finding_id": "WEB-01", "url": "https://baselinepayments.com/", "title": "Baseline Payments — Home", "retrieved": "2026-05-02", "tier": 2}
  ]
}
```

Per-finding citations also live in `citations[]` keyed by `finding_id`. Tier ratings: 1=Authoritative (10-K, SEC), 2=Owned (company site), 3=Trade press, 4=LinkedIn/professional, 5=Community (Reddit/Discord).

### Rules

1. **Every finding must cite data.** No finding without a `data_source` field.
2. **Severity × Confidence.** Synthesis sorts by `(severity_weight × confidence_weight × impact_weight)`.
3. **Effort vs. Impact.** Every opportunity scores both. Synthesis ranks by `(impact - effort)`.
4. **No silent gaps.** If subagent didn't analyze something, it goes in `coverage_gaps`.
5. **Open questions always carry a recommended answer.**
6. **Max 10 findings, max 5 opportunities, max 10 behavioral_trace_findings per subagent.**
7. **Classification defaults to `internal`.** `restricted` never reaches the report; `confidential` surfaces as Coverage Gap only.
8. **`_trace[]` is required (v3.0).** Every subagent prepends a self-trace array showing every tool call.

---

## Synthesizer output contract

The master `discover` skill produces this structured JSON at Phase 5a. Both renderers consume it.

```json
{
  "contract_version": "3.0",
  "plugin_version": "0.8.0",
  "cowork_observed": true,
  "depth_tier": "Standard | Medium | Very-deep",

  "company_name": "Baseline Payments",
  "company_slug": "baseline-payments",
  "company_industry": "B2B payments processor",
  "audit_date": "2026-05-02",
  "depth": "Very-deep",
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
      "one_liner": "815 of your 1,149 open deals (71%) sit in pipelines explicitly labeled DO NOT USE.",
      "ai_mechanism": "One-hour HubSpot Workflows audit. Zero code.",
      "impact_metric": "~3 hrs/week back",
      "effort": "Low",
      "impact": "High",
      "confidence": "High",
      "surprise": "High",
      "evidence": "142 of 200 sampled open deals sit in pipelines named Jetpay Registration New - DO NOT USE."
    }
  ],

  "why_now": "Today is the inflection moment...",

  "losing_time": [
    {
      "headline": "...",
      "one_liner": "...",
      "time_cost": "2.5 hrs/week",
      "ai_fix": "..."
    }
  ],

  "roadmap": [
    {"window": "Now → 3 months", "title": "Quick wins", "body": "...", "accent": "green"},
    {"window": "3 → 6 months", "title": "Skills layer", "body": "...", "accent": "cyan"},
    {"window": "6 → 12 months", "title": "Scheduled tasks", "body": "...", "accent": "purple"},
    {"window": "12 months+", "title": "Durable agents", "body": "...", "accent": "brass"}
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
      "headline": "Have Prescyent build your knowledge base + skills",
      "body": "We build the knowledge base foundation plus a few custom skills mapped to your workflows. Hand it back. Support your team through the first month.",
      "cta_label": "Talk to us"
    },
    {
      "name": "Full",
      "headline": "Engage Prescyent for the complete discovery",
      "body": "Our team interviews leadership. Voice agents interview the rest of the company. Custom plugin built around how you actually run.",
      "cta_label": "Talk to us"
    }
  ],

  "vocabulary_primer": {
    "knowledge_base": "A single source on your drive every AI tool reads from.",
    "plugin": "A cookbook of capabilities tailored to your company.",
    "skill": "A single recipe in that cookbook — one workflow, one trigger.",
    "agent": "A recipe that hands itself off to other recipes when the work needs more than one step.",
    "scheduled_task": "A recipe that runs on a clock, even when you're asleep.",
    "kicker": "Each one removes a kind of toil. The audit picks the ones that hurt most this quarter."
  },

  "path_forward": "...",
  "tyler_brief": "...",
  "kb_explainer": { "what_it_is": "...", "why_now_for_company": "...", "what_youd_build": [], "how_kb_build_does_it": "..." },

  "coverage": [],
  "dimensions": [],
  "conflicts": [],
  "coverage_gaps": [],
  "open_questions": [],

  "next_steps_role_aware": "...",
  "next_steps_connector_aware": "...",
  "tan_attribution_footnote": "The zero-sum vs positive-sum framing comes from Garry Tan's February 2026 essay on AI strategy bifurcation.",

  "behavioral_history_findings": [],

  "entity_map": [
    {"name": "Baseline Payments", "type": "primary", "domain": "baselinepayments.com"},
    {"name": "JetPay", "type": "product_line", "parent": "Baseline Payments"}
  ],

  "voice_samples": [
    {"source": "audit-email", "source_ref": "thread:abc123", "excerpt": "verbatim sent-thread text", "to_domain": "@partner.io"},
    {"source": "audit-drive", "source_ref": "/Drafts/q1-recap.md", "excerpt": "verbatim drive-doc text"}
  ],

  "voice_pattern": {
    "formality": "casual",
    "median_length_words": 87,
    "em_dash_density_per_100w": 0.4,
    "sign_off_pattern": "first-name-only"
  },

  "email_matrix": {
    "top_inbound_senders": [],
    "top_outbound_domains": [],
    "sent_received_ratios": {},
    "response_time_medians": {},
    "recurring_workflows": [],
    "attachment_patterns": []
  },

  "drive_taxonomy": {
    "root_label": "...",
    "top_folders": [],
    "authority_clusters": [],
    "stale_pages": [],
    "doctrine_pages": []
  },

  "comms_patterns": {
    "calendar_meeting_density": {},
    "recurring_meeting_cadences": [],
    "chat_top_spaces": [],
    "cross_channel_decision_flow": "..."
  },

  "meeting_inventory": {
    "total_meetings_12mo": 0,
    "by_counterparty": [],
    "by_type": [],
    "cadence_patterns": []
  },

  "transcript_deep_reads": [],

  "web_research": {
    "per_entity_summaries": [],
    "individual_operator_flag": false
  },

  "citations": [
    {"finding_id": "WEB-01", "url": "https://...", "title": "...", "retrieved": "2026-05-02", "tier": 2}
  ],

  "resume_trace": [
    {
      "round": 1,
      "subagent": "audit-systems",
      "session_id": "abc-123",
      "follow_up_prompt": "You found the zombie pipelines but didn't dig into ownership. Who owns the deals in DO NOT USE pipelines?",
      "refined_finding_summary": "Of 815 zombie deals, 612 owned by 3 reps who left in Q4 2025; remainder unassigned.",
      "ms": 9300,
      "tokens_est": 12400
    }
  ],

  "raw_subagent_dumps": {
    "audit-systems": { "...full subagent JSON..." },
    "audit-knowledge": { "...full subagent JSON..." },
    "audit-drive": { "...full subagent JSON..." },
    "audit-email": { "...full subagent JSON..." },
    "audit-comms": { "...full subagent JSON..." },
    "audit-meeting-transcripts": { "...full subagent JSON..." },
    "audit-stack": { "...full subagent JSON..." },
    "audit-sessions": { "...full subagent JSON..." },
    "audit-web-search": { "...full subagent JSON..." }
  }
}
```

### Synthesizer field notes

- **`the_answer`** — Minto Level 1. ONE contestable sentence. ≤60 words. Specific enough that someone could disagree. No hedging.
- **`scores`** — split scoring (v0.5). `stack` = 1-10 grade of the AI tool surface; `workflow_integration` = 1-10 grade of how those tools wire into deterministic workflows; `overall` = 0-100 weighted (`stack × 4 + workflow_integration × 6`).
- **`wins_top_3`** — exactly 3 entries. Each ≤50 words combined. The `ai_mechanism` field is mandatory and must name a concrete Prescyent ladder rung (skill / scheduled task / custom plugin / durable agent). We-tense ("we'd want to..."), not Tyler-singular.
- **`why_now`** — boil-the-ocean framing. ≤100 words. **Do NOT name Garry Tan** in this field. **Do NOT date-stamp** ("May 2026", "Q2 2026"). Use timeless openers ("Today is the inflection moment").
- **`losing_time`** — 3-5 entries. Each ≤40 words combined. The `ai_fix` field is mandatory.
- **`roadmap`** — exactly 4 entries (now-3mo / 3-6mo / 6-12mo / 12mo+). Foaster-style ladder.
- **`lanes`** — exactly 3 entries (DIY / Light-touch / Full). No pricing in body copy. v0.8 (EM-51): Light-touch reads "Have Prescyent build your knowledge base + skills"; Full reads "leadership human discovery → voice-agent team discovery → custom plugin" — three distinct moves, not "two layers".
- **`vocabulary_primer`** (v3.0, NEW per EM-52) — object with 6 plain-English term definitions used by the deck's vocabulary primer section (between why-now and losing-time) AND by the markdown YAML frontmatter (so `/kb-build` ingests as glossary). Tyler's cookbook/recipe analogy is the basis. ~75 words rendered.
- **`tyler_brief`** — 100-word executive brief that lands at the top of the analyst markdown. Spell out "knowledge base" first mention.
- **`company_industry`** — short string ("B2B payments processor", "marina management SaaS"). Used by `draft-upsell-email` as the company-introduction seed.
- **`kb_explainer`** (v0.6, EM-39) — object with four fields used by Phase 5g.
- **`dimensions`** — 4 entries, one per audit category (or 9 in expanded mode). Each finding has `severity` + `surprise` + `headline` + `recommendation`.
- **`tan_attribution_footnote`** — appears ONLY in the analyst markdown's footnote. Never in buyer deck.
- **`cowork_observed`** (v0.7) — boolean. `true` when `audit-sessions` ran and returned at least one finding.
- **`behavioral_history_findings[]`** (v0.7) — distilled session-history patterns NOT in `wins_top_3`. Cap 3. Surfaces in analyst markdown's "Behavioral history" appendix only.
- **`entity_map[]`** (v3.0, audit-web-search) — primary entity + product lines + operating companies. Each `{name, type, domain?, parent?, relationship?, description?}`. The synthesis section explicitly names secondary entities when >1 — "For Baseline + JetPay — wire pipeline reports separately" — instead of treating the company as monolith.
- **`voice_samples[]`** (v3.0, audit-email + audit-drive) — verbatim text excerpts (5-10 sentences each) demonstrating the buyer's tone-of-voice. Used by `/kb-build` to anchor draft-skill outputs against actual voice.
- **`voice_pattern{}`** (v3.0, audit-email) — quantified voice signals: formality, median length, em-dash density, sign-off pattern.
- **`email_matrix{}`** (v3.0, audit-email) — top-20 senders, sent/received ratios, response-time medians, recurring workflows, attachment patterns.
- **`drive_taxonomy{}`** (v3.0, audit-drive) — root label, top folders, authority clusters, stale pages, doctrine pages.
- **`comms_patterns{}`** (v3.0, audit-comms) — calendar density, recurring cadences, chat top-spaces, cross-channel decision flow.
- **`meeting_inventory{}`** (v3.0, audit-meeting-transcripts) — total meetings 12mo, by-counterparty, by-type, cadence patterns.
- **`transcript_deep_reads[]`** (v3.0, audit-meeting-transcripts, very-deep mode only) — up to 12 high-signal meetings with full-transcript extracts.
- **`web_research{}`** (v3.0, audit-web-search) — per-entity summaries from open web.
- **`citations[]`** (v3.0, audit-web-search + per-finding) — keyed by `finding_id`. Tier ratings 1-5.
- **`resume_trace[]`** (v3.0, master gap-detection) — every resume call the master made: round, subagent, session_id, follow-up prompt, refined finding summary, timing.
- **`raw_subagent_dumps{}`** (v3.0) — full per-lane JSON returns (the load-bearing addition for `/kb-build --from-discover` — lets mining subagents see EVERY finding, not just synthesized Top 3 + losing_time + dimensions).
- **`lane_health[]`** (v3.0, QA-4) — connector-failure / inference-only banner. When ANY subagent returns `dimension_scores` with `score: null` OR `score: 0` AND its coverage_gaps mention "connector not accessible" / "blocked" / "not invoked" / "no records", emit a `lane_health[]` entry. Each entry: `{lane, status, headline, impact, fix}`. Status enum: `no_connector` | `blocked` | `inference_only` | `partial`. Renderers surface this as a prominent banner at the top of the deck (before the answer) AND immediately under the title in the markdown. **Hard rule:** lane_health entries SUPERSEDE silently-buried coverage_gaps for unreachable connectors. The user must see this before drawing conclusions from the audit.

### Behavioral promotion rule

When `audit-sessions` returns findings AND a behavioral finding ties a tool-source finding on `(severity, confidence, impact, surprise)` for the same `wins_top_3` slot: behavioral wins. The user has lived the workflow; "I keep doing X manually" beats "your data shows X is incomplete" at equal weight.

Findings that lose this tie-break flow to `behavioral_history_findings[]` for the analyst markdown appendix.

### Web-search behavioral promotion (v3.0)

When `audit-web-search` produces an `entity_map` with >1 entity, the synthesis report explicitly names the secondary entities in `the_answer` / `wins_top_3` / `roadmap` body — e.g. *"For Baseline + JetPay — wire pipeline reports separately"* — instead of treating the company as a single monolith. The synthesizer's entity-aware language is a hard rule when entity_map has >1 entry.

### Renderer responsibilities

`render_deck.py` (buyer HTML):

- Hero with `the_answer` blockquote + split-score display + inline SVG score bars.
- "The 3 wins" cards built from `wins_top_3`. Behavioral findings can occupy any slot per promotion rule.
- Mid-page CTA after the 3 wins.
- "Why this matters now" from `why_now` (no Tan name).
- **Vocabulary primer section (v3.0, EM-52)** — between why-now and losing-time. Renders `vocabulary_primer{}` as 6 term-definition rows + kicker. ~75 words.
- "Where you're losing time" from `losing_time` with explicit `ai_fix` lines + inline SVG hour bars.
- "The path from here to AI-native" timeline from `roadmap` rendered as Gantt-style horizontal SVG track + caption cards.
- Three lanes from `lanes` (v3.0 EM-51 copy).
- Always-visible appendix `<section>` with `dimensions` + `conflicts` + `coverage_gaps` + `open_questions`. NOT `behavioral_history_findings[]` (analyst-only). NOT raw_subagent_dumps (analyst-only).
- Canonical Prescyent footer with mailto + booking link.
- **`.cta.primary` styling (v3.0, EM-50)** — solid cyan background + near-black text + 900 weight. Hover layers gradient.

`render_markdown.py` (analyst MD) — v3.0 MAJOR REWRITE. Target output 50-100 KB:

- YAML frontmatter (company, slug, dates, scores, plugin_version, contract_version, `cowork_observed`, **vocabulary_primer inline (v3.0)**).
- Top section: `tyler_brief` (100-word executive brief).
- Full report: contestable answer, top 3, why now (with Tan footnote), losing time, vocabulary primer, path forward, full per-dimension findings, conflicts, gaps, open questions, next steps.
- **NEW v3.0 appendices** (load-bearing for `/kb-build --from-discover` ingestion):
  - `## Appendix: Entity map (web research)` — from `entity_map[]`
  - `## Appendix: Voice samples` — from `voice_samples[]`
  - `## Appendix: Tool stack matrix` — from `audit-stack` raw (classification_surface + per-connector readiness)
  - `## Appendix: Email behavior matrix` — from `email_matrix{}`
  - `## Appendix: Drive taxonomy` — from `drive_taxonomy{}`
  - `## Appendix: Calendar / chat patterns` — from `comms_patterns{}`
  - `## Appendix: Meeting transcripts` — from `meeting_inventory{}` + `transcript_deep_reads[]`
  - `## Appendix: Session history` — full session-history dump (was a sub-section in v0.7; promoted)
  - `## Appendix: Web research deep-pull` — from `web_research{}`
  - `## Appendix: Resume calls` — from `resume_trace[]`
  - `## Appendix: Citations` — from `citations[]` + per-finding source URLs
  - `## Appendix: Behavioral history` — v0.7 (unchanged)
  - `## Appendix: Raw subagent JSON` — fenced ```json blocks per subagent (last section, load-bearing for /kb-build mining)
- Verbose persona-tailored next-steps (5-10 lines, naming specific people / connectors / workflows).
- Plain markdown — no HTML. Suitable for `/kb-build` ingestion.
