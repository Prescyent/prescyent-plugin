---
name: kb-interview
description: >
  Structured 5-stage interview (45 min). Captures tasks, tools,
  process, pain, and deep work patterns. Produces private transcript,
  public per-person profile, and SOPs promoted to the operations
  folder. Invoke when user asks to "interview me", "capture my work",
  "ask me about my job", or when `/discover` Phase 5 recommends it.
background_safe: false
---

# kb-interview

45-minute structured chat. Five stages. The interviewer asks; the user talks; the script captures what ends up in the KB.

Every user-facing line passes the voice gauntlet (`../../_references/plugin-ux-voice.md` and `../../_references/voice.md`). Banned words list at the bottom of this file. Word budgets: status ≤30 words, errors ≤20 words + one recovery step, orientation ≤100 words.

---

## Mode detection

If invoked via `/kb-interview` OR with no mode flag → **full mode** (all 5 stages, ~45 min).

If invoked via `/kb-screener` OR with `mode: screener` → **screener mode** (Stages 1, 2, truncated 3; ~10-15 min; see `references/screener-script.md` for exact pacing). Phase headers below note `[full only]`, `[screener + full]`, or `[both]` — obey the gating in each phase.

Screener mode additionally skips:
- Off-the-record detection logic (short interview; user can self-filter).
- Concept-map generation + validation (Phase 7 Mermaid block).
- SOP extraction + write (Phase 8c).

Screener mode still runs the consent opener verbatim (Phase 2) and still previews any public write before shipping (Phase 8b).

---

Three writes land on the drive (full mode), all via `kb-writer.py`. Screener mode writes only 8a (transcript) + a lighter 8b (profile stub):
- Private transcript → `{KB_ROOT}/_meta/interviews/{user_email}/{YYYY-MM-DD}-{session-id}.md`
- Public per-person profile → `{KB_ROOT}/public/06-people/{user-slug}.md`
- Extracted SOPs (one per deeply-walked task) → `{KB_ROOT}/public/05-operations/{slug}.md`

The public writes only happen after the user explicitly approves them via an `AskUserQuestion` preview.

---

## Phase 1 — Preflight + identity check  [both]

Resolve user groups from env:
- `USER_GROUPS="${USER_GROUPS:-}"` — comma-separated list from orchestrator (e.g., "engineering,exec")
- If empty, ceiling is `internal` per kb-writer's default

Resolve the KB root with `storage.py`:

```bash
KB_ROOT_LABEL="${CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL:-prescyent-kb}"
python3 "${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/storage.py" --test "${KB_ROOT_LABEL}"
```

If the scaffold is missing (`{KB_ROOT}/MANIFEST.md` absent), print and exit:

> No scaffold found. Run `/kb-build` first to scaffold + populate, then come back here.

Read `{KB_ROOT}/_meta/preflight.md`. Pull `user_email` and `company_name`. If `user_email` is missing, ask once via `AskUserQuestion` (single-select "enter your email", free text). If the response is empty, log + exit cleanly without any side effects.

Derive `user_slug` from `user_email` (lowercase, non-alphanumerics → `-`). Session id = `session-{HHMM}` from current local time.

---

## Phase 2 — Consent opener (verbatim — do NOT paraphrase)  [both — ALWAYS runs, even in screener mode]

Print exactly:

> Before we start: this conversation will be recorded as a transcript stored on your drive under `_meta/interviews/{your-email}/`. The plugin enforces that only you and the champion can read that folder via a classification + path check; your drive's own permissions are the final backstop. I'll also write a summary to the public KB that your coworkers will see. You can mark anything as off-the-record by saying "off the record" — that line and the next ten stay in your private transcript only. Continue?

Then call `AskUserQuestion` single-select:
- `Continue` → proceed to Stage 1.
- `Not now` → print "No problem. Run `/kb-interview` when you have forty-five minutes." and exit.

