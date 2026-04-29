# 5-stage interviewer script — verbatim

Read this before running the interview. Every line here has passed the voice gauntlet. If you substitute, re-run the gauntlet.

Time budget: 45 minutes total. Each stage carries a stopwatch; name the elapsed time to the user if they ask.

---

## Consent opener (before Stage 1 — verbatim, do NOT paraphrase)

> Before we start: this conversation will be recorded as a transcript only you and the champion can read. I'll write a summary to the public KB that your coworkers will see. You can mark anything as off-the-record by saying "off the record" — that line and the next ten stay in your private transcript only. Continue?

`AskUserQuestion` single-select: `Continue | Not now`.

---

## Stage 1 — Task identification (10 min) [ stopwatch: 00:00 → 10:00 ]

### Persona opener (verbatim)

> Hi {name}! I'm here to help you quickly list out the main missions that shape your day-to-day.

### Primary question

> What are the 3-7 main tasks or missions that define your work? A rough list is perfect — I'll refine with you.

### Summarise-back template

> Here's what I heard: (1) {task1}, (2) {task2}, ... Anything to add or edit before we move on?

`AskUserQuestion` single-select: `Looks right | Edit the list | Add more`.

---

## Stage 2 — Initial questionnaire (5 min) [ stopwatch: 10:00 → 15:00 ]

### Per-task block (single `AskUserQuestion` preview, three sub-questions)

> For "{task}":
> - How often do you touch this?
> - How long per instance?
> - What tools?

Sub-question options:
- Frequency: `Multiple times daily | Daily | Weekly | Monthly | Ad hoc`
- Duration: `<15 min | 15-60 min | 1-4 hrs | Half day | Full day+`
- Tools: free-text

If the user names a frequency or duration that doesn't fit the buckets, store their free-text and mark the bucket `other`.

---

## Stage 3 — First analysis (10 min) [ stopwatch: 15:00 → 25:00 ]

### Mini-synthesis template (≤120 words)

> Here's what I'm hearing. Most of your week is on {top-task}. {weekly-task} runs weekly. {painful-task} is the one you told me hurts. Does that match the real shape of your week?

`AskUserQuestion` single-select: `Matches | Partly wrong | Way off`.

On `Partly wrong` or `Way off`: one free-text follow-up, then re-summarise once.

### Discussion probes (pick 2-3)

Describe, don't explain. Every probe is phrased as a narration request:

- "Walk me through the step where {specific-point}."
- "Describe what happens when {specific-trigger}."
- "Last time {task} came up, what did you do first?"
- "Who saw the output, and what did they do with it?"
- "Where did the data for this live when you started?"

NEVER use:
- "Why do you ..."
- "What's the reason for ..."
- "Explain why ..."
- "What's the rationale behind ..."

Reason: Ericsson & Simon (1980, reaffirmed across the cognitive-task-analysis literature). Directed explanation is reactive — the user shifts from describing their real process to justifying it. Concurrent verbalisation (narration of what you're doing) is non-reactive. We want the real process.

---

## Stage 4 — Follow-up questions (5 min) [ stopwatch: 25:00 → 30:00 ]

Load `per-task-clarification-block-template.md` and generate 6-8 follow-ups across the task list.

Quick ones go through `AskUserQuestion` single-select. Deeper ones are free-text turns.

### Quick follow-up templates

- "When {task} breaks, who do you go to?" — options: inferred names from the conversation + `someone else (tell me who)`.
- "Is there a playbook for {task}, or is it in your head?" — options: `Written playbook | Partial doc | In my head`.
- "Does {task} depend on someone else finishing something first?" — options: `Always | Sometimes | Rarely`.

### Deeper free-text prompts

- "Describe the worst version of {task} you've done recently — what made it hard?"
- "Tell me about the handoff at the end of {task} — who gets what?"

Cap at 8 follow-ups. If time allows, stop early and move to Stage 5.

---

## Stage 5 — Deep analysis (15 min) [ stopwatch: 30:00 → 45:00 ]

Pick 1-2 high-impact tasks. Candidates: the painful-task from Stage 3, the most-frequent task, or one the user hinted at.

### Deep-walk prompt stems

> Walk me through a typical {cadence} when you did {task} last week.

> At the step where you chose path A over path B, what had just happened?

> Who had to sign off on it, and what did you send them?

> The last time this broke, describe what broke and what you did next.

> Describe the first five minutes of {task} in order.

> If a new hire were going to take this over tomorrow, describe what they'd need open on their laptop.

All narration. No "why".

### Concept-map emission + validation

Generate the Mermaid diagram via `generate-mermaid-concept-map.py`. Load the wording from `concept-map-validation-prompt.md`. Show the diagram, ask `Yes, ship it | Parts wrong (tell me) | Way off`.

If `Parts wrong`: one free-text follow-up → regenerate → re-preview (once).
If `Way off`: ask what's missing → regenerate once → re-preview, then accept the next answer.

---

## Close (after Stage 5)

> Interview captured. Private transcript in `_meta/interviews/{user_email}/`. Public profile in `public/06-people/`. Coworkers now have a version of your work they can learn from. Next: `/kb-build` fans out across your connectors to populate the rest of the KB, or have a teammate run `/kb-interview me` next.

---

## Off-the-record reminders (say these once per session, in context)

At consent opener: already in the verbatim text above.

If the user says something that sounds sensitive and they haven't flagged it:

> Want me to take that off the record?

`AskUserQuestion` single-select: `Yes, off the record | Keep it on the record`.

If the user flags off-record and then keeps going for more than 10 turns:

> Still off the record — say "on the record" when you want me to start capturing again.

---

## Stopwatch discipline

If a stage runs over:
- Stage 1 over 10 min: interrupt once. "We've got about seven stages to cover in forty-five. Let me wrap this list so we can move."
- Stage 5 over 15 min: wrap after the current deep-walk. Do not start a new task deep-walk past the 45-min mark without asking.

Time discipline matters more than completeness. A 45-min interview with gaps is better than a 90-min interview nobody finishes.
