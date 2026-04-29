---
name: draft-upsell-email
description: >
  Final skill in the Prescyent Discovery Audit. Drafts (never sends) an email to
  tyler@prescyent.ai using the user's connected email MCP (Gmail or Outlook), with
  the audit HTML attached and a 3-bullet executive summary. The user reviews in
  their drafts folder and clicks send if they want to engage Prescyent. Invoked
  programmatically by the `audit` master skill at Phase 8, after the HTML report
  is rendered. Not user-invocable directly.
background_safe: true
---

# Draft Upsell Email

You are the final step of the Prescyent Discovery Audit. Your job is narrow: use the user's connected email MCP (Gmail or Outlook) to **draft** an email to `tyler@prescyent.ai`. You never send. The user sends.

## Inputs (passed by the master skill)

- `company_name` — string
- `report_path_html` — absolute path to the rendered HTML audit
- `report_path_md` — absolute path to the markdown audit
- `three_bullets` — the Executive Summary (three numbered findings + recommendations)
- `top_opportunities` — the ranked top 3 opportunities from the audit
- `overall_score` — integer 0–100

## Step 1 — Detect Email Connector

Inventory the active MCP tools. Identify whether the user has:
- Gmail MCP connected (tools with `gmail_` prefix or similar)
- Outlook / MS365 MCP connected (tools with `ms365_` or `outlook_` prefix)

If neither is connected:
> Your Gmail or Outlook isn't connected to Claude Cowork. I can't draft the email for you. Two options:
>
> 1. Connect Gmail or Outlook in your Cowork settings and re-run `/discover`
> 2. Send manually. Subject: "{{company_name}} AI Discovery Audit complete". Attach `{{report_path_html}}`. Body is below — copy/paste.
>
> [then output the email body inline]

If both are connected, prefer the one the user has been sending from most recently (if you can infer it), else prefer Gmail. If unclear, ask: "Draft in Gmail or Outlook?"

## Step 2 — Compose the Email

**Subject line:** `{{company_name}} — AI Discovery Audit complete`

Keep it 4–8 words. Adjust for tone only if the company name is long.

**Body template** (use the exact structure below — adapt phrasing to match what the audit actually surfaced):

```
Hi Tyler,

I just ran the Prescyent AI Discovery Audit on {{company_name}}. Overall readiness score: {{overall_score}}/100.

Top three things the audit surfaced:

1. {{three_bullets[0]}}
2. {{three_bullets[1]}}
3. {{three_bullets[2]}}

Top opportunity the audit ranked:

{{top_opportunities[0].headline}} — {{top_opportunities[0].why_now}}

I've attached the full HTML report. Want to talk about what comes next?

— {{user_name_or_first_line_signature}}
```

**Voice rules:**
- No markdown formatting in the body. Plain text only (email clients mangle markdown).
- No corporate softeners. No "I hope this finds you well." No "Please let me know if you have any questions."
- No hedge words. No "just wanted to," "I was wondering," "maybe we could."
- Signoff is first name only. Or, if you cannot infer the user's name, `—` with a space for them to fill in.
- Banned words: delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, leverage, synergies, innovative, cutting-edge, holistic, seamless, transformative, utilize, game-changer, best-in-class.

## Step 3 — Attach the Report

Attach the HTML file at `{{report_path_html}}`.

If the user's email MCP cannot handle attachments:
- Upload the HTML to the user's connected `~~cloud-storage` if available (`/Prescyent Audits/{{company-slug}}-{{date}}.html`) and include the shareable link in the email body instead of an attachment.
- If neither attachment nor cloud-storage is available, fall back to embedding the 3-bullet summary + key findings inline in the email body, and reference the local path for the full report.

## Step 4 — Save as Draft (Never Send)

Use the email MCP's draft-creation tool. **Do not** use the send tool. Even if the user later says "go ahead and send it" — you still only draft. They send.

After drafting:
> Email draft saved to your Outlook/Gmail drafts folder. Subject: "{{company_name}} — AI Discovery Audit complete". Review and send when ready — or edit first, or don't send. Your call.
>
> The audit is done. Files:
>   - HTML: `{{report_path_html}}`
>   - Markdown: `{{report_path_md}}`

## Why This Skill Exists

This is the conversion step of the Prescyent plugin ladder. Every plugin in the ladder ends with a draft-email-to-Prescyent, because:

1. **Drafting is the canonical Claude "Needs Approval" pattern.** Fighting that pattern breaks trust.
2. **Drafts converted one-click-to-sent are higher-intent than any form submission.** The user already did the work, saw real findings, and chose to send.
3. **The draft preserves user agency.** They can edit, delete, or ignore. That consent surface is the point.

This skill is also the feedback loop for Prescyent: drafts that arrive in Tyler's inbox are a direct signal that the audit found something worth paying for. Audits that end without a sent email are a signal to iterate on the audit quality, not on conversion copy.

## Failure Modes

- **User has no email connector AND no cloud-storage:** fall back to a "copy-paste me" block. Still a conversion — just manual.
- **Report HTML is missing (render failed upstream):** attach the markdown instead. Note in the email body: "HTML render failed — markdown attached."
- **User's email MCP throws auth error:** surface it. Do not silently fail. User can re-auth and re-run `/discover`.

## Never Do

- Never call the email MCP's `send_email` tool. Only the `create_draft` tool.
- Never fabricate a signature. If you don't know the user's name, leave `—` and let them fill it in.
- Never include a call-to-action link in the email body that points back to Prescyent's pricing page. The link is the report. The ask is "want to talk?" — nothing more aggressive.
- Never use markdown formatting inside the email body. Plain text, linebreaks only.
