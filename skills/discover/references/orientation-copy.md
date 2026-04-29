# Orientation Copy — LOCKED

The canonical Phase 1 orientation message for `/discover`. Voice-gauntlet-passed on 2026-04-29. Never auto-regenerate. If copy needs to change, edit here, re-run the gauntlet at `../../kb-builder/references/voice-rules.md`, and commit as a deliberate voice update.

## The message

> Your AI sessions feel generic because Claude doesn't know your company. Your senior people do — but that knowledge lives only in their heads. Prescyent fixes both.
>
> I'll read what you've connected and bring back a one-page assessment of where AI is leaving value on the table — in about five minutes.
>
> **Connected:** {doc_platforms}. **Supplementary:** {comms_intel_crm}. **Not connected:** {missing_named}.
>
> Discover → Map → Build → Deliver. Ready when you are.

## Substitution rules

The three placeholders are filled at render time from `connectors_detected`:

- `{doc_platforms}` — comma-separated list of connected document platforms (Drive, OneDrive, SharePoint, Notion, Confluence, Box, Dropbox). If empty, write `none yet`.
- `{comms_intel_crm}` — comma-separated list of connected supplementary platforms (Gmail, Outlook, Slack, Teams, Fathom, Granola, Gong, HubSpot, Salesforce, Linear, Jira, etc.). If empty, write `none yet`.
- `{missing_named}` — up to 5 supported-but-unconnected platforms, friendly names, comma-separated. If 0, omit the entire `**Not connected:** ...` line. Pick the most-likely-to-help missing platforms (favor doc platforms first, then CRM, then comms).

## Why this message

- **First sentence re-sells the promise.** "Generic outputs" is the pain the buyer already feels. "Senior people knowledge in their heads" is the second pain. "Prescyent fixes both" is the framing.
- **Second sentence sets the deliverable.** "One-page assessment", "five minutes", "where AI is leaving value on the table" — all exec-language outcomes, no process narration, no subagent names.
- **Third line names what's connected.** Connector inventory builds trust ("you're reading my actual data") and primes coverage expectations.
- **Fourth line names the verb quartet.** Discover → Map → Build → Deliver, in full, locked order. Never shorten. Never reorder. This sets buyer expectation that Prescyent is an outcome partner, not a diagnosis vendor.
- **Final line is consent.** "Ready when you are" — plain text, not `AskUserQuestion`. The user replies "yes", "go", or asks a question. Either way, they're committed before any subagent dispatches.

## Word count

72 words (excluding placeholders). Under the 80-word orientation budget per voice rules.

## Banned-word check

Run on 2026-04-29 — no banned words present (delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, seamlessly, unlock, empower, game-changer, best-in-class, cutting-edge, holistic, paradigm, synergy, leverage, utilize, facilitate, tapestry, ecosystem, solution, journey, transformation).
