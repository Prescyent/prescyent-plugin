# Prescyent Plugin

**Discover → Map → Build → Deliver** — in your own AI workspace.

Install this plugin in Claude Cowork or Claude Code. The plugin reads the tools you have already connected, runs a discovery against your actual data, and returns a one-page AI readiness assessment inline in your chat. From there, it can turn the assessment into a living wiki on your own drive — interviewing your senior people for the work nobody wrote down — that every future Claude session reads from.

**v0.8 architecture.** Nine audit lanes run in parallel: `audit-systems`, `audit-knowledge`, `audit-drive`, `audit-email`, `audit-comms`, `audit-meeting-transcripts`, `audit-stack`, `audit-sessions`, `audit-web-search`. The master then runs a gap-detection pass that resumes specific subagents to deepen findings (1/3/6 follow-ups per subagent at Standard/Medium/Very-deep depth). The buyer-facing HTML deck stays light and marketing-grade; the analyst markdown report becomes the load-bearing deliverable — 50-100 KB, AI-consumable for downstream `/kb-build --from-discover` ingestion or Prescyent's deal-context tooling.

**Model defaults.** v0.8 ships with all subagents on Opus 4.7 + 1M context flag for self-dogfood validation. **Sonnet fallback** for cost-sensitive deployments: a single sed pass swaps every `model: opus` → `model: sonnet` across the agent files. Toggle for the alpha cohort before wider distribution.

## What you get

| Command | What it does | When you run it |
|---|---|---|
| `/discover` | Connector-aware AI readiness assessment, rendered inline. About five minutes. | First time you install — or any time you want a fresh read |
| `/kb-build` | Build a living wiki from your connectors. Storage selection happens here. | After `/discover`, or directly with `--from-discover <path>` |
| `/kb-interview me` | 45-min structured chat. Writes a private transcript and a public profile page. | Per team member |
| `/kb-screener me` | 10–15 min triage variant of the interview | Fast start, narrower scope |
| `/kb-my-pages` | Show every KB page about you (GDPR art. 15) | Anytime |
| `/kb-edit-mine` | Edit pages you own or that mention you (GDPR art. 16) | Anytime |
| `/kb-forget-me` | Propose deletion or redaction of your content (GDPR art. 17) | Anytime |

## Install (alpha)

In a fresh Cowork or Claude Code session:

```
/plugin marketplace add Prescyent/prescyent-plugin
/plugin install prescyent-plugin@prescyent
/discover
```

For the wiki backend (Drive / OneDrive / SharePoint), install Drive Desktop or OneDrive Desktop first so the shared drive shows up under `~/Library/CloudStorage/`. The plugin writes through that local mount — no extra API credentials needed.

You can also run `/discover` against any single connector you have plugged into your session. Two or more is better — discovery cross-references findings.

## How it flows

```
                 ┌────────────────────────────────────────┐
                 │  /discover                             │
                 │  Reads your connectors + the open web  │
                 │  Single widget form (3-tier depth)     │
                 │  9 audit subagents in parallel         │
                 │  Master gap-detection + resumption     │
                 │  HTML deck + 50-100 KB markdown report │
                 │  rendered inline + email body inline   │
                 │  embeds the full artifact bundle       │
                 └────────────────────────────────────────┘
                                   │
                                   ▼
                          ┌──────────────────┐
                          │  Three options:  │
                          ├──────────────────┤
                          │  • Save to drive │
                          │  • Email Tyler   │
                          │  • Build the KB  │
                          └──────────────────┘
                                   │
                                   ▼  (if "Build the KB")
                 ┌────────────────────────────────────────┐
                 │  /kb-build --from-discover <path>      │
                 │  Storage pick + scaffold (13 folders)  │
                 │  3 mining subagents in parallel        │
                 │  kb-graph synthesis (wikilinks, MOCs)  │
                 │  Living wiki on YOUR drive             │
                 └────────────────────────────────────────┘
                                   │
                                   ▼
                 /kb-interview me  /kb-screener me
                 /kb-my-pages  /kb-edit-mine  /kb-forget-me
```

`/discover` writes nothing to your drive unless you opt in at the chained-action step. `/kb-build` is where storage selection, scaffolding, and mining happen.

## What lives on your drive (after `/kb-build`)

The scaffold creates three top-level trees under `{KB_ROOT}/`:

- `public/00-meta/` — how this KB is organized
- `public/01-company/` — mission, history, org chart, values
- `public/02-products/` — product catalog, one page per product
- `public/03-customers/` — named customers, segments, ICPs
- `public/04-gtm/` — positioning, pricing, channels, playbooks
- `public/05-operations/` — core processes (lead-to-cash, hire-to-retire)
- `public/06-people/` — Role pages by function, not person
- `public/07-systems/` — every tool, with system of record named
- `public/08-projects/` — in-flight initiatives
- `public/09-decisions/` — ADRs, immutable, with supersede chains
- `public/10-glossary/` — company dialect, exact phrasing preserved
- `public/11-playbooks/` — step-by-step runbooks
- `public/12-external/` — public-domain context that still matters here
- `_meta/` — plugin operational files: preflight, voice profile, team stubs, interview transcripts, audit log, gap reports
- `_raw/` — immutable source: interviews, connector dumps, documents

