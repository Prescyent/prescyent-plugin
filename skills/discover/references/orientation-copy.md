# Orientation Copy — LOCKED

The canonical Phase 1 orientation message for `/discover`. Voice-gauntlet-passed on 2026-05-01. Plain text only — no placeholder substitution, no widget render, no connector picker. Never auto-regenerate. If copy needs to change, edit here, re-run the gauntlet at `../../kb-builder/references/voice-rules.md`, and commit as a deliberate voice update.

## The message

> Here's how Prescyent discovery works:
>
> 1. **Read** — I'll read what you've connected to Cowork (Drive, Notion, HubSpot, Gmail, etc.) to understand how your company actually runs.
> 2. **Audit** — Four agents work in parallel: GTM systems, knowledge & docs, communications, and AI stack. Each one grades your readiness on its slice.
> 3. **Report** — You get a one-page assessment with the top 3 moves you can make this week, where you're losing time today, and the path forward.
> 4. **Next** — Save the report, draft a follow-up email, or chain to `/kb-build` to turn this into a living wiki every future Claude session reads from. Nothing writes anywhere without your explicit consent.
>
> **What to know.** I'll request access to a few tools as I go — Terminal and Python Launcher to compute counts and render your HTML report, plus read access on whichever connectors you've already authorized. You can review each prompt and decline anything that feels off. Nothing leaves your machine.
>
> The audit usually takes 4–6 minutes. Let me check your settings and ask a few quick scope questions before I kick off.

## Why this message

- **Mirrors brand-voice's `/discover-brand` orientation pattern** (partner-built/brand-voice/skills/discover-brand/SKILL.md). Four numbered bullets covering what we're doing, how it works, what they get, what comes next. Plain text. Bridges directly to the elicitation.
- **No FUD opener.** Drops "Your AI sessions feel generic because Claude doesn't know your company." Buyers who installed the plugin don't need to be re-sold; they need expectations set.
- **No verb-quartet vagueness.** Drops "Discover → Map → Build → Deliver. Ready when you are." That closer left "ready for what?" hanging.
- **No "Ready to start?" gate.** Brand-voice's `/discover-brand` emits orientation prose then immediately renders the elicitation form — same flow here. The elicitation IS the gate; the user submits or skips.
- **"What to know" paragraph (added 2026-05-01).** Pre-explains the permission asks the user will see — Terminal, Python Launcher, MCP read access. Sets expectation BEFORE the permission gate fires so non-technical buyers (CFO, VP of Sales, founder/CEO) don't bounce when the first system prompt appears. Tyler 2026-05-01: *"Most people are going to get scared away right there and not want to allow Claude Cowork to use the terminal on their computer. Most people might not even know what a terminal is."*
- **Closing bridge to elicitation.** Final sentence ("Let me check your settings and ask a few quick scope questions...") matches brand-voice's "Let me check for any existing settings and validate what's connected before kicking off the search."
- **No connector picker.** The previous flow called `mcp__mcp-registry__list_connectors`, which renders Cowork's connector-management UI panel as a side effect. Coverage gaps now surface in the elicitation form's connector-inventory question (Phase 2b).

## Word count

~155 words (excluding header). Slightly above the 120-word budget, but the "What to know" paragraph is load-bearing for non-technical persona trust. Voice-checked: no banned words, no AI tells, no hedge language.

## Banned-word check

Run on 2026-05-01 — no banned words present (delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, seamlessly, unlock, empower, game-changer, best-in-class, cutting-edge, holistic, paradigm, synergy, leverage, utilize, facilitate, tapestry, ecosystem, solution, journey, transformation).
