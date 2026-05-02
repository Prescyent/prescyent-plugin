---
name: discover
description: >
  Reads the user's connected Cowork tools (Drive, Notion, HubSpot, Gmail, etc.)
  and produces a one-page AI readiness assessment inline in chat in about five
  minutes. Fans out four audit subagents in parallel. No drive writes unless
  the user opts in. Invoke when the user asks to "set me up", "where do I
  start", "onboard me", "audit my company", "AI readiness check", "what's our
  readiness", "we bought Claude — now what?", "run discovery", or just
  installs the plugin.
background_safe: false
---

# `/discover` — Prescyent entry point

> `background_safe: false` is load-bearing. Phase 2 explicitly invokes
> `mcp__visualize__read_me({modules: ["elicitation"]})` then `mcp__visualize__show_widget`
> to render an elicitation form, with `AskUserQuestion` as the fallback when those tools
> aren't loaded. Either rendering requires the foreground main thread.
> Do not move into a background `Task`.

You are running the buyer's first encounter with Prescyent. The deliverable is a buyer-facing marketing-style HTML deck rendered inline in chat as a Cowork artifact, plus an analyst-grade markdown report saved alongside. No drive writes unless the user opts in.

Every user-visible string passes the voice gauntlet at `../kb-builder/references/voice-rules.md` before emit. No banned words. Word budgets hold (orientation ≤155, scope ≤120, status ≤30, errors ≤20 + one recovery step).

**Empty-response contract:** every elicitation site aborts on empty input. Print `Phase 2 returned empty — aborting before any side effects` and exit. No silent defaults, no writes, no subagent dispatch. Single documented exception: the optional `verbatim_pain` field, where empty means "skip" and is logged as `verbatim_pain: null`.

If the user submits a Cowork elicitation form via Skip with `company_name` empty, apply the same contract — log and exit.

---

## Phase 1 — Orient the user

Emit the message at `references/orientation-copy.md` verbatim. Plain text only — no widget, no connector picker, no panel render. Do not call `mcp__mcp-registry__list_connectors` (it pops a UI surface in Cowork). Do not paraphrase. Do not prepend "Welcome!" or similar. Do not append process notes or subagent names.

**Do not pause for user acknowledgment after the orientation.** Move directly to Phase 2 in the same turn. The elicitation form IS the gate — the user submits, skips, or asks a question.

---

## Phase 2 — Settings + pre-detection + elicitation form

### 2a. Check settings file (silent)

Read `.claude/prescyent.local.md` if it exists. Extract:

- Company name
- User role (`founder`, `cfo`, `ops`, `sales`, `marketing`, `product`, `other`)
- Search depth (`standard` or `deep`) — default `standard`
- Known doc locations or primary pain points (optional)

A template lives at `settings/prescyent.local.md.example`.

If the settings file exists AND has at minimum `company_name` + `user_role`, **skip Phase 2c**, surface a one-line confirmation (`Found your settings file — running discovery for {company_name}.`), and proceed directly to Phase 2f.

### 2b. Pre-detect company candidates + role from connector signals

Before rendering the elicitation form, attempt to pre-populate the answers we'd otherwise have to ask. This is the "don't ask the doctor's-office question twice" pattern. Run these checks in parallel; cap total wall time at ~10 seconds:

**Company candidates** — collect up to 3, ranked by confidence:

1. **Email domain.** `mcp__41c208e8…__get_identity` returns the authenticated Fathom email. Domain → company candidate.
2. **Connected MCP scopes.** HubSpot `get_organization_details`, Notion `notion-get-teams`. Each unique org name = a candidate.
3. **Recent calendar attendees.** `list_events` last 30 days → most-frequent external domain → candidate company name.
4. **Working folder name.** Cowork session's working folder may be named after a company.
5. **Settings-file leftover.** If `prescyent.local.md` partial-exists with a `company_name` field but missing `user_role`, treat the stored name as a candidate.

Deduplicate by canonical name (lowercase, strip "Inc"/"LLC"/"Ltd"). Cap at 3 candidates. Always include "Other" as the 4th option.

**User role candidates** — collect from the same signals where possible:

- HubSpot user title (`get_user_details`).
- Email signature in last sent message (`mcp__6dc6e6dc…__search_threads from:me`).
- Job title in connected directory MCPs.

If a single role candidate emerges with high confidence, pre-select it in Phase 2c's role pill. If none emerge, no pre-selection — the user picks.

