#!/usr/bin/env python3
"""
render_markdown.py — render the analyst-grade markdown report from the synthesizer JSON.

This is the deep-reader artifact: complete, dense, structured, machine-friendly.
Tyler's read + the input that `/kb-build --from-discover` ingests.

Input:  same structured JSON consumed by render_deck.py
        (see skills/discover/references/subagent-output-contract.md
         section "Synthesizer output contract").
Output: markdown file with YAML frontmatter, executive brief at top, full report below.

Usage:
  python3 render_markdown.py \
    --input  ~/.../baseline-payments-discovery.json \
    --output ~/.../baseline-payments-discovery-report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PLUGIN_VERSION = "0.7.0"
CONTRACT_VERSION = "2.3"


def _table(coverage: list[dict]) -> str:
    if not coverage:
        return ""
    out = ["| Category | Platforms | Records analyzed | Confidence |", "|---|---|---|---|"]
    for c in coverage:
        out.append(
            f"| {c.get('category','')} "
            f"| {c.get('platforms','')} "
            f"| {c.get('records_analyzed','')} "
            f"| {c.get('confidence','')} |"
        )
    return "\n".join(out)


def render(data: dict) -> str:
    company = data.get("company_name", "")
    slug = data.get("company_slug", "")
    audit_date = data.get("audit_date", "")
    depth = data.get("depth", "Standard")
    user_role = data.get("user_role", "")
    user_email = data.get("user_email", "")
    unconnected = data.get("unconnected_tools", "")

    scores = data.get("scores", {}) or {}
    stack_score = scores.get("stack", "")
    workflow_score = scores.get("workflow_integration", "")
    overall_score = scores.get("overall", "")
    interpretation = scores.get("interpretation", "")

    the_answer = data.get("the_answer", "")
    tyler_brief = data.get("tyler_brief", "")

    wins = data.get("wins_top_3", []) or []
    why_now = data.get("why_now", "")
    losing_time = data.get("losing_time", []) or []
    roadmap = data.get("roadmap", []) or []
    path_forward = data.get("path_forward", "")

    coverage = data.get("coverage", []) or []
    dimensions = data.get("dimensions", []) or []
    conflicts = data.get("conflicts", []) or []
    gaps = data.get("coverage_gaps", []) or []
    open_qs = data.get("open_questions", []) or []

    next_role = data.get("next_steps_role_aware", "")
    next_conn = data.get("next_steps_connector_aware", "")
    tan_footnote = data.get("tan_attribution_footnote", "")
    cowork_observed = bool(data.get("cowork_observed", False))
    behavioral_history = data.get("behavioral_history_findings", []) or []

    # ----- assemble -----

    lines = []

    # YAML frontmatter
    lines.append("---")
    lines.append(f"company_name: {company}")
    lines.append(f"company_slug: {slug}")
    lines.append(f"user_role: {user_role}")
    if user_email:
        lines.append(f"user_email: {user_email}")
    lines.append(f"buyer_intent: ai-readiness")
    lines.append(f"depth: {depth.lower()}")
    lines.append(f"generated_at: {audit_date}")
    lines.append(f"plugin_version: {PLUGIN_VERSION}")
    lines.append(f"contract_version: {CONTRACT_VERSION}")
    lines.append(f"score_stack: {stack_score}")
    lines.append(f"score_workflow_integration: {workflow_score}")
    lines.append(f"score_overall: {overall_score}")
    lines.append(f"cowork_observed: {'true' if cowork_observed else 'false'}")
    lines.append("---")
    lines.append("")

    # Title block
    lines.append(f"# {company}")
    lines.append(f"**AI Readiness Audit · {audit_date} · Depth: {depth}**")
    lines.append("")

    # Tyler brief (executive summary for forwarding)
    if tyler_brief:
        lines.append("## Brief for Tyler")
        lines.append("")
        lines.append("> _The 100-word summary you can paste into an email if you want to engage Prescyent._")
        lines.append("")
        lines.append(tyler_brief)
        lines.append("")

    # The answer
    lines.append("## The answer")
    lines.append("")
    lines.append(f"> {the_answer}")
    lines.append("")
    lines.append(f"**AI stack:** {stack_score}/10  ·  **Workflow integration:** {workflow_score}/10  ·  **Overall readiness:** {overall_score}/100")
    if interpretation:
        lines.append(f"_{interpretation}_")
    lines.append("")

    # Top 3 moves (analyst framing — uses "Top 3 moves" naming)
    if wins:
        lines.append("## Top 3 moves")
        lines.append("")
        for w in wins:
            rank = w.get("rank", "")
            head = w.get("headline", "")
            one_liner = w.get("one_liner", "")
            mech = w.get("ai_mechanism", "")
            impact = w.get("impact_metric", "")
            effort = w.get("effort", "")
            impact_tag = w.get("impact", "")
            confidence = w.get("confidence", "")
            surprise = w.get("surprise", "")
            evidence = w.get("evidence", "")
            lines.append(f"{rank}. **{head}** {one_liner}")
            lines.append(f"   - **AI mechanism:** {mech}")
            lines.append(f"   - **Impact:** {impact}")
            lines.append(f"   - **Tags:** Effort {effort} · Impact {impact_tag} · Confidence {confidence} · Surprise {surprise}")
            if evidence:
                lines.append(f"   - **Evidence:** {evidence}")
            lines.append("")

    # Why now (with Tan footnote attribution in analyst markdown only)
    if why_now:
        lines.append("## Why this matters now")
        lines.append("")
        lines.append(why_now)
        lines.append("")
        if tan_footnote:
            lines.append(f"_Footnote: {tan_footnote}_")
            lines.append("")

    # Where you're losing time
    if losing_time:
        lines.append("## Where you're losing time today")
        lines.append("")
        for it in losing_time:
            head = it.get("headline", "")
            detail = it.get("one_liner", "")
            time_cost = it.get("time_cost", "")
            ai_fix = it.get("ai_fix", "")
            lines.append(f"- **{head}** {detail}")
            lines.append(f"  - **Cost today:** {time_cost}")
            lines.append(f"  - **AI fix:** {ai_fix}")
            lines.append("")

    # Roadmap
    if roadmap:
        lines.append("## The path from here to AI-native")
        lines.append("")
        for step in roadmap:
            window = step.get("window", "")
            title = step.get("title", "")
            body = step.get("body", "")
            lines.append(f"### {window} — {title}")
            lines.append("")
            lines.append(body)
            lines.append("")

    # Path forward
    if path_forward:
        lines.append("## The path forward")
        lines.append("")
        lines.append(path_forward)
        lines.append("")

    # The detail
    lines.append("## The detail")
    lines.append("")

    # Coverage
    if coverage:
        lines.append("### Coverage")
        lines.append("")
        lines.append(_table(coverage))
        lines.append("")
        if unconnected:
            lines.append(f"**Not in scope:** {unconnected}. The audit ran on what's connected — these gaps are flagged in Coverage Gaps below.")
            lines.append("")

    # Per-dimension findings
    for d in dimensions:
        title = d.get("title", "")
        score = d.get("score", "")
        lines.append(f"### {title} — {score}/10")
        lines.append("")
        for f in d.get("findings", []) or []:
            sev = f.get("severity", "")
            surprise = f.get("surprise", "")
            head = f.get("headline", "")
            rec = f.get("recommendation", "")
            tag = f"[{sev} · {surprise} surprise]" if sev or surprise else ""
            line = f"- {tag} **{head}**".strip()
            lines.append(line)
            if rec:
                lines.append(f"  - **Fix:** {rec}")
        lines.append("")

    # Conflicts
    if conflicts:
        lines.append("### Conflicts between sources")
        lines.append("")
        for c in conflicts:
            topic = c.get("topic", "")
            summary = c.get("summary", "")
            rec = c.get("recommendation", "")
            decision = c.get("needed_decision", "")
            lines.append(f"- **{topic}:** {summary}")
            if rec:
                lines.append(f"  - **Recommendation:** {rec}")
            if decision:
                lines.append(f"  - **Need from you:** {decision}")
        lines.append("")

    # Coverage gaps
    if gaps:
        lines.append("### Coverage gaps")
        lines.append("")
        for g in gaps:
            gap = g.get("gap", "")
            impact = g.get("impact", "")
            fix = g.get("fix", "")
            lines.append(f"- **{gap}:** {impact} **Fix:** {fix}")
        lines.append("")

    # Open questions
    if open_qs:
        lines.append("### Open questions")
        lines.append("")
        for i, q in enumerate(open_qs, start=1):
            question = q.get("question", "")
            rec = q.get("recommended_answer", "")
            decision = q.get("needed_decision", "")
            lines.append(f"{i}. **{question}**")
            if rec:
                lines.append(f"   - Recommended answer: {rec}")
            if decision:
                lines.append(f"   - Need from you: {decision}")
        lines.append("")

    # Behavioral history (v0.7) — analyst-only appendix
    if behavioral_history:
        lines.append("### Behavioral history")
        lines.append("")
        lines.append("> _Patterns derived from your Cowork session log — workflows you keep running, where you correct AI output, prompts you re-paste. Surfaces in this appendix only; never in the buyer-facing deck._")
        lines.append("")
        for bh in behavioral_history:
            pattern = bh.get("pattern", "")
            confidence = bh.get("confidence", "")
            evidence = bh.get("evidence", "")
            line = f"- **{pattern}**"
            if confidence:
                line += f" _(confidence: {confidence})_"
            lines.append(line)
            if evidence:
                lines.append(f"  - **Evidence:** {evidence}")
        lines.append("")

    # Recommended next steps
    lines.append("## Recommended next steps")
    lines.append("")
    lines.append("1. **Run `/kb-build --from-discover`** with this report as the input. Scaffolds the wiki, mines your connectors, hands back the persistent context layer.")
    if next_role:
        lines.append(f"2. {next_role}")
    if next_conn:
        lines.append(f"3. {next_conn}")
    lines.append("")

    return "\n".join(lines)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to synthesizer JSON")
    parser.add_argument("--output", required=True, help="Output markdown path")
    args = parser.parse_args()

    input_path = Path(os.path.expanduser(args.input)).resolve()
    output_path = Path(os.path.expanduser(args.output)).resolve()

    if not input_path.exists():
        sys.exit(f"error: input JSON not found: {input_path}")

    raw = input_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: input is not valid JSON: {exc}")

    rendered = render(data)
    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"rendered → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
