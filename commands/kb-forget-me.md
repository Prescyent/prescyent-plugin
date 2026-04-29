---
description: Propose deletion or redaction of every page that mentions you. Champion approves the batch before any deletion. Your right under GDPR article 17.
argument-hint: "[--confirm] [--requester <email>] [--batch-date <YYYY-MM-DD>]"
background_safe: false
---

Two-phase. Phase 1 proposes a batch (any user). Phase 2 applies it (champion only, with `--confirm` + `--requester` + `--batch-date`). Interactive, so `background_safe: false`.

## Step 1 — resolve identity

Parse `$ARGUMENTS` for:
- `--email <email>` (identity override).
- `--confirm` (boolean flag — required for Phase 2).
- `--requester <email>` (Phase 2 only — the user whose batch the champion is approving).
- `--batch-date <YYYY-MM-DD>` (Phase 2 only — the batch date to load).

Else resolve identity via `skills/kb-compliance/scripts/kb-compliance.py` against `{KB_ROOT}/_meta/preflight.md`.

If no identity can be resolved: "No identity. Pass `--email <your-email>` or run `/kb-build` first to register your identity."

Once resolved, emit one line before any other output:

> Running as: {resolved-email} (groups: {$USER_GROUPS or "(none)"}).

The kb-compliance walker logs an `identity_assertion` event to the per-user JSONL on every call. If Phase 2 fires, `kb-writer.py` also emits its own identity line on each redact write. Anything a champion approves is traceable.

## Step 2 — walk the KB

Shell out to the shared walker:

```
python3 skills/kb-compliance/scripts/kb-compliance.py \
  --user-email "<resolved-email>" \
  --user-groups "<$USER_GROUPS env, or empty>" \
  --kb-root-label "${CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL:-prescyent-kb}"
```

Payload includes: `is_champion`, `champion_email`, and the full `pages[]` array with `is_owner` and `is_transcript` per page.

## Step 3 — categorize each page

For each page in `pages[]`:

