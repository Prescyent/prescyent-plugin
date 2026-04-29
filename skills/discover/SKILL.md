---
name: discover
description: >
  Tier 0 entry point for the Prescyent plugin. Reads the user's connected Cowork
  tools, fans out four audit subagents in parallel, and returns a one-page AI
  readiness assessment inline in chat. No drive writes unless the user opts in.
  Invoke when the user asks to "set me up", "where do I start", "onboard me",
  "audit my company", "AI readiness check", "what's our readiness", "we bought
  Claude — now what?", "run discovery", or just installs the plugin.
background_safe: false
---

# `/discover` — Prescyent Tier 0 Entry Point

> `background_safe: false` is load-bearing. This skill uses widget elicitation
> (`mcp__visualize__show_widget` when available) and `AskUserQuestion` as the
> fallback. Both require the foreground main thread. Do not move into a
> background `Task`.

You are running the buyer's first encounter with Prescyent. The deliverable is a one-page assessment rendered inline in chat — no drive writes, no scaffolding, no storage selection. The assessment IS the deliverable.

Every user-visible string passes the voice gauntlet at `../kb-builder/references/voice-rules.md` before emit. No banned words. Word budgets hold (orientation ≤80, scope ≤120, status ≤30, errors ≤20 + one recovery step).

**Empty-response contract:** every `AskUserQuestion` site aborts on empty input. Print `AskUserQuestion returned empty — aborting before any side effects` and exit. No silent defaults, no writes, no subagent dispatch. Single documented exception: Phase 2 fallback Q4 (`verbatim_pain`) where empty means "skip" and is logged as `verbatim_pain: null`.

If the widget elicitation form is dismissed with `submitted: false` AND `company_name` empty, apply the same contract — log and exit.

---

## Phase 1 — Orient + connector inventory

### 1a. Read connected MCPs

If `mcp__mcp-registry__list_connectors` is available (Cowork host), call it once. Otherwise, run `/mcp list` via Bash and parse the output. If neither produces data, proceed with `connectors_detected = []` — orientation still emits, just with empty lists.

Classify every detected connector into one of four buckets:

| Bucket | Purpose | Example platforms |
|---|---|---|
| `doc_platforms` | Where docs live (primary signal) | Google Drive, OneDrive, SharePoint, Notion, Confluence, Box, Dropbox |
| `comms_platforms` | Email + chat + calendar (supplementary) | Gmail, Outlook, Slack, Teams, Google Chat, Google Calendar |
| `intel_platforms` | Conversation + meeting intel (supplementary) | Fathom, Granola, Gong, Otter, Chorus |
| `crm_systems` | CRM, project trackers, ticketing (supplementary) | HubSpot, Salesforce, Pipedrive, Linear, Jira, Asana, Zendesk |

Build three rendering lists from those buckets:

- `doc_platforms` — connected document platforms, friendly names, comma-separated.
- `comms_intel_crm` — connected comms + intel + CRM platforms, friendly names, comma-separated.
- `missing_named` — supported-but-unconnected platforms, capped at 5, picking the most-likely-to-help (favor doc platforms first, then CRM, then comms).

If a list is empty, render `none yet` instead of an empty string.

### 1b. Render the LOCKED orientation message

Emit the message at `references/orientation-copy.md` verbatim, with the three placeholders substituted. Do not paraphrase. Do not prepend "Welcome!" or similar. Do not append process notes or subagent names.

### 1c. Coverage gates

Run these gates BEFORE moving to Phase 2:

- **Zero connectors detected** — stop. Emit (≤30 words):

  > No connectors are active in this session. Connect at least one — Drive, Gmail, Slack, HubSpot, or Notion are good starting points — then re-run `/discover`.

- **Zero document platforms but 1+ supplementary** — warn (proceed):

  > No document storage is connected. Discovery will run on what's available, but expect coverage gaps where docs would normally help.

- **Single connector total** — warn (proceed):

  > Only one tool is connected. Discovery works best with two or more — connect another for a richer read.

