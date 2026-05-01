---
name: draft-upsell-email
description: >
  Final skill in the Prescyent Discovery Audit. Drafts (never sends) an email to
  tyler@prescyent.ai using the user's connected email MCP (Gmail or Outlook), with
  the audit markdown + HTML deck attached and the body written in buyer-frame
  voice for an unfamiliar recipient. The user reviews in their drafts folder and
  clicks send if they want to engage Prescyent. Invoked programmatically by the
  `discover` master skill at Phase 6, after the audit is rendered. Not user-invocable
  directly.
background_safe: true
---

# Draft Upsell Email

You are the conversion step of the Prescyent Discovery Audit. Your job is narrow: use the user's connected email MCP (Gmail or Outlook) to **draft** an email to `tyler@prescyent.ai`. You never send. The user sends.

## Inputs (passed by the master skill)

- `company_name` — string, the company being audited.
- `company_industry` — short string describing what the company does (e.g., "B2B payments processor", "marina management SaaS"). Used as the company-introduction seed when writing to a recipient who doesn't know this company.
- `report_path_html` — absolute path to the rendered buyer HTML deck.
- `report_path_md` — absolute path to the analyst markdown report.
- `session_audit_log_path` — absolute path to the current Cowork session's `audit.jsonl`. Passed only when `userConfig.attach_session_log == true`. Else `null`.
- `the_answer` — the Minto Level 1 contestable sentence from the synthesizer.
- `wins_top_3` — the ranked Top 3 wins (each with `headline`, `one_liner`, `ai_mechanism`, `impact_metric`).
- `overall_score` — integer 0–100.
- `tyler_brief` — 100-word executive brief from synthesizer. Seed for the body, NOT the body itself. You rewrite it into buyer-frame voice with the company introduction prepended.
- `to_email` — recipient address. Default `tyler@prescyent.ai`. When the master skill chains for "Send to a teammate," this is the teammate's email.

## v0.6 contract

This skill ships v0.6 (EM-36 + EM-37). Two behavior changes vs v0.5:

1. **Mandatory attachments.** Every draft attaches BOTH `report_path_md` and `report_path_html`. If `session_audit_log_path` is non-null AND `to_email == tyler@prescyent.ai` AND the path exists, attach that too as a third file. (Audit logs NEVER attach when `to_email` is a teammate — the log is for Prescyent dogfood only.)
2. **Buyer-frame body POV.** Body is written FROM the user TO an outside party who doesn't know the company. Lead sentence introduces the company. Top 3 phrased as commitment surfaces ("we're considering acting on these three") not analyst observations. Drop any local file paths from the body — attachments replace them.

## Step 1 — Detect email connector

Inventory the active MCP tools. Identify whether the user has:
- Gmail MCP connected (tools with `gmail_*` prefix or `mcp__*__create_draft` shape).
- Outlook / MS365 MCP connected (tools with `ms365_*` or `outlook_*` prefix).

If neither is connected:

> Your Gmail or Outlook isn't connected to Claude Cowork. We can't draft the email for you. Two options:
>
> 1. Connect Gmail or Outlook in your Cowork settings and re-run the "Draft email" option in the audit.
> 2. Send manually. Subject: "{{company_name}} AI Discovery Audit complete". Attach `{{report_path_md}}` and `{{report_path_html}}`. Body is below — copy/paste.
>
> [then output the email body inline]

If both are connected, prefer the one the user has been sending from most recently (if you can infer it), else prefer Gmail. If unclear, ask: "Draft in Gmail or Outlook?"

## Step 2 — Compose the email

**Subject line:** `{{company_name}} — AI Discovery Audit complete`

Keep it 4–8 words. Adjust for tone only if the company name is long.

**Body template** (use the exact structure below — adapt phrasing to match what the audit actually surfaced; do NOT use markdown formatting; plain prose only):

```
Hi Tyler,

We're {{company_name}}, {{company_industry}}. I just ran your Prescyent AI Discovery Audit against our connected stack — overall readiness score {{overall_score}}/100.

The audit surfaced one contestable verdict: {{the_answer in plain prose, not as a quote}}.

Three things we're considering acting on this quarter:

1. {{wins_top_3[0].headline}} — {{wins_top_3[0].one_liner}} {{wins_top_3[0].ai_mechanism}} {{wins_top_3[0].impact_metric}}.

2. {{wins_top_3[1].headline}} — {{wins_top_3[1].one_liner}} {{wins_top_3[1].ai_mechanism}} {{wins_top_3[1].impact_metric}}.

3. {{wins_top_3[2].headline}} — {{wins_top_3[2].one_liner}} {{wins_top_3[2].ai_mechanism}} {{wins_top_3[2].impact_metric}}.

The bigger move the audit pointed at is finishing our knowledge base on the Drive so the team can self-serve these workflows instead of running them through one person.

Full markdown report and the buyer deck attached. Open to a 30-min call to discuss whether your engagement model fits this stage of the work. Calendar: https://calendar.app.google/wwabJHCKHufyqW7Q6

— {{user_first_name_or_dash}}
```

**POV rules (v0.6, EM-37):**