Your drive, your data. Every file is plain markdown — open, edit, or delete by hand any time.

## Security and privacy

- Every KB write runs through `kb-writer.py` — a single funnel that redacts PII, classifies confidentiality, checks the user's access, writes, and appends an audit line.
- Five classification tiers: `public`, `internal`, `department-only`, `team-only`, `restricted`. Defaults lean most-restrictive on uncertainty.
- No Prescyent-operated backend reads your data. MCP connectors are yours; the session is yours; the KB lives on your drive.
- Right of access, rectification, and erasure are first-class commands — `/kb-my-pages`, `/kb-edit-mine`, `/kb-forget-me`.
- Interview transcripts are `restricted` by default — visible to the participant and the champion only.

## Page types

Seven schemas keep pages consistent and link-friendly. Full definitions under `skills/kb-builder/references/page-types/`.

- **Process** — end-to-end value stream (lead-to-cash, hire-to-retire). Has stages, owners, systems.
- **System** — a tool your company runs on. Names the system of record, owner, contract terms.
- **Role** — a function (not a person). Responsibilities, decision rights, informal go-to pattern.
- **Decision** — ADR-style, immutable, with supersede chains.
- **Concept** — anything else worth a wiki page: strategies, frameworks, models.
- **Playbook** — step-by-step runbook. Linked to a Process or Role.
- **Glossary** — company dialect. Aliases, `do_not_confuse_with`, exact phrasing preserved.

## Voice and multi-user

Every employee is a first-class user. `/kb-build` captures a champion on first run; each teammate joins later with their own widget submission and identity record. `/kb-interview` produces one private transcript plus one public profile per person. Multi-user converge is the design, not an afterthought.

Voice is extracted from your team's actual writing and stored at `_meta/voice.md`. Every new page writes in your tone, not a generic corporate one.

## Email body inline-embed (v0.8)

When you select "Draft a follow-up email to us at Prescyent" at the end of `/discover`, the draft body **inline-embeds** the full artifact bundle (markdown + HTML + JSON) below the signoff. Gmail MCP `create_draft` doesn't accept attachments, so the body string IS the deliverable. Both human readers (top section, email-as-email) and AI consumers (bottom section, fenced ``` blocks for ingestion) are served from one body string.

Body size is typically 110-180 KB — well within Gmail's 25 MB message limit. Some email clients (Outlook, Apple Mail) may truncate or warn at very large bodies; eyeball the first dogfood draft.

## Modes for `/discover`

| Argument | What it does |
|---|---|
| `/discover` | Standard run. Five fields, 10–15 sources analyzed, ~5 minutes. |
| `/discover depth:deep` | Broader sweep, more sources. Adds a few minutes. |
| `/discover role:founder` | Pre-seed your role; skip that widget question. |

## Supported connectors

The plugin adapts to whatever you have connected. It does not require a specific stack.

| Category | Example platforms |
|----------|-------------------|
| CRM | HubSpot, Salesforce, Pipedrive, Zoho, Close, Attio |
| Project tracker | Linear, Jira, Asana, Monday, Trello, ClickUp |
| Cloud storage | Google Drive, OneDrive, SharePoint, Box, Dropbox |
| Wiki | Notion, Confluence, Guru, Coda, Slite |
| Email | Gmail, Outlook (MS365) |
| Chat | Slack, Teams, Google Chat, Discord |
| Calendar | Google Calendar, Outlook Calendar |
| Meeting intelligence | Fathom, Gong, Granola, Otter, Chorus |
| Ticketing | Zendesk, Intercom, Freshdesk, HelpScout |

See `CONNECTORS.md` for the full map — both `/discover` audit subagents and `/kb-build` mining subagents read from this same pool.

## Composes with Anthropic's plugins

This plugin is designed to sit next to Anthropic's free knowledge-work plugins, not replace them. After `/discover`, the assessment names which complementary plugins would pay off the most in your stack — `enterprise-search`, `sales`, `customer-support`, and so on. Install them alongside.

## License

Apache License 2.0. See `LICENSE`.

Fork it, build on it, sell your own version, or run it air-gapped.

## Updating

Cowork's "Update" button only fires automatically when the Claude GitHub App is installed on the plugin repo. For installs that don't have the GH App, run `/plugin marketplace update prescyent` periodically to pull the latest, then `/plugin install prescyent-plugin@prescyent` again.

## Contributing

Open issues at https://github.com/Prescyent/prescyent-plugin/issues.

## Support + contact

- Issues: https://github.com/Prescyent/prescyent-plugin/issues
- Commercial questions: tyler@prescyent.ai
- The ladder above this plugin: https://prescyent.ai
