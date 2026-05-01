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

You are running the buyer's first encounter with Prescyent. The deliverable is a one-page assessment rendered inline in chat — no drive writes, no scaffolding, no storage selection. The assessment IS the deliverable.

Every user-visible string passes the voice gauntlet at `../kb-builder/references/voice-rules.md` before emit. No banned words. Word budgets hold (orientation ≤120, scope ≤120, status ≤30, errors ≤20 + one recovery step).

**Empty-response contract:** every elicitation site aborts on empty input. Print `Phase 2 returned empty — aborting before any side effects` and exit. No silent defaults, no writes, no subagent dispatch. Single documented exception: the optional `verbatim_pain` field, where empty means "skip" and is logged as `verbatim_pain: null`.

If the user submits a Cowork elicitation form via Skip with `company_name` empty, apply the same contract — log and exit.

---

## Phase 1 — Orient the user

Emit the message at `references/orientation-copy.md` verbatim. Plain text only — no widget, no connector picker, no panel render. Do not call `mcp__mcp-registry__list_connectors` (it pops a UI surface in Cowork). Do not paraphrase. Do not prepend "Welcome!" or similar. Do not append process notes or subagent names.

**Do not pause for user acknowledgment after the orientation.** Move directly to Phase 2 in the same turn. The elicitation form IS the gate — the user submits, skips, or asks a question. This mirrors brand-voice's `/discover-brand`, which emits orientation prose and immediately renders the elicitation without waiting for "go." Tyler validated this UX 2026-05-01: an explicit "Ready to start?" → reply "go" → form is one extra step the user shouldn't have to take.

Coverage gaps surface in the final report — Phase 5's Coverage table names what was actually read, and the failure mode at the bottom of this file handles the zero-findings case.

---

## Phase 2 — Settings + pre-detection + elicitation form

