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
| 6 | `depth` | How deep should the search go? | plain pills | Standard — top 10–15 sources, ~5 min, fits a Pro session; Deep — broader sweep, ~10–15 min, best on Team plan |

**Title text rules:**

- Q1 — exact title text: `"Whose company are we discovering?"`. No parenthetical decoration.
- Q3 — exact title text: `"Which platforms should I search?"`. No parenthetical decoration. The pre-selection behavior (every card starts selected, user deselects to exclude) is a UI behavior — do NOT echo it as title text. The inference layer should NOT add "(All pre-selected — deselect any to skip.)" or similar; render the title verbatim.
- Q6 — exact title text: `"How deep should the search go?"`. The Pro/Team framing lives in the option labels, not the title.

For Q1, pre-select the highest-confidence pre-detected candidate if Phase 2b found one. If multiple candidates emerged, render them all as un-selected pills so the user picks.

For Q3, the connector list comes from a low-cost lookup at form-build time — call `mcp__mcp-registry__list_connectors` ONCE during HTML construction (not as a separate UI render). Use the returned list to populate Q3's pills with friendly names + subtitles. Default state: every card starts selected. **This is the only call to `list_connectors` in the flow** — its UI side effect lands inside the elicitation form, not as a separate panel.

If `mcp__mcp-registry__list_connectors` is unavailable, fall back to: emit Q3 as a textarea with placeholder "Which platforms should I search? (Drive, HubSpot, Notion, etc.)".

For Q6, pre-select Standard.

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

## Phase 3 — Subagent fan-out

Dispatch the four audit subagents IN PARALLEL via the `Task` tool. **Single message, four tool calls.** Do not serialize. Always dispatch all four — each subagent discovers what's available in its own category and surfaces gaps in `coverage_gaps[]`.

For each subagent, the Task `prompt` includes verbatim:

- `company_name`, `today_date`, `user_role`, `verbatim_pain`, `depth` from `discovery_scope`.
- The category slice it owns (see mapping below).
- **The full subagent JSON contract spec, inlined into the prompt** (NOT a path reference). The contract block from `references/subagent-output-contract.md` § "Audit subagent contract" — paste verbatim into each subagent prompt. Subagents read the contract from the prompt, not from disk. (v0.5 change: previous versions referenced the contract by path; the path didn't resolve in Cowork's plugin sandbox and three subagents wasted tool calls hunting for it.)
- Instruction to return JSON only, no prose, no preamble.

### Subagent → category mapping (from `CONNECTORS.md`)

| Subagent | Category slice |
|---|---|
| `audit-systems` | `~~crm`, `~~project-tracker`, `~~ticketing` |
| `audit-knowledge` | `~~cloud-storage`, `~~wiki` |
| `audit-comms` | `~~email`, `~~chat`, `~~calendar`, `~~meeting-intel` |
| `audit-stack` | All connectors visible in the session (catalog-only against the AI-readiness rubric) |

If a subagent finds no connected tools in its category, it returns null findings and populates `coverage_gaps[]`.

### Status update during dispatch

Emit ONE status line (≤40 words) immediately after the parallel block:

> Discovery agents reading your data. Should be done in 8–10 min — go grab a coffee or high-five a friend.

Do not narrate process. Do not name subagents. Do not stream sub-progress. The 8–10 min estimate is the discover 4 dogfood wall-clock; previous "4–6 minutes" was wrong and lived in the orientation, where it set the user up to step away during the elicitation. Time estimate now lands AFTER form submission.

---

## Phase 4 — Strategic clarifications (elicitation)

When all dispatched subagents return, parse each JSON. Aggregate `findings[]`, `behavioral_trace_findings[]`, `opportunities[]`, `coverage_gaps[]`, and `open_questions[]`.

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

The synthesizer produces a single structured JSON object that drives BOTH renderers (deck + markdown). Shape per `references/subagent-output-contract.md` § "Synthesizer output contract" (contract_version 2.2).

Required fields:

- `the_answer` — Minto Level 1. ONE contestable sentence. ≤60 words.
- `scores` — split scoring: `stack` (1-10 grade of AI tool surface), `workflow_integration` (1-10 grade of how tools wire into deterministic workflows), `overall` (0-100 weighted: `stack × 4 + workflow_integration × 6`), `interpretation` (one-line tied to overall band).
- `wins_top_3` — exactly 3 entries. Each `{rank, headline, one_liner, ai_mechanism, impact_metric, effort, impact, confidence, surprise, evidence}`. The `ai_mechanism` field is mandatory and names a concrete Prescyent ladder rung (Claude skill / scheduled task / custom plugin / durable agent). Total word budget per win ≤50 words across `headline + one_liner + ai_mechanism`.
- `why_now` — boil-the-ocean framing. ≤100 words. **Do NOT name Garry Tan in this field** — the buyer deck never names him. **Do NOT date-stamp the framing** (no "May 2026", no "Q2 2026", no "this month"). v0.6 change (EM-30): the buyer deck must read fresh in any quarter. Use timeless openers: "Today is the inflection moment", "Right now is where companies split", "We're at the moment AI strategies are bifurcating." The zero-sum vs positive-sum idea stands on its own.
- `losing_time` — 3-5 entries. Each `{headline, one_liner, time_cost, ai_fix}`. The `ai_fix` field is mandatory — names the AI mechanism that solves this pain.
- `roadmap` — exactly 4 entries (now-3mo / 3-6mo / 6-12mo / 12mo+). Each `{window, title, body, accent}` with accent ∈ {`green`, `cyan`, `purple`, `brass`}.
- `lanes` — exactly 3 entries (DIY / Light-touch / Full). Each `{name, headline, body, cta_label}`. **No pricing in body copy.**
- `tyler_brief` — 100-word executive brief that lands at the top of the analyst markdown.
- `coverage` — 4 entries (one per audit category) with `{category, platforms, records_analyzed, confidence}`.
- `dimensions` — 4 entries (one per audit category) with `{title, score, findings[]}`. Each finding `{severity, surprise, headline, recommendation}`.
- `conflicts` — list of `{topic, summary, recommendation, needed_decision}`.
- `coverage_gaps` — list of `{gap, impact, fix}`. Withhold `confidential` findings and surface them here as `{gap: "Confidential signal detected", impact: "...", fix: "Surfaced only in private analyst review"}`. Drop `restricted` findings entirely.
- `open_questions` — list of `{question, recommended_answer, needed_decision}`. This is where subagent `open_questions[]` flow.
- `next_steps_role_aware` — one-line tailored next step based on `user_role`.
- `next_steps_connector_aware` — one-line tailored next step based on biggest unconnected platform.
- `tan_attribution_footnote` — Garry Tan attribution string, surfaces ONLY in the analyst markdown footnote, NEVER in the buyer deck.

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

- **If `verdict: ship` AND `hard_fails: []`** → proceed to Phase 5e. Log `soft_warns` to a sidecar `_review.json` file next to the deck for Tyler's later review.
- **If `verdict: regenerate` AND `iteration < 3`** → for each `hard_fail`, fix the underlying issue:
  - `RENDER_*` codes → typically a renderer or template bug. Read the failing pattern, patch in the JSON synthesizer output if the data is wrong, or re-run the renderer if the bug is transient.
  - `MISSING_AI_MECHANISM` / `MISSING_AI_FIX` → re-run synthesis with explicit "every win must have ai_mechanism, every losing_time must have ai_fix" reminder. Update the JSON, re-render.
  - `MISSING_CTA` → check the template + footer were correctly applied; re-render.
  - `APPENDIX_OPEN_BY_DEFAULT` → renderer bug; report and ship at iteration 3.
  - `TAN_NAME_IN_BUYER_COPY` → re-write the offending field (`why_now` typically), regenerate JSON, re-render.

  Re-dispatch the reviewer with `iteration: 2`. Cap at 3 iterations.
- **If `iteration == 3` AND hard_fails persist** → ship anyway with a short user-visible note: `The audit's ready, but I caught a couple of polish items I couldn't fix in this session. The deck is below; the full report is saved alongside.` Log the unfixed `hard_fails` to the sidecar `_review.json`.

### 5e. Display inline as a Cowork artifact (mandatory)

If `mcp__cowork__create_artifact` is in the tool list, render the HTML buyer deck as a Cowork artifact. The artifact IS the primary deliverable — visible inline in chat without the user having to open a file link.

```
mcp__cowork__create_artifact({
  type: "text/html",
  title: "{company_name} · AI Readiness Audit",
  content: "<contents of HTML_PATH>"
})
```

If `mcp__cowork__create_artifact` is NOT available (Claude Code, headless), fall back to:

- Surface the HTML path so the user can open it: `Open your custom audit page at: {HTML_PATH}`.

**Closing chat copy** (after the artifact renders):

> Your custom audit page is above. Skim the 3 wins and the roadmap — that's where the value is. The full markdown report is also saved to `{MD_PATH}` if you want to forward it.

Do NOT use phrases like "open in your browser for the full layout" or "read the markdown if you prefer flat text." The artifact IS the deliverable; the markdown is the analyst secondary.

### 5f. Inline answer + Top 3 hook (post-artifact)

After the artifact renders, print the contestable answer + Top 3 wins as inline chat text. The hook gives the user something to anchor to in the chat history without re-scrolling the artifact:

> **The answer:** {Minto Level 1 sentence verbatim from the synthesizer}
>
> **Three wins this quarter:**
> 1. {wins_top_3[0].headline}
> 2. {wins_top_3[1].headline}
> 3. {wins_top_3[2].headline}

### 5g. Knowledge-base explainer (v0.6 — EM-39)

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

Frame building the knowledge base as the recommended action. The Phase 5g explainer above sold the user on what a knowledge base is and why it fixes their specific pain — Phase 6 closes the loop with three paths.

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

### "No — close the audit here"

Go directly to Phase 7.

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

## Phase 7 — Closing handoff

If the user picked `"Yes — chain inline (I have token room)"` in Phase 6, skip this phase — `/kb-build` owns the next moment.

Otherwise emit a closing handoff (≤90 words, voice-checked):

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
- `references/subagent-output-contract.md` — JSON contracts (audit subagent + synthesizer output, contract_version 2.2)
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
