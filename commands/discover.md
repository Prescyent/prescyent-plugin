---
description: Run a Prescyent discovery — connector-aware AI readiness assessment that renders a buyer-facing marketing-style HTML deck inline in your chat in about five minutes. No drive writes unless you opt in.
argument-hint: "[depth:standard | depth:deep | role:<role>]"
background_safe: false
---

Run a Prescyent discovery against the user's connected Cowork tools. Follow `skills/discover/SKILL.md` exactly — seven phases:

1. Orient the user (4 numbered bullets + "What to know" paragraph framing the permission asks — proceeds directly to Phase 2 in the same turn, no "Ready to start?" gate)
2. Settings file check + connector pre-detection + elicitation form (**6 questions** — company pills with detected candidates, role pills, connector inventory cards with multi-select, unconnected-tools textarea, verbatim pain textarea, depth pills with Pro/Team plan-aware labels). v0.5 dropped the "What brought you here today?" question — the skill's purpose IS AI readiness; the alternate intents pulled users toward `/kb-interview` and `/kb-build` outcomes those commands serve better.
3. Subagent fan-out (4 audit-* agents in parallel via the Task tool, each producing JSON per `subagent-output-contract.md` v2.2 with `surprise_factor`). Master skill inlines the contract spec into each subagent prompt at dispatch — no path reference, no failed Read calls.
4. Strategic clarifications (3 high-altitude questions calibrated to the synthesizer's internal draft of the contestable answer + Top 3 — NOT subagent open_questions[]). Strategy-partner framing, McKinsey/BCG altitude. Synthesizer hypothesis pre-selected on each pill.
5. Synthesize structured JSON, render TWO artifacts (analyst markdown + buyer HTML deck), run `audit-deck-reviewer` validation pass (cap 3 iterations), display deck inline as Cowork artifact.
6. Recommended next step ("chain to /kb-build" framed as primary action) + secondary options (save to drive, draft email, send to teammate) — also via elicitation.
7. Closing handoff with settings-file discoverability hint if Phase 2c ran.

Arguments (optional, in `$ARGUMENTS`):

- `depth:standard` or `depth:deep` — pre-seed the search depth and skip that scope question
- `role:<role>` — pre-seed the role field and skip that scope question

**Critical constraints (v0.5):**

- No drive writes unless the user explicitly opts in at Phase 6.
- Subagents fan out via the `Task` tool in a single parallel block — do not serialize.
- Subagent contract is **inlined into each Task prompt** — no path reference. Subagents read the contract spec from the prompt itself.
- Subagents follow per-tool hard limits in their `## Tool-call discipline` sections to prevent token-budget overruns. Don't filesystem-spelunk on overflow — re-issue with smaller params.
- Synthesizer produces a single structured JSON. Both renderers (`render_deck.py`, `render_markdown.py`) build their artifacts directly from JSON fields — no markdown→HTML middleman, no token-injection from markdown blobs into template slots.
- Buyer HTML deck includes mandatory sections: hero with answer + split scoring (stack + workflow integration + overall), the 3 wins (compressed cards with explicit AI-mechanism translations), why-now (boil-the-ocean framing — DO NOT name Garry Tan in buyer copy), losing-time (every pain has an explicit AI-fix translation), Foaster-style 0-3 / 3-6 / 6-12 / 12+ roadmap, three lanes (DIY / Light-touch / Full — no pricing), collapsed appendix with full per-dimension findings.
- Three CTA placements: in-hero, mid-page (post-3-wins banner), footer.
- `audit-deck-reviewer` subagent validates the rendered HTML before final display. Hard-fails on: unfilled tokens, literal markdown, broken severity tags, missing CTAs, missing AI-mechanism / AI-fix translations, appendix open by default, "Garry Tan" name in buyer copy. Soft-warns on: banned words, word-budget overruns, em-dash density.
- Empty-response contract on every elicitation site: empty = abort cleanly, no silent defaults.
- Cowork artifact rendering is **mandatory** when `mcp__cowork__create_artifact` is available. The deck displays inline; no "open in your browser" or "prefer flat text" language.
- Markdown report includes the 100-word `tyler_brief` at the top — the executive summary the buyer can copy/paste into a lead email if they want to engage Prescyent.
- Every user-visible string passes the v0.5 voice gauntlet: banned words, AI-translation present on every problem named in buyer copy, no Tan attribution in buyer copy.
- The deliverable IS the inline buyer deck. Storage selection lives in `/kb-build`, not here.