After the gates, wait for the user to acknowledge with plain text ("yes", "go", "continue"). **Do NOT use `AskUserQuestion` here** — keep it conversational. The orientation message ends with "Ready when you are." which the user replies to.

---

## Phase 2 — Single widget form

Use the form spec at `references/widget-form-spec.md`. Five fields, one submit.

### 2a. Render the form

If `mcp__visualize__show_widget` is available:

- Dispatch the form per the spec.
- Read responses via `mcp__cowork__read_widget_context`.

If `mcp__visualize__show_widget` is NOT available (Claude Code, headless runs, older Cowork):

- Fall back to sequential `AskUserQuestion` calls — five questions in field order. Each call applies the empty-response contract EXCEPT Q4 (`verbatim_pain`), where empty = skip = `null`.

### 2b. Argument pre-seed

If `$ARGUMENTS` contains:

- `depth:standard` or `depth:deep` — pre-seed `depth`; skip the corresponding question.
- `role:<value>` — pre-seed `user_role`; skip that question. Valid values: `founder`, `cfo`, `ops`, `sales`, `marketing`, `product`, `other`.

Pre-seeded fields skip the empty-response contract.

### 2c. Build the orchestrator state

After the form returns (or AskUserQuestion fallback completes), build `discovery_scope`:

```jsonc
{
  "company_name": "Acme",
  "company_slug": "acme",
  "user_role": "founder",
  "buyer_intent": "ai-readiness",
  "verbatim_pain": "Sales reps don't update HubSpot.",
  "depth": "standard",
  "today_date": "2026-04-29",
  "user_email": "<from session>",
  "connectors_detected": [...]   // from Phase 1
}
```

`company_slug` derives from `company_name`: lowercase, replace `[^a-z0-9-]+` with `-`, strip leading/trailing hyphens, collapse runs of `-`.

---

## Phase 3 — Subagent fan-out

Dispatch the four audit subagents IN PARALLEL via the `Task` tool. **Single message, four tool calls.** Do not serialize.

For each subagent, the Task `prompt` includes verbatim:

- `company_name` and `today_date` from `discovery_scope`.
- `user_role`, `buyer_intent`, `verbatim_pain` (so each subagent prioritizes findings against the specific pain — verbatim_pain is calibration text, not classification input).
- `depth` (`standard` vs `deep` — deep raises the records_analyzed targets in the JSON contract).
- The slice of `connectors_detected` mapped to this subagent's category, with specific platform names.
- The path to the JSON contract: `skills/discover/references/subagent-output-contract.md`.
- Instruction to return JSON only, no prose, no preamble.

### Subagent → category mapping (from `CONNECTORS.md`)

| Subagent | Category slice |
|---|---|
| `audit-systems` | `~~crm`, `~~project-tracker`, `~~ticketing` |
| `audit-knowledge` | `~~cloud-storage`, `~~wiki` |
| `audit-comms` | `~~email`, `~~chat`, `~~calendar`, `~~meeting-intel` |
| `audit-stack` | All detected connectors (catalog-only against the AI-readiness rubric) |

If a subagent's category has zero connectors, **skip dispatching that subagent entirely** — log it in `coverage_gaps` at synthesis. Do not dispatch a subagent with empty input; it'll just return null findings.

### Status update during dispatch

Emit ONE status line (≤30 words) immediately after the parallel block:

> Discovery agents reading your data. Back in a minute or two with findings.

Do not narrate process. Do not name subagents. Do not stream sub-progress.

---

## Phase 4 — Optional follow-up questions

When all dispatched subagents return, parse each JSON. The aggregate has `findings[]`, `behavioral_trace_findings[]`, `opportunities[]`, `coverage_gaps[]`, and `open_questions[]` per subagent (per the contract at `references/subagent-output-contract.md`).

