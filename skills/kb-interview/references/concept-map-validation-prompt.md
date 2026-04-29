# Concept-map validation prompt — Stage 5

Used at the end of Stage 5 of `/kb-interview`. The interviewer has a rendered Mermaid diagram from `generate-mermaid-concept-map.py`. This file gives the exact wording for the preview.

---

## Preview block — show this verbatim

> Here's how your work looks from what you told me.
>
> ```mermaid
> {diagram}
> ```
>
> Does this reflect how your work actually looks?

`AskUserQuestion` single-select with three options:

- `Yes, ship it` — accept the diagram; include it in the public profile body.
- `Parts wrong (tell me)` — one free-text follow-up; regenerate once; re-preview.
- `Way off` — free-text ask: "What's missing, or what's in there that shouldn't be?"; regenerate once; re-preview and accept.

---

## Regeneration rules

Each regeneration call feeds the user's correction back to `generate-mermaid-concept-map.py`:

```bash
python3 "${CLAUDE_PLUGIN_ROOT}/skills/kb-builder/scripts/generate-mermaid-concept-map.py" \
  --from-json /tmp/kb-interview-{session-id}.json \
  --correction "{user-correction-text}" \
  > /tmp/kb-interview-{session-id}.mmd
```

Cap at two regenerations. After the second pass, whichever answer the user gives, accept and move on. Time discipline.

---

## Empty-response contract

If `AskUserQuestion` returns empty on the preview: skip the diagram in the public profile body. Log `concept_map_empty` to `_meta/build-log/`. Continue to Phase 8.

The transcript (Phase 8a) still stores the generated diagram in a code fence — it's just not promoted to the public profile.

---

## Voice

Do not narrate the rendering process. "Here's the diagram I generated from the Mermaid template using the concept-map synthesiser" is banned framing. "Here's how your work looks" is the framing. Every user-visible line re-sells the promise: they talked, we captured, here's the picture.
