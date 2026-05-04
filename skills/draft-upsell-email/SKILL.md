---
name: draft-upsell-email
description: >
  Final skill in the Prescyent Discovery Audit. Drafts (never sends) an email to
  tyler@prescyent.ai using the user's connected email MCP (Gmail or Outlook).
  v0.8: body INLINE-EMBEDS the markdown + HTML + JSON below the signoff
  because Gmail MCP can't accept attachments. The user reviews in their drafts
  folder and clicks send if they want to engage Prescyent. Invoked programmatically
  by the `discover` master skill at Phase 6, after the audit is rendered. Not
  user-invocable directly.
background_safe: true
---

# Draft Upsell Email

You are the conversion step of the Prescyent Discovery Audit. Your job is narrow: use the user's connected email MCP (Gmail or Outlook) to **draft** an email to `tyler@prescyent.ai`. You never send. The user sends.

## Inputs (passed by the master skill)

- `company_name` — string, the company being audited.
- `company_industry` — short string describing what the company does (e.g., "B2B payments processor", "marina management SaaS").
- `report_path_html` — absolute path to the rendered buyer HTML deck.
- `report_path_md` — absolute path to the analyst markdown report.
- `report_path_json` — absolute path to the synthesizer JSON.
- `session_audit_log_path` — absolute path to the current Cowork session's `audit.jsonl`. Passed only when `userConfig.attach_session_log == true`. Else `null`.
- `the_answer` — the Minto Level 1 contestable sentence from the synthesizer.
- `wins_top_3` — the ranked Top 3 wins (each with `headline`, `one_liner`, `ai_mechanism`, `impact_metric`).
- `overall_score` — integer 0–100.
- `tyler_brief` — 100-word executive brief from synthesizer. Seed for the body, NOT the body itself.
- `to_email` — recipient address. Default `tyler@prescyent.ai`.

## v0.8.2 contract — body inline-embeds the markdown only, chunked-Read for size

Tyler 2026-05-02 directive (v0.8): *"the Gmail MCP doesn't allow to add attachments, so we can't attach the markdown file directly. I just want to see what is possible if we could actually just in the MCP tool call add in as text everything from the markdown file, the HTML file, and the JSON file directly into the body of the email."*

**v0.8 attempted all three artifacts inline. v0.8.1 walked back to markdown only. v0.8.2 keeps the markdown-only design and adds chunked Read so the full markdown actually fits regardless of size.**

Why v0.8.2 was needed: v0.8.1 was sized against a stub fixture that produced ~30KB rendered markdown. Real audits on rich Cowork sessions produce ~99KB markdown (3.3× the spec) — measured against `local_8a427367` Baseline Payments audit on 2026-05-04. Cowork's Read tool caps responses at 25K tokens (~100KB of typical markdown), so a single Read on a 99KB file returned a truncation error and the skill fell back to synthesis-only inline + a pointer-to-local-file note. That fallback wasn't supposed to be the default path.

**v0.8.2 fix:** branch on file size before reading.
- File < 80KB: single Read (existing v0.8.1 behavior).
- File ≥ 80KB: chunked Read via `offset` + `limit` (500 lines per chunk), assemble in Claude's context, pass full body to `create_draft`.

