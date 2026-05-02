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

## v0.8 contract — body inline-embeds artifact bundle

Tyler 2026-05-02 directive: *"since one of the deliverables being send an email to tyleratpresident.ai, instead of having to drag asking the user because Google ... the Gmail MCP doesn't allow to add attachments, so we can't attach the markdown file directly. I just want to see what is possible if we could actually just in the MCP tool call add in as text everything from the markdown file, the HTML file, and the JSON file directly into the body of the email. Now it would be below the sign-off of that person's name but just as documentation or whatever. So let's maybe try that."*

**The fix:** Gmail MCP `create_draft` accepts a single `body` string parameter and that string can be arbitrarily long (Gmail itself accepts ~25-50MB messages). v0.8 embeds the FULL artifact contents directly into the body below the signoff. No attachments needed.

The signoff line still ends the email-as-email at `Tyler`. Below the signoff is documentation/data for the recipient (or Prescyent's deal-context tool when it ingests). Most humans skim past horizontal rules; AI consumers parse fenced sections. Both audiences served from one body string.

**Size estimate.** Markdown ~50-100 KB + HTML ~40-50 KB + JSON ~20-30 KB = ~110-180 KB email body. Gmail's 25 MB limit, well within. Some email clients (Outlook, Apple Mail) may truncate or warn at very large body sizes — Tyler will eyeball this when the first v0.8 dogfood draft lands.

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

## Step 2 — Read the three artifact files

Use the `Read` tool to load:

1. The markdown report at `{{report_path_md}}` — full text.
2. The HTML deck at `{{report_path_html}}` — full text.
3. The synthesizer JSON at `{{report_path_json}}` — full text.

Capture each into a string variable. Compute size in KB for the size labels in the body separator banners.

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

The full audit content is embedded below as plain-text dump for direct
ingestion by Prescyent's deal-context tooling. Skip past this if you
just wanted the email above. To use this with /kb-build, copy the
markdown section into a fresh Cowork project and run
/kb-build --from-discover with it.

═══════════════════════════════════════════════════
Markdown report ({{md_size_kb}} KB):
═══════════════════════════════════════════════════

{{full markdown file contents verbatim}}

═══════════════════════════════════════════════════
HTML deck ({{html_size_kb}} KB) — copy this raw HTML to a .html file to view:
═══════════════════════════════════════════════════

{{full HTML file contents verbatim}}

═══════════════════════════════════════════════════
Synthesizer JSON ({{json_size_kb}} KB):
═══════════════════════════════════════════════════

{{full JSON file contents verbatim, formatted}}

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

## Step 4 — Concatenate body string + create draft

Concatenate:

1. The voice-checked email body (everything from `{{company_name}} here.` through `{{user_first_name_or_dash}}`).
2. The horizontal rule + ARTIFACT BUNDLE separator banner.
3. The full markdown text (read in Step 2).
4. The HTML separator banner + full HTML text.
5. The JSON separator banner + full JSON text.
6. The END ARTIFACT BUNDLE separator banner.

Pass the concatenated string as the `body` parameter to the email MCP's `create_draft` tool. NO `attachments` parameter — the artifacts ARE the body now.

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
- **Report HTML is missing (render failed upstream):** embed the markdown + JSON only. Note above the artifact bundle: "(HTML deck render failed — markdown + JSON below for full detail.)"
- **Markdown is also missing:** abort with a clear message — there's nothing useful to embed.
- **User's email MCP throws auth error:** surface it. Do not silently fail.
- **Body size > 10 MB:** rare with reasonable audit scopes, but if it happens, fall back to attachments-or-paths-in-body fallback. Surface the size.
- **`session_audit_log_path` was previously a third attachment:** v0.8 deprecates this — the session log is too large to inline-embed and isn't part of the buyer-facing artifact bundle. If the master skill passes a non-null path, ignore it for v0.8.

## Never do

- Never call the email MCP's `send_email` tool. Only the `create_draft` tool.
- Never fabricate a signature. If you don't know the user's name, leave a single line for them to fill in.
- Never include a call-to-action link in the email body that points to Prescyent's pricing page. The link is the booking link. The ask is the call.
- Never apply voice rules to the artifact bundle. That's raw export content; banned-word rules don't apply to embedded markdown/HTML/JSON.
