# Per-task clarification block — template

Used in Stage 4 of `/kb-interview`. The interviewer loads this template, picks 6-8 questions across the `tasks[]` list, and asks them via `AskUserQuestion`.

Default: 2 questions per task for a 3-4 task list; 1 per task for a 5-7 task list. Cap at 8 total.

---

## Per-task follow-up block

For task "{task}":

- How often do you touch this?
  `AskUserQuestion` single-select: `Multiple times daily | Daily | Weekly | Monthly | Ad hoc`
  (skip if already captured in Stage 2)

- Where does this usually break?
  `AskUserQuestion` free-text.

- When it breaks, who do you go to?
  `AskUserQuestion` single-select, options = inferred names from the conversation so far, plus `someone else (tell me who)`.

- Is there a playbook, or is it all in your head?
  `AskUserQuestion` single-select: `Written playbook | Partial doc | In my head`.

- Does this depend on someone else finishing something first?
  `AskUserQuestion` single-select: `Always | Sometimes | Rarely`.

- What tool do you wish existed for this?
  `AskUserQuestion` free-text (optional — only if time allows).

---

## Selection rules

- If a task came up in Stage 3 as the painful-task, pick at least 2 questions from this template for it.
- If a task is rare (`Monthly` or `Ad hoc`), one question is enough.
- Prefer single-select questions in Stage 4 — the free-text deep-dive belongs in Stage 5.

## Voice

Every question runs the gauntlet. No banned words. "Your work" framing, not "the task".