**Empty-response contract.** If the `AskUserQuestion` returns nothing (user dismissed, harness error), append a `consent_empty` line to `_meta/build-log/{today}-{user_slug}.jsonl` via `kb-writer.py`-style log and exit. No transcript written. No public profile written. No partial state on disk.

Initialise the in-memory transcript buffer now:

```
transcript_lines = []             # list[dict] — each turn: {speaker, text, private}
private_counter = 0               # turns remaining in current off-record window
off_record_ranges = []            # list[(start_line, end_line)]
```

---

## Phase 3 — Stage 1: Task identification (10 min)  [both — screener caps at 5 min per `references/screener-script.md`]

Print the persona opener, substituting `{name}` from the preflight (fall back to the local-part of the email):

> Hi {name}! I'm here to help you quickly list out the main missions that shape your day-to-day.

Ask:

> What are the 3-7 main tasks or missions that define your work? A rough list is perfect — I'll refine with you.

Collect the response (free-text conversation, possibly multi-turn). Parse into a `tasks[]` list — one line per task. Summarise back:

> Here's what I heard: (1) {task1}, (2) {task2}, ... Anything to add or edit before we move on?

Use `AskUserQuestion` single-select with options `Looks right | Edit the list | Add more`. Loop until the user picks `Looks right` or the list is 3-7 tasks.

**Empty-response contract.** If the returned answer is empty, null, or `""`, log `AskUserQuestion returned empty — aborting before any side effects` and exit cleanly. No transcript written. No public profile written.

Every turn appends to `transcript_lines` with `speaker` set to `user` or `interviewer`. If the user's text contains `off the record` (case-insensitive substring), set `private_counter = 10` starting with that turn.

---

## Phase 4 — Stage 2: Initial questionnaire (5 min)  [both]

For each task in `tasks[]`, capture three facts. Send a **single `AskUserQuestion` preview** block with three sub-questions per task (parallel form). If the caller's `AskUserQuestion` cannot bundle multiple questions in one call, serialise them.

Per task, ask:

1. Frequency — single-select: `Multiple times daily | Daily | Weekly | Monthly | Ad hoc`
2. Duration per instance — single-select: `<15 min | 15-60 min | 1-4 hrs | Half day | Full day+`
3. Tools used — free-text

Store results as `task_facts[task_name] = {frequency, duration, tools}`.

**Empty-response contract.** Empty answers for any sub-question: keep the task in the list but mark that sub-field `unknown`. Do not error out. Do not fabricate.

---

## Phase 5 — Stage 3: First analysis (10 min)  [both — screener truncates to 3-5 min, skips the 2-3 open probes at the end, goes straight to Phase 8 after the "Matches | Partly wrong | Way off" check]

Synthesise back to the user. Short. Keep under 120 words:

> Here's what I'm hearing. Most of your week is on {top-task}. {weekly-task} runs weekly. {painful-task} is the one you told me hurts. Does that match the real shape of your week?

Use `AskUserQuestion` single-select: `Matches | Partly wrong | Way off`. If partly-wrong or way-off, ask one free-text follow-up to correct the picture and re-summarise.

**Empty-response contract.** Empty response here: log + exit cleanly before any side effects. The transcript in memory is discarded; the user re-runs `/kb-interview` when ready.

Now open discussion. Ask about WHAT they do, not WHY. From Ericsson & Simon: directed "explain why" questions are reactive; "describe what you did" stays neutral. Phrase every probe:

- "Walk me through the step where..."
- "Describe what happens when..."
- "Last time this came up, what did you do first?"

Never: "why do you...", "what's the reason...", "explain why...".

Pick 2-3 probes. Let the user talk. Append every turn to `transcript_lines`.

---

## Phase 6 — Stage 4: Follow-up questions (5 min)  [full only — screener skips]

Adaptive. Load the template at `references/per-task-clarification-block-template.md`. Generate 6-8 follow-ups total, distributed across tasks.

Quick ones go through `AskUserQuestion` single-select (e.g., "When {task} breaks, who do you go to? [inferred names]"). Deeper ones go through free-text turns.