Scan for follow-up candidates: **conversational** clarifications the user can answer in chat (NOT data they'd need to fetch from a system). Examples:

- "audit-comms found 12+ recurring meetings/week. What's actually happening in those — status, decisions, or working sessions?"
- "audit-systems sees stale `Qualified` deals. Is `Qualified` the gate stage or a placeholder?"

If 1–3 such follow-ups exist, surface them inline in plain text:

> Two quick clarifications before I write the report:
>
> 1. {question 1}
> 2. {question 2}

The user answers conversationally. Incorporate into synthesis. If they say "skip" or "not sure," continue without — log in the report's Open Questions section.

If no useful follow-ups remain, skip Phase 4 entirely.

**Do NOT use `AskUserQuestion` here.** Plain text only.

---

## Phase 5 — Synthesize, render markdown + HTML deck

### 5a. Synthesize the markdown report

Score the 8 dimensions of the AI Readiness Rubric (see `references/ai-readiness-rubric.md`) using the per-subagent dimension scores. The final overall score is the weighted average × 10, rendered 0–100. Don't fabricate scores from thin data — mark dimensions Unknown if the subagent couldn't read them.

Write the report in this section order, derived from brand-voice's Discovery Report shape and the Prescyent rubric. Adapt phrasing to what the data actually surfaced. Voice gauntlet on every line.

```markdown
---
company_name: {company_name}
company_slug: {company_slug}
user_role: {user_role}
buyer_intent: {buyer_intent}
depth: {depth}
generated_at: {today_date}
plugin_version: 0.3-alpha
---

# {company_name} — Prescyent Discovery
Date: {today_date}
Depth: {depth}
Overall AI Readiness Score: {0-100}

## Executive Summary
1. {one-sentence finding + recommendation}
2. {one-sentence finding + recommendation}
3. {one-sentence finding + recommendation}

## Coverage
| Category | Connected | Records analyzed | Confidence |
|---|---|---|---|
| GTM & Systems | {platforms} | {N} records | High/Medium/Low |
| Knowledge & Docs | {platforms} | {N} docs | High/Medium/Low |
| Communications | {platforms} | {N} threads | High/Medium/Low |
| Stack | {platforms} | {N} apps | n/a |

## GTM & Systems Readiness — {N}/10
- [Severity] Headline — detail. **Recommendation:** fix.
- ... (top findings, sorted by severity × confidence × impact)

## Knowledge & Document Readiness — {N}/10
- ...

## Communications Readiness — {N}/10
- ...

## AI Stack Readiness — {N}/10
- ...

## Top 3 AI Opportunities
1. {opportunity headline} — {why_now}. Effort: {Low/Med/High}. Impact: {Low/Med/High}. Confidence: {High/Med/Low}.
2. ...
3. ...

## Conflicts Between Sources
- **{topic}**: {subagent A finding} vs. {subagent B finding}.
  - Recommendation: {which to adopt and why}.
  - Need from you: {specific decision}.

## Coverage Gaps
- {gap}: {impact}. Fix: {connector to add or process to verify}.

## Open Questions
1. **{question}**
   - Recommended answer: {recommendation with reasoning}.
   - Need from you: {specific decision or confirmation}.

## Recommended Next Steps
1. Run `/kb-build --from-discover {report_path_md}` to turn this into a living wiki every Claude session reads from.
2. {role-aware tailored next step}
3. {connector-aware tailored next step}
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

### 5d. Inline executive summary

Always print the 3-bullet Executive Summary inline in chat AFTER the artifact, even if the user is reading the full report inline already. The summary is the asynchronous "what to scroll to" hook. Format:

> **In one screen:**
> 1. {bullet 1}
> 2. {bullet 2}
> 3. {bullet 3}

---

## Phase 6 — Three chained-action options

Offer three independent options. The user picks any combination. Format:

> Three things you can do with this:
>
> 1. **Save the report to your drive.** I'll request directory consent and write the markdown + HTML to whatever folder you point me at.
> 2. **Email it to tyler@prescyent.ai.** I'll draft (never send) an email with the report attached. You review in your drafts folder.
> 3. **Build a living wiki from this.** Chain into `/kb-build --from-discover` and turn this assessment into the context layer every future Claude session reads from.
>
> Pick any. None of them write anywhere without explicit consent.

Use `AskUserQuestion` with a multi-select if available (options: 1, 2, 3, none). Empty-response contract applies — empty = abort cleanly, do not silently default to "none."

If the user replies "none" or "skip", go directly to Phase 7.

### Option 1 — Save to drive

- If `mcp__cowork__request_cowork_directory` is available, request directory consent.
- If granted, write `{HTML_PATH}` and `{MD_PATH}` to the granted folder under `prescyent-discovery-{slug}-{date}.{html,md}`.
- If declined, surface that ("Saved to chat only — re-run option 1 when you're ready") and skip.

### Option 2 — Draft email

Chain to `skills/draft-upsell-email/SKILL.md`. Pass these inputs:

- `company_name`
- `report_path_html` — the drive path if Option 1 also picked, else the sandbox temp path
- `report_path_md` — same logic
- `three_bullets` — the Executive Summary
- `top_opportunities` — the ranked Top 3 from synthesis
- `overall_score` — integer 0–100

`draft-upsell-email` handles email-MCP detection, drafting, attachment fallback, and never sends.

### Option 3 — Chain to `/kb-build`

Invoke `/kb-build --from-discover {MD_PATH}` (or the drive path if Option 1 also picked). The `/kb-build` command parses the markdown's YAML frontmatter for `company_name`, `company_slug`, `user_role`, then asks only for the storage target and KB root label.

If the user picks Option 3, control transfers to `/kb-build` and Phase 7 below is skipped.

---

## Phase 7 — Closing handoff

If the user picked Option 3 in Phase 6, skip this phase — `/kb-build` owns the next moment.

Otherwise emit a closing handoff (≤60 words, voice-checked):

> Your assessment is in your chat. When you want to turn this into a living wiki — the same context every future Claude session will read from — run `/kb-build`.
>
> That's the **Map** + **Build** step. **Deliver** is what we do together once the wiki is in your hands.

If `mcp__plugins__suggest_plugin_install` is available, also surface a plugin-install card pointing at `prescyent-plugin` (the Tier 1 entry is the same plugin in v0.3-alpha — the card just nudges the user to keep going).

---

## Voice gauntlet — every string before emit

(Full rules at `../kb-builder/references/voice-rules.md`.)

1. Help the reader feel more excited / trusting? If no, cut.
2. About them or about us? If us, flip.
3. Jargon a mid-market exec wouldn't say? Replace.
4. Banned word present? Fix.
5. Implementation detail that doesn't change their next move? Strip.
6. Under the word budget? Orientation ≤80, scope ≤120, status ≤30, errors ≤20 + one recovery step.

Pass all six — ship. Fail one — rewrite.

---

## Failure modes

- **Subagent times out** (>maxTurns or >5 min wall clock): continue with the others. Flag the missing slice in Coverage Gaps. Do not retry — retry burns tokens and the user can re-run.
- **Subagent returns malformed JSON:** include the raw return verbatim in Coverage Gaps. Do not retry. Do not fabricate findings.
- **All four subagents return zero findings:** emit (≤30 words):
  > Your connectors didn't surface enough signal for a useful read. Connect more tools — or run `/kb-build` to capture knowledge directly from your team via interview.
- **Render script (`render-report.py`) fails:** save the markdown anyway. Surface the markdown path and the stderr. Skip Phase 5c HTML and continue with markdown-only display.
- **`mcp__cowork__create_artifact` unavailable:** fall back to inline markdown code block (Phase 5c).
- **`mcp__visualize__show_widget` unavailable:** fall back to sequential AskUserQuestion calls (Phase 2).
- **`mcp__cowork__request_cowork_directory` unavailable AND user picked Option 1:** print the sandbox path and tell the user to copy manually:
  > I can't request drive access in this session. Copy the report from `{HTML_PATH}` if you want a local copy.

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
- `references/widget-form-spec.md` — the Phase 2 form definition + show_widget invocation shape
- `references/subagent-output-contract.md` — the JSON contract every audit subagent returns
- `references/ai-readiness-rubric.md` — 8-dimension scoring rubric for synthesis
- `references/report-template.html` — Prescyent dark-mode HTML shell used by `render-report.py`
- `scripts/render-report.py` — markdown → HTML renderer
