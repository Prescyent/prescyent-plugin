---
description: Show every KB page that mentions you (by email or name match). Read-only. You see path, classification, last edited. Your right under GDPR article 15 / CCPA.
argument-hint: "[--email <email>]"
background_safe: true
---

Read-only. No writes. No interactive prompts. You get a table of every KB page that names you, plus a portable copy at `~/.prescyent/{slug}/my-pages-{you}-{date}.md`.

## Step 1 — resolve identity

Parse `$ARGUMENTS`. If it contains `--email <email>`, use that email.

Else load identity from `{KB_ROOT}/_meta/preflight.md` via `skills/kb-compliance/scripts/kb-compliance.py`. The helper walks `user_email` plus `joining_users[]` and returns the current user. If preflight is missing AND `$ARGUMENTS` has no `--email`, stop with: "No identity. Re-run with `--email <your-email>` or run `/kb-build` first."

Once resolved, emit one line before any other output:

> Running as: {resolved-email} (groups: {$USER_GROUPS or "(none)"}).

So the caller sees exactly which identity the walker used. Spoofing leaves a paper trail — kb-compliance logs every invocation to the per-user JSONL as an `identity_assertion` event.

## Step 2 — walk the KB

Shell out to the shared walker:

```
python3 skills/kb-compliance/scripts/kb-compliance.py \
  --user-email "<resolved-email>" \
  --user-groups "<from $USER_GROUPS env, or empty>" \
  --kb-root-label "${CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL:-prescyent-kb}"
```

The helper uses `skills/kb-builder/scripts/storage.py` to read pages (same KBStorage class `kb-writer.py` uses, so classification handling stays consistent). It enforces the classification-aware read filter — pages the user can't read are NOT in the output. Surfacing their existence would itself be a classification bypass.

Mention detection (first match wins on `reason`):
- `owner` / `created_by` / `last_edited_by` equals your email
- `audience[]` or `informal_goto_for[]` contains your email or name
- `source_artifacts[]` references your email slug
- Path contains your email slug (covers `_meta/team/{email}.md`, `interviews/{email}/*`)
- Body has your email (case-insensitive) or your name (whole-word)

## Step 3 — render output table

Parse the JSON payload. Print a markdown table:

```
| Path | Type | Classification | Last edited | Why you're mentioned |
|------|------|----------------|-------------|-----------------------|
```

Sort by classification (public first, then internal, then deeper tiers). Truncate paths longer than 60 chars from the left with an ellipsis.

Footer (single line each):

> `{N}` pages mention you. `{O}` you own, `{T}` are transcripts.
>
> Edit one: `/kb-edit-mine --page <path>`. Pages you own auto-apply; others queue a PR for the owner.
>
> Propose deletion or redaction of your content: `/kb-forget-me`.

If N is zero, say: "No KB pages mention you. Either nothing's been written yet or you run under a different email. Try `/kb-my-pages --email <other>`."

## Step 4 — persist the portable record

Write to `~/.prescyent/{company-slug}/my-pages-{email-slug}-{YYYY-MM-DD}.md`:

```yaml
---
user_email: "<resolved-email>"
run_date: "<today>"
kb_root: "<store.root>"
kb_root_label: "<label>"
page_count: <N>
---
```

Then the same markdown table from Step 3 in the body. Company slug comes from `preflight.company_slug`; fall back to `"prescyent"` if missing. Mkdir `-p` the parent. Use direct Python `open(..., 'w')` — this file is the user's own portable copy, NOT a KB page, so it does not route through `kb-writer.py`.

Print one final line: `Saved portable copy: {path}`.

## Voice

No banned words. Short sentences. Footer ≤30 words per line.