**Empty-response contract.** Empty answer on a single-select follow-up: skip that follow-up with no side effects, continue to the next one. Do not abort the whole stage — these are optional adaptive probes.

If you run out of material before 5 minutes, move on. If you run over, cap at 8 follow-ups and move on. Time discipline matters more than completeness here — the deep dive comes next.

---

## Phase 7 — Stage 5: Deep analysis (15 min)  [full only — screener skips, no Mermaid concept-map]

Pick one or two of the highest-impact tasks (usually the painful-task from Stage 3 or the most-frequent). Deep-walk each:

- "Walk me through a typical {cadence} when you did {task} last week."
- "At the step where you chose path A over path B, what had just happened?"
- "Who had to sign off on it, and what did you send them?"
- "The last time this broke, describe what broke and what you did next."

Again: describe, not explain. Keep the user in narration mode, not justification mode.

When both tasks feel covered, emit the concept map. Build a JSON payload from the collected tasks, tools, frequencies, and any handoffs the user mentioned:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/generate-mermaid-concept-map.py" \
  --from-json /tmp/kb-interview-{session-id}.json \
  > /tmp/kb-interview-{session-id}.mmd
```

Load the rendered Mermaid string and preview it. Use the exact template from `references/concept-map-validation-prompt.md`:

> Here's how your work looks from what you told me.
>
> ```mermaid
> {diagram}
> ```
>
> Does this reflect how your work actually looks?

`AskUserQuestion` single-select: `Yes, ship it | Parts wrong (tell me) | Way off`. If parts-wrong: one free-text follow-up, regenerate the diagram, re-preview. If way-off: ask what's missing, regenerate once, re-preview, then accept whatever the user picks (do not loop forever).

**Empty-response contract.** On empty: skip the concept-map write but keep everything else. Log `concept_map_empty` and continue to Phase 8.

---

## Phase 8 — Write phase  [screener runs 8a + lighter 8b only; 8c is full-only]

Three writes. Every one goes through `kb-writer.py`. No direct file writes.

### 8a. Private transcript  [both]

Serialise `transcript_lines` to markdown. Off-record segments are fenced with `---private-start---` / `---private-end---` markers and carry `[off the record]` inline tags. Example:

```markdown
User: walk me through the pipeline review.
Interviewer: got it — which system do you start in?

---private-start---
User: [off the record] the CRO is the actual bottleneck.
Interviewer: acknowledged; continuing privately.
User: ... every review stalls until he responds.
---private-end---

User: back on the record. After the review, I...
```

Frontmatter for the transcript page — `type: Concept` (the validator allowlist today: `Process | System | Role | Decision | Concept | Playbook | Glossary`; `Interview` is not a valid type, so `Concept` is the closest fit, with extra fields carrying the interview-specific metadata):

```yaml
---
id: interview.{user-slug}.{YYYY-MM-DD}.{session-id}
title: Interview transcript — {user_name} — {YYYY-MM-DD}
type: Concept
owner: {user_email}
confidence: high
source_artifacts: ["kb-interview://session-{session-id}"]
last_verified: {YYYY-MM-DD}
review_cycle_days: 365
created_by: kb-interview

# Interview-specific extensions (passed through the envelope, not envelope-required)
interviewer: kb-interview
interviewee: {user_email}
session_date: {YYYY-MM-DD}
duration_min: {actual_minutes}
off_record_ranges: {list of [start_line, end_line]}
related_concepts: []
aliases: []
examples: []
---
```

Write it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/kb-writer.py" \
  --path "_meta/interviews/{user_email}/{YYYY-MM-DD}-{session-id}.md" \
  --content-file /tmp/kb-interview-transcript-{session-id}.md \
  --frontmatter-json "$(cat /tmp/kb-interview-transcript-{session-id}.json)" \
  --user-email "{user_email}" \
  --user-groups "${USER_GROUPS}"
```

