---
description: Run a Prescyent discovery — connector-aware AI readiness assessment that lands a one-page report inline in your chat in about five minutes. No drive writes unless you opt in.
argument-hint: "[depth:standard | depth:deep | role:<role>]"
background_safe: false
---

Run a Prescyent discovery against the user's connected Cowork tools. Follow `skills/discover/SKILL.md` exactly — seven phases:

1. Orient the user (plain text, 4 numbered bullets, "Ready to start?")
2. Settings file check + conversational scope confirmation (one block of questions; Cowork infers elicitation rendering, others fall back to plain prose)
3. Subagent fan-out (4 audit-* agents in parallel via the Task tool)
4. Optional follow-up questions in plain text
5. Synthesize markdown report + render HTML deck inline (both are part of the deliverable)
6. Three chained-action options — save to drive, draft email, chain to `/kb-build`
7. Closing handoff (with settings-file discoverability hint if Phase 2b ran)

Arguments (optional, in `$ARGUMENTS`):

- `depth:standard` or `depth:deep` — pre-seed the search depth and skip that scope question
- `role:<role>` — pre-seed the role field and skip that scope question

**Critical constraints:**

- No drive writes unless the user explicitly opts in at Phase 6.
- Subagents fan out via the `Task` tool in a single parallel block — do not serialize.
- Every user-visible string passes the voice gauntlet at `skills/kb-builder/references/voice-rules.md`.
- Phase 2 does NOT explicitly call `mcp__visualize__show_widget`. Cowork infers elicitation rendering from the natural-language scope-confirmation prose (mirrors `partner-built/brand-voice/skills/discover-brand/SKILL.md`). Other hosts render the same prose as plain text or `AskUserQuestion`.
- Empty-response contract on every elicitation site: empty = abort cleanly, no silent defaults.
- The deliverable is the chat-rendered assessment — markdown + HTML deck, both inline. Storage selection lives in `/kb-build`, not here.
