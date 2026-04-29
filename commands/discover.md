---
description: Run a Prescyent discovery — connector-aware AI readiness assessment that lands a one-page report inline in your chat in about five minutes. No drive writes unless you opt in.
argument-hint: "[depth:standard | depth:deep | role:<role>]"
background_safe: false
---

Run a Prescyent discovery against the user's connected Cowork tools. Follow `skills/discover/SKILL.md` exactly — seven phases:

1. Orient + connector inventory
2. Single widget form (5 fields, one submit)
3. Subagent fan-out (4 audit-* agents in parallel via the Task tool)
4. Optional follow-up questions in plain text
5. Synthesize markdown report + render HTML deck inline
6. Three chained-action options — save to drive, draft email, chain to `/kb-build`
7. Closing handoff

Arguments (optional, in `$ARGUMENTS`):

- `depth:standard` or `depth:deep` — pre-seed the search depth and skip that widget question
- `role:<role>` — pre-seed the role field and skip that widget question

**Critical constraints:**

- No drive writes unless the user explicitly opts in at Phase 6.
- Subagents fan out via the `Task` tool in a single parallel block — do not serialize.
- Every user-visible string passes the voice gauntlet at `skills/kb-builder/references/voice-rules.md`.
- The widget elicitation uses `mcp__visualize__show_widget` if available, else falls back to sequential `AskUserQuestion` calls.
- Empty-response contract on every elicitation site: empty = abort cleanly, no silent defaults.
- The deliverable is the chat-rendered assessment. Storage selection lives in `/kb-build`, not here.