The recipient (tyler@prescyent.ai or alpha-cohort recipients like Jack/Josh/BioMaxx) still gets ONLY the email body — no Cowork artifact, no local file paths. Markdown alone carries the full audit including the `Raw subagent JSON` appendix in fenced ```json blocks, so /kb-build --from-discover ingestion sees every subagent return without us also inlining the synthesizer JSON file.

**Size budget:** typical real audit is ~95-100 KB email body (lead-in ~2KB + 3 wins + closing CTA + signoff + horizontal rule + ARTIFACT BUNDLE banner + 95KB markdown). Well within Gmail's ~25MB limit. Cowork's Read 25K-token cap is irrelevant — chunked Read sidesteps it.

**v0.9 future:** if a future audit produces >250KB markdown (multi-entity discoveries, very-deep retrofitted with parallel resumption), the chunked-Read pattern still works but starts ballooning Claude's context (~60K+ tokens just to assemble the body). At that point, the right fix is a sandbox-side Python helper that posts to the Gmail MCP authenticated proxy URL without round-tripping the body through Claude's context. NOT scoped for v0.8.2.

## Step 1 — Detect email connector

Inventory the active MCP tools. Identify whether the user has:
- Gmail MCP connected (tools with `mcp__claude_ai_Gmail__*` or `gmail_*` shape).
- Outlook / MS365 MCP connected (`ms365_*` or `outlook_*` shape).

If neither is connected:

> Your Gmail or Outlook isn't connected to Claude Cowork. We can't draft the email for you. Two options:
>
> 1. Connect Gmail or Outlook in your Cowork settings and re-run the "Draft email" option in the audit.
> 2. Send manually. Subject: "{{company_name}} AI Discovery Audit". Body is below — copy/paste.
>
> [then output the full email body inline including the artifact bundle]

If both are connected, prefer the one the user has been sending from most recently, else prefer Gmail. If unclear, ask: "Draft in Gmail or Outlook?"

## Step 2 — Read the markdown artifact (v0.8.2 — chunked Read for any size)

**Step 2a — Get file size first.** Don't blindly Read; Cowork's Read tool caps responses at 25K tokens (~100KB of typical text). Real audit markdowns regularly exceed 80KB. Run a Bash one-liner first:

```bash
wc -lc {{report_path_md}}
```

This returns line count + byte count without reading the file into Claude's context.

**Step 2b — Branch on size.**

- **File < 80,000 bytes** → single `Read({file_path: report_path_md})`. Captures the full text in one shot. Existing v0.8.1 behavior.
- **File ≥ 80,000 bytes** → chunked Read. Loop until eof:
  1. Start `offset = 0`, `chunk_lines = 500`.
  2. `Read({file_path: report_path_md, offset: <offset>, limit: <chunk_lines>})` — captures up to 500 lines per chunk, well under the 25K-token cap.
  3. Append chunk content to your accumulating body string.
  4. Increment `offset` by `chunk_lines`. Repeat until a Read returns fewer than `chunk_lines` lines (eof) or returns empty.

**Step 2c — Verify completeness.** After assembly, the captured string length should equal the source byte count (give or take line-ending normalization). If your assembled string is significantly shorter than the source file's byte count, you have a chunking bug — abort with a clear error rather than sending a truncated email.

**Capture into a string variable.** Compute size in KB for the body separator banner. The markdown carries the full audit including the `Raw subagent JSON` appendix at the end (fenced ```json blocks) — so /kb-build ingestion sees every subagent's full output without us also inlining the synthesizer JSON file.

**Do NOT** read `report_path_html` or `report_path_json` (v0.8.1 walked back from the all-three-artifacts inline attempt; v0.8.2 maintains that decision). HTML deck stays as the buyer's Cowork artifact (rendered inline in the buyer's chat); JSON stays as the synthesizer's working file (the markdown's appendix already carries it). The recipient (tyler@prescyent.ai or alpha-cohort recipients) gets ONLY the email body — no local file paths in this body, no Cowork artifact link, just inline markdown.

**Why this matters:** without chunked Read, any audit producing >12K tokens of markdown (which will be most real audits) hits Cowork's Read cap on the single-Read approach. The skill then falls back to synthesis-only inline (~10KB) plus a "see local file" pointer. The recipient loses the per-subagent appendix, /kb-build can't ingest cleanly without separate file access, and v0.8.1's documented behavior is silently bypassed. v0.8.2's chunked Read closes that gap so the recipient always gets the full audit in the body.

## Step 3 — Compose the email body

**Subject line (v0.8 — EM-45 drops em-dash):** `{{company_name}} AI Discovery Audit`

Keep it 4–8 words. NO em-dash in subject (was `{{company_name}} — AI Discovery Audit complete` in v0.6; v0.8 drops the em-dash and the redundant "complete").

**Body template (v0.8 — EM-44 drops "Hi Tyler" + EM-43 drops em-dash signoff):**

