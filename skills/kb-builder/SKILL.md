---
name: kb-builder
description: >
  Captures preflight, scaffolds the 13-folder Karpathy wiki on the user's drive,
  fans out mining subagents in parallel, then synthesizes the graph. Invoked from
  `/kb-build`. Run after `/discover` (chained via `--from-discover`) or run
  directly. Used when the user asks to "build the KB", "build the knowledge base",
  "populate the wiki", "set up the wiki", or "scaffold the KB".
background_safe: false
---

# kb-builder

`background_safe: false` unconditionally. Phase 0 uses widget elicitation (with `AskUserQuestion` fallback). Phase 1 scaffold has a `--reset` confirmation. Phase 2 mining fan-out has to originate from the main thread so `Task` dispatch works.

This is the **Map** + **Build** step in the Prescyent Discover → Map → Build → Deliver quartet.

---

## Mode + flow

`/kb-build` runs three phases in order:

- **Phase 0 — Preflight capture** (always)
- **Phase 1 — Scaffold** (skipped if KB already scaffolded)
- **Phase 2 — Mining + graph** (always — this is what the user came for)

Plus optional **Phase 3 — Reset**, gated by `--reset` in `$ARGUMENTS`.

`/kb-scaffold` was retired in v0.3 — `/kb-build` owns the scaffold step internally.

---

## Phase 0 — Preflight capture

### 0a. Cowork project session check (v0.6, EM-38)

`/kb-build` writes intermediate artifacts to the Cowork session's working folder AND mines content to the user's drive. It needs a Cowork PROJECT session, not a one-shot Cowork chat.

Inspect the current working directory:

- If `cwd` matches the pattern `*/local-agent-mode-sessions/*/local_*/outputs` AND there's no `.cowork-project` marker (or equivalent project metadata) up the tree, treat as a one-shot session and abort.
- If `cwd` is inside a Cowork project's working folder (the user explicitly opened the session inside a project from the Cowork UI), continue.

When aborting, emit (≤80 words):

> `/kb-build` needs a Cowork project session to run cleanly. The skill writes 13 folders of mined content to your drive AND uses the Cowork session's working folder for intermediate artifacts. A one-shot chat doesn't give it that.
>
> Open a new Cowork session inside a Cowork project (Projects sidebar → your project → New session), then re-run:
>
>     /kb-build --from-discover {discover_md_path if present, else nothing}
>
> This protects you from running out of token budget halfway through and from polluting your chat sandbox with wiki files.

Then return cleanly. Do not proceed to 0b.

The check is heuristic — Cowork's project-vs-chat distinction may not always be cleanly inferrable from cwd. Err on the side of WARNING (continue with a one-line note) rather than blocking when the heuristic is uncertain. Hard abort only when we're confident the session is a one-shot chat.

### 0b. Argument parsing

Parse `$ARGUMENTS`:

- `--from-discover <path>` — path to a `/discover` markdown report. Read its YAML frontmatter for preflight seed values.
- `--reset` — force-wipe the public wiki and re-mine. Confirmation required (Phase 3).
- `only:<a>,<b>` — dispatch only the named mining subagents.
- `skip:<a>` — dispatch every mining subagent except the named ones.

### 0c. Existing preflight check

Resolve the staging path: `~/.prescyent/<slug>/preflight.md` (slug derived from preliminary `company_name` if known, otherwise from `--from-discover` path or `_pending` placeholder).

Resolve the KB-root path via `python3 skills/kb-builder/scripts/storage.py --test "${KB_ROOT_LABEL:-prescyent-kb}"` — if it returns cleanly AND `{KB_ROOT}/_meta/preflight.md` exists, the user has a scaffolded KB. Skip to Phase 2 in **resume** mode (the file already has everything needed).

If the KB-root preflight exists but the staging-dir preflight does not, that's the join-existing-KB case — capture only `user_email`, `user_role`, append to `joining_users[]` in the existing preflight, and continue.

### 0d. Seed from `--from-discover`

If `--from-discover <path>` was provided:

```bash
python3 - <<'EOF'
import yaml, sys
md = open("<path>").read()
if md.startswith("---\n"):
    end = md.find("\n---\n", 4)
    fm = yaml.safe_load(md[4:end]) if end > 0 else {}
    print(yaml.safe_dump(fm))
EOF
```