- `is_owner == True` → action `delete` (full deletion; page is yours).
- `is_transcript == True` → action `delete` (transcripts are personal content by default per security spec §4.5).
- Otherwise → action `redact` (replace the user's name with `[former employee]`; strip `user_email` from `audience[]`, `informal_goto_for[]`, and any other people-field; scrub email + name from body prose).

Count `N_delete` and `N_redact`.

## Step 4 — write the batch manifest

Target path in the KB itself (champion reviews in-drive, not in the requester's home dir):

```
{KB_ROOT}/_meta/proposed-updates/forget-me-{user-slug}-{YYYY-MM-DD}/manifest.md
```

Write through `skills/kb-builder/scripts/storage.py` directly — this is a proposal queue, not a published page. Instantiate `store = KBStorage(kb_root_label)` and call `store.write(manifest_path, body, frontmatter)`.

**Manifest frontmatter MUST include the full `pages[]` list.** Step 5 iterates this list directly — not a fresh kb-compliance discovery. Re-running discovery in Phase 2 would run as the champion's identity and delete the champion's pages, not the requester's.

Manifest frontmatter:

```yaml
---
requested_by: "<resolved-email>"
requested_at: "<ISO timestamp>"
kb_root: "<store.root>"
page_count: <N>
delete_count: <N_delete>
redact_count: <N_redact>
status: "proposed"
champion_email: "<from payload>"
batch_date: "<YYYY-MM-DD>"
pages:
  - path: "<kb-relative path>"
    action: "delete"
    rationale: "you own this page"
  - path: "<kb-relative path>"
    action: "delete"
    rationale: "transcript"
  - path: "<kb-relative path>"
    action: "redact"
    rationale: "mentioned in body; not owner"
---
```

Manifest body (a human-readable mirror of the `pages[]` frontmatter list):

```markdown
## Overview

`{N}` pages mention you. `{N_delete}` proposed for deletion, `{N_redact}` for redaction.

## Batch

| Path | Action | Rationale |
|------|--------|-----------|
| <path> | delete | you own this page |
| <path> | delete | transcript |
| <path> | redact | mentioned in body; not owner |
...
```

Then echo to the user:

> Batch proposed at `{manifest_path}`. Champion ({champion_email}) must approve.
>
> If you are the champion and want to apply now: `/kb-forget-me --confirm --requester {resolved-email} --batch-date {YYYY-MM-DD}`.

## Step 5 — apply the batch (champion-only, requires --confirm)

Run this block only if ALL of these hold:

1. `--confirm` in `$ARGUMENTS`.
2. `--requester <email>` in `$ARGUMENTS`. (The original submitter whose batch the champion is approving. Required — there is NO implicit default.)
3. `--batch-date <YYYY-MM-DD>` in `$ARGUMENTS`.
4. `payload.is_champion == True` (i.e., the current resolved identity IS the champion per kb-compliance's payload).

**If any of 1/2/3 is missing:** print:

> Refused. `--confirm` requires `--requester <email>` and `--batch-date <YYYY-MM-DD>`. Example: `/kb-forget-me --confirm --requester jack@acme.com --batch-date 2026-04-24`.

Exit. Do NOT delete. Do NOT redact.

**If `--confirm` but NOT champion:** print `"Refused. Only the champion ({champion_email}) can apply a forget-me batch."` and exit. Do NOT delete. Do NOT redact.

**If all four conditions hold:**

Load the batch manifest at:

```
{KB_ROOT}/_meta/proposed-updates/forget-me-{slug_email(requester)}-{batch-date}/manifest.md
```

Use `store = KBStorage(kb_root_label)` and `fm, _body = store.read(manifest_path)`. The manifest's `pages[]` frontmatter list IS the source of truth. **Do NOT re-run kb-compliance here** — kb-compliance would walk for the champion's own mentions and delete the CHAMPION'S pages, not the requester's.

If the manifest is missing or has no `pages[]`: print `"Refused. No batch manifest at {manifest_path}. Check --requester and --batch-date."` and exit.

If `fm.status != "proposed"`: print `"Refused. Manifest status is {fm.status}; only 'proposed' batches can be applied."` and exit. (Prevents double-apply.)

If `fm.requested_by.lower() != requester.lower()`: print `"Refused. Manifest requested_by ({fm.requested_by}) does not match --requester ({requester})."` and exit.

Iterate `fm.pages[]`. For each page with `path`, `action`, `rationale`:

- **`action: delete`** — deletion is not a content op; it does not go through `kb-writer.py` (no redact / classify / envelope merge to run).

    ```python
    target = store._resolve(page["path"])
    if target.exists():
        target.unlink()
    ```

    Append one line to `{KB_ROOT}/_meta/build-log/{YYYY-MM-DD}-{slug_email(champion)}.jsonl`:

    ```json
    {"timestamp": "<ISO>", "user": "<champion>", "action": "forget-me-delete", "path": "<path>", "requester": "<requester>", "approved_by": "<champion>", "batch_date": "<batch-date>"}
    ```

- **`action: redact`** — load the page via `store.read(page["path"])`. Mechanically scrub the requester's email and name from the body (case-insensitive replace with `[former employee]`). Strip their email from `audience[]`, `informal_goto_for[]`, and any similar people-field in frontmatter. Keep `classification` and `audience` tier unchanged. Write back through `kb-writer.py`:

    ```
    python3 skills/kb-builder/scripts/kb-writer.py \
      --path "<page.path>" \
      --content-file "<tmp redacted body>" \
      --frontmatter-json '<cleaned fm>' \
      --user-email "<champion-email>" \
      --user-groups "<champion groups>" \
      --kb-root-label "${CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL:-prescyent-kb}"
    ```

    `kb-writer.py` logs the edit with `last_edited_by: <champion>`. Additionally append one line to the build-log tagging the action:

    ```json
    {"timestamp": "<ISO>", "user": "<champion>", "action": "forget-me-redact", "path": "<path>", "requester": "<requester>", "approved_by": "<champion>", "batch_date": "<batch-date>"}
    ```

Count successes: `count_deleted`, `count_redacted`. After the loop, write two things in this order:

1. **Update the manifest frontmatter** — flip `status: "proposed"` to `status: "applied"`. Use `store.write(manifest_path, body, fm)` (same pages[] list preserved).

2. **Write `applied.md` next to `manifest.md`** at `{KB_ROOT}/_meta/proposed-updates/forget-me-{slug_email(requester)}-{batch-date}/applied.md`:

    ```yaml
    ---
    applied_at: "<ISO timestamp>"
    approved_by: "<champion-email>"
    requester: "<requester>"
    batch_date: "<batch-date>"
    count_deleted: <count_deleted>
    count_redacted: <count_redacted>
    ---
    ```

    Body: short confirmation prose. Write via `store.write` (direct, not kb-writer — this is proposal-queue metadata).

3. **Append a summary line to the build-log:**

    ```json
    {"timestamp": "<ISO>", "user": "<champion>", "action": "forget-me-batch-applied", "requester": "<requester>", "batch_date": "<batch-date>", "count_deleted": <N>, "count_redacted": <N>}
    ```

Print: `Applied. {count_deleted} deleted, {count_redacted} redacted. Manifest status -> applied.`

## Empty-response contract

Every AskUserQuestion call — including any confirm-before-applying prompt you add in Phase 2 — follows:

```
answer = AskUserQuestion(...)
if not answer or answer.strip() == "":
    log("AskUserQuestion returned empty — aborting before any side effects")
    exit(0)
```

## Voice

No banned words. Short sentences. Every status line ≤30 words. Every error ≤20 words + one recovery step.