```
{{company_name}} here. We're a {{company_industry}}, and we just ran your Prescyent AI Discovery Audit against our connected stack. Overall readiness score: {{overall_score}}/100.

The audit's contestable verdict: {{the_answer in plain prose, not as a quote}}.

Three things we're considering acting on this quarter:

1. {{wins_top_3[0].headline}} {{wins_top_3[0].one_liner}} {{wins_top_3[0].ai_mechanism}} {{wins_top_3[0].impact_metric}}.

2. {{wins_top_3[1].headline}} {{wins_top_3[1].one_liner}} {{wins_top_3[1].ai_mechanism}} {{wins_top_3[1].impact_metric}}.

3. {{wins_top_3[2].headline}} {{wins_top_3[2].one_liner}} {{wins_top_3[2].ai_mechanism}} {{wins_top_3[2].impact_metric}}.

The bigger move the audit pointed at is finishing our knowledge base on the Drive so the team can self-serve these workflows instead of running them through one person.

Open to a 30-min call to discuss whether your engagement model fits this stage of the work. Calendar: https://calendar.app.google/wwabJHCKHufyqW7Q6

{{user_first_name_or_dash}}

────────────────────────────────────────────────────
ARTIFACT BUNDLE — for AI ingestion
────────────────────────────────────────────────────

The full audit markdown is embedded below for direct ingestion by Prescyent's
deal-context tooling. Skip past this if you just wanted the email above.
To use this with /kb-build, copy the markdown section into a fresh Cowork
project and run /kb-build --from-discover with it.

═══════════════════════════════════════════════════
Markdown report ({{md_size_kb}} KB):
═══════════════════════════════════════════════════

{{full markdown file contents verbatim}}

═══════════════════════════════════════════════════
END ARTIFACT BUNDLE
═══════════════════════════════════════════════════
```

**POV rules (v0.8):**

- **Lead with "{{company_name}} here. We're a {{company_industry}}…"** (EM-44 drops "Hi Tyler"). Recipient (tyler@prescyent.ai) doesn't know who this company is. The first sentence does the introduction without a sycophantic opener.
- "we just ran your Prescyent AI Discovery Audit" — first-person from the sender.
- "Three things we're considering acting on" — buyer commitment voice, NOT analyst voice.
- "The bigger move … is finishing our knowledge base" — first-person buyer commitment to the path forward.
- "Open to a 30-min call" — buyer-initiated CTA.
- Calendar link as raw URL — recipients can't click anchored links in plain-text email bodies.
- **Signoff: first name only on its own line, no em-dash** (EM-43 drops the em-dash signoff).

**Voice rules (apply to the email portion above the signoff):**

- No markdown formatting in the email body above the signoff. Plain text only.
- No corporate softeners. No "I hope this finds you well." No "Please let me know if you have any questions."
- No hedge words. No "just wanted to," "I was wondering," "maybe we could."
- **Em-dash limit: 0 in subject** (EM-45). 0–1 in the email body above the signoff.
- Signoff is first name only on its own line.
- Banned words: delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, leverage (verb), synergies, innovative, cutting-edge, holistic, seamless, transformative, utilize, game-changer, best-in-class, paradigm, synergy, facilitate, tapestry, unlock, empower.

**Voice rules DO NOT apply to the artifact bundle below the signoff** — that's raw artifact content, not voice-checked composition.

**Teammate variant** — when `to_email` is a teammate's email (not tyler@prescyent.ai), the lead sentence changes:

```
{{teammate_first_name}} —

I just ran the Prescyent AI Discovery Audit on us. Overall readiness {{overall_score}}/100, and the verdict was sharper than I expected. Sharing in case you want to weigh in before we decide what to act on.
```

The rest of the body stays roughly the same, but the closing CTA shifts from "engagement model fits" to internal-action-oriented — e.g., "Want to grab 15 to walk through the top 3?". **Teammate variant DOES NOT include the artifact bundle below the signoff** — that's Prescyent-only context. Teammates get the email-as-email only.

## Step 4 — Concatenate body string + create draft (v0.8.1 — markdown only)

Concatenate:

1. The voice-checked email body (everything from `{{company_name}} here.` through `{{user_first_name_or_dash}}`).
2. The horizontal rule + ARTIFACT BUNDLE separator banner.
3. The full markdown text (read in Step 2).
4. The END ARTIFACT BUNDLE separator banner.

Pass the concatenated string as the `body` parameter to the email MCP's `create_draft` tool. NO `attachments` parameter. NO HTML or JSON inline — markdown only.