The path starts with `_meta/` — kb-writer's classifier will see the `_meta` prefix plus the explicit `source_artifacts: ["kb-interview://..."]` and bump to `internal` at minimum. Alpha single-drive model: readable by the named user + the champion only. The path-scoped ACL enforcement is a WP-09+ item; today the classification metadata captures it so the next writer (or a human audit) can enforce.

### 8b. Public per-person profile  [both — screener ships a lighter stub: tasks + frequency + tools only, no deep-analysis-derived fields]

Strip every turn inside `---private-start---` / `---private-end---` before synthesising. The public profile never sees off-record material.

Synthesise a Role page from `tasks[]`, `task_facts[]`, and the deep-analysis walkthroughs. Fields (per `references/page-types/role.md`):
- `processes_owned` — slugged task names that became SOPs.
- `systems_owned` — tools with high-frequency mention (appearing in 3+ tasks).
- `informal_goto_for` — inferred from "when this breaks, who do you go to" — **only include items the user said themselves**; never fabricate.
- `domain_expertise` — extracted from deep-analysis themes.
- `tenure_at_company` — from preflight if captured, else `unknown`.

Path: `public/06-people/{user-slug}.md`. Frontmatter `type: Role`. Default `status: draft` — the user has not yet seen a published version.

**Preview before write.** `AskUserQuestion` preview block with the rendered markdown:

> Here's the public profile. Ship it, edit, or skip?

Options: `Ship it | Edit first | Skip public profile`.

- `Ship it` → pass to kb-writer.
- `Edit first` → open a free-text turn asking what to change, regenerate the profile, re-preview.
- `Skip public profile` → log and skip; only the transcript is written.

**Empty-response contract.** Empty response on the preview: default to `Skip public profile`. Never ship without an explicit yes.

Write it:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/kb-writer.py" \
  --path "public/06-people/{user-slug}.md" \
  --content-file /tmp/kb-interview-profile-{session-id}.md \
  --frontmatter-json "$(cat /tmp/kb-interview-profile-{session-id}.json)" \
  --user-email "{user_email}" \
  --user-groups "${USER_GROUPS}"
```

### 8c. Extracted SOPs  [full only — screener skips; no Stage-5 walkthrough means no material to synthesise]

For each task that got a detailed walkthrough in Stage 5, synthesise a Process page. Path: `public/05-operations/{task-slug}.md`. Frontmatter `type: Process`. Classification default `internal`.

Strip off-record material first.

Preview each one the same way the profile was previewed:

> Here's the SOP for "{task}". Ship it, edit, or skip?

Options: `Ship it | Edit first | Skip this SOP`. Same empty-response contract as 8b: empty = skip.

Write each approved SOP via `kb-writer.py` to `public/05-operations/{task-slug}.md`. Each invocation follows the same shape as 8a/8b and MUST include `--user-groups "${USER_GROUPS}"` so classifier ceilings above `internal` are respected for legitimately high-tier interviewees:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/kb-writer.py" \
  --path "public/05-operations/{task-slug}.md" \
  --content-file /tmp/kb-interview-sop-{session-id}-{task-slug}.md \
  --frontmatter-json "$(cat /tmp/kb-interview-sop-{session-id}-{task-slug}.json)" \
  --user-email "{user_email}" \
  --user-groups "${USER_GROUPS}"
```

---

## Phase 9 — Close  [both — screener adds a follow-up signal line]

Print (≤100 words, voice-checked):

> Interview captured. Private transcript in `_meta/interviews/{user_email}/`. Public profile in `public/06-people/`. Coworkers now have a version of your work they can learn from. Next: `/kb-build` fans out across your connectors to populate the rest of the KB, or have a teammate run `/kb-interview me` next.

Show absolute paths so the user can open in Finder.

**Screener mode close** — swap the final sentence for one of these, based on whether the tasks look deep enough to warrant a full 45 min:

- Recommend follow-up: "Screener captured the shape. Your work has enough layers that a full `/kb-interview` would pay off — book forty-five minutes when you can."
- No follow-up: "Screener captured what we needed. No full interview required — run `/kb-build` to populate the rest of the KB."