Extract: `company_name`, `company_slug`, `user_role`, `buyer_intent`, `verbatim_pain`, `connectors_detected` (if present). Carry these forward as preflight seeds.

If the discovery markdown is missing or malformed, surface (≤30 words):

> Couldn't read `--from-discover` at `{path}`. Re-run `/discover`, save the report (Phase 6 option 1), and pass that path here.

Then exit cleanly.

### 0e. Capture remaining fields via widget

Determine which preflight fields are still missing. Always-required fields not derivable from `--from-discover`:

- `storage_target` — `gdrive` / `onedrive` / `sharepoint` / `local`
- `kb_root_label` — defaults to the `userConfig.kb_root_label` value (`prescyent-kb`)
- `user_email` — from session identity
- `company_name` (if not seeded by `--from-discover`)
- `user_role` (if not seeded by `--from-discover`)

If `mcp__visualize__show_widget` is available, render a single form for the missing fields. Field shape mirrors `skills/discover/references/widget-form-spec.md`:

```jsonc
{
  "title": "Where should your knowledge base live?",
  "subtitle": "Pick a backend the team can read. We'll write through the local sync mount, no extra credentials needed.",
  "fields": [
    {
      "key": "storage_target",
      "type": "select",
      "label": "Backend",
      "required": true,
      "options": [
        {"value": "gdrive",     "label": "Google Drive (Shared Drive synced by Drive Desktop)"},
        {"value": "onedrive",   "label": "OneDrive / SharePoint (synced by OneDrive Desktop)"},
        {"value": "local",      "label": "This computer only (no team sharing)"}
      ]
    },
    {
      "key": "kb_root_label",
      "type": "text",
      "label": "KB folder name",
      "default": "prescyent-kb",
      "required": true
    },
    {
      "key": "company_name",
      "type": "text",
      "label": "What's your company called?",
      "required": true
    },
    {
      "key": "user_role",
      "type": "select",
      "label": "Your role",
      "required": true,
      "options": [
        {"value": "founder",   "label": "Founder / CEO"},
        {"value": "cfo",       "label": "CFO / Finance lead"},
        {"value": "ops",       "label": "Head of Ops"},
        {"value": "sales",     "label": "Sales / GTM lead"},
        {"value": "marketing", "label": "Marketing lead"},
        {"value": "product",   "label": "Product / Engineering lead"},
        {"value": "other",     "label": "Other"}
      ]
    }
  ],
  "submit_label": "Build my KB",
  "skip_label": "Cancel"
}
```

**Skip the entire field if `--from-discover` already seeded it.** Don't ask twice.

If `mcp__visualize__show_widget` is unavailable, fall back to sequential `AskUserQuestion` calls for the missing fields. Each one applies the empty-response contract.

### 0f. Derive the slug

`company_slug` derives from `company_name`: lowercase, replace `[^a-z0-9-]+` with `-`, strip leading/trailing hyphens, collapse runs of `-` (use `slug_email`-style canonicalization if needed for email-derived slugs — see `scripts/storage.py::slug_email`).

### 0g. Write the preflight

Write to `~/.prescyent/<company_slug>/preflight.md` with the full schema at `references/preflight-schema.md`. Include:

```yaml
---
company_name: <name>
company_slug: <slug>
user_role: <role>
user_email: <email>
buyer_intent: <intent>          # if seeded from --from-discover
verbatim_pain: <pain>           # if seeded from --from-discover
storage_target: <target>
kb_root_label: <label>
created_at: <today_date>
champion_user:
  email: <email>
  role: <role>
joining_users: []
connectors_detected: [...]
---
```

If a preflight already exists at that path, merge — `champion_user` is write-once; new joiners append to `joining_users`.

---

## Phase 1 — Scaffold (skipped if already scaffolded)

### 1a. Discover the KB root

Resolve via `storage.py` with the captured `storage_target`:

```bash
KB_ROOT_LABEL="${PREFLIGHT_KB_ROOT_LABEL:-prescyent-kb}"
EXPECTED_TARGET="${PREFLIGHT_STORAGE_TARGET}"
python3 skills/kb-builder/scripts/storage.py --expected "${EXPECTED_TARGET}" --test "${KB_ROOT_LABEL}"
```

If the discovered root falls back to `~/prescyent-kb/...` but the user picked Drive / OneDrive, walk through setup (≤120 words):

> I couldn't find a `{KB_ROOT_LABEL}` folder in your Google Drive / OneDrive sync mount. To use cloud sync:
>
> 1. Create a Shared Drive named `{KB_ROOT_LABEL}` in Google Drive (or a single My Drive folder for solo work).
> 2. Confirm Drive Desktop is syncing it — it should appear at `~/Library/CloudStorage/GoogleDrive-{email}/Shared drives/{KB_ROOT_LABEL}/`.
> 3. Re-run `/kb-build`.
>
> Or re-run `/kb-build` with `storage_target: local` to write to `~/prescyent-kb/{KB_ROOT_LABEL}/` on this machine.

Exit cleanly. Do not proceed to writes.

### 1b. Champion check

If `{KB_ROOT}/MANIFEST.md` already exists, the current user is **joining** an existing KB.

Join-mode behavior:

- Skip scaffold.
- Write `{KB_ROOT}/_meta/team/{slug_email}.md` with a stub Role page (identity + date joined + role from preflight).
- Append to `joining_users[]` in `{KB_ROOT}/_meta/preflight.md`.
- Skip to Phase 2.

If `MANIFEST.md` does not exist, the current user is the **champion**. Continue.

### 1c. Run init-kb.py

```bash
python3 skills/kb-builder/scripts/init-kb.py \
  --kb-root-label "${KB_ROOT_LABEL}" \
  --user-email "${USER_EMAIL}" \
  --slug "${COMPANY_SLUG}"
```

The script is idempotent — re-running without `--reset` on an already-scaffolded root is a no-op aside from the champion check.

What it does:

1. Creates `_meta/{team,interviews,build-log,proposed-updates,gaps}/`.
2. Creates `public/{00-meta..12-external}/` (13 folders) each with a stub `AGENTS.md`.
3. Creates `_raw/{interviews,connector-dumps,documents}/` each with a `.gitkeep`.
4. Writes root `CLAUDE.md`, `MANIFEST.md`, `index.md`, `log.md` from the templates in `skills/kb-builder/references/root-claude-md-template.md` and the inline templates in `init-kb.py`.
5. Moves `~/.prescyent/<slug>/preflight.md` → `{KB_ROOT}/_meta/preflight.md`.

### 1d. Scaffold-complete summary

Print (≤80 words, voice-checked):

> KB scaffold complete at `{KB_ROOT}`.
>
> 13 `public/` folders, each with its own `AGENTS.md`. `_meta/` ready for interviews, build logs, team files. `_raw/` ready for source artifacts. Root `CLAUDE.md` + `MANIFEST.md` + `index.md` + `log.md` written.
>
> Mining your connectors next.

Move directly to Phase 2 — do not exit between scaffold and mining.

---

## Phase 2 — Mining + graph

### 2a. Verify scaffold + preflight at KB root

Refuse fast if any required precondition is missing. Print one banned-word-free error + a recovery step, then exit.

1. **Scaffold present.** `{KB_ROOT}/MANIFEST.md` exists. (Should always be true after Phase 1; check anyway.)
2. **Preflight at KB root.** `{KB_ROOT}/_meta/preflight.md` exists. If not:

   > Preflight didn't make it to your KB root. Re-run `/kb-build` to repair the staging — your scaffold is intact.

3. **`ANTHROPIC_API_KEY` set.** Required by `kb-writer.py` for the inline classifier + redactor calls. If not:

   > `ANTHROPIC_API_KEY` is not set. Add it to your environment so kb-writer can classify and redact.

4. **At least one MCP connector detected.** Mirror Phase 1 of `/discover` — inventory active MCP tools, classify per `CONNECTORS.md`. If none:

   > No connectors detected. Connect at least one tool (CRM, cloud storage, or chat) in this session, then re-run `/kb-build`.

### 2b. Read context

