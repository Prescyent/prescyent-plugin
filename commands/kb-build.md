---
description: Build a living wiki on your drive from your connected tools. The KB every future Claude session reads from. Run after /discover to seed scope, or run directly.
argument-hint: "[--from-discover <path> | only:<subagent>,<subagent> | skip:<subagent> | --reset]"
background_safe: false
---

Build the Prescyent knowledge base. This command owns the full setup-to-mining flow — preflight capture, scaffold, and the parallel-fan-out mining run.

Routes to `skills/kb-builder/SKILL.md`. The skill:

1. **Captures preflight.** Either reads it from a `/discover` markdown via `--from-discover <path>`, or asks the user via a single widget form (storage target, KB root label, company name, role).
2. **Scaffolds the wiki.** Calls `scripts/init-kb.py` to create the 13-folder Karpathy structure on the user's drive, with universal frontmatter envelopes and access-controlled folders. Idempotent — re-running on an already-scaffolded root is a no-op aside from the champion check.
3. **Mines the connectors.** Dispatches three subagents in parallel via the `Task` tool: `kb-company`, `kb-gtm`, `kb-ops`. Each writes through `scripts/kb-writer.py` — the single funnel that redacts PII, classifies confidentiality, checks access, and appends an audit log line per write.
4. **Synthesizes the graph.** Runs `kb-graph` to add wikilinks, write maps-of-content, build the index, extract voice, and surface coverage gaps.

This is the **Map** + **Build** step in the Discover → Map → Build → Deliver quartet. Every page lands in the user's drive, not Prescyent's.

## Arguments (optional, in `$ARGUMENTS`)

- `--from-discover <path>` — seed preflight from a `/discover` markdown report. Reads `company_name`, `company_slug`, `user_role`, `buyer_intent`, `verbatim_pain` from the markdown's YAML frontmatter. Asks only for missing fields (typically storage target + KB root label).
- `only:kb-company,kb-gtm` — dispatch only the named mining subagents. Useful for re-running a single slice.
- `skip:kb-ops` — dispatch every mining subagent except the ones named.
- `--reset` — wipe the public wiki and re-mine. Preserves identity, team stubs, interviews, build log, and proposed-updates queues. Confirmation required.

## Critical constraints

- Storage selection happens HERE (not in `/discover`). The user picks Drive / OneDrive / SharePoint / Local before any drive write.
- Every mining write goes through `kb-writer.py` — never write directly to public wiki paths.
- Empty-response contract on every `AskUserQuestion` site: empty answer aborts before any side effects.
- `--reset` confirmation is destructive; `AskUserQuestion` empty response = treated as abort, never silently confirmed.
- Subagent fan-out goes via the `Task` tool in a single parallel block — do not serialize.
- Every user-visible string passes the voice gauntlet at `skills/kb-builder/references/voice-rules.md`.
