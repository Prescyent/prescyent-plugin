# `preflight.md` — Schema

Every `/kb-build` run reads (and writes, if missing) a `preflight.md` file. The champion's run writes to `~/.prescyent/{slug}/preflight.md` (local staging); `init-kb.py` then moves it into `{KB_ROOT}/_meta/preflight.md` during scaffold. Joining team members append their entry to the KB copy directly via `/kb-build`.

Every downstream command (`/kb-build`, `/kb-interview`, `/kb-screener`, `/kb-my-pages`, `/kb-edit-mine`, `/kb-forget-me`) reads this file to scope behavior.

## Fields

| Field | Type | Written by | Notes |
|---|---|---|---|
| `company_name` | string, **required** | champion only | Captured in `/kb-build` Phase 0. From `--from-discover` markdown frontmatter if available, else widget form. Write-once. |
| `company_slug` | string, **required** | champion only | Derived from `company_name` by lowercasing and replacing non-`[a-z0-9-]` with `-`, collapsing runs. Used in every downstream path. Write-once. |
| `company_size` | enum, optional | champion only | `1-10` / `11-50` / `51-200` / `201-1000` / `1000+`. v0.3 doesn't require this — drives optional copy choices only. |
| `user_role` | enum | every user | `founder` / `cfo` / `ops` / `sales` / `marketing` / `product` / `other`. From `--from-discover` markdown if available, else widget form. |
| `user_email` | string | every user | Captured from session identity. Required. |
| `buyer_intent` | enum, optional | champion only | `ai-readiness` / `capture-senior-knowledge` / `claude-actually-useful` / `other`. From `--from-discover` markdown if available. Drives mining-subagent prompt prioritization. |
| `verbatim_pain` | string, optional | champion only | Free-text pain. Preserved verbatim — drives voice tuning. From `--from-discover` markdown if available. |
| `storage_target` | enum | champion only | `local` / `gdrive` / `onedrive` / `sharepoint`. Always asked in `/kb-build` Phase 0 (not derivable from `--from-discover`). |
| `kb_root_path` | string | champion only | Absolute path discovered by `storage.py` after storage_target is chosen. |
| `kb_root_label` | string | champion only | Matches the `userConfig.kb_root_label` value (default `prescyent-kb`). Always asked in `/kb-build` Phase 0. |
| `created_at` | ISO-8601 date | champion only | Date of champion's first `/kb-build` run. |
| `champion_user` | object | champion only | `{email, role, name?}`. **Never changes after first write.** |
| `joining_users` | list of objects | every joining user | Each entry: `{email, role, name?, joined_at}`. Appended only by joiners. |
| `connectors_detected` | list of strings | every user | MCP categories present at run-time (e.g., `~~crm`, `~~email`). Latest wins. |

## Example

```yaml
---
company_name: Acme Inc
company_slug: acme
company_size: 51-200
user_role: cfo
user_email: alex@acme.com
buyer_intent: capture-senior-knowledge
verbatim_pain: "Tribal knowledge walks out the door every time someone leaves."
storage_target: onedrive
kb_root_path: /Users/alex/Library/CloudStorage/OneDrive-Acme/prescyent-kb
kb_root_label: prescyent-kb
created_at: 2026-04-29
champion_user:
  email: alex@acme.com
  role: cfo
  name: Alex Chen
joining_users:
  - email: robin@acme.com
    role: ops
    name: Robin Q.
    joined_at: 2026-04-30
connectors_detected:
  - ~~email
  - ~~cloud-storage
  - ~~meeting-intel
---
```

## Rules

1. `champion_user` is write-once. Any later run that detects an existing preflight switches to join mode and appends to `joining_users`.
2. `company_slug` is write-once. Derived from `company_name` on first run, used in every path after.
3. Empty-response contract applies to every elicitation site that contributes to preflight: empty answer = abort cleanly, no silent defaults, no preflight write.
4. v0.3 — fields populated from a `--from-discover <path>` markdown's YAML frontmatter must NOT be re-asked via the widget. Only ask for fields the markdown didn't cover.
