# AI Readiness Rubric (8 dimensions, 0–10 each, weighted)

The synthesis phase scores the company across 8 dimensions. Final score = weighted average × 10, rendered 0–100.

| # | Dimension | Weight | Signals (higher = better) |
|---|-----------|--------|---------------------------|
| 1 | Data accessibility | 1.5 | Core business data (CRM, tickets, docs) is in cloud systems with APIs/MCP. Not locked in local files, legacy ERP, or paper. |
| 2 | Process discipline | 1.5 | Pipeline stages are enforced. Required fields are required. Task owners are assigned. Systems reflect reality. |
| 3 | Document structure | 1.0 | Docs live in a findable hierarchy. Naming is consistent. Knowledge isn't only in people's heads. |
| 4 | Communication hygiene | 1.0 | Meetings have agendas. Decisions are written down. Async-to-sync ratio is healthy. |
| 5 | Tool stack coherence | 1.0 | One CRM, one project tracker, one chat, one doc store. Not five overlapping tools per category. |
| 6 | AI literacy | 1.0 | Team has tried LLMs. Some workflows already use AI. At least one person is an internal champion. |
| 7 | Permissions surface | 1.0 | Cloud connectors can be authorized without a 6-week security review. OAuth is understood. |
| 8 | Executive sponsorship | 1.0 | Leadership has committed to AI as a priority, not a side project. Budget exists. |

## Scoring Guidance per Dimension

**9–10**: Best-in-class. Finding is "you're ahead of your peers."
**7–8**: Solid foundation. Finding is "you can build on this."
**5–6**: Mixed. Some signals good, some bad. Finding is "here's the gap to close."
**3–4**: Meaningful gap. Finding is "this is blocking AI adoption. Fix before plugin-level work."
**0–2**: Critical blocker. Finding is "AI initiatives will fail here until this is fixed."

## Confidence Rules per Dimension

Do not score a dimension if the subagent had insufficient data. Instead, mark the dimension `Unknown` and flag it in "Coverage Gaps" with the recommendation "Connect `{connector}` to score this dimension."

An audit with 5 scored dimensions and 3 unknown is still a valid audit. Do not fabricate scores from thin data.

## Final Score Interpretation

| Score | Interpretation |
|-------|----------------|
| 80–100 | Ready for advanced agentic workflows. Prescyent KB Builder + Department Packs are the right next step. |
| 60–79 | Ready for Phase 1 plugins (automate existing workflows as-is). KB Builder will unlock Phase 2 (agentic). |
| 40–59 | Foundation work first. Subtract tools before adding AI. Fix one process before touching three. |
| 20–39 | AI is premature. Fix data hygiene, enforce process, and THEN revisit. |
| 0–19 | Do not deploy AI. Stabilize the company first. |

The rubric is intentionally opinionated. Anthropic's plugins are generic. Prescyent's audit tells you whether you're ready to use them.