Brand-voice's `/discover-brand` runtime explicitly invokes `mcp__visualize__read_me({modules: ["elicitation"]})` then `mcp__visualize__show_widget` to render the polished form. We do the same here — explicit invocation, deterministic. We also pre-detect everything we can before showing the form, because Tyler's ethos is "don't make me re-explain who I am" (the doctor's-office paperwork problem).

### 2a. Check settings file (silent)

Read `.claude/prescyent.local.md` if it exists. Extract:

- Company name
- User role (`founder`, `cfo`, `ops`, `sales`, `marketing`, `product`, `other`)
- Buyer intent (`ai-readiness`, `capture-senior-knowledge`, `claude-actually-useful`, `other`)
- Search depth (`standard` or `deep`) — default `standard`
- Known doc locations or primary pain points (optional)

A template lives at `settings/prescyent.local.md.example`.

If the settings file exists AND has at minimum `company_name` + `user_role`, **skip Phase 2c**, surface a one-line confirmation (`Found your settings file — running discovery for {company_name}.`), and proceed directly to Phase 2f.

### 2b. Pre-detect company candidates + role from connector signals

Before rendering the elicitation form, attempt to pre-populate the answers we'd otherwise have to ask. This is the "don't ask the doctor's-office question twice" pattern. Run these checks in parallel; cap total wall time at ~10 seconds:

**Company candidates** — collect up to 3, ranked by confidence:

1. **Email domain.** `mcp__41c208e8…__get_identity` returns the authenticated Fathom email. Domain → company candidate. (e.g. `tyler@hernandocapital.co` → "Hernando Capital".)
2. **Connected MCP scopes.** Some connectors expose org / workspace name (HubSpot `get_organization_details`, Notion `notion-get-teams`). Each unique org name = a candidate.
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

The response is the canonical contract: required CSS class names (`elicit`, `elicit-group`, `elicit-question`, `elicit-pills`, `elicit-pill`, `elicit-textarea`), required data attributes (`data-name`, `data-multi`, `data-value`, `data-other`), the four option formats (plain pills, cards, preview tiles, sliders/dates), the locked header SVG (File anthropicon), and the submit payload format. Build the HTML against this spec — don't guess the shape.

**Step 2 — Build the elicitation HTML** with seven `.elicit-group` blocks. Header title: `"Discovery details"`. Submit label: `"Run discovery"`. Skip label: `"Skip — use defaults"`.

The seven questions, in render order:

| # | Field (`data-name`) | Question | Type | Options |
|---|---|---|---|---|
| 1 | `company_name` | Whose company are we discovering? | plain pills | {Pre-detected candidates from Phase 2b — up to 3}; Other |
| 2 | `user_role` | Which describes you best? | plain pills | Founder / CEO; CFO / Finance lead; Head of Ops; Sales / GTM lead; Marketing lead; Product / Engineering lead; Other |
| 3 | `buyer_intent` | What brought you here today? | card pills (icon + subtitle) | Understand AI readiness; Capture senior knowledge before someone leaves; Make Claude actually useful for the team; Something else |
| 4 | `connectors_in_scope` | Which platforms should I search? | card pills, multi-select | One card per detected connector with friendly name + one-line subtitle (e.g. "Notion — Wiki, playbooks, briefs"; "HubSpot — CRM, deals, contacts"; "Fathom — Sales call transcripts"; "Gmail — Sent emails, voice samples"). All cards pre-selected. |
| 5 | `unconnected_tools` | Other tools you use that aren't connected here? | textarea | Free text. Placeholder: "e.g. Google Chat, Slack, Salesforce, Linear — I'll flag what I can't reach so you can decide whether to connect them." |
| 6 | `verbatim_pain` | Anything specific been frustrating? (Optional) | textarea | Free text |
| 7 | `depth` | How deep should the search go? | plain pills | Standard — top 10–15 sources, ~5 min, fits a Pro session; Deep — broader sweep, ~10–15 min, best on Team plan |

For Q1, pre-select the highest-confidence pre-detected candidate if Phase 2b found one. If multiple candidates emerged, render them all as un-selected pills so the user picks.

For Q4, the connector list comes from a low-cost lookup at form-build time — call `mcp__mcp-registry__list_connectors` ONCE during HTML construction (not as a separate UI render). Use the returned list to populate Q4's pills with friendly names + subtitles. **This is the only call to `list_connectors` in the flow** — its UI side effect lands inside the elicitation form, not as a separate panel.

If `mcp__mcp-registry__list_connectors` is unavailable, fall back to: emit Q4 as a textarea with placeholder "Which platforms should I search? (Drive, HubSpot, Notion, etc.)".

For Q7, pre-select Standard. The Pro/Team framing is in the option label itself — no separate copy required.

**Step 3 — Render**:

```
mcp__visualize__show_widget({html: "<elicitation HTML built per the spec>"})
```

**Step 4 — Read the submission**:

```
mcp__cowork__read_widget_context()
```

The response arrives as a single-line message per the spec. Parse the seven fields. If the user clicked Skip with `company_name` empty, apply the empty-response contract — log `Phase 2 returned empty — aborting before any side effects` and exit. No subagent dispatch.

**After parsing, surface a coverage warning if Q5 has content:**

If `unconnected_tools` is non-empty, emit (≤40 words):

> Heads up — I won't be able to read what's in {unconnected_tools_list}. Discovery will run on what is connected; I'll flag specifically what's missing so you can decide whether to connect it for a richer audit next time.

Do NOT stonewall. Do NOT block the run. Some users won't know how to connect tools. Some tools won't have MCPs. Run with what we have, log the gap, surface it in Coverage Gaps at synthesis.

### 2d. Fallback when elicitation unavailable (Claude Code, headless)

If `mcp__visualize__show_widget` is NOT in the tool list:

- Fall back to sequential `AskUserQuestion` calls — seven questions in field order. Map the elicitation pill options 1:1 to AskUserQuestion options.
- Each call applies the empty-response contract EXCEPT Q5 (`unconnected_tools`) and Q6 (`verbatim_pain`), where empty = skip = `null`.

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
  "buyer_intent": "ai-readiness",
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

Dispatch the four audit subagents IN PARALLEL via the `Task` tool. **Single message, four tool calls.** Do not serialize. Always dispatch all four — each subagent discovers what's available in its own category and surfaces gaps in `coverage_gaps[]`. No pre-filtering by connectivity.

For each subagent, the Task `prompt` includes verbatim:

- `company_name` and `today_date` from `discovery_scope`.
- `user_role`, `buyer_intent`, `verbatim_pain` (so each subagent prioritizes findings against the specific pain — verbatim_pain is calibration text, not classification input).
- `depth` (`standard` vs `deep` — deep raises the records_analyzed targets in the JSON contract).
- The category slice it owns (see mapping below). The subagent itself enumerates which platforms in that slice are actually connected.
- The path to the JSON contract: `skills/discover/references/subagent-output-contract.md`.
- Instruction to return JSON only, no prose, no preamble.

### Subagent → category mapping (from `CONNECTORS.md`)

| Subagent | Category slice |
|---|---|
| `audit-systems` | `~~crm`, `~~project-tracker`, `~~ticketing` |
| `audit-knowledge` | `~~cloud-storage`, `~~wiki` |
| `audit-comms` | `~~email`, `~~chat`, `~~calendar`, `~~meeting-intel` |
| `audit-stack` | All connectors visible in the session (catalog-only against the AI-readiness rubric) |

If a subagent finds no connected tools in its category, it returns null findings and populates `coverage_gaps[]`. Synthesis at Phase 5 surfaces those gaps in the Coverage table and the Coverage Gaps section.

### Status update during dispatch

Emit ONE status line (≤30 words) immediately after the parallel block:

> Discovery agents reading your data. Back in a minute or two with findings.

Do not narrate process. Do not name subagents. Do not stream sub-progress.

---

## Phase 4 — Optional follow-up questions (elicitation)

When all dispatched subagents return, parse each JSON. The aggregate has `findings[]`, `behavioral_trace_findings[]`, `opportunities[]`, `coverage_gaps[]`, and `open_questions[]` per subagent (per the contract at `references/subagent-output-contract.md`, contract_version 2.1).

Scan for follow-up candidates: **conversational** clarifications the user can answer (NOT data they'd need to fetch from a system). Examples:

- "audit-comms found 12+ recurring meetings/week. What's actually happening in those — status, decisions, or working sessions?"
- "audit-systems sees stale `Qualified` deals. Is `Qualified` the gate stage or a placeholder?"
- "audit-systems found 536 deals in pipelines named DO NOT USE. Real prospects, zombies, or mix?"

Cap at **3 follow-ups total** across all subagents. Each subagent's `open_questions[]` carries a `recommended_answer` — that becomes the pre-selected pill default.

### 4a. Render the follow-up elicitation form

If 1–3 follow-ups exist AND `mcp__visualize__show_widget` is available, render a second elicitation form. Title: `"Two quick clarifications"` (or "Three" if N=3). Submit label: `"Use these"`. Skip label: `"Skip — log as open questions"`.

Each follow-up becomes one `.elicit-group` block. Use plain pills with the recommended_answer's `data-value` pre-selected. Always include an "Other / not sure" pill that maps to `null` (logged as open question).

Example structure for one follow-up:

| Field key | Question | Type | Options |
|---|---|---|---|
| `followup_1_pipelines_jetpay` | The 536 deals in pipelines named DO NOT USE — what are they? | plain pills | Real prospects we should migrate (recommended); Zombies — close lost in bulk; Mix — flag for review case-by-case; Not sure / log as open question |

Render via the same explicit `mcp__visualize__read_me({modules: ["elicitation"]})` then `mcp__visualize__show_widget` pattern as Phase 2.

Read responses via `mcp__cowork__read_widget_context()`. Parse. Incorporate into synthesis.

### 4b. Fallback when elicitation unavailable

If `mcp__visualize__show_widget` is NOT in the tool list, fall back to plain text:

> Two quick clarifications before I write the report:
>
> 1. {question 1} (recommended: {recommended_answer})
> 2. {question 2} (recommended: {recommended_answer})

User answers conversationally. Each question's empty/skip = log to report's Open Questions section.

### 4c. Skip when no useful follow-ups

If no useful follow-ups remain, skip Phase 4 entirely. Move directly to Phase 5.

---

## Phase 5 — Synthesize, render markdown + HTML deck

### 5a. Synthesize the markdown report — Minto pyramid structure

The report follows Barbara Minto's Pyramid Principle (per `research/frontier/2026-02-07-gary-tan-boil-the-ocean.md` cross-reference + the canonical Minto skill at `https://raw.githubusercontent.com/olelehmann1337/claude-skills/main/skills/minto/SKILL.md`):

- **Level 1 — The Answer.** ONE contestable sentence at the top of the report. Specific enough that someone could disagree. Not a topic label, not a hedged claim, not a question.
- **Level 2 — Supporting Arguments.** 2–4 claims, MECE (mutually exclusive, collectively exhaustive). Each is a full sentence. These are the report's section headers.
- **Level 3 — Evidence.** One concrete piece per argument — named stat, specific example, attributed quote, or detailed anecdote.

Score the 8 dimensions of the AI Readiness Rubric (see `references/ai-readiness-rubric.md`) using the per-subagent dimension scores. The overall score is the weighted average × 10, rendered 0–100. Don't fabricate scores from thin data — mark dimensions Unknown if the subagent couldn't read them.

**Bias the report toward HIGH `surprise_factor` findings in the top sections.** Findings the user almost certainly already knows (Low surprise) belong in the appendix. Findings the user could not have written without us (High surprise) belong above the fold.

**Persona-tailoring** based on `discovery_scope.user_role`:

| Role | Lead the synthesis with | Avoid leading with |
|---|---|---|
| `founder` / `cfo` | Cost, risk, time-to-value, $/month implications | Technical debt, integration patterns |
| `sales` / `marketing` | Pipeline impact, conversion, time-saved-per-rep | API scopes, data hygiene minutiae |
| `ops` | Process visibility, hygiene gaps, automation candidates | Brand voice, conversion |
| `product` / `other` (technical) | Tech debt, integration risk, build-vs-buy, agentic patterns | Generic risk statements |
| `other` (non-technical default) | Treat as `founder` |

Same data, different lead sentence. The rest of the report stays consistent.

**Voice gauntlet on every line. No banned words. No process narration. Embed boil-the-ocean framing in "Why this matters now" — the May 2026 inflection point, positive-sum vs zero-sum AI plays.**

Write the report in this exact section order:

```markdown
---
company_name: {company_name}
company_slug: {company_slug}
user_role: {user_role}
buyer_intent: {buyer_intent}
depth: {depth}
generated_at: {today_date}
plugin_version: 0.4-alpha
contract_version: 2.1
---

# {company_name}
**AI Readiness Audit · {today_date} · {Depth: Standard | Deep}**

## The answer
> {ONE contestable sentence — Minto Level 1.
>  Examples (calibrate to actual findings, never copy verbatim):
>  - "Your AI tools aren't bad — they're starving on context. Three connector fixes get you 80% of the value, two months of KB work gets you the rest."
>  - "Your CRM hygiene is the structural cause of every bad AI output. Subtract before you add — fix four required fields and your pipeline forecasts double in accuracy."
>  - "You're three connector authorizations and one wiki-mount fix away from making Claude actually useful for {company_name}. The work is small. The compounding is large."
> }

**Overall AI Readiness Score: {0-100}** · {one-line interpretation tied to the score band}

## Top 3 moves
[The 3 highest-priority opportunities — moved from old slot 7 to the top. Bias toward HIGH surprise_factor and (impact - effort) × confidence. Each is a full Minto Level 2 argument.]

1. **{opportunity headline}** — {why_now in one sentence}. Effort: {Low/Med/High}. Impact: {Low/Med/High}. Confidence: {High/Med/Low}. Surprise: {Low/Med/High}.
   - **Evidence:** {one concrete data citation — Minto Level 3}.
2. ...
3. ...

## Why this matters now
[Boil-the-ocean framing tied to May 2026. Two-paragraph max. Voice-checked.]

We're at the inflection moment Garry Tan called out in February — the strategic split between zero-sum AI plays (do the same thing cheaper) and positive-sum AI plays (attempt things previously impossible). {Company-name} is currently positioned for {zero-sum / positive-sum / neither, depending on score band}. {One specific observation about why, tied to the data the audit surfaced.}

The companies pulling ahead are the ones that stopped asking "how do we cut headcount with AI" and started asking "what would it look like to do something dramatically bigger." The audit findings below are the building blocks for that bigger move.

## Where you're losing time today
[Persona-tailored. 3-5 specific blind spots. Each is a HIGH or MEDIUM surprise_factor finding, tied to verbatim_pain when the user provided one.]

- **{Blind spot headline}** — {one-paragraph explanation grounded in the data, written in the persona's vocabulary}. **Cost today:** {time / $ / risk}.
  - **Evidence:** {citation}.
- ...

## The path forward
[Sell the KB Builder. Frame as the inevitable next step, not one of three options. ~150 words.]

The audit findings above point at one structural pattern: AI tools at {company_name} are operating without a persistent context layer. Every Claude session starts cold. Every ChatGPT prompt is hand-fed. Every new hire rebuilds context from scratch. That's the friction making AI feel underwhelming.

The fix is a knowledge base — a single Karpathy-style wiki on {their existing storage: Drive / OneDrive / etc.} that every AI tool reads from. The KB compounds. Every interview adds to it. Every meeting transcript lands in it. Every new hire onboards into it.

`/kb-build --from-discover` takes this report and scaffolds that wiki in 20 minutes. The mining subagents read your connected systems, distill institutional knowledge into structured pages, and hand you back a folder you can hand to your CFO, your VP of Sales, and your new hire on day one.

That's the boil-the-ocean version of "make AI useful." The small-fix version is "buy a better AI tool." The big-fix version is "give every AI tool the context they're missing."

## The detail
[Everything below is appendix — the per-dimension breakdown, full findings, conflicts, gaps, and open questions. Surface high-surprise findings above; relegate low-surprise findings here.]

### Coverage
| Category | Connected | Records analyzed | Confidence |
|---|---|---|---|
| GTM & Systems | {platforms} | {N} records | High/Medium/Low |
| Knowledge & Docs | {platforms} | {N} docs | High/Medium/Low |
| Communications | {platforms} | {N} threads | High/Medium/Low |
| Stack | {platforms} | {N} apps | n/a |

If the user listed `unconnected_tools` at Phase 2c Q5, append:
> **Not in scope:** {unconnected_tools_list}. The audit ran on what's connected — these gaps are flagged in Coverage Gaps below.

### GTM & Systems Readiness — {N}/10
- [Severity, Surprise] Headline — detail. **Recommendation:** fix.
- ... (sorted by surprise_factor DESC, then severity × confidence × impact)

### Knowledge & Document Readiness — {N}/10
- ...

### Communications Readiness — {N}/10
- ...

### AI Stack Readiness — {N}/10
- ...

### Conflicts Between Sources
- **{topic}**: {subagent A finding} vs. {subagent B finding}.
  - Recommendation: {which to adopt and why}.
  - Need from you: {specific decision}.

### Coverage Gaps
- {gap}: {impact}. Fix: {connector to add or process to verify}.
- {if unconnected_tools were listed at Phase 2c Q5, repeat each one with a one-line "what we couldn't see and why it matters" note}

### Open Questions
1. **{question}**
   - Recommended answer: {recommendation with reasoning}.
   - Need from you: {specific decision or confirmation}.

## Recommended next steps
1. **Run `/kb-build --from-discover {report_path_md}`.** This is the path forward described above. It scaffolds the wiki, mines your connectors, and produces the persistent context layer.
2. **{role-aware tailored next step}** — for {user_role}, this is typically: {founder/cfo: "review the Top 3 moves with your senior team this week"; sales: "fix the four required-field workflows in HubSpot before any new AI tooling"; ops: "audit the deprecated pipelines / stale records flagged above"; product/other: "prototype the highest-impact opportunity as a one-off agent before scoping the KB build"}.
3. **{connector-aware tailored next step}** — connect {first unconnected platform that would meaningfully expand coverage}; the audit's biggest blind spot today is {specific category}.
```

**Confidence tagging** — every finding gets High / Medium / Low based on volume:

- **High:** subagent analyzed ≥50 records / ≥10 documents / ≥1 month of messages
- **Medium:** ≥10 records / ≥3 documents / ≥1 week of messages
- **Low:** below the medium thresholds, or single-source signal with no corroboration

**Drop `restricted` findings entirely. Withhold `confidential` findings unless `buyer_intent` includes a confidentiality-aware signal — otherwise list as "Coverage Gap: confidential signal detected, omitted from report."**

### 5b. Render the HTML deck

Save the markdown to a sandbox temp path, then render via the existing renderer:

```bash
SLUG="{company_slug}"
DATE="{today_date}"
MD_PATH="/tmp/prescyent-discovery-${SLUG}-${DATE}.md"
HTML_PATH="/tmp/prescyent-discovery-${SLUG}-${DATE}.html"

# write the markdown to MD_PATH first (skill is responsible for that write)

python3 "${CLAUDE_PLUGIN_ROOT}/skills/discover/scripts/render-report.py" \
  --input  "${MD_PATH}" \
  --output "${HTML_PATH}" \
  --company "{company_name}"
```

The renderer uses `references/report-template.html` (the Prescyent dark-mode design system).

### 5c. Display inline

If `mcp__cowork__create_artifact` is available:

- Render the HTML inline as a Cowork artifact (visible in chat without drive writes).
- Render the markdown as a second artifact too — some users prefer reading flat markdown.

If `mcp__cowork__create_artifact` is NOT available (Claude Code, etc.):

- Print the markdown inline as a fenced code block.
- Surface the HTML path so the user can open it manually: `Open the deck at: {HTML_PATH}`.

### 5d. Inline answer + Top 3 hook

Always print the Minto Level 1 answer + Top 3 moves inline in chat AFTER the artifact, even if the user is reading the full report inline already. The hook is the asynchronous "what to scroll to" entry point. Format:

> **The answer:** {Minto Level 1 sentence verbatim from the report}
>
> **Three moves this week:**
> 1. {Top move 1 headline}
> 2. {Top move 2 headline}
> 3. {Top move 3 headline}

---

## Phase 6 — Recommended next step + secondary options (elicitation)

Frame the path forward as the recommended action with two secondary options for the user to optionally pick alongside. The KB build is NOT one of three equal options — it's THE next step the report's "Path forward" section sold them on.

Render Phase 6 as an elicitation form (same explicit `mcp__visualize__read_me` + `mcp__visualize__show_widget` pattern as Phase 2). Title: `"Next step"`. Submit label: `"Go"`. Skip label: `"Skip — close the audit"`.

**Form structure:**

| Field key | Question | Type | Options (recommended pre-selected) |
|---|---|---|---|
| `primary_action` | Ready to chain into `/kb-build`? | plain pills | Yes — chain into /kb-build now (recommended); Yes — but later, save the audit first; No — close the audit here |
| `secondary_actions` | Anything else you want me to do with this report? | plain pills, multi-select | Save markdown + HTML to my drive; Draft a follow-up email to tyler@prescyent.ai; Send to a teammate (paste their email below) |
| `teammate_email` | Teammate email (optional) | textarea | (free text, only used if "Send to a teammate" is selected) |

If `mcp__visualize__show_widget` is unavailable, fall back to plain text:

> The path forward is `/kb-build` — the audit's Path Forward section makes the case for why. Reply with one of:
>
> - "go" — chain into /kb-build now (recommended)
> - "save" — save markdown + HTML to my drive
> - "email" — draft a follow-up email to tyler@prescyent.ai
> - "send to {email}" — send to a teammate
> - "skip" — close the audit here

Empty response = abort cleanly per the empty-response contract.

If `primary_action = "Yes — chain into /kb-build now"`, transfer control to `/kb-build --from-discover {MD_PATH}` and skip Phase 7. The `/kb-build` command parses the markdown's YAML frontmatter for `company_name`, `company_slug`, `user_role`, then asks only for the storage target and KB root label.

If the user picks `"No — close the audit here"`, go directly to Phase 7.

### Option 1 — Save to drive

- If `mcp__cowork__request_cowork_directory` is available, request directory consent.
- If granted, write `{HTML_PATH}` and `{MD_PATH}` to the granted folder under `prescyent-discovery-{slug}-{date}.{html,md}`.
- If declined, surface that ("Saved to chat only — re-run option 1 when you're ready") and skip.

### Secondary action — Save to drive

If `secondary_actions` includes `"Save markdown + HTML to my drive"`:

- If `mcp__cowork__request_cowork_directory` is available, request directory consent.
- If granted, write `{HTML_PATH}` and `{MD_PATH}` to the granted folder as `prescyent-discovery-{slug}-{date}.{html,md}`.
- If declined, surface ("Saved to chat only — re-run later when you're ready") and skip.

### Secondary action — Draft email to tyler@prescyent.ai

If `secondary_actions` includes `"Draft a follow-up email to tyler@prescyent.ai"`:

Chain to `skills/draft-upsell-email/SKILL.md`. Pass these inputs:

- `company_name`
- `report_path_html` — the drive path if Save was also selected, else the sandbox temp path
- `report_path_md` — same logic
- `the_answer` — the Minto Level 1 sentence
- `top_3_moves` — the ranked Top 3 from synthesis
- `overall_score` — integer 0–100

`draft-upsell-email` handles email-MCP detection, drafting, attachment fallback, and never sends.

### Secondary action — Send to teammate

If `secondary_actions` includes `"Send to a teammate"` AND `teammate_email` is non-empty:

Chain to `skills/draft-upsell-email/SKILL.md` with the teammate email as the `to` field instead of `tyler@prescyent.ai`. Same drafting flow. Never sends.

If `teammate_email` is empty after the user picked the option, prompt for it once via plain text (or a tiny one-question elicitation if available). If still empty, skip with a one-line note.

### Primary action — Chain to `/kb-build`

If `primary_action = "Yes — chain into /kb-build now"`:

Invoke `/kb-build --from-discover {MD_PATH}` (or the drive path if Save was also picked). The `/kb-build` command parses the markdown's YAML frontmatter for `company_name`, `company_slug`, `user_role`, then asks only for the storage target and KB root label.

Control transfers to `/kb-build` and Phase 7 below is skipped.

---

## Phase 7 — Closing handoff

If the user picked `"Yes — chain into /kb-build now"` in Phase 6, skip this phase — `/kb-build` owns the next moment.

Otherwise emit a closing handoff (≤90 words, voice-checked):

> Your assessment is in your chat. The path forward is in the report — when you're ready to turn this into a living wiki every future Claude session reads from, run `/kb-build --from-discover {MD_PATH}`.
>
> That's the **Map** + **Build** step. **Deliver** is what we do together once the wiki is in your hands.
>
> Want to skip the scope questions next time? Save your answers at `.claude/prescyent.local.md` — there's a template at `settings/prescyent.local.md.example` in this plugin.

The settings-file hint only emits IF Phase 2c actually ran (the user answered scope questions in this session). If Phase 2a hit and the settings file already existed, drop the third paragraph.

If `mcp__plugins__suggest_plugin_install` is available, also surface a plugin-install card pointing at `prescyent-plugin` (the Tier 1 entry is the same plugin in v0.4-alpha — the card just nudges the user to keep going).

---

## Voice gauntlet — every string before emit

(Full rules at `../kb-builder/references/voice-rules.md`.)

1. Help the reader feel more excited / trusting? If no, cut.
2. About them or about us? If us, flip.
3. Jargon a mid-market exec wouldn't say? Replace.
4. Banned word present? Fix.
5. Implementation detail that doesn't change their next move? Strip.
6. Under the word budget? Orientation ≤155 (the "what to know" paragraph adds room), scope ≤120, status ≤30, errors ≤20 + one recovery step.
7. **Boil-the-ocean check (added v0.4):** does this string frame the reader as positive-sum (attempt things previously impossible) or zero-sum (do the same thing cheaper)? If zero-sum, rewrite. The discovery report's job is to make the bigger move feel inevitable, not to enumerate small fixes.

Pass all six — ship. Fail one — rewrite.

---

## Failure modes

- **Subagent times out** (>maxTurns or >5 min wall clock): continue with the others. Flag the missing slice in Coverage Gaps. Do not retry — retry burns tokens and the user can re-run.
- **Subagent returns malformed JSON:** include the raw return verbatim in Coverage Gaps. Do not retry. Do not fabricate findings.
- **All four subagents return zero findings:** emit (≤30 words):
  > Your connectors didn't surface enough signal for a useful read. Connect more tools — or run `/kb-build` to capture knowledge directly from your team via interview.
- **Render script (`render-report.py`) fails:** save the markdown anyway. Surface the markdown path and the stderr. Skip Phase 5c HTML and continue with markdown-only display.
- **`mcp__cowork__create_artifact` unavailable:** fall back to inline markdown code block (Phase 5c).
- **`mcp__visualize__show_widget` unavailable** (Claude Code, headless runs, host without the visualize MCP loaded): fall back to sequential `AskUserQuestion` per Phase 2c. Every elicitation field maps 1:1 to an AskUserQuestion call.
- **`mcp__cowork__request_cowork_directory` unavailable AND user picked the Save secondary action:** print the sandbox path and tell the user to copy manually:
  > I can't request drive access in this session. Copy the report from `{HTML_PATH}` if you want a local copy.
- **`mcp__mcp-registry__list_connectors` unavailable at Phase 2c form-build time:** fall back per Phase 2c — emit Q4 as a textarea with placeholder "Which platforms should I search? (Drive, HubSpot, Notion, etc.)". Discovery still runs; the model uses connector availability discovered at Phase 3 dispatch time instead.

---

## What this skill does NOT do

- Does not write to the user's drive (unless they pick Option 1 in Phase 6 and grant directory consent).
- Does not scaffold a knowledge base.
- Does not ask for storage target or KB root label.
- Does not collect or persist preflight data beyond the chat session.
- Does not call any subagent that calls `AskUserQuestion` (subagents are `background_safe: true`).
- Does not narrate process. Does not name subagents in user-facing strings. Does not surface phase numbers in user-visible text.

The deliverable IS the chat-rendered assessment. Everything beyond is opt-in.

---

## Reference files

- `references/orientation-copy.md` — the LOCKED Phase 1 message
- `references/subagent-output-contract.md` — the JSON contract every audit subagent returns (contract_version 2.1, includes surprise_factor)
- `references/ai-readiness-rubric.md` — 8-dimension scoring rubric for synthesis
- `references/report-template.html` — Prescyent dark-mode HTML shell used by `render-report.py` (v0.4 — full design system + canonical deck-footer-pattern + favicon/OG/Twitter meta tags per `prescyent/references/shared/deck-head-pattern.md`)
- `scripts/render-report.py` — markdown → HTML renderer (PLUGIN_VERSION = "0.4.0")
- `../../settings/prescyent.local.md.example` — per-project settings template buyers can copy to skip Phase 2c on subsequent runs

## Cross-references (mothership context)

- `prescyent/research/frontier/2026-02-07-gary-tan-boil-the-ocean.md` — the ethos that drives the "Why this matters now" + "Path forward" framing in the Minto report shape
- `prescyent/references/shared/deck-footer-pattern.md` — canonical Prescyent deck close (mailto + booking link + sign-off) — embedded into `report-template.html`
- `prescyent/references/shared/deck-head-pattern.md` — canonical favicon + OG + Twitter tags — embedded into `report-template.html`
