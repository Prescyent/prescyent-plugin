---
description: 10-15 min triage interview. Lighter than /kb-interview. Captures your top 3-5 tasks and decides whether a full 45-min follow-up is worth it.
argument-hint: "[me]"
background_safe: false
---

Short-form triage. For the "I can give you fifteen minutes between meetings" case. Produces a lighter per-person profile stub and a yes/no signal on whether a full `/kb-interview` is worth scheduling.

Invoke the `kb-interview` skill in **screener mode** (`mode: screener`). It runs Stages 1 + 2 + a truncated Stage 3 only (~10-15 min total). The skill reads the pacing from `skills/kb-interview/references/screener-script.md`.

**What screener mode keeps:**
- Consent opener (ALWAYS runs — legal/ethical floor, identical verbatim text as the full interview).
- Task identification (Stage 1, 5 min).
- Per-task questionnaire — frequency, duration, tools (Stage 2, 5 min).
- Quick synthesis + "does this match your week?" (truncated Stage 3, 3-5 min).
- Lighter public profile stub, previewed before any write.

**What screener mode skips:**
- Stage 5 deep walkthrough.
- Mermaid concept-map generation + validation.
- Off-the-record detection logic (the interview is short enough that the user can simply not say the sensitive thing).
- Extracted SOPs (screener produces a stub only — SOPs come from the full interview).

**Follow-up signal.** At close, the skill prints one line: either "recommend `/kb-interview` next" (tasks look deep enough to warrant 45 min) or "screener captured what we needed — no follow-up required." The user decides whether to book.

Arguments (optional, in `$ARGUMENTS`):
- `me` — screen the current user (default).

Follow `skills/kb-interview/SKILL.md` exactly in screener mode. Every user-visible string passes the voice gauntlet.
