---
name: kb-compliance
description: Shared logic for the three GDPR/CCPA commands (/kb-my-pages, /kb-edit-mine, /kb-forget-me). Identity resolution, KB walk with mention detection, classification-aware read filtering, and champion verification. Called by the command files — not user-facing.
background_safe: false
---

# kb-compliance — shared logic for user-rights commands

This skill backs three commands:

- `/kb-my-pages` — right to access (GDPR art 15 / CCPA).
- `/kb-edit-mine` — right to rectify (GDPR art 16).
- `/kb-forget-me` — right to erasure (GDPR art 17).

It never runs standalone. The command files do the AskUserQuestion turns; this skill supplies the identity resolution, the KB walk, mention detection, the classification-aware read filter, and the champion check.

All writes route through `skills/kb-builder/scripts/kb-writer.py`. Deletes route through `skills/kb-builder/scripts/storage.py`.

## 1. Identity resolution (single source of truth)

Every command opens by resolving the current user's identity. Order:

1. If the command received `--email <email>` in `$ARGUMENTS`, use that email.
2. Else read `{KB_ROOT}/_meta/preflight.md`. Look up `user_email` (the champion's email) and also walk `joining_users[]` for a match against `$USER_EMAIL` (env) or the Cowork-provided identity.
3. Else fall back to asking the user once via AskUserQuestion. Empty-response contract:

    ```
    answer = AskUserQuestion(
      question="What's the email you use at this company?",
      type="free_text",
      background_safe=False,
    )
    if not answer or answer.strip() == "":
        log("AskUserQuestion returned empty — aborting before any side effects")
        exit(0)
    ```

Name derivation: if `{KB_ROOT}/_meta/team/{email-slug}.md` exists, read the `name` field from its frontmatter. Otherwise derive a display name from the local part of the email (e.g. `alex@acme.com` → `wes`). The name is used for fuzzy mention matching; the email is always the primary key.

## 2. KB walk with mention detection

A page "mentions the user" if any of these match:

- Frontmatter: `owner`, `created_by`, `last_edited_by` equals `user_email`.
- Frontmatter `audience[]` or `informal_goto_for[]` contains `user_email` or the user's name.
- Body prose contains `user_email` (exact, case-insensitive) OR the user's derived name as a whole-word match.
- Path contains the user's email slug (covers `_meta/team/{email}.md`, `interviews/{email}/*`, and any per-person folder).
- `source_artifacts[]` contains a URL or identifier that includes the user's email slug.

Implementation uses `subprocess.run(['find', KB_ROOT, '-name', '*.md', '-type', 'f'])` (not `ls` — Drive Desktop sync folders underreport under BSD `ls`; see `storage.py` doc comment). For each file:

1. Call `KBStorage.read(path)` to get `(frontmatter, body)`.
2. Check the six conditions above.
3. Record the FIRST matching reason (short string) for the output table.

## 3. Classification-aware read filter

The plugin refuses to show a user pages they can't read. Alpha rule (matches `kb-writer.py::user_ceiling`):

- No elevated groups → ceiling is `internal`. User sees `public` + `internal`.
- `exec@` / `leadership@` → ceiling is `exec-only`. User sees up through `exec-only`.
- `legal@` / `finance@` / `legal-finance@` → ceiling is `confidential`.
- `department-only` pages require the user's groups to include the department named in `audience[]`.

User groups come from `--user-groups` (passed through from the command) OR default to empty (junior-level). For alpha, most users run with empty groups and the safe default applies.

A page that matches the mention test but fails the read-access test is silently filtered OUT of the output. We never surface the existence of a page the user can't read — that leak would itself be a classification bypass.

## 4. Champion verification (for /kb-forget-me --confirm)

`current_user == champion_user` means:

1. Read `{KB_ROOT}/_meta/preflight.md`.
2. Compare the resolved `user_email` (from step 1) against `champion_user.email` (case-insensitive).
3. Only on exact match does `--confirm` apply the batch.

If preflight is missing or `champion_user.email` is absent, `--confirm` refuses with: "Champion not registered. Run /start-here first to set the champion."

## 5. Output artifact (portable record)

`/kb-my-pages` writes a run artifact to `~/.prescyent/{company-slug}/my-pages-{email-slug}-{YYYY-MM-DD}.md` so the user has a file they can save, email to counsel, or attach to a DSAR response. Format: YAML frontmatter (user email, run date, KB root, page count) plus the markdown table.

`/kb-forget-me` writes the batch manifest INTO the KB itself at `{KB_ROOT}/_meta/proposed-updates/forget-me-{email-slug}-{date}/manifest.md`. This is intentional — the champion reviews it in-drive, not in the requester's home directory.

## 6. Voice

User-visible strings obey the banned-words list. Short sentences. Status updates ≤30 words. Errors ≤20 words + one recovery step.

Banned list (verbatim from `../../CLAUDE.md`): delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, seamlessly, unlock, empower, game-changer, best-in-class, cutting-edge, holistic, paradigm, synergy, leverage (verb), utilize, facilitate, tapestry.

## 7. Python helper (optional)

`scripts/kb-compliance.py` bundles the walk + mention detection + classification filter so each command can shell out once and get a JSON payload back rather than re-implementing the walk in prose. It is a pure reader — it never writes, never deletes. Writes go through `kb-writer.py`; deletes go through direct `storage.py` calls made by the command file.

Usage:

```
python3 skills/kb-compliance/scripts/kb-compliance.py \
  --user-email alex@acme.com \
  --user-groups "" \
  --kb-root-label prescyent-kb
```

Returns JSON: `{user_email, user_name, kb_root, champion_email, pages: [{path, type, classification, last_edited, reason, is_owner, is_transcript}]}`.