Heuristic for the recommend/skip call: if 3+ tasks were marked high-frequency AND any single task ran `1-4 hrs` or longer per instance, recommend the follow-up. Otherwise, skip.

---

## Off-the-record mechanic

When a user turn contains "off the record" (case-insensitive substring), the NEXT TEN user turns are tagged `private: true` in the transcript. The counter decrements on every user turn regardless of stage boundary. The window closes early on:
- user says "on the record" (resets counter to 0)
- counter hits 0 (10 turns elapsed)
- interview ends

Private segments are stripped BEFORE synthesizing the public profile and BEFORE extracting SOPs. Public-state accumulators (tasks[], task_facts[], deep_walkthroughs[]) MUST be rebuilt from the stripped transcript, not from live state gathered during the private window.

Transcript storage uses fenced markers:
```
---private-start---
User: [off the record] ...
Claude: acknowledged; continuing privately
...
---private-end---
```

`off_record_ranges: [[line_start, line_end], ...]` goes in the transcript frontmatter for audit.

Private segments are stripped before:
- public profile synthesis (Phase 8b)
- SOP synthesis (Phase 8c)
- any kb-graph link extraction (WP-09)

They stay in the private transcript file (Phase 8a) where only the user and champion can read.

This behavior is turn-based, not stage-based. A user who says "off the record" at the end of Stage 3 keeps the full 10-turn window as the interview moves into Stage 4.

---

## AskUserQuestion contract

Every call in this skill:
- Single-select, multi-select, or preview — never free-text as the primary mechanism (free-text is fine inside a turn, not as the gating mechanism).
- On empty response: log the event to `_meta/build-log/` and either skip that step with no side effects, or exit cleanly if the empty response came from consent or identity (Phases 1-2).
- `background_safe: false` — this skill is interactive end-to-end. The `/kb-interview` command is foreground-only.

---

## Voice rules (condensed)

Banned words: delve, crucial, robust, comprehensive, nuanced, landscape, furthermore, seamlessly, unlock, empower, game-changer, best-in-class, cutting-edge, holistic, paradigm, synergy, leverage (verb), utilize, facilitate, tapestry, ecosystem (vague), solution (software), journey (process), transformation (no specifics), it's worth noting, it's important to note, please note.

Every user-visible string:
- Under its word budget.
- "Your company" / "your work" framing.
- Re-sells the promise; no process narration.
- No implementation detail that doesn't change the user's next move.

Fail any of these → rewrite before shipping.

---

## Error recovery

- Transcript write fails (`kb-writer.py` nonzero): keep the in-memory transcript, print the path where it would have landed, dump the markdown to stdout so the user can copy-paste. Do not lose the conversation.
- Public profile write fails: the transcript is already safe. Tell the user "transcript saved; profile write failed — here's the draft" and print the markdown.
- Concept-map script fails: skip the diagram, continue to Phase 8. Log `concept_map_render_failure`.
- Mid-interview abort (user says "stop" or closes the session): write whatever's in the buffer to `_meta/interviews/{user_email}/{YYYY-MM-DD}-{session-id}-partial.md` via `kb-writer.py`. No public profile, no SOPs.

---

## References

- `references/5-stage-script.md` — verbatim interviewer script per stage.
- `references/screener-script.md` — 10-15 min triage variant (used by `/kb-screener`, WP-11).
- `references/per-task-clarification-block-template.md` — adaptive follow-up generator.
- `references/concept-map-validation-prompt.md` — Stage 5 validation wording.
- `../kb-builder/scripts/generate-mermaid-concept-map.py` — diagram helper.
- `../kb-builder/scripts/kb-writer.py` — the single funnel every write passes through.
- `../kb-builder/references/page-types/role.md` — public profile schema.
- `../kb-builder/references/page-types/process.md` — extracted SOP schema.
- `../kb-builder/references/page-types/concept.md` — transcript schema (used because `Interview` is not a valid type in the current validator).
