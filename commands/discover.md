---
description: Run a Prescyent discovery — connector-aware AI readiness assessment that lands a one-page report inline in your chat in about five minutes. No drive writes unless you opt in.
argument-hint: "[depth:standard | depth:deep | role:<role>]"
background_safe: false
---

Run a Prescyent discovery against the user's connected Cowork tools. Follow `skills/discover/SKILL.md` exactly — seven phases:

1. Orient the user (4 numbered bullets + "What to know" paragraph framing the permission asks — proceeds directly to Phase 2 in the same turn, no "Ready to start?" gate)
2. Settings file check + connector pre-detection + elicitation form (7 questions: company pills with detected candidates, role pills, intent cards, connector inventory cards with multi-select, unconnected-tools textarea, verbatim pain textarea, depth pills with Pro/Team plan-aware labels). Explicit `mcp__visualize__read_me({modules: ["elicitation"]})` + `mcp__visualize__show_widget` invocation; `AskUserQuestion` fallback.
3. Subagent fan-out (4 audit-* agents in parallel via the Task tool, each producing JSON per `subagent-output-contract.md` v2.1 with `surprise_factor`)
4. Optional follow-up questions (also via elicitation when available, capped at 3 questions)
5. Synthesize Minto-style markdown report + render Prescyent-design-system HTML deck inline (both are part of the deliverable)
6. Recommended next step ("chain to /kb-build" framed as primary action) + secondary options (save to drive, draft email, send to teammate) — also via elicitation
7. Closing handoff with settings-file discoverability hint if Phase 2c ran

Arguments (optional, in `$ARGUMENTS`):

- `depth:standard` or `depth:deep` — pre-seed the search depth and skip that scope question
- `role:<role>` — pre-seed the role field and skip that scope question

**Critical constraints:**

- No drive writes unless the user explicitly opts in at Phase 6.
- Subagents fan out via the `Task` tool in a single parallel block — do not serialize.
- Every user-visible string passes the voice gauntlet at `skills/kb-builder/references/voice-rules.md` + the boil-the-ocean check (positive-sum framing, not zero-sum).
- Phase 2 EXPLICITLY invokes `mcp__visualize__read_me({modules: ["elicitation"]})` followed by `mcp__visualize__show_widget` to render the form, then `mcp__cowork__read_widget_context` to read the submission. Mirrors brand-voice's runtime tool-call pattern. `AskUserQuestion` is the fallback when these tools aren't in the host's tool list.
- Empty-response contract on every elicitation site: empty = abort cleanly, no silent defaults.
- The Phase 5 report follows Barbara Minto's Pyramid Principle: ONE contestable answer at the top, Top 3 moves second (NOT buried at the bottom), why-this-matters-now framing tied to the May 2026 Garry Tan boil-the-ocean moment, persona-tailored to `user_role`, sells the KB Builder as the inevitable next step.
- The HTML deck uses the Prescyent dark-mode design system + canonical deck-footer-pattern (mailto + booking link + sign-off) + favicon/OG/Twitter meta tags per `prescyent/references/shared/deck-{head,footer}-pattern.md`.
- The deliverable is the chat-rendered assessment — markdown + HTML deck, both inline. Storage selection lives in `/kb-build`, not here.
