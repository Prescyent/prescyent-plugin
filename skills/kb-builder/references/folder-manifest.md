# KB Folder Manifest

The canonical structure for every Prescyent KB. Single source of truth — both `SKILL.md` and `scripts/init-kb.py` read from this list. Changes here propagate to scaffold.

## Top-level files

| File | Purpose |
|---|---|
| `CLAUDE.md` | Karpathy Layer 3 — tells every future AI session how to read this KB. |
| `MANIFEST.md` | Agent routing — which subagent owns which folders. |
| `index.md` | Human-navigable catalog. One line per page. |
| `log.md` | Append-only audit trail of every scaffold, build, and refresh. |

## `_meta/` — plugin operational metadata

Everything the plugin needs to operate. Not customer knowledge; scaffolding around it.

| Path | Purpose |
|---|---|
| `_meta/preflight.md` | Captured from `/kb-build` Phase 0. Read by every downstream command. |
| `_meta/voice.md` | Extracted voice profile from observed customer writing (written by `/kb-build`). |
| `_meta/team/` | One `{email}.md` per team member. Written on `/kb-interview` or via `/kb-build` join-mode. |
| `_meta/interviews/` | Per-user interview transcripts (`{email}/{YYYY-MM-DD}-{slug}.md`). |
| `_meta/build-log/` | Per-user JSONL audit trail (`{YYYY-MM-DD}-{email}.jsonl`). |
| `_meta/proposed-updates/` | AI-suggested edit queue for human-owned pages. |
| `_meta/gaps/` | Gap reports from `kb-graph` (broken supersede chains, orphaned pages). |

## `public/` — the 12-folder Karpathy wiki

All 12 folders get a stub `AGENTS.md` at scaffold time. Subagents populate the pages later.

| Folder | What belongs here |
|---|---|
| `public/00-meta/` | KB-about-itself pages: taxonomy, how to contribute, review cadence. |
| `public/01-company/` | Company identity: mission, history, org chart, values, locations. |
| `public/02-products/` | Product catalog: each product as its own Concept or System page with version, owner, status. |
| `public/03-customers/` | Named customers, segments, ICPs, personas. Redact individuals unless public. |
| `public/04-gtm/` | Go-to-market: positioning, pricing, channels, playbooks, competitive intel. |
| `public/05-operations/` | How the company runs: core Processes (lead-to-cash, order-to-cash, hire-to-retire). |
| `public/06-people/` | Roles and functions — the Role page type. Not individual people (that's _meta/team/). |
| `public/07-systems/` | Every tool the company runs on. `records_authoritative_for` names the SOR. |
| `public/08-projects/` | In-flight initiatives. Link to Decisions, Systems, and Roles they touch. |
| `public/09-decisions/` | ADRs. Immutable; supersede chains track what changed. |
| `public/10-glossary/` | Company dialect. Preserves exact phrasing. `do_not_confuse_with` is the point. |
| `public/11-playbooks/` | Step-by-step runbooks. Each linked to the Process or Role it serves. |
| `public/12-external/` | Public-domain context that still matters to this company (regulatory docs, market reports). |

## `_raw/` — immutable source (Karpathy Layer 1)

Never rewritten. Subagents read; they never mutate. Every subfolder gets a `.gitkeep` at scaffold.

| Folder | Contents |
|---|---|
| `_raw/interviews/` | Raw interview transcripts before synthesis. |
| `_raw/connector-dumps/` | Untransformed MCP extracts (Slack JSON, HubSpot CSV, Gmail mbox). |
| `_raw/documents/` | Exported docs, PDFs, spreadsheets. |

## Counts

- Top-level files: 4 (CLAUDE.md, MANIFEST.md, index.md, log.md)
- `_meta/` files + subfolders: 1 file (preflight, moved in from ~/.prescyent) + 6 subfolders
- `public/` subfolders: 12 (each with its own `AGENTS.md` stub)
- `_raw/` subfolders: 3 (each with `.gitkeep`)

Total directories created by scaffold: **21** (1 `_meta/` + 6 `_meta/` children + 12 `public/NN-*/` + 3 `_raw/*/` — minus the KB root itself, which already exists).