- Lead with **"We're {{company}}, {{industry}}"** — recipient (tyler@prescyent.ai) doesn't know who this company is. The first sentence does the introduction.
- "I just ran your Prescyent AI Discovery Audit" — first-person from the sender (the user), present-tense action verb, "your audit" attributes the artifact to Prescyent, not the user.
- "Three things we're considering acting on" — buyer commitment voice, NOT "the audit ranked these as opportunities" (analyst voice). The user is signaling intent, not summarizing analysis.
- "The bigger move … is finishing our knowledge base" — first-person buyer commitment to the path forward. Spell out "knowledge base" first mention; subsequent mentions in the same paragraph can use "KB."
- "Open to a 30-min call to discuss whether your engagement model fits this stage of the work" — buyer-initiated CTA, frames the call as a fit-check, not a sales pitch.
- Calendar link as raw URL — recipients can't click anchored links in plain-text email bodies, so the booking link goes in the visible URL.

**Voice rules (apply to every draft):**

- No markdown formatting in the body. Plain text only (email clients mangle markdown).
- No corporate softeners. No "I hope this finds you well." No "Please let me know if you have any questions."
- No hedge words. No "just wanted to," "I was wondering," "maybe we could."
- Em-dash limit: 0–1 per email.
- Signoff is first name only. If you cannot infer the user's name, `—` with a space for them to fill in.
- Banned words: delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, leverage (verb), synergies, innovative, cutting-edge, holistic, seamless, transformative, utilize, game-changer, best-in-class, paradigm, synergy, facilitate, tapestry, unlock, empower.

**Teammate variant** — when `to_email` is a teammate's email (not tyler@prescyent.ai), the lead sentence changes:

```
Hi {{teammate_first_name}},

I just ran the Prescyent AI Discovery Audit on us. Overall readiness {{overall_score}}/100, and the verdict was sharper than I expected. Sharing in case you want to weigh in before we decide what to act on.
```

The rest of the body (top 3 + bigger move + CTA) stays roughly the same, but the closing CTA shifts from "engagement model fits" to internal-action-oriented — e.g., "Want to grab 15 to walk through the top 3?"

## Step 3 — Attach the report

Two mandatory attachments:

1. The markdown report at `{{report_path_md}}`. Filename in attachment: `{{slug}}-discovery-report.md`.
2. The HTML deck at `{{report_path_html}}`. Filename in attachment: `{{slug}}-discovery-deck.html`.

If `session_audit_log_path` is non-null AND `to_email == tyler@prescyent.ai` AND the file exists at that path, attach a third file:

3. The session audit log. Filename in attachment: `{{slug}}-cowork-session-{{session_id}}.jsonl`.

The session-log attachment is gated by `userConfig.attach_session_log == true` (default `false`). The master skill checks this flag before passing `session_audit_log_path` — if false, it passes `null`. The master skill is the gate; this skill just respects what's passed.

If the user's email MCP cannot handle multipart attachments:
- Surface a clear error: "Your email connector ({{mcp_name}}) doesn't support attachments. The draft body has been created, but the report files at {{report_path_md}} and {{report_path_html}} need to be attached manually before send."
- Do NOT fall back to embedding-the-HTML-link in the body. The whole point of v0.6 EM-36 is that local file paths in email bodies are useless to recipients.

## Step 4 — Save as draft (never send)

Use the email MCP's draft-creation tool. **Do not** use the send tool. Even if the user later says "go ahead and send it" — you still only draft. They send.

After drafting:

> Email draft saved to your {{Gmail|Outlook}} drafts folder.
>
> Subject: "{{company_name}} — AI Discovery Audit complete"
> To: {{to_email}}
> Attachments: {{N}} files ({{report_path_md basename}}, {{report_path_html basename}}{{, audit log basename if present}})
>
> Review and send when ready — or edit first, or don't send. Your call.

## Why this skill exists

The conversion step of the Prescyent plugin ladder. Every plugin in the ladder ends with a draft-email-to-Prescyent, because:

1. **Drafting is the canonical Claude "Needs Approval" pattern.** Fighting that pattern breaks trust.
2. **Drafts converted one-click-to-sent are higher-intent than any form submission.** The user already did the work, saw real findings, and chose to send.
3. **The draft preserves user agency.** They can edit, delete, or ignore. That consent surface is the point.

This skill is also the feedback loop for Prescyent: drafts that arrive in Tyler's inbox are a direct signal that the audit found something worth paying for. Audits that end without a sent email are a signal to iterate on the audit quality, not on conversion copy.

## Failure modes

- **User has no email connector:** copy-paste fallback (per Step 1). Still a conversion — just manual.
- **Report HTML is missing (render failed upstream):** attach the markdown only. Note in the email body: "(HTML deck render failed — markdown report attached for full detail.)"
- **Markdown is also missing:** abort with a clear message — there's nothing useful to attach.
- **User's email MCP throws auth error:** surface it. Do not silently fail. User can re-auth and re-run the option from Phase 6.
- **`session_audit_log_path` provided but file doesn't exist:** silently skip the third attachment, log to console. Don't fail the whole draft.
- **Email MCP doesn't support attachments at all:** surface error per Step 3. Do not fall back to local-path-in-body.

## Never do

- Never call the email MCP's `send_email` tool. Only the `create_draft` tool.
- Never fabricate a signature. If you don't know the user's name, leave `—` and let them fill it in.
- Never embed local file paths (`/Users/...`, `/sessions/...`) in the email body — recipients can't reach them.
- Never use markdown formatting inside the email body. Plain text, linebreaks only.
- Never attach the session audit log when `to_email` is a teammate, regardless of `attach_session_log` flag. The audit log is Prescyent-only.
- Never include a call-to-action link in the email body that points to Prescyent's pricing page. The link is the booking link. The ask is the call.
