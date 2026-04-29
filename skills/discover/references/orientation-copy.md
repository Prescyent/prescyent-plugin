# Orientation Copy — LOCKED

The canonical Phase 1 orientation message for `/discover`. Voice-gauntlet-passed on 2026-04-29. Plain text only — no placeholder substitution, no widget render, no connector picker. Never auto-regenerate. If copy needs to change, edit here, re-run the gauntlet at `../../kb-builder/references/voice-rules.md`, and commit as a deliberate voice update.

## The message

> Here's how Prescyent discovery works:
>
> 1. **Read** — I'll read what you've connected to Cowork (Drive, Notion, HubSpot, Gmail, etc.) to understand how your company actually runs.
> 2. **Audit** — Four agents work in parallel: GTM systems, knowledge & docs, communications, and AI stack. Each one grades your readiness on its slice.
> 3. **Report** — You get a one-page assessment with the top 3 AI opportunities, where you're losing time today, and what to fix first.
> 4. **Next** — Save the report, draft a follow-up email, or chain to `/kb-build` to turn it into a living wiki. Nothing writes anywhere without your explicit consent.
>
> The audit usually takes 4–6 minutes. Ready to start?

## Why this message

- **Mirrors brand-voice's `/discover-brand` orientation pattern** (partner-built/brand-voice/skills/discover-brand/SKILL.md). Four numbered bullets covering what we're doing, how it works, what they get, what comes next. Plain text. Conversational close.
- **No FUD opener.** Drops "Your AI sessions feel generic because Claude doesn't know your company." Buyers who installed the plugin don't need to be re-sold; they need expectations set.
- **No verb-quartet vagueness.** Drops "Discover → Map → Build → Deliver. Ready when you are." That closer left "ready for what?" hanging. New closer is concrete: "The audit usually takes 4–6 minutes. Ready to start?"
- **No connector picker.** The previous flow called `mcp__mcp-registry__list_connectors`, which renders Cowork's connector-management UI panel as a side effect. Coverage gaps now surface in the final report's Coverage table instead of pre-listing.
- **Final line is consent.** Plain text reply, not `AskUserQuestion`. The user types "yes", "go", or asks a question. Either way, they're committed before any subagent dispatches.

## Word count

~110 words (excluding header). Matches brand-voice's discover-brand orientation length.

## Banned-word check

Run on 2026-04-29 — no banned words present (delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, seamlessly, unlock, empower, game-changer, best-in-class, cutting-edge, holistic, paradigm, synergy, leverage, utilize, facilitate, tapestry, ecosystem, solution, journey, transformation).
