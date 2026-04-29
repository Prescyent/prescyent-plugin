---
description: 45-min structured chat. Captures the senior-person-in-your-head knowledge that never makes it into documents. Writes a private transcript + public per-person profile.
argument-hint: "[me | --topic <topic>]"
background_safe: false
---

Run the interview. Your private transcript stays private (only you + the champion read it). A short public profile goes to the KB after you approve it.

Routes to `skills/kb-interview/SKILL.md`, which runs the 5-stage script:

1. Task identification (10 min)
2. Initial questionnaire (5 min)
3. First analysis (10 min)
4. Follow-ups (5 min)
5. Deep analysis (15 min) + concept-map validation

Arguments (optional, in `$ARGUMENTS`):
- `me` — interview the current user (default).
- `--topic <topic>` — anchor the interview to a single topic (e.g., `--topic onboarding`). Use this for a narrower 20-30 min pass.

Consent opener runs before any transcription. Say "off the record" any time to mark the next ten lines private. Follow `skills/kb-interview/SKILL.md` exactly. Every user-visible string passes the voice gauntlet.