- `{KB_ROOT}/_meta/preflight.md` → `company_name`, `user_email`, `user_role`, `buyer_intent`, `verbatim_pain`, `connectors_detected`, `today_date`, `kb_root_label`.
- `{KB_ROOT}/MANIFEST.md` → confirms which subagent owns which folders.
- If `--from-discover <path>` is in `$ARGUMENTS`, read the discovery markdown — extract `Top 3 AI Opportunities`, `Recommended Next Steps`, and the per-section findings. Pass these as scope hints to each mining subagent so they prioritize the same gaps the discovery surfaced.

### 2c. Dispatch mining subagents in parallel

Apply `only:` / `skip:` filters first. Dispatch the remaining mining subagents via **a single Task message with multiple tool calls**. Serial dispatch defeats the parallel context windows.

Connector slice per subagent (per `CONNECTORS.md`):

- `kb-company` ← `~~cloud-storage` (HR + About folders), `~~email` (leadership + HR mailbox metadata), `~~chat` (profile bios + admin channels)
- `kb-gtm` ← `~~crm`, `~~meeting-intel`, `~~cloud-storage` (marketing + sales folders), `~~chat` (sales channels), `~~email` (outbound + inbound deal traffic, metadata only)
- `kb-ops` ← `~~wiki`, `~~cloud-storage` (ops + SOP folders), `~~project-tracker` (repeating workflow patterns), `~~email` + `~~chat` (metadata for recurring ops traffic)

Each Task `prompt` includes verbatim:

- `company_name`, `user_email`, `today_date`, `kb_root_label` from preflight
- The relevant connector subset (filtered to what this subagent owns)
- The path to the latest discovery markdown if `--from-discover` was provided (so each subagent can prioritize against discovered gaps); else `none`
- Absolute path to `kb-writer.py`: `${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/kb-writer.py`
- Instruction: every write goes through `python3 kb-writer.py ...` via Bash. Never write files directly.
- Return contract: a single JSON object per the schema in the subagent's own AGENTS file (`pages_written`, `pages_by_folder`, `classifications`, `redactions_applied_total`, `errors`, `coverage_gaps`)
- Word-budget reminder: status updates ≤30 words, no banned words, "your company" framing.

### 2d. Collect mining results

When all dispatched subagents return, parse each JSON and aggregate:

- Total pages written across all subagents
- Pages by top-level folder (union of each subagent's `pages_by_folder`)
- Classification distribution (sum across `classifications` maps)
- Total redactions applied
- Errors (concatenate per-subagent `errors[]`)
- Coverage gaps (concatenate per-subagent `coverage_gaps[]`)

If any subagent returned malformed JSON, log the raw return and treat as zero pages from that subagent — never fabricate counts.

### 2e. Dispatch kb-graph

After all mining subagents return, dispatch `kb-graph` via one `Task` tool call. kb-graph runs alone (not parallel) because it reads what the mining subagents just wrote.

**Compute `user_ceiling` before dispatch.** kb-graph writes four `_meta/*` files that bypass the kb-writer funnel (redactor + classifier do not run). Without scoping, exec-only page titles, first paragraphs, owners, or voice excerpts could be laundered into plugin metadata that any reader of `_meta/` can open. kb-graph filters its synthesis by the caller's access ceiling — but only if you pass it in.

Derive the ceiling from `USER_GROUPS` (env var, comma-separated):

- `exec`, `leadership`, or `board` in groups → `user_ceiling = confidential`
- any department tag (`sales`, `engineering`, `finance`, etc.) in groups → `user_ceiling = department-only`
- empty or unknown groups → `user_ceiling = internal`

Never default to `confidential`. Never default to `public`.

```bash
USER_GROUPS="${USER_GROUPS:-}"
case ",${USER_GROUPS}," in
  *,exec,*|*,leadership,*|*,board,*) USER_CEILING="confidential" ;;
  ",,"|"") USER_CEILING="internal" ;;
  *) USER_CEILING="department-only" ;;
esac
```

Use the Task tool with:

- `subagent_type: "kb-graph"`
- `description: "Synthesizing wikilinks + MOCs + voice"`
- `prompt`: include verbatim — `kb_root_label`, `user_email`, `user_groups`, `user_ceiling: <tier>` (one of `public`, `internal`, `department-only`, `confidential`), the aggregated `mining_subagent_summaries` collected in 2d (total pages, pages_by_folder, classifications), and the expected return JSON contract (`wikilinks_added`, `mocs_written`, `mocs_skipped`, `index_entries`, `manifest_pages`, `voice_profile_sentences`, `gaps_detected`, `gaps_by_class`, `errors`).

If `user_ceiling` is omitted from the prompt, kb-graph falls back to reading `_meta/preflight.md` for the champion email and assuming the champion's ceiling; it defaults to `internal` when preflight is silent. Prefer passing it explicitly — the orchestrator knows the caller's identity and groups, kb-graph does not.

Wait for kb-graph to return. Parse its JSON. If malformed, log raw return and treat as zero-graph-work-done; never fabricate counts.

### 2f. Final summary

Print (≤120 words, voice-checked, no banned words):

> `{N}` pages written across `{M}` folders.
>
> - `public/01-company/` — N pages
> - `public/02-products/` — N pages
> - ... (one line per folder with non-zero count)
>
> Classification: `{public: n, internal: n, department-only: n}` (omit zero tiers).
> Voice profile: `{N}` sentences extracted from your team's writing.
> Coverage gaps: one line per gap, prefixed `-`. Omit if none.
>
> Next:
> - `/kb-interview me` — capture what only you know (the 5-stage script).
> - `/kb-my-pages` — list every page where you're owner or named in `audience`.

Re-sell the promise at the end: every future Claude session reads from this KB, so what lives here compounds.

---

## Phase 3 — Reset (gated by `--reset`)

If `--reset` is in `$ARGUMENTS`, confirm via `AskUserQuestion` (single-select) BEFORE running anything. Show the full enumeration so the champion knows exactly what survives and what doesn't:

> ⚠️ `--reset` will wipe all mined content:
>
> - All pages under `public/` (every Process / System / Role / Playbook / etc. that `/kb-build` wrote)
> - `_meta/MANIFEST.md`, `_meta/index.md`, `_meta/log.md`, `_meta/voice.md`
> - `_meta/gaps/*` (gap reports — regenerate on next `/kb-build`)
>
> **Preserved across reset:**
>
> - `_meta/preflight.md` (champion identity + company info)
> - `_meta/team/*` (team stubs from every joiner)
> - `_meta/interviews/*` (every captured transcript)
> - `_meta/build-log/*` (audit trail)
> - `_meta/proposed-updates/*` (queued forget-me / edit-mine batches)
> - `_raw/*` (immutable source artifacts)
>
> After reset, mining runs fresh against your current connectors. Continue?
>
> Options: "Yes, reset and preserve my identity", "Cancel".

If confirmed, `init-kb.py --reset` handles the stash/wipe/restore and re-scaffold. Then continue to Phase 2 mining as normal.
If aborted, exit without writing.

**Empty-response contract.** If the `AskUserQuestion` returns empty, null, or `""`, log `AskUserQuestion returned empty — aborting before any side effects` and exit. Never treat an empty response as `yes`. No wipe.

---

## Error handling

- `storage.py` raises `StorageNotFound` → Phase 1a recovery copy.
- `init-kb.py` exits non-zero → print stderr verbatim and stop. Do not retry.
- Missing `USER_EMAIL` in session → ask once via `AskUserQuestion` single free-text. Empty-response contract: empty = abort.
- Drive Desktop conflict copy detected mid-scaffold → stop, print the conflict path, tell the user to resolve by hand.
- Mining subagent timeout (>maxTurns or >30 min wall clock) → log, keep whatever pages that subagent wrote, continue summary with partial results.
- `kb-writer.py` non-zero exit → subagent captures stderr JSON, adds to `errors[]`, continues with remaining pages. Orchestrator does not retry.
- Access-denied writes (`status: access_denied` from kb-writer) → expected for tier mismatches. Do not fail the run; surface count in summary.

---

## Voice

Every user-facing string runs the gauntlet at `references/voice-rules.md` before it ships. Banned words: see voice-rules. Word budgets: orientation ≤80, status ≤30, errors ≤20 + one recovery step.
