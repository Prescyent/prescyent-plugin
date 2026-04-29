# Screener script — 10-15 min triage variant

The screener is a truncated `kb-interview`. Runs Stages 1 + 2 + a shortened Stage 3 only. Produces a lighter per-person profile stub. Suggests the full `/kb-interview` as a follow-up.

Used by `/kb-screener` (WP-11). This file is the reference; the command wiring ships in the next work package.

Time budget: 10-15 minutes. Designed for the "I can give you 15 minutes between meetings" case.

---

## Consent opener (same verbatim text as full interview)

> Before we start: this conversation will be recorded as a transcript only you and the champion can read. I'll write a summary to the public KB that your coworkers will see. You can mark anything as off-the-record by saying "off the record" — that line and the next ten stay in your private transcript only. Continue?

`AskUserQuestion` single-select: `Continue | Not now`.

---

## Stage 1 — Task identification (5 min) [ stopwatch: 00:00 → 05:00 ]

### Persona opener

> Hi {name}! This is the short version — about fifteen minutes. I'll ask what you do, how often, and what tools. If there's time we'll go one step deeper.

### Primary question

> What are the 3-7 main tasks or missions that define your work?

### Summarise-back

> Here's what I heard: (1) {task1}, (2) {task2}, ... Anything to add or edit?

`AskUserQuestion` single-select: `Looks right | Edit the list | Add more`.

Cap this stage at 5 minutes. Do not probe for detail — that's Stage 5 in the full version.

---

## Stage 2 — Initial questionnaire (5 min) [ stopwatch: 05:00 → 10:00 ]

Same per-task block as the full interview:

Per task:
- Frequency — single-select
- Duration per instance — single-select
- Tools — free-text

If you have more than 5 tasks and you're running tight on time, cover frequency + duration for all of them, tools for the top 3.

---

## Stage 3 — Truncated analysis (3-5 min) [ stopwatch: 10:00 → 15:00 ]

### Mini-synthesis (≤60 words — shorter than full interview)

> Here's what I heard. Most of your week is on {top-task}. {weekly-task} runs weekly. Does that match?

`AskUserQuestion` single-select: `Matches | Partly wrong | Way off`.

On `Partly wrong` or `Way off`: one free-text correction, update, move on.

### No deep-walk, no probes, no follow-ups

Skip Stages 4 and 5. The screener's job is to get a lightweight profile stub up, not a complete capture.

---

## Write phase — profile stub + transcript

Two writes. Both via `kb-writer.py`.

### Private transcript

Same schema as the full interview (Phase 8a of `SKILL.md`). Path: `_meta/interviews/{user_email}/{YYYY-MM-DD}-{session-id}-screener.md`. Filename suffix `-screener` so it's distinguishable from full interviews.

### Public profile stub

Same Role-page schema as the full interview. The difference: fewer fields are filled:

- `processes_owned` — empty list (no SOPs extracted from a screener).
- `systems_owned` — from Stage 2 tool mentions.
- `informal_goto_for` — empty list (no depth to infer).
- `domain_expertise` — empty list.
- `tenure_at_company` — from preflight if available.

Add a body note at the top:

> This is a screener stub. Run `/kb-interview me` for the full capture — tasks in context, handoffs, and the one-or-two things you wish everyone knew.

Preview before write:

> Here's the short profile. Ship it, edit, or skip?

Options: `Ship it | Edit first | Skip public profile`. Empty response defaults to skip.

---

## Close

> Short capture done. Profile stub in `public/06-people/{user-slug}.md`. Come back and run `/kb-interview me` when you have forty-five minutes — that's when the deep stuff lands.

---

## When to suggest the screener vs the full interview

- Full (`/kb-interview`) — new hire onboarding, role change, quarterly refresh, champion's own profile.
- Screener (`/kb-screener`) — field interviews during a `/kb-build` sweep, someone volunteering between meetings, round-one coverage of a team.

Both write to the same KB tree. The full interview supersedes the screener stub on the same user-slug — `kb-writer.py`'s conflict-copy handling preserves both files for manual merge.

---

## Voice rules (same as full interview)

Banned words: delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, seamlessly, unlock, empower, game-changer, best-in-class, cutting-edge, holistic, paradigm, synergy, leverage (verb), utilize, facilitate, tapestry, ecosystem (vague), solution (software), journey (process), transformation (no specifics).

Word budgets: status ≤30 words, errors ≤20 words + one recovery step, orientation ≤100 words. Screener mini-synthesis ≤60 words (tighter than full interview).