**Hard assertions (v0.8.2, LOAD-BEARING — three checks):** before calling `create_draft`, verify all three:

1. **Marker check.** Assembled body contains the literal text "ARTIFACT BUNDLE" AND contains the markdown's first section header (e.g. "# {{company_name}}"). Catches cases where Read returned an error, markdown was empty, or the artifact bundle banner was forgotten in concatenation.
2. **Length check (NEW in v0.8.2).** The portion of the assembled body below the "Markdown report" banner must be within ±5% of the source markdown file's byte count (per `wc -c` from Step 2a). Catches partial-chunk-assembly bugs in the chunked-Read path — if you walked the offset loop and only got 60% of the file in, this fires before send.
3. **No fallback-leak check (NEW in v0.8.2).** Body must NOT contain the literal phrase "synthesis-only inline" or "documented fallback applies" (legacy v0.8.1 fallback strings). If those phrases appear, an upstream branch escaped to the wrong path — abort.

If ANY assertion fails: do NOT call create_draft. Fail loud with: *"Email inline-embed assertion failed: <which check> — <details>. Aborting draft."* This prevents the v0.8 silent-deferral failure mode AND the v0.8.1 fallback-was-canonical failure mode where the skill produced an email that looked complete but had truncated or summarized artifact content.

For Gmail MCP:

```
mcp__claude_ai_Gmail__create_draft({
  to: "{{to_email}}",
  subject: "{{company_name}} AI Discovery Audit",
  body: "<concatenated body string from above>"
})
```

For Outlook / MS365 MCP, use the equivalent draft-creation primitive with the same single `body` string.

## Step 5 — Confirm draft saved (never send)

After drafting:

> Email draft saved to your {{Gmail|Outlook}} drafts folder.
>
> Subject: "{{company_name}} AI Discovery Audit"
> To: {{to_email}}
> Body length: ~{{body_size_kb}} KB (markdown + HTML + JSON inline-embedded below signoff)
>
> Review and send when ready — or edit first, or don't send. Your call.

**Do not** use the send tool. Even if the user later says "go ahead and send it" — you still only draft.

## Why this skill exists

The conversion step of the Prescyent plugin ladder. Every plugin in the ladder ends with a draft-email-to-Prescyent because:

1. **Drafting is the canonical Claude "Needs Approval" pattern.** Fighting that pattern breaks trust.
2. **Drafts converted one-click-to-sent are higher-intent than any form submission.** The user already did the work, saw real findings, and chose to send.
3. **The draft preserves user agency.** They can edit, delete, or ignore.

The v0.8 inline-embed design serves a SECOND purpose: when Tyler does open the draft, the deal-context-ingestion tooling on the Prescyent side can parse the artifact bundle directly from the email body. No file-attachment dance. The same body string serves both the human reader (top section) and the AI ingestor (bottom section).

## Failure modes

- **User has no email connector:** copy-paste fallback (per Step 1). Still a conversion — just manual.
- **Markdown is missing (render failed upstream):** abort with a clear message — there's nothing useful to embed. Hard assertion in Step 4 catches this.
- **Markdown is empty / 0 bytes:** abort. Hard assertion catches this.
- **Markdown >25K tokens / >100KB:** rare given typical audit scope, but if Cowork's Read tool refuses, surface the error. Do NOT silently defer — that was the v0.8 failure mode. If the body genuinely doesn't fit, escalate to Tyler with a path forward (chunk via offset/limit Read pattern, OR fall back to inlining only the YAML frontmatter + Top 3 + losing_time sections, OR defer to v0.9 sandbox helper).
- **User's email MCP throws auth error:** surface it. Do not silently fail.
- **`session_audit_log_path` provided:** v0.8 deprecated as a third attachment; v0.8.1 keeps it deprecated. Ignore.

## Never do

- Never call the email MCP's `send_email` tool. Only the `create_draft` tool.
- Never fabricate a signature. If you don't know the user's name, leave a single line for them to fill in.
- Never include a call-to-action link in the email body that points to Prescyent's pricing page. The link is the booking link. The ask is the call.
- Never apply voice rules to the artifact bundle. That's raw export content; banned-word rules don't apply to embedded markdown/HTML/JSON.
