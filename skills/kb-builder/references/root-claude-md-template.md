# Root CLAUDE.md Template

This template is rendered into `{KB_ROOT}/CLAUDE.md` by `init-kb.py` on first scaffold. It is the single most-read file in the whole knowledge base — every future AI session opens it. Keep it under 1500 tokens.

Placeholders (double-braced) are substituted at render time:

- `{{champion_email}}` — email of the user who ran `/kb-build` first
- `{{created_at}}` — ISO date of scaffold
- `{{kb_root_label}}` — the folder name (e.g. `prescyent-kb`)

---

## TEMPLATE BODY (everything below this line is written verbatim into `CLAUDE.md`, with placeholders substituted)

```markdown
# {{kb_root_label}}

This folder is the company knowledge base. It is markdown on your drive. You own it. Any AI session — Claude Cowork, Claude Code, or a future client — can read it and answer questions about your company with specifics, not generalities.

Created: {{created_at}}
Champion: {{champion_email}}

## What this KB is

A typed, atomic, hyperlinked wiki. Every page has a page type (Process, System, Role, Decision, Concept, Playbook, Glossary). Every page has frontmatter: an owner, a confidence level, a last-verified date, a confidentiality class. Pages are short on purpose — an agent reading the KB should be able to hold one page fully in context and follow links outward.

## How to read this KB (if you are an AI agent)

1. Start at `MANIFEST.md` to find which folder owns the topic you care about.
2. Open `_meta/preflight.md` for the company basics and the champion's goals.
3. Every page is self-describing via frontmatter. Trust the frontmatter; it is the contract.
4. Every folder under `public/` has an `AGENTS.md` with domain-specific instructions. Read it before writing into that folder.
5. Do not edit any page under `_raw/`. Those are immutable source artifacts. Read them; synthesize from them; never rewrite them.
6. To update a page that a human owns, write a proposal to `_meta/proposed-updates/` instead of editing in place.

## Folder map

- `public/00-meta/` — this KB about itself.
- `public/01-company/` — identity, mission, history, org chart.
- `public/02-products/` — product catalog.
- `public/03-customers/` — customer segments, ICPs, personas.
- `public/04-gtm/` — positioning, pricing, channels, competitive intel.
- `public/05-operations/` — the core processes the company runs on.
- `public/06-people/` — roles and functions (Role pages). Not individuals.
- `public/07-systems/` — every tool the company runs on, with SOR pointers.
- `public/08-projects/` — in-flight initiatives.
- `public/09-decisions/` — ADRs. Immutable; supersede chains record change.
- `public/10-glossary/` — company dialect, preserved exactly.
- `public/11-playbooks/` — step-by-step runbooks.
- `public/12-external/` — public-domain context that shapes this company.
- `_meta/` — plugin operational metadata. Interviews, build logs, team files.
- `_raw/` — source artifacts. Immutable.

## Page types

Seven types, each with its own schema. See `skills/kb-builder/references/page-types/` in the plugin repo:

- **Process** — a workflow with inputs, outputs, steps, owner.
- **System** — a tool, with what records it is authoritative for.
- **Role** — a function, with responsibilities and informal go-to patterns.
- **Decision** — an ADR. Alternatives, rationale, tradeoffs. Immutable.
- **Concept** — a noun the company uses, with aliases.
- **Playbook** — a runbook.
- **Glossary** — company dialect, preserved exactly.

Every page opens with the universal frontmatter envelope (see `skills/kb-builder/references/universal-frontmatter-envelope.md`).

## Confidentiality tiers

Every page has a `classification` field. Pages route to folders based on this:

- `public` — everyone in the company reads.
- `internal` — employees only. Most pages land here.
- `department-only` — scoped to one department's folder.
- `exec-only` — board, execs, champion only.
- `confidential` — legal / finance / hr only.

The `kb-classifier` subagent assigns this on write. When the classifier is uncertain (<0.9 confidence), it defaults to the most-restrictive tier.

## How to add content

- Run `/kb-build` to have the plugin mine your connectors and populate the wiki.
- Run `/kb-interview me` to capture knowledge that lives only in your head.
- Edit a page by hand — keep the frontmatter intact, update `last_edited_by` and `last_verified`.
- Propose an edit to someone else's page via `_meta/proposed-updates/`.

Every write passes through `kb-writer`, which runs PII redaction, classification, and an audit log entry. Do not sidestep it.

## Voice

Pages read like a careful internal writer wrote them. Direct. Specific. No hedging. No process narration. Terms the company actually uses, not sanitized synonyms. When you don't know something, say "unknown" in the frontmatter's `confidence` field — don't guess.

## AGENTS.md per folder

Each folder under `public/` has an `AGENTS.md` with folder-specific expectations: what page types belong there, what depth is right, what to never write. Read the folder's `AGENTS.md` before writing into it.

## If something looks wrong

- Gaps and broken links are logged to `_meta/gaps/`. Fix them or flag them.
- Conflict copies (`page (1).md`) mean Drive sync caught a simultaneous edit. Merge them by hand; never let the writer overwrite.
- Supersede chains must be bidirectional. If a page's `status` is `superseded`, its `superseded_by` names the successor, and the successor's `supersedes` names it.
- `kb-graph` runs after every `/kb-build` and catches most of this automatically.

## Questions

Ask the champion ({{champion_email}}). For plugin bugs, check the plugin repo on GitHub.
```
