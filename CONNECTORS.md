# Connectors — What the Plugin Reads

The Prescyent plugin does **not** install its own MCP servers. It inherits whatever is connected in your Claude Cowork or Claude Code session and adapts scope accordingly.

Subagents reference connectors by **category** (`~~placeholder` syntax, matching Anthropic's `enterprise-search` convention). Skills map your connected platforms to these categories at runtime.

Both `/discover` and `/kb-build` read the same connector pool. If you've already run `/discover`, `/kb-build` reuses that detection rather than re-scanning — so you pay the detection cost once per session.

## Connector Categories → Audit Subagents

The audit maps each connector to one of four fan-out subagents. Each subagent owns its own 200K context window.

| Placeholder | Maps to | Feeds audit subagent |
|-------------|---------|----------------------|
| `~~crm` | HubSpot, Salesforce, Pipedrive, Zoho, Close, Attio | `audit-systems` |
| `~~project-tracker` | Linear, Jira, Asana, Monday, Trello, ClickUp | `audit-systems` |
| `~~cloud-storage` | Google Drive, OneDrive, SharePoint, Box, Dropbox | `audit-knowledge` |
| `~~wiki` | Notion, Confluence, Guru, Coda, Slite | `audit-knowledge` |
| `~~email` | Gmail, Outlook (MS365) | `audit-comms` |
| `~~chat` | Slack, Teams, Google Chat, Discord | `audit-comms` |
| `~~calendar` | Google Calendar, Outlook Calendar | `audit-comms` |
| `~~meeting-intel` | Fathom, Gong, Granola, Otter, Chorus | `audit-comms` |
| `~~ticketing` | Zendesk, Intercom, Freshdesk, HelpScout | `audit-systems` |
| `~~design` | Figma, Sketch, Canva | `audit-stack` (catalog only) |
| `~~dev` | GitHub, GitLab, Bitbucket | `audit-stack` (catalog only) |

## Connector Categories → KB-Builder Subagents

`/kb-build` dispatches three mining subagents in parallel — `kb-company`, `kb-gtm`, `kb-ops`. Each one owns a slice of the KB (different `public/NN-*` folders) and pulls from a different slice of your connector pool.

Primary = the subagent that owns the folder this data lands in. Secondary = that subagent also reads this category for cross-reference signal.

| Category | Example platforms | Primary subagent | Also used by |
|----------|-------------------|------------------|--------------|
| `~~crm` | HubSpot, Salesforce, Pipedrive, Zoho, Close, Attio | `kb-gtm` (accounts, pipeline, personas → `public/03-customers/`, `public/04-gtm/`) | `kb-company` (account contacts for org chart) |
| `~~project-tracker` | Linear, Jira, Asana, Monday, Trello, ClickUp | `kb-ops` (repeating workflow patterns → `public/05-operations/`, `public/11-playbooks/`) | — |
| `~~cloud-storage` | Google Drive, OneDrive, SharePoint, Box, Dropbox | split by subfolder: HR + About → `kb-company`; marketing + sales → `kb-gtm`; ops + SOP → `kb-ops` | all three |
| `~~wiki` | Notion, Confluence, Guru, Coda, Slite | `kb-ops` (SOPs → `public/05-operations/`, `public/11-playbooks/`) | `kb-gtm` (customer-facing docs), `kb-company` (HR + about pages) |
| `~~email` | Gmail, Outlook (MS365) | behavioral-trace metadata only — all three use it | `kb-company` (leadership + HR), `kb-gtm` (outbound + inbound deal traffic), `kb-ops` (recurring ops threads) |
| `~~chat` | Slack, Teams, Google Chat, Discord | split by channel: profile bios + admin channels → `kb-company`; sales channels → `kb-gtm`; ops channels → `kb-ops` | all three |
| `~~calendar` | Google Calendar, Outlook Calendar | behavioral-trace (meeting cadence, recurring-invite patterns) — read by all three | — |
| `~~meeting-intel` | Fathom, Gong, Granola, Otter, Chorus | `kb-gtm` (sales and customer calls → `public/03-customers/`, `public/04-gtm/`) | `kb-ops` (internal ops meetings) |
| `~~ticketing` | Zendesk, Intercom, Freshdesk, HelpScout | `kb-ops` (support Process pages) | `kb-gtm` (customer pain signal) |
| `~~design` | Figma, Sketch, Canva | catalog only — named in `public/07-systems/` by `kb-ops` | — |
| `~~dev` | GitHub, GitLab, Bitbucket | catalog only — named in `public/07-systems/` by `kb-ops` | — |

## Detection Behavior

The audit skill inventories active MCP tools at Phase 3 and classifies them into these categories. `/kb-build` reuses that map rather than re-detecting. If a category has no active connector, the corresponding read is skipped and flagged in the final report under "Coverage Gaps."

## Minimum Viable Audit

The audit runs with **any single connector** and flags low coverage. Recommended minimums:

- **Fast audit (15 min):** 1 `~~crm` OR 1 `~~cloud-storage`
- **Standard audit (30–45 min):** 1 `~~crm` + 1 `~~cloud-storage` + 1 `~~email`
- **Deep audit (60+ min):** all four categories plus at least one supplementary connector

## Minimum Viable KB Build

`/kb-build` will run with a single connector, but the output is thin. Recommended:

- **Fast KB (15 min):** 1 `~~cloud-storage` + 1 `~~chat`
- **Standard KB (30–45 min):** + 1 `~~crm` + 1 `~~wiki`
- **Full KB (45–60 min):** + 1 `~~meeting-intel` + 1 `~~email`

## What the Plugin Does NOT Do

- It does not install connectors for you. Connect what you want read in your session first.
- It does not grant Prescyent access to your data. Nothing leaves your session except a summary email you explicitly approve.
- It does not write back to any connected system. The only writes go to your own drive (`{KB_ROOT}/`, `~/prescyent-audits/`, `~/.prescyent/{slug}/`).