If pre-detection finds nothing useful, log it (don't surface to user) and proceed to Phase 2c with no pre-selections. Failure here is silent — never block the user on detection that didn't resolve.

### 2c. Render the elicitation form (Cowork host)

When `mcp__visualize__show_widget` is in the tool list, render the form via the elicitation module — explicit invocation, NOT inference.

**Step 1 — Fetch the elicitation spec** (first run of the session only; cache the response):

```
mcp__visualize__read_me({modules: ["elicitation"]})
```

The response is the canonical contract: required CSS class names, required data attributes, the four option formats, the locked header SVG, and the submit payload format. Build the HTML against this spec — don't guess the shape.

**Step 2 — Build the elicitation HTML** with **six** `.elicit-group` blocks. Header title: `"Discovery details"`. Submit label: `"Run discovery"`. Skip label: `"Skip — use defaults"`.

The six questions, in render order:

| # | Field (`data-name`) | Question | Type | Options |
|---|---|---|---|---|
| 1 | `company_name` | Whose company are we discovering? | plain pills | {Pre-detected candidates from Phase 2b — up to 3}; Other |
| 2 | `user_role` | Which describes you best? | plain pills | Founder / CEO; CFO / Finance lead; Head of Ops; Sales / GTM lead; Marketing lead; Product / Engineering lead; Other |
| 3 | `connectors_in_scope` | Which platforms should I search? | card pills, multi-select | One card per detected connector with friendly name + one-line subtitle (e.g. "Notion — Wiki, playbooks, briefs"; "HubSpot — CRM, deals, contacts"; "Fathom — Sales call transcripts"; "Gmail — Sent emails, voice samples") |
| 4 | `unconnected_tools` | Other tools you use that aren't connected here? | textarea | Free text. Placeholder: "e.g. Google Chat, Slack, Salesforce, Linear — I'll flag what I can't reach so you can decide whether to connect them." |
| 5 | `verbatim_pain` | Anything specific been frustrating? (Optional) | textarea | Free text |
| 6 | `depth` | How deep should the search go? | plain pills | Standard — last 90 days, ~5 min, light pass on each connector; Medium — last 12 months, ~10–15 min, summary-wide on meetings, 3 master follow-ups per lane; Very-deep — last 12 months, ~20–30 min, summary-wide PLUS transcript-deep on ~12 meetings, 6 master follow-ups per lane |

**Title text rules:**

- Q1 — exact title text: `"Whose company are we discovering?"`. No parenthetical decoration.
- Q3 — exact title text: `"Which platforms should I search?"`. No parenthetical decoration. The pre-selection behavior (every card starts selected, user deselects to exclude) is a UI behavior — do NOT echo it as title text. The inference layer should NOT add "(All pre-selected — deselect any to skip.)" or similar; render the title verbatim.
- Q6 — exact title text: `"How deep should the search go?"`. v0.8 (EM-59) drops Pro/Team/Max plan-name strings (collide with ChatGPT Pro). Labels are time + scope + behavior — universal across platforms. The three tiers drive `audit-meeting-transcripts` mode + master resumption cap + per-lane time window:

| Tier | audit-meeting-transcripts | Resume follow-ups per subagent | Time window per lane |
|---|---|---|---|
| Standard | DOES NOT FIRE (or fires with `summary_count: 10` cap) | 1 | 90 days |
| Medium | Summary-wide mode (`summary_count: 80`, no transcript deep-read) | 3 | 12 months |
| Very-deep | Summary-wide + Transcript-deep mode (`summary_count: 120, transcript_count: 12`) | 6 | 12 months |

After Q6 submission, emit a footnote in chat: *"Heads up: Very-deep reads 10× more source material across the year. If you hit a usage limit mid-audit, you'll see partial findings."*

For Q1, pre-select the highest-confidence pre-detected candidate if Phase 2b found one. If multiple candidates emerged, render them all as un-selected pills so the user picks.

For Q3, the connector list comes from a low-cost lookup at form-build time — call `mcp__mcp-registry__list_connectors` ONCE during HTML construction. **v0.8.1 (QA-Q7) fix:** iterate the response and create one pill per `connected: true` entry. Map each entry's `name` field directly to the pill label, with the `description` field (when present) as the subtitle. **Do NOT filter by tool-prefix recognition** — the v0.8 dogfood dropped Excalidraw + Firebase Hosting because Cowork-Claude's deferred-tool registry uses UUID prefixes that don't match the friendly names. If a connector is irrelevant for the audit (e.g., Excalidraw), the user can deselect it. Better to over-show than under-show.

Default state: every pill starts selected. **This is the only call to `list_connectors` in the flow** — its UI side effect lands inside the elicitation form, not as a separate panel.

If `mcp__mcp-registry__list_connectors` is unavailable, fall back to: emit Q3 as a textarea with placeholder "Which platforms should I search? (Drive, HubSpot, Notion, etc.)".

For Q6, pre-select Medium (was Standard in v0.7 — the Medium tier is the new default for v0.8 since it captures the 12-month window without the very-deep transcript-fetch overhead).

**v0.5 change:** Q3 from earlier rounds (`buyer_intent` — "What brought you here today?") is dropped. The skill's stated purpose IS AI readiness. The other intent options pulled users toward outcomes that other commands serve better (`/kb-interview` for senior knowledge capture, `/kb-build` for "make Claude useful"). `buyer_intent` is hard-coded to `ai-readiness` in the discovery_scope build at Phase 2f. Subagents no longer receive a buyer_intent field.

**Step 3 — Render**:

```
mcp__visualize__show_widget({html: "<elicitation HTML built per the spec>"})
```

**Step 4 — Read the submission**:

```
mcp__cowork__read_widget_context()
```

The response arrives as a single-line message per the spec. Parse the six fields. If the user clicked Skip with `company_name` empty, apply the empty-response contract — log `Phase 2 returned empty — aborting before any side effects` and exit. No subagent dispatch.

**After parsing, surface a coverage warning if Q4 has content:**

If `unconnected_tools` is non-empty, emit (≤40 words):

> Heads up — I won't be able to read what's in {unconnected_tools_list}. Discovery will run on what is connected; I'll flag specifically what's missing so you can decide whether to connect it for a richer audit next time.

Do NOT stonewall. Do NOT block the run.

### 2d. Fallback when elicitation unavailable (Claude Code, headless)

If `mcp__visualize__show_widget` is NOT in the tool list:

- Fall back to sequential `AskUserQuestion` calls — six questions in field order. Map the elicitation pill options 1:1 to AskUserQuestion options.
- Each call applies the empty-response contract EXCEPT Q4 (`unconnected_tools`) and Q5 (`verbatim_pain`), where empty = skip = `null`.

### 2e. Argument pre-seed

If `$ARGUMENTS` contains:

- `depth:standard` or `depth:deep` — pre-seed `depth`; skip the corresponding field/question.
- `role:<value>` — pre-seed `user_role`; skip that field/question. Valid values: `founder`, `cfo`, `ops`, `sales`, `marketing`, `product`, `other`.

Pre-seeded fields skip the empty-response contract. If all required fields are pre-seeded by args + settings + Phase 2b detection, skip Phase 2c/2d entirely.

### 2f. Build discovery_scope

After Phase 2a (settings hit) or Phase 2c/2d (elicitation/fallback) completes, build:

```jsonc
{
  "company_name": "Acme",
  "company_slug": "acme",
  "user_role": "founder",
  "connectors_in_scope": ["HubSpot", "Notion", "Drive", "Fathom", "Gmail"],
  "unconnected_tools": "Google Chat, Salesforce",
  "verbatim_pain": "Sales reps don't update HubSpot.",
  "depth": "standard",
  "today_date": "2026-05-01",
  "user_email": "<from session>",
  "known_locations": []
}
```

`company_slug` derives from `company_name`: lowercase, replace `[^a-z0-9-]+` with `-`, strip leading/trailing hyphens, collapse runs of `-`.

---

## Phase 2g — Connector pre-flight gate (v0.8.1 NEW — LOAD-BEARING)

**The problem this solves:** v0.8 dogfood surfaced 3 of 9 lanes silently failing — audit-systems / audit-drive / audit-comms each burned ~30K tokens producing inference-only fallback findings because their subagent didn't successfully reach a connector. Cowork-Claude's introspection diagnosed it as a deferred-tool schema-loading gap (Step 0 in each agent file is the agent-side fix), but we ALSO need a master-side pre-flight to catch genuine connector outages (auth expired, scope decay, MCP server down) BEFORE we burn tokens on a doomed dispatch.

**Run probes in parallel** — single message, multiple cheap MCP tool calls. Each probe is the lightest call that proves the connector is alive AND has the right scopes.

| Connector category | Probe call | Pass | Fail |
|---|---|---|---|
| HubSpot (CRM) | `get_user_details` (no params) | Response contains `userInformation.email` AND no `REQUIRES_REAUTHORIZATION` flag on the scopes the audit needs | 401 / scope error → mark audit-systems DEGRADED with specific scope ask |
| Drive | `list_recent_files(pageSize: 1)` | Response is array (even if empty) | 401 / not-connected → mark audit-drive DEGRADED |
| Gmail | `list_labels()` | Returns array including system labels (INBOX, SENT) | Auth error → mark audit-email DEGRADED |
| Notion | `notion-get-users()` | Returns user list | Auth error → mark audit-knowledge DEGRADED |
| Calendar | `list_calendars(pageSize: 1)` | Returns at least one calendar | Auth error → mark audit-comms (calendar half) DEGRADED |
| Chat (Google Chat / Slack) | `list_spaces(pageSize: 1)` | Returns array, even empty | Auth error → mark audit-comms (chat half) DEGRADED |
| Fathom | `get_identity()` | Returns `{name, email}` | Auth error → mark audit-meeting-transcripts (fathom half) DEGRADED |
| Granola | `get_account_info()` | Returns user account JSON | Auth error → mark audit-meeting-transcripts (granola half) DEGRADED |
| ZoomInfo (optional) | `search_companies(query: 'a', pageSize: 1)` OR skip if not connected | Returns array | Quota / auth → mark audit-web-search ZoomInfo-side DEGRADED, WebSearch still OK |
| Cowork sessions | `list_sessions(limit: 1)` | Returns array | Tool absent → audit-sessions skipped (already conditional in Phase 3) |

**Probe budget:** ~10 parallel calls, ~5K tokens, ~3-5 sec wall-clock. Negligible vs the ~92K we'd otherwise burn on a doomed lane.

### Pre-flight outcomes

After probes return, classify each lane as:

- **HEALTHY** — probe passed, dispatch lane normally
- **DEGRADED** — probe failed; emit a `lane_health[]` entry up front, dispatch the lane anyway with a "best-effort" note (the subagent's Step 0 ToolSearch will redundantly catch this)
- **ABSENT** — connector entirely missing; do NOT dispatch the lane (saves the doomed-fallback tokens), emit `lane_health[]` entry with `status: no_connector`

### User-facing surfacing

If `HEALTHY` lane count < 6 of 9, surface a coverage warning to the user BEFORE Phase 3 dispatch:

> Heads up — N of 9 audit lanes can't reach their data right now:
> - HubSpot: REQUIRES_REAUTHORIZATION on `crm.deals.read`. Reconnect at Cowork settings.
> - Google Drive: connector blocked. Check Cowork connector settings.
> - [other failed lanes]
>
> You can:
> 1. Reconnect and re-run /discover (faster path to a complete audit)
> 2. Proceed with the {N} healthy lanes (faster but the report will have gaps)
>
> What would you like?

If user picks (1), abort cleanly — no subagent dispatch. If user picks (2), dispatch only the HEALTHY + DEGRADED lanes (DEGRADED still gets dispatched because Step 0 in the agent will probe again — defense in depth).

If `HEALTHY` count >= 6 of 9, proceed silently to Phase 3 — the lane_health[] banner will surface the failures in the deck without blocking dispatch.

### Pre-flight cache

Cache the probe results in working state. The synthesizer at Phase 5a reads `lane_health[]` from the pre-flight + any additions from the subagents themselves (e.g., subagent ran but its Step 0 ToolSearch returned no matches → adds a `lane_health` entry). Master de-dupes.

---

## Phase 3 — Subagent fan-out (v0.8 — 9 lanes)

Dispatch the audit subagents IN PARALLEL via the `Task` tool. **Single message, all subagent calls together.** Do not serialize. Always dispatch the full set — each subagent discovers what's available in its own category and surfaces gaps in `coverage_gaps[]`.

**v0.8 expansion: 9 lanes.** Email, drive, and meeting-transcripts get DEDICATED subagents because they're the three highest-volume context surfaces. Plus `audit-web-search` to read the open web's view of the company.

**Conditional 9th lane:** `audit-sessions` runs only when `mcp__session_info__list_sessions` is in the tool list. The other 8 always dispatch.

For each subagent, the Task `prompt` includes verbatim:

- **STEP 0 directive (v0.8.1, LOAD-BEARING)** — the FIRST line of every subagent prompt must be a hard instruction to call ToolSearch with category-specific keywords BEFORE any other action. This is belt-and-suspenders alongside the agent file's Step 0 section. Without this, the dispatch prompt's lane-specific category mapping (which references tools by short name like "search_crm_objects") doesn't resolve schemas, and the subagent silently falls back to inference. Per-lane STEP 0 keyword queries:

| Subagent | STEP 0 ToolSearch query |
|---|---|
| audit-systems | `"hubspot crm deals contacts pipeline"` |
| audit-knowledge | `"notion confluence wiki search fetch pages"` |
| audit-drive | `"drive onedrive sharepoint dropbox box files folders search read"` |
| audit-email | `"gmail outlook email threads draft labels search"` |
| audit-comms | `"calendar chat slack teams events spaces messages list"` |
| audit-meeting-transcripts | `"fathom granola meeting transcript summary recordings"` |
| audit-stack | `"list_connectors registry mcp suggest"` |
| audit-sessions | `"session_info list_sessions read_transcript"` |
| audit-web-search | `"WebSearch WebFetch zoominfo company research"` |

Wrap the directive verbatim:

```
STEP 0 (CRITICAL — DO NOT SKIP, DO NOT REASON BEFORE THIS):
Before reading the rest of this prompt or doing anything else, call:

  ToolSearch({query: "<lane-specific keyword query>", max_results: 15})

Inspect the response. If it surfaces tools matching your category, proceed
to the algorithm below. If it returns NO matches, the connector for this
lane isn't available in this session — return immediately with findings
empty and coverage_gaps populated. Do NOT produce inference-only findings.
```

- `company_name`, `today_date`, `user_role`, `verbatim_pain`, `depth` from `discovery_scope`.
- The category slice it owns (see mapping below).
- **The full subagent JSON contract spec, inlined into the prompt** (NOT a path reference). The contract block from `references/subagent-output-contract.md` § "Audit subagent contract" — paste verbatim into each subagent prompt. Subagents read the contract from the prompt, not from disk.
- For `audit-sessions`: also paste the lane addendum from § "audit-sessions addendum".
- For `audit-meeting-transcripts`: pass the `mode` derived from `discovery_scope.depth`:
  - Standard → `mode: "standard"` (or skip lane entirely with `summary_count: 0`)
  - Medium → `mode: "medium"` (`summary_count: 80, transcript_count: 0`)
  - Very-deep → `mode: "very-deep"` (`summary_count: 120, transcript_count: 12`)
- For `audit-web-search`: pass `company_industry` so it can run industry-tagged web queries.
- All subagents: include the v3.0 `_trace[]` requirement — every subagent prepends a `_trace[]` array showing every tool call.
- Instruction to return JSON only, no prose, no preamble.

### Subagent → category mapping (v0.8 9-lane fan-out)

| Subagent | Category slice | Dispatch condition |
|---|---|---|
| `audit-systems` | `~~crm`, `~~project-tracker`, `~~ticketing` | Always |
| `audit-knowledge` | `~~wiki` (Notion / Confluence / etc — wiki only, drive moved out) | Always |
| `audit-drive` | `~~cloud-storage` (Google Drive / OneDrive / Dropbox / SharePoint / Box) | Always |
| `audit-email` | `~~email` (Gmail / Outlook) | Always |
| `audit-comms` | `~~chat`, `~~calendar` (chat + calendar only, email + meeting-intel moved out) | Always |
| `audit-meeting-transcripts` | `~~meeting-intel` (Fathom / Granola / etc) | Always (mode varies by depth — standard mode may skip with `summary_count: 0`) |
| `audit-stack` | All connectors visible in the session (catalog-only against the AI-readiness rubric) | Always |
| `audit-sessions` | Cowork session history (behavioral signal) | Only when `mcp__session_info__list_sessions` is in the tool list |
| `audit-web-search` | Open web (WebSearch + WebFetch + ZoomInfo when present) | Always (60-query budget per audit run) |

If a subagent finds no connected tools / no session history in its category, it returns null findings and populates `coverage_gaps[]`.

### Status update during dispatch

Emit ONE status line (≤40 words) immediately after the parallel block:

> Discovery agents reading your data. Very-deep depth runs across 12 months — should be done in 15–25 min. Medium fits in 8–10 min. Go grab a coffee or high-five a friend.

Time estimate adapts to the user's Q6 selection. Standard ~5 min, Medium ~10 min, Very-deep ~20-30 min. Do not narrate process. Do not name subagents. Do not stream sub-progress.

---

## Phase 4 — Strategic clarifications (elicitation)

When all dispatched subagents return, parse each JSON. Aggregate `findings[]`, `behavioral_trace_findings[]`, `opportunities[]`, `coverage_gaps[]`, and `open_questions[]`. If `audit-sessions` ran, set `cowork_observed: true` in the synthesizer-input working state; otherwise `false`.

**v0.5 change:** Phase 4 is no longer driven by subagent `open_questions[]`. Subagent open questions are tactical operations triage ("are these 815 records zombies or live?") — wrong altitude for a McKinsey/BCG-grade clarification moment. Subagent `open_questions[]` flow to the analyst markdown's Open Questions appendix, NOT to this elicitation.

Instead: synthesizer drafts the contestable answer + Top 3 wins INTERNALLY first (in your reasoning, not yet emitted). Then generate exactly **3 strategic clarification questions** calibrated to that internal draft.

### The strategic-question prompt

Operate as a Tier-1 strategy partner (McKinsey, BCG, Bain, Deloitte S&O, Accenture Strategy) parachuted into the business. You've reviewed the data. You've internally drafted the contestable answer + the Top 3 moves. You now want **3 questions that calibrate your final recommendation** before you write the report.

These questions:

- Operate at the same altitude as the contestable answer (Minto Level 1).
- Do NOT require the user to recall specific record counts or system minutiae.
- Surface the user's strategic frame (zero-sum vs positive-sum AI play, willingness to absorb change, real strategic priority).
- Help fork the report between zero-sum framings (small fix) and positive-sum framings (rebuild).

Question shapes that hit the bar:

- **The "real game" question.** "Looking at where your AI tools point today, the data suggests you're optimizing for [observable]. Is that the actual 12-month strategy, or are you building toward something different?"
- **The "constraint" question.** "If we automated the busywork tomorrow, what bottleneck still hurts {Company} revenue? Pipeline, people, product, or process?" (Plain English. No "AI workflow capacity" jargon — Tyler 2026-05-01: *"AI workflow capacity, I don't think that really means a whole lot to people. I don't even know what AI workflow capacity is."*) Alternative shapes: "If your team got 10 hours back per person per week, what's the lever they couldn't pull yet?" / "If everything routine got handled by Claude tomorrow, what's the constraint that still slows you down?"
- **The "willingness" question.** "How much org-design change can absorb in the next 90 days? Optimize inside current workflows, or rebuild?"

Question shapes that DO NOT hit the bar (these are tactical triage — DO NOT use):

- "The 815 deals in DO NOT USE pipelines — what are they?" (operations question)
- "Daily GTM Huddle ran 9 times in 30 days — what's happening on those calls?" (process question)
- "Stale Qualified deals — gate stage or placeholder?" (admin question)

### 4a. Render the strategic-clarification elicitation form

If `mcp__visualize__show_widget` is available, render an elicitation form. Title: `"Three things to lock in"`. Submit label: `"Use these"`. Skip label: `"Skip — write the report as-is"`.

Each clarification becomes one `.elicit-group` block. Use plain pills. The synthesizer's hypothesis (the answer it would write if no clarification came back) is the pre-selected pill default. Always include an "Other / not sure" pill that maps to `null`.

Example structure:

| Field key | Question | Type | Options (synthesizer hypothesis pre-selected) |
|---|---|---|---|
| `clarification_1_real_game` | The data points at workflow consolidation as the real game. Confirm? | plain pills | Yes — that's the play (recommended); Different — we're optimizing for headcount cost; Different — we're going for net-new revenue; Other / not sure |

Render via the same explicit `mcp__visualize__read_me({modules: ["elicitation"]})` then `mcp__visualize__show_widget` pattern as Phase 2.

Read responses via `mcp__cowork__read_widget_context()`. Parse. Incorporate into synthesis — each confirmed pill firms up the report's framing; each "Other / not sure" downgrades the matching synthesis claim.

### 4b. Fallback when elicitation unavailable

If `mcp__visualize__show_widget` is NOT in the tool list, fall back to plain text:

> Three things to lock in before I write the report:
>
> 1. {strategic question 1} (my read: {synthesizer hypothesis})
> 2. {strategic question 2} (my read: {synthesizer hypothesis})
> 3. {strategic question 3} (my read: {synthesizer hypothesis})

User answers conversationally. Empty/skip = synthesizer ships its hypothesis as-is, with a soft hedge in the report.

### 4c. Skip when synthesizer has high confidence

If the synthesizer's internal draft has uniformly high confidence across the contestable answer + Top 3 (no genuine forks to clarify), skip Phase 4 entirely. Move directly to Phase 5. Don't ask three questions just because the rubric says you should — three weak questions is worse than zero strong ones.

---

## Phase 5 — Synthesize, render two artifacts, run reviewer

### 5a. Synthesize the structured JSON

The synthesizer produces a single structured JSON object that drives BOTH renderers (deck + markdown). Shape per `references/subagent-output-contract.md` § "Synthesizer output contract" (contract_version 3.0).

**Synthesis anti-pattern block (v0.8 — lifted from enterprise-search plugin):**

Do NOT:
- List results source by source (write the SYNTHESIZED finding, not the per-subagent dump — that's the appendix's job)
- Include irrelevant results just because they matched a keyword
- Bury the answer under methodology explanation
- Present conflicting info without flagging the conflict
- Omit source attribution
- Present uncertain information with the same confidence as well-supported facts

**Confidence-tagged language (v0.8):**

- **High confidence** → direct claim ("HubSpot has 412 deals with no close date.")
- **Moderate confidence** → "based on the discussion in #engineering last month, the team was leaning toward..."
- **Low confidence** → "...The information may be outdated. You might want to check with the team for current status."

Required fields (v3.0 — see contract spec for full list including v0.8 additions):

- `the_answer` — Minto Level 1. ONE contestable sentence. ≤60 words.
- `scores` — split scoring: `stack` (1-10 grade of AI tool surface), `workflow_integration` (1-10 grade of how tools wire into deterministic workflows), `overall` (0-100 weighted: `stack × 4 + workflow_integration × 6`), `interpretation` (one-line tied to overall band).
- `wins_top_3` — exactly 3 entries. Each `{rank, headline, one_liner, ai_mechanism, impact_metric, effort, impact, confidence, surprise, evidence}`. The `ai_mechanism` field is mandatory and names a concrete Prescyent ladder rung (Claude skill / scheduled task / custom plugin / durable agent). Total word budget per win ≤50 words across `headline + one_liner + ai_mechanism`. We-tense ("we'd want to..."), not Tyler-singular.
- `why_now` — boil-the-ocean framing. ≤100 words. **Do NOT name Garry Tan in this field**. **Do NOT date-stamp the framing**. Use timeless openers: "Today is the inflection moment", "Right now is where companies split", "We're at the moment AI strategies are bifurcating."
- `losing_time` — 3-5 entries. Each `{headline, one_liner, time_cost, ai_fix}`. The `ai_fix` field is mandatory.
- `roadmap` — exactly 4 entries (now-3mo / 3-6mo / 6-12mo / 12mo+). Each `{window, title, body, accent}` with accent ∈ {`green`, `cyan`, `purple`, `brass`}.
- `lanes` — exactly 3 entries (DIY / Light-touch / Full). v0.8 (EM-51) lanes copy:
  - **DIY** — `headline: "Run /kb-build now"`. Body: `"Free, ~20 min. Mining subagents read your connectors and scaffold the wiki. You own everything."` cta_label: `"Free path"`.
  - **Light-touch** — `headline: "Have Prescyent build your knowledge base + skills"`. Body: `"We build the knowledge base foundation plus a few custom skills mapped to your workflows. Hand it back. Support your team through the first month."` cta_label: `"Talk to us"`.
  - **Full** — `headline: "Engage Prescyent for the complete discovery"`. Body: `"Our team interviews leadership. Voice agents interview the rest of the company. Custom plugin built around how you actually run."` cta_label: `"Talk to us"`. Three distinct moves — leadership human discovery → voice-agent team discovery → custom plugin — NOT "two layers" (the v0.7 wording was confused).
- `vocabulary_primer` (v0.8 NEW — EM-52) — object with 6 plain-English term definitions used by the deck's vocabulary primer section AND markdown YAML frontmatter glossary:
  ```json
  {
    "knowledge_base": "A single source on your drive every AI tool reads from.",
    "plugin": "A cookbook of capabilities tailored to your company.",
    "skill": "A single recipe in that cookbook — one workflow, one trigger.",
    "agent": "A recipe that hands itself off to other recipes when the work needs more than one step.",
    "scheduled_task": "A recipe that runs on a clock, even when you're asleep.",
    "kicker": "Each one removes a kind of toil. The audit picks the ones that hurt most this quarter."
  }
  ```
- `tyler_brief` — 100-word executive brief.

**Web-search entity-aware language (v0.8):** When `audit-web-search` produces an `entity_map` with >1 entity, the synthesis explicitly names the secondary entities in `the_answer` / `wins_top_3` / `roadmap` body — e.g. *"For Baseline + JetPay — wire pipeline reports separately"* — instead of treating the company as a single monolith. Hard rule when entity_map has >1 entry.

**Lane health banner (v0.8 QA-4 — LOAD-BEARING).** Before writing any synthesis copy, scan every subagent return for connector-failure signals:

- `dimension_scores.*.score == null` AND `dimension_scores.*.confidence == "Low"` AND `coverage_gaps[].gap` mentions "connector not accessible" / "no MCP" / "blocked" / "not invoked" / "no records analyzed"
- `records_analyzed.total_records == 0` AND the connector was supposed to be active
- Subagent's `_trace[]` shows zero successful tool calls against the expected connector category

For each lane that triggers, emit a `lane_health[]` entry:

```json
{
  "lane": "audit-systems",
  "status": "no_connector",
  "headline": "HubSpot connector wasn't reachable",
  "impact": "GTM/Systems findings are inferred from your verbatim pain + industry baselines for sub-10-person merchant services firms. No record-level hygiene metrics computed.",
  "fix": "Connect HubSpot in your Cowork session settings and re-run /discover for a real read."
}
```

Status enum: `no_connector` (connector not in tool surface) | `blocked` (auth/permission denied) | `inference_only` (subagent ran but fell back to generic patterns) | `partial` (subagent got partial data — e.g., 1 of 4 quarters succeeded).

**Synthesis voice with active lane_health entries:** any wins_top_3 / losing_time / dimensions content that derives from a lane with active lane_health MUST carry an inference hedge in `confidence` (downgrade to Low) and the rationale field should mention it. Don't bury connector failures in the appendix — the banner is mandatory whenever a lane fell back.
- `coverage` — 4 entries (one per audit category) with `{category, platforms, records_analyzed, confidence}`.
- `dimensions` — 4 entries (one per audit category) with `{title, score, findings[]}`. Each finding `{severity, surprise, headline, recommendation}`.
- `conflicts` — list of `{topic, summary, recommendation, needed_decision}`.
- `coverage_gaps` — list of `{gap, impact, fix}`. Withhold `confidential` findings and surface them here as `{gap: "Confidential signal detected", impact: "...", fix: "Surfaced only in private analyst review"}`. Drop `restricted` findings entirely.
- `open_questions` — list of `{question, recommended_answer, needed_decision}`. This is where subagent `open_questions[]` flow.
- `next_steps_role_aware` — one-line tailored next step based on `user_role`.
- `next_steps_connector_aware` — one-line tailored next step based on biggest unconnected platform.
- `tan_attribution_footnote` — Garry Tan attribution string, surfaces ONLY in the analyst markdown footnote, NEVER in the buyer deck.
- `cowork_observed` (v0.7) — boolean. True when `audit-sessions` ran and produced findings. Renderers tag the analyst markdown frontmatter with this so downstream `/kb-build` knows session-history evidence informed the report.
- `behavioral_history_findings[]` (v0.7) — distilled session-history patterns that did NOT win a `wins_top_3` slot. Cap at 3. Each `{pattern, confidence, evidence}`. Surfaces in the analyst markdown's "Behavioral history" appendix only — NEVER in the buyer deck.

**Behavioral promotion rule (v0.7):** when `audit-sessions` returned findings AND a behavioral finding ties a tool-source finding on `(severity, confidence, impact, surprise)` for the same `wins_top_3` slot — the behavioral finding wins the slot. The user lived the workflow; "I keep doing X manually" beats "your data shows X is incomplete" at equal weight. Findings that lose the tie-break flow into `behavioral_history_findings[]` instead of being dropped.

**Persona-tailoring** based on `discovery_scope.user_role`:

| Role | Lead the synthesis with | Avoid leading with |
|---|---|---|
| `founder` / `cfo` | Cost, risk, time-to-value, $/month implications | Technical debt, integration patterns |
| `sales` / `marketing` | Pipeline impact, conversion, time-saved-per-rep | API scopes, data hygiene minutiae |
| `ops` | Process visibility, hygiene gaps, automation candidates | Brand voice, conversion |
| `product` / `other` (technical) | Tech debt, integration risk, build-vs-buy, agentic patterns | Generic risk statements |
| `other` (non-technical default) | Treat as `founder` |

**Voice gauntlet on every field. No banned words. Em-dash density ≤1 per 100 words. AI-translation present on every win + every losing-time entry.**

### 5b. Write the structured JSON to disk

Write the synthesizer output to the Cowork session's writable working directory. **Do NOT use `/tmp/`** — Cowork sandbox blocks writes outside connected folders.

```bash
SLUG="{company_slug}"
DATE="{today_date}"
JSON_PATH="{cwd}/prescyent-discovery-${SLUG}-${DATE}.json"
MD_PATH="{cwd}/prescyent-discovery-${SLUG}-${DATE}.md"
HTML_PATH="{cwd}/prescyent-discovery-${SLUG}-${DATE}.html"
```

Where `{cwd}` is the Cowork session's current working directory (typically `outputs/` inside the session sandbox). Use relative paths if absolute resolution is uncertain — the renderers handle path expansion.

Use the `Write` tool to save the synthesizer JSON to `JSON_PATH`.

### 5c. Render both artifacts

Run both renderers from the JSON. Both are pure-stdlib Python.

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/discover/scripts/render_markdown.py" \
  --input  "${JSON_PATH}" \
  --output "${MD_PATH}"

python3 "${CLAUDE_PLUGIN_ROOT}/skills/discover/scripts/render_deck.py" \
  --input  "${JSON_PATH}" \
  --output "${HTML_PATH}"
```

Each script reads the JSON, builds its target artifact directly from structured fields (no markdown→HTML middleman, no token-injection from markdown blobs), and writes the output.

### 5d. Run the deck reviewer

Dispatch the `audit-deck-reviewer` subagent via `Task` to validate the rendered HTML deck before showing it to the user.

```
Task(
  subagent_type: "prescyent-plugin:audit-deck-reviewer",
  description: "Review the buyer deck before final output",
  prompt: "{verbatim instructions including deck_path, synthesizer_json_path, iteration: 1}"
)
```

The reviewer returns structured JSON with `verdict`, `hard_fails[]`, `soft_warns[]`, `stats{}`. Decision tree:

**Sidecar `_review.json` — always written (v0.8 EM-42).** Regardless of verdict, hard_fails, or soft_warns, write a sidecar `_review.json` next to the deck. Costs ~120-400 bytes per run; gains durable reviewer telemetry. The sidecar captures the full reviewer JSON return for Tyler's post-hoc audit.

- **If `verdict: ship` AND `hard_fails: []`** → proceed to Phase 5e (gap-detection + resumption pass). Sidecar already written above.
- **If `verdict: regenerate` AND `iteration < 3`** → for each `hard_fail`, fix the underlying issue:
  - `RENDER_*` codes → typically a renderer or template bug. Read the failing pattern, patch in the JSON synthesizer output if the data is wrong, or re-run the renderer if the bug is transient.
  - `MISSING_AI_MECHANISM` / `MISSING_AI_FIX` → re-run synthesis with explicit "every win must have ai_mechanism, every losing_time must have ai_fix" reminder. Update the JSON, re-render.
  - `MISSING_CTA` → check the template + footer were correctly applied; re-render.
  - `APPENDIX_OPEN_BY_DEFAULT` → renderer bug; report and ship at iteration 3.
  - `TAN_NAME_IN_BUYER_COPY` → re-write the offending field (`why_now` typically), regenerate JSON, re-render.

  Re-dispatch the reviewer with `iteration: 2`. Cap at 3 iterations.
- **If `iteration == 3` AND hard_fails persist** → ship anyway with a short user-visible note: `The audit's ready, but I caught a couple of polish items I couldn't fix in this session. The deck is below; the full report is saved alongside.` Log the unfixed `hard_fails` to the sidecar `_review.json`.

### 5e. Gap-detection + resumption pass (v0.8 NEW)

After Wave 1 (all 9 subagents return), run an internal critique BEFORE displaying the artifact. This is the v0.8 quality lever — closes the surface-level gap that Round 6 EM-58 flagged.

**Algorithm:**

1. **Score each subagent's output** for thin spots, contradictions, missing entity coverage. Examples of thin spots:
   - audit-systems mentioned the zombie pipeline but didn't dig into ownership distribution.
   - audit-email's voice_pattern is empty (didn't sample sent threads).
   - audit-web-search returned <3 entities for a known multi-entity company.
   - audit-meeting-transcripts in very-deep mode returned <8 transcript_deep_reads.
   - audit-drive returned drive_taxonomy without doctrine_pages identified.

2. **For each thin spot, resume the responsible subagent** with a targeted follow-up question via the SDK's documented resume pattern:

   ```
   query({
     prompt: "Resume agent {agentId} and dig into {specific question}",
     options: { resume: sessionId }
   })
   ```

   Subagents retain their full prior conversation, all tool calls, and all reasoning. The follow-up is a continuation, not a new dispatch.

3. **Cap follow-ups by depth tier** (Tyler 2026-05-02: *"set it at four, set it at six. Like go wild."*):
   - **Standard:** 1 follow-up per subagent (9 max)
   - **Medium:** 3 follow-ups per subagent (27 max)
   - **Very-deep:** 6 follow-ups per subagent (54 max)

4. **Each resume call adds to `resume_trace[]`** in the synthesizer JSON: `{round, subagent, session_id, follow_up_prompt, refined_finding_summary, ms, tokens_est}`.

5. **Re-run synthesis** on the post-follow-up consolidated finding set. Update `the_answer`, `wins_top_3`, `losing_time`, etc. with the deeper signal.

6. **Re-run the deck reviewer** if the synthesis changed any rendered field. Re-render the deck + markdown if reviewer iteration was triggered.

This is the v0.8 quality lever. Wider fan-out makes the audit go wider; resumption makes it go deeper without spinning up new subagents that lack context. SpaceX-ethos.

### 5f. Display inline as a Cowork artifact (mandatory)

If `mcp__cowork__create_artifact` is in the tool list, render the HTML buyer deck as a Cowork artifact. The artifact IS the primary deliverable.

```
mcp__cowork__create_artifact({
  type: "text/html",
  title: "{company_name} · AI Readiness Audit",
  content: "<contents of HTML_PATH>"
})
```

If `mcp__cowork__create_artifact` is NOT available (Claude Code, headless), fall back to:

- Surface the HTML path so the user can open it: `Open your custom audit page at: {HTML_PATH}`.

**Closing chat copy (v0.8 — EM-41/EM-47/EM-53 cleanup):**

> Your custom audit page is above. Skim the 3 wins and the roadmap — that's where the value is.

**Lane-health pre-amble (v0.8 QA-4).** If the synthesizer emitted `lane_health[]` entries (one or more lanes ran without their data source), prepend the closing chat copy with a heads-up BEFORE the artifact-render line. Concrete example for the v0.8 Baseline run that surfaced HubSpot + Drive failures:

> Heads up before you read the deck — two lanes ran without their data source: HubSpot wasn't reachable, and Google Drive was blocked. Findings on those lanes are inference-only. Connect both and re-run for a real read.

The user sees this BEFORE the deck renders so they don't draw conclusions from inference-only findings. The same warning lives at the top of the deck (banner) and at the top of the markdown (immediately under the title).

That's it. Do NOT emit:
- The "saved to {MD_PATH} if you want to forward it" line (EM-41 — Cowork's create_artifact emits its own link to the markdown; ours is redundant).
- The "Open full-screen in Chrome → file://..." line (EM-53 — Cowork's create_artifact emits its own clickable "View your audit deck" link; file:// links don't render clickable in Cowork chat anyway).
- Any "open in your browser for the full layout" or "read the markdown if you prefer flat text" disclaimers — the artifact IS the deliverable.

### 5g. Inline answer + Top 3 hook (post-artifact)

After the artifact renders, print the contestable answer + Top 3 wins as inline chat text. The hook gives the user something to anchor to in the chat history without re-scrolling the artifact:

> **The answer:** {Minto Level 1 sentence verbatim from the synthesizer}
>
> **Three wins this quarter:**
> 1. {wins_top_3[0].headline}
> 2. {wins_top_3[1].headline}
> 3. {wins_top_3[2].headline}

### 5h. Knowledge-base explainer (v0.6 — EM-39)

Before Phase 6 fires the next-step elicitation, emit a 4-paragraph explainer in chat that introduces what a knowledge base is, why it specifically helps THIS company, what they'd build, and how `/kb-build` does it. Each paragraph pulls from synthesizer JSON fields — no hard-coded copy. Persona-tailored.

```markdown
**What's a knowledge base?**

A single source on your {storage — Drive / OneDrive} that every AI tool reads from. Karpathy-style — structured pages your team writes once, that compound across every Claude session, every employee, every quarter.

**Why now for {company_name}?**

The audit found {pull from `the_answer`'s second clause + the highest-cost `losing_time` entry — 1-2 sentences}. A knowledge base directly fixes that — {specific reasoning tied to audit data: e.g., "your post-call email loop needs a place to read your tone-of-voice and your customer-segment patterns from"}. Without it, every workflow on the roadmap above runs cold every time.

**What you'd build:**

- {KB page 1 — derived from wins_top_3[0].ai_mechanism + the underlying pain it solves. e.g., "Esker pipeline doctrine — so the Monday report draft has context for stage hygiene + Virginie's review pattern"}
- {KB page 2 — same pattern for wins_top_3[1]}
- {KB page 3 — same pattern for wins_top_3[2]}
- {KB page 4 — pulled from the highest-surprise dimension finding, e.g., "Customer onboarding patterns — so support ticket triage knows when to escalate to Elsy/Georgina"}

**How `/kb-build` does it:**

Mining subagents read your connectors. They distill what's already there into typed pages. Then `/kb-interview` adds the parts that only live in your team's heads — 30-min voice conversations with {role-aware list: founder/cfo → "your senior team"; sales → "your top reps + closers"; ops → "your process owners"} that fill the gaps. The whole thing takes about a week.
```

The synthesizer fills these placeholders during Phase 5a; the explainer ships as part of the synthesis output (new field `kb_explainer` in the JSON contract — see updated subagent-output-contract.md). If `kb_explainer` is empty (synthesizer didn't generate it), Phase 5g emits a generic shorter version instead, then continues to Phase 6.

---

## Phase 6 — Recommended next step + secondary options (elicitation)

Frame building the knowledge base as the recommended action. The Phase 5h explainer above sold the user on what a knowledge base is and why it fixes their specific pain — Phase 6 closes the loop with three paths.

**ASST #6 bridge sentence (v0.8 — EM-49).** Before rendering the form, emit a chat lead-in that bridges from the Phase 5h explainer to the action:

> Pick a path. The recommended one opens `/kb-build` in a fresh Cowork project session, where the mining subagents read your connectors and turn the knowledge-base pages above into a real wiki you can self-serve from. Each phase gets its own session so token budget stays tractable.

~50 words, two sentences, trades terse for concrete mechanism.

Render Phase 6 as an elicitation form. Title: `"Next step"`. Submit label: `"Go"`. Skip label: `"Skip — close the audit"`.

**Form structure:**

| Field key | Question | Type | Options (recommended pre-selected) |
|---|---|---|---|
| `primary_action` | Ready to build your knowledge base? | plain pills | Yes — open `/kb-build` in a new session (recommended); Yes — chain inline (I have token room); Yes — save the audit first, I'll start later; No — close the audit here |
| `secondary_actions` | Anything else you want us to do with this report? | plain pills, multi-select | Save markdown + HTML to my drive; Draft a follow-up email to us at Prescyent; Send to a teammate (paste their email below) |
| `teammate_email` | Teammate email (optional) | textarea | (free text, only used if "Send to a teammate" is selected) |

**v0.6 change (EM-31, EM-38, EM-29):**

- Question 1 spells out "knowledge base" instead of using the `KB` abbreviation.
- Recommended primary action is now `"Yes — open /kb-build in a new session"` — NOT inline chain. `/kb-build` is token-heavy (mining subagents + graph synthesis); chaining inline can push a Cowork session past 500K tokens. Opening in a new Cowork project session (with a dedicated working folder) keeps each phase tractable AND gives `/kb-build` a real folder to write the wiki into.
- Inline chain stays available as a secondary opt-in for users who explicitly know they have token room.
- "Anything else you want me to do" → "Anything else you want us to do" (we-tense per EM-29).
- "Draft a follow-up email to tyler@prescyent.ai" → "Draft a follow-up email to us at Prescyent" (we-tense + drops the bare email address from buyer-facing copy).

If `mcp__visualize__show_widget` is unavailable, fall back to plain text:

> The path forward is `/kb-build` — the audit's "How to climb the ladder" + the explainer above make the case. Reply with one of:
>
> - "go" — open `/kb-build` in a new Cowork project session (recommended). I'll save the audit + give you a paste-able prompt.
> - "inline" — chain `/kb-build` here (heads up: this Cowork session is already token-heavy)
> - "save" — save markdown + HTML to my drive
> - "email" — draft a follow-up email to us at Prescyent
> - "send to {email}" — send to a teammate
> - "skip" — close the audit here

Empty response = abort cleanly per the empty-response contract.

### Primary action — Open `/kb-build` in a new session (recommended)

If `primary_action = "Yes — open /kb-build in a new session"`:

1. Confirm the markdown report is saved at `{MD_PATH}` (Phase 5b already wrote it).
2. If the user did NOT also pick the "Save markdown + HTML to my drive" secondary action, surface a one-line nudge: `"Save the audit to your drive too — your future Cowork session won't have access to this Cowork sandbox."` Then run the save flow (request directory consent, write files).
3. Emit the seed-prompt handoff message:

   ```
   The audit is saved at {drive_path}. To build your knowledge base:
   
   1. Open a new Cowork session inside a Cowork PROJECT (not a one-off chat). Projects give /kb-build a real working folder it can write the wiki into.
   2. Paste this prompt:
   
      /kb-build --from-discover {drive_path}
   
   That hands /kb-build the audit context — company name, role, scope — so it skips the preflight and goes straight to scaffolding.
   ```

4. End the Phase 6 flow. Phase 7 (closing handoff) can still emit the settings-file hint if Phase 2c ran.

### Primary action — Chain inline (secondary opt-in)

If `primary_action = "Yes — chain inline (I have token room)"`:

1. Surface a one-line warning: `"Heads up — /kb-build runs mining subagents + graph synthesis. If this session is past 200K tokens, you may hit limits. Switch to a new session if anything stalls."`
2. Invoke `/kb-build --from-discover {MD_PATH}`. Control transfers to `/kb-build`; Phase 7 below is skipped.

### Primary action — Save first, start later

If `primary_action = "Yes — save the audit first, I'll start later"`:

1. Run the save-to-drive flow.
2. Emit the same seed-prompt handoff as the recommended path (so the user has the exact paste-text when they're ready).
3. End Phase 6. Phase 7 fires.

### "No — close the audit here" (v0.8 — EM-48)

ASST #7 just confirms saves + draft email if those secondary actions ran. **Do NOT emit the `/kb-build --from-discover` seed prompt.** The user explicitly said no. Drop the handoff. Go directly to Phase 7.

### Option — Save to drive

If `secondary_actions` includes `"Save markdown + HTML to my drive"`:

- If `mcp__cowork__request_cowork_directory` is available, request directory consent.
- If granted, write `{HTML_PATH}` and `{MD_PATH}` to the granted folder as `prescyent-discovery-{slug}-{date}.{html,md}`.
- If declined, surface ("Saved to chat only — re-run later when you're ready") and skip.

### Option — Draft email to us at Prescyent

If `secondary_actions` includes `"Draft a follow-up email to us at Prescyent"`:

Chain to `skills/draft-upsell-email/SKILL.md`. Pass these inputs:

- `company_name`
- `company_industry` — pulled from the synthesizer's company-context inference (audit-stack subagent populates from connector signals).
- `report_path_html` — the drive path if Save was also selected, else the sandbox path
- `report_path_md` — same logic
- `session_audit_log_path` — passed only if `userConfig.attach_session_log == true`. Path to the current Cowork session's `audit.jsonl`.
- `the_answer` — the Minto Level 1 sentence
- `wins_top_3` — the ranked Top 3 from synthesis
- `overall_score` — integer 0–100
- `tyler_brief` — the 100-word executive brief (seed for the email body — `draft-upsell-email` rewrites into buyer-frame voice with company introduction prepended)

`draft-upsell-email` (v0.6, EM-36 + EM-37) attaches `report_path_md` + `report_path_html` to the draft. If `session_audit_log_path` was passed, attaches that too. Body is rewritten in buyer-frame voice: 1-2 sentence company introduction, then "we're considering acting on these three…" framing, closing with "Open to a 30-min call to discuss whether your engagement model fits this stage of the work" + booking link. Skill never sends; draft lands in user's mail-MCP draft folder.

### Option — Send to teammate

If `secondary_actions` includes `"Send to a teammate"` AND `teammate_email` is non-empty:

Chain to `skills/draft-upsell-email/SKILL.md` with the teammate email as the `to` field. Same drafting flow + same attachments (md + html; audit log NOT attached when sending to a teammate, regardless of `attach_session_log` flag — the audit log is for Prescyent dogfood only). Never sends.

---

## Phase 7 — Closing handoff (v0.8 — branches on Phase 6 primary_action)

If the user picked `"Yes — chain inline (I have token room)"` in Phase 6, skip this phase — `/kb-build` owns the next moment.

If the user picked `"No — close the audit here"` (v0.8 EM-48), do NOT emit the seed prompt. Phase 7 just confirms saves + draft email if those secondary actions ran:

> {Saves confirmed if the user picked the save secondary action.} {Email draft confirmed if the user picked the draft-upsell-email secondary action.} You're set.

Otherwise (user picked `"Yes — open /kb-build in a new session"` or `"Yes — save the audit first"`), emit the closing handoff (≤90 words, voice-checked):

> Your custom audit page is above. The path forward is `/kb-build` — turn this into a living knowledge base every Claude session reads from. Open a new Cowork project session and paste:
>
>     /kb-build --from-discover {MD_PATH}
>
> That's the **Map** + **Build** step. **Deliver** is what we do together once the knowledge base is in your hands.
>
> Want to skip the scope questions next time? Save your answers at `.claude/prescyent.local.md` — there's a template at `settings/prescyent.local.md.example` in this plugin.

The settings-file hint only emits IF Phase 2c actually ran (the user answered scope questions in this session). If Phase 2a hit and the settings file already existed, drop the third paragraph.

**v0.6 change (EM-31 + EM-38):** "wiki" replaced with "knowledge base" (first mention spells it out; subsequent mentions in the same paragraph can abbreviate). Closing handoff now points at opening a new Cowork project session for `/kb-build`, matching the Phase 6 recommended primary-action flow.

If `mcp__plugins__suggest_plugin_install` is available, also surface a plugin-install card pointing at `prescyent-plugin`.

---

## Voice gauntlet — every string before emit

(Full rules at `../kb-builder/references/voice-rules.md`.)

1. Help the reader feel more excited / trusting? If no, cut.
2. About them or about us? If us, flip.
3. Jargon a mid-market exec wouldn't say? Replace.
4. Banned word present? Fix.
5. Implementation detail that doesn't change their next move? Strip.
6. Under the word budget? Orientation ≤155, scope ≤120, status ≤30, errors ≤20 + one recovery step.
7. **Boil-the-ocean check:** does this string frame the reader as positive-sum (attempt things previously impossible) or zero-sum (do the same thing cheaper)? If zero-sum, rewrite.
8. **AI-translation check (v0.5):** every problem named in the buyer deck has an explicit AI mechanism translation (skill / scheduled task / custom plugin / durable agent). If a problem appears without a fix mechanism, rewrite.
9. **Tan-attribution check (v0.5):** "Garry Tan" or "Tan" never appears in buyer-facing copy (deck HTML, chat text). Tan attribution is allowed in the analyst markdown footnote only.

Pass all nine — ship. Fail one — rewrite.

---

## Failure modes

- **Subagent times out** (>maxTurns or >5 min wall clock): continue with the others. Flag the missing slice in Coverage Gaps. Do not retry.
- **Subagent returns malformed JSON:** include the raw return verbatim in Coverage Gaps. Do not retry. Do not fabricate findings.
- **All four subagents return zero findings:** emit (≤30 words):
  > Your connectors didn't surface enough signal for a useful read. Connect more tools — or run `/kb-build` to capture knowledge directly from your team via interview.
- **Render script (`render_deck.py` or `render_markdown.py`) fails:** save the JSON and the markdown anyway. Surface the markdown path and the stderr. If the deck failed but the markdown succeeded, ship the markdown via inline code block + offer to re-run the deck.
- **Deck reviewer dispatched but returns malformed JSON:** ship the deck without the validation gate; log the reviewer's raw output to `_review.json` for Tyler.
- **`mcp__cowork__create_artifact` unavailable:** fall back to printing the file path with affirmative copy ("Your custom audit page is at: {HTML_PATH}"). No "flat text" disclaimer.
- **`mcp__visualize__show_widget` unavailable** (Claude Code, headless): fall back to sequential `AskUserQuestion` per Phase 2d. Every elicitation field maps 1:1 to an AskUserQuestion call.
- **`mcp__cowork__request_cowork_directory` unavailable AND user picked the Save secondary action:** print the sandbox path and tell the user to copy manually:
  > I can't request drive access in this session. Copy the report from `{HTML_PATH}` if you want a local copy.
- **`mcp__mcp-registry__list_connectors` unavailable at Phase 2c form-build time:** fall back per Phase 2c — emit Q3 as a textarea with placeholder.

---

## What this skill does NOT do

- Does not write to the user's drive (unless they pick the Save option in Phase 6 and grant directory consent).
- Does not scaffold a knowledge base.
- Does not ask for storage target or KB root label.
- Does not call any subagent that calls `AskUserQuestion` (subagents are `background_safe: true`).
- Does not narrate process. Does not name subagents in user-facing strings. Does not surface phase numbers in user-visible text.
- Does not name Garry Tan in buyer-facing copy.

The deliverable IS the chat-rendered audit deck. Everything beyond is opt-in.

---

## Reference files

- `references/orientation-copy.md` — the LOCKED Phase 1 message
- `references/subagent-output-contract.md` — JSON contracts (audit subagent + synthesizer output, contract_version 3.0)
- `references/ai-readiness-rubric.md` — 8-dimension scoring rubric for synthesis
- `references/report-template.html` — Prescyent dark-mode HTML layout shell (slot-based — no content tokens, no markdown→HTML middleman)
- `scripts/render_markdown.py` — JSON → analyst markdown
- `scripts/render_deck.py` — JSON → buyer-facing HTML deck
- `../../agents/audit-deck-reviewer.md` — deck reviewer subagent (validates HTML before final output)
- `../../settings/prescyent.local.md.example` — per-project settings template

## Cross-references (mothership context)

- `prescyent/research/frontier/2026-02-07-gary-tan-boil-the-ocean.md` — the ethos behind "why this matters now" (analyst-side attribution only)
- `prescyent/wiki/concepts/foaster-mechanics-and-steal-list.md` — Foaster's 0-3 / 3-6 / 6-12 / 12+ ladder pattern (informs the roadmap section)
- `prescyent/references/shared/deck-footer-pattern.md` — canonical Prescyent deck close (mailto + booking link + sign-off)
- `prescyent/references/shared/deck-head-pattern.md` — canonical favicon + OG + Twitter tags
