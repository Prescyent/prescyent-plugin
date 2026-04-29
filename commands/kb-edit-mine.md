---
description: Edit any KB page you own or that mentions you. Owners auto-apply; non-owners queue a PR for the owner. Your right under GDPR article 16.
argument-hint: "[--page <path>]"
background_safe: false
---

Interactive. Uses AskUserQuestion, so `background_safe: false`.

## Step 1 — resolve identity

Parse `$ARGUMENTS` for `--email <email>` (rare — usually auto). Else resolve via `skills/kb-compliance/scripts/kb-compliance.py` (reads `{KB_ROOT}/_meta/preflight.md`; matches against `user_email` and `joining_users[]`).

If no identity can be resolved, stop with: "No identity. Pass `--email <your-email>` or run `/kb-build` first to register your identity."

Once resolved, emit one line before any other output:

> Running as: {resolved-email} (groups: {$USER_GROUPS or "(none)"}).

Identity is also logged to the per-user JSONL as an `identity_assertion` event via the kb-compliance shell-out. Any downstream `kb-writer.py` call (Step 6, owner auto-apply path) emits its own identity line so every layer is visible to the user.

## Step 2 — target a page

Parse `$ARGUMENTS` for `--page <path>`. If present, validate the path exists under the KB root (via `KBStorage.exists`). If the page doesn't exist, stop with: "No such page: {path}."

If `--page` is NOT provided:

1. Run the shared walker (same script as `/kb-my-pages`) to get the filtered list of pages that mention the current user.
2. If the list is empty, stop with: "No KB pages mention you. Nothing to edit here."
3. Show the table exactly like `/kb-my-pages`.
4. Ask the user to pick one:

    ```
    answer = AskUserQuestion(
      question="Which page do you want to edit?",
      type="single_select",
      options=[<path> for each page in the table],
      background_safe=False,
    )
    if not answer or answer.strip() == "":
        log("AskUserQuestion returned empty — aborting before any side effects")
        exit(0)
    ```

Set `target_path = answer`.

## Step 3 — load and show the relevant section

`fm, body = KBStorage.read(target_path)`. Print a short header:

> **{target_path}**  ({fm.classification}) — owner: {fm.owner}, last edited: {fm.last_verified}

Then print the mention-context: the paragraph(s) of body that actually mention the user (email or name). If the match is frontmatter-only, print the relevant frontmatter fields and skip body preview.

## Step 4 — ask what needs to change

```
answer = AskUserQuestion(
  question="What needs to change? Describe the edit in plain words, or say 'cancel'.",
  type="free_text",
  background_safe=False,
)
if not answer or answer.strip() == "":
    log("AskUserQuestion returned empty — aborting before any side effects")
    exit(0)
if answer.strip().lower() == "cancel":
    print("Cancelled. No changes written.")
    exit(0)
```

## Step 5 — propose the edit

Generate the new body (and any frontmatter changes) based on the user's description. Show a diff preview in a markdown code block: removed lines prefixed with `- `, added lines prefixed with `+ `. Ask once more:

```
confirm = AskUserQuestion(
  question="Apply this edit?",
  type="single_select",
  options=["apply", "cancel"],
  background_safe=False,
)
if not confirm or confirm.strip() == "":
    log("AskUserQuestion returned empty — aborting before any side effects")
    exit(0)
if confirm == "cancel":
    print("Cancelled. No changes written.")
    exit(0)
```

## Step 6 — branch on ownership

Let `current_email = resolved-email` (step 1). Let `page_owner = fm.owner`, `page_creator = fm.created_by`.

**If `current_email` matches `page_owner` OR `page_creator` (case-insensitive):**

Auto-apply via `skills/kb-builder/scripts/kb-writer.py`:

```
python3 skills/kb-builder/scripts/kb-writer.py \
  --path "<target_path>" \
  --content-file "<tmp-file with new body>" \
  --frontmatter-json '<merged fm with last_verified=today>' \
  --user-email "<current_email>" \
  --user-groups "<$USER_GROUPS or empty>" \
  --kb-root-label "${CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL:-prescyent-kb}"
```

`kb-writer.py` handles redaction, classification, the access check, writing, and the per-user JSONL log entry at `{KB_ROOT}/_meta/build-log/{YYYY-MM-DD}-{user-slug}.jsonl`. On success, echo: "Applied. New `last_edited_by`: {you}. Logged."

On `access_denied` / `conflict_copy` / any non-zero exit, surface the status verbatim and the recovery hint kb-writer returned. Do NOT fall through to the PR path — an owner who can't write is a classification bug, not a queue-a-PR case.

**Else (non-owner):**

Write a proposal file directly through `skills/kb-builder/scripts/storage.py` — NOT through `kb-writer.py`. A proposed update is not a published page; it does not carry the envelope contract and it should not trigger redact/classify. Target:

```
{KB_ROOT}/_meta/proposed-updates/{YYYY-MM-DD}/{page-slug}-proposed-by-{user-slug}.md
```

where `page-slug` is the target path with `/` replaced by `--` and the `.md` stripped. Content:

```yaml
---
proposed_for: "<target_path>"
proposed_by: "<current_email>"
requested_at: "<ISO timestamp>"
owner_email: "<page_owner>"
change_summary: "<first-line of user's description>"
---

## Original (unchanged)

<original body>

## Proposed change

<new body>

## Rationale (from requester)

<user's full description>
```

Instantiate `store = KBStorage(kb_root_label)` and call `store.write(proposal_path, content, frontmatter)` directly. This is a proposal queue — intentionally outside the kb-writer pipeline.

Echo: "Proposed. Owner ({page_owner}) reviews in `_meta/proposed-updates/`. Ping them directly if urgent."

## Voice

No banned words. Short sentences. Status updates ≤30 words. Errors ≤20 words plus a recovery step.
