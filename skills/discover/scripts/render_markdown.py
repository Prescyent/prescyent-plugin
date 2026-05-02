#!/usr/bin/env python3
"""
render_markdown.py — render the analyst-grade markdown report from the synthesizer JSON.

This is the deep-reader artifact: complete, dense, structured, machine-friendly.
v0.8 makes the markdown THE deliverable. Two AI consumers:
  (a) Prescyent's deal-context ingestion if buyer engages
  (b) /kb-build --from-discover seed

Target output 50-100 KB / 15-25K tokens (was 15 KB / 3K tokens — 5-7× expansion).

Input:  same structured JSON consumed by render_deck.py
        (see skills/discover/references/subagent-output-contract.md
         section "Synthesizer output contract" — contract_version 3.0).
Output: markdown file with YAML frontmatter (vocabulary primer inline),
        executive brief at top, full report + 12 appendices below.

Usage:
  python3 render_markdown.py \\
    --input  ~/.../baseline-payments-discovery.json \\
    --output ~/.../baseline-payments-discovery-report.md
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path

PLUGIN_VERSION = "0.8.1"
CONTRACT_VERSION = "3.0"

# Order of subagent appendices in the raw JSON dump section
SUBAGENT_ORDER = [
    "audit-systems",
    "audit-knowledge",
    "audit-drive",
    "audit-email",
    "audit-comms",
    "audit-meeting-transcripts",
    "audit-stack",
    "audit-sessions",
    "audit-web-search",
]


# ---------- Utility helpers ----------


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


def _yaml_escape(s: str) -> str:
    """Minimal YAML string escape for inline values."""
    if not s:
        return '""'
    s = str(s)
    if any(c in s for c in [':', '#', "'", '"', '\n', '|', '>', '{', '}', '[', ']', ',', '&', '*', '!', '%', '@']):
        return '"' + s.replace('\\', '\\\\').replace('"', '\\"') + '"'
    return s


# ---------- Section: YAML frontmatter (with vocabulary primer inline) ----------


def _frontmatter(data: dict) -> list[str]:
    company = data.get("company_name", "")
    slug = data.get("company_slug", "")
    user_role = data.get("user_role", "")
    user_email = data.get("user_email", "")
    audit_date = data.get("audit_date", "")
    depth = data.get("depth", "Medium")
    scores = data.get("scores", {}) or {}
    cowork_observed = bool(data.get("cowork_observed", False))

    lines = []
    lines.append("---")
    lines.append(f"company_name: {_yaml_escape(company)}")
    lines.append(f"company_slug: {slug}")
    lines.append(f"user_role: {user_role}")
    if user_email:
        lines.append(f"user_email: {user_email}")
    lines.append(f"buyer_intent: ai-readiness")
    lines.append(f"depth: {depth.lower()}")
    lines.append(f"generated_at: {audit_date}")
    lines.append(f"plugin_version: {PLUGIN_VERSION}")
    lines.append(f"contract_version: {CONTRACT_VERSION}")
    lines.append(f"score_stack: {scores.get('stack', '')}")
    lines.append(f"score_workflow_integration: {scores.get('workflow_integration', '')}")
    lines.append(f"score_overall: {scores.get('overall', '')}")
    lines.append(f"cowork_observed: {'true' if cowork_observed else 'false'}")

    # v0.8 NEW: vocabulary primer inline in YAML — /kb-build ingests as glossary
    vocab = data.get("vocabulary_primer", {}) or {}
    if vocab:
        lines.append("vocabulary_primer:")
        for key in ["knowledge_base", "plugin", "skill", "agent", "scheduled_task", "kicker"]:
            if key in vocab:
                lines.append(f"  {key}: {_yaml_escape(vocab[key])}")

    # v0.8 NEW: entity map summary in frontmatter
    entity_map = data.get("entity_map", []) or []
    if entity_map:
        lines.append("entity_map:")
        for e in entity_map:
            lines.append(f"  - name: {_yaml_escape(e.get('name', ''))}")
            lines.append(f"    type: {e.get('type', '')}")
            if e.get("domain"):
                lines.append(f"    domain: {e['domain']}")

    lines.append("---")
    lines.append("")
    return lines


# ---------- Top-of-report sections ----------


def _section_title_block(data: dict) -> list[str]:
    company = data.get("company_name", "")
    audit_date = data.get("audit_date", "")
    depth = data.get("depth", "Medium")
    return [f"# {company}", f"**AI Readiness Audit · {audit_date} · Depth: {depth}**", ""]


def _section_lane_health(data: dict) -> list[str]:
    """v0.8 QA-4 — surface connector failures + inference-only lanes immediately
    under the title, BEFORE the executive brief. If a buyer reads only the top
    of the markdown, they need to know which lanes ran without their data."""
    lane_health = data.get("lane_health", []) or []
    if not lane_health:
        return []
    out = ["## ⚠ Heads up — read this before the findings", ""]
    out.append("Some lanes ran without their data source. Findings below those lanes are inference-only — connect the missing tools and re-run for a real read.")
    out.append("")
    for lh in lane_health:
        status = lh.get("status", "")
        headline = lh.get("headline", "")
        impact = lh.get("impact", "")
        fix = lh.get("fix", "")
        status_label = {
            "no_connector": "**No connector**",
            "blocked": "**Blocked**",
            "inference_only": "**Inference only**",
            "partial": "**Partial**",
        }.get(status, f"**{status}**")
        out.append(f"- {status_label} — **{headline}**")
        out.append(f"  - {impact}")
        out.append(f"  - **Fix:** {fix}")
    out.append("")
    return out


def _section_tyler_brief(data: dict) -> list[str]:
    brief = data.get("tyler_brief", "")
    if not brief:
        return []
    return [
        "## Brief for Tyler",
        "",
        "> _The 100-word summary you can paste into an email if you want to engage Prescyent._",
        "",
        brief,
        "",
    ]


def _section_answer(data: dict) -> list[str]:
    answer = data.get("the_answer", "")
    scores = data.get("scores", {}) or {}
    interp = scores.get("interpretation", "")
    out = ["## The answer", "", f"> {answer}", ""]
    out.append(
        f"**AI stack:** {scores.get('stack','')}/10  ·  "
        f"**Workflow integration:** {scores.get('workflow_integration','')}/10  ·  "
        f"**Overall readiness:** {scores.get('overall','')}/100"
    )
    if interp:
        out.append(f"_{interp}_")
    out.append("")
    return out


def _section_top_3(data: dict) -> list[str]:
    wins = data.get("wins_top_3", []) or []
    if not wins:
        return []
    out = ["## Top 3 moves", ""]
    for w in wins:
        rank = w.get("rank", "")
        head = w.get("headline", "")
        one_liner = w.get("one_liner", "")
        mech = w.get("ai_mechanism", "")
        impact = w.get("impact_metric", "")
        out.append(f"{rank}. **{head}** {one_liner}")
        out.append(f"   - **AI mechanism:** {mech}")
        out.append(f"   - **Impact:** {impact}")
        out.append(
            f"   - **Tags:** Effort {w.get('effort','')} · Impact {w.get('impact','')} · "
            f"Confidence {w.get('confidence','')} · Surprise {w.get('surprise','')}"
        )
        if w.get("evidence"):
            out.append(f"   - **Evidence:** {w['evidence']}")
        out.append("")
    return out


def _section_why_now(data: dict) -> list[str]:
    why_now = data.get("why_now", "")
    tan_footnote = data.get("tan_attribution_footnote", "")
    if not why_now:
        return []
    out = ["## Why this matters now", "", why_now, ""]
    if tan_footnote:
        out.append(f"_Footnote: {tan_footnote}_")
        out.append("")
    return out


def _section_losing_time(data: dict) -> list[str]:
    items = data.get("losing_time", []) or []
    if not items:
        return []
    out = ["## Where you're losing time today", ""]
    for it in items:
        out.append(f"- **{it.get('headline','')}** {it.get('one_liner','')}")
        out.append(f"  - **Cost today:** {it.get('time_cost','')}")
        out.append(f"  - **AI fix:** {it.get('ai_fix','')}")
        out.append("")
    return out


def _section_vocabulary(data: dict) -> list[str]:
    """v0.8 NEW EM-52 — vocabulary primer in body (also lives in frontmatter)."""
    vocab = data.get("vocabulary_primer", {}) or {}
    if not vocab:
        return []
    out = ["## Vocabulary", "", "_The terms used across this audit, in plain English._", ""]
    term_order = [
        ("knowledge_base", "Knowledge base"),
        ("plugin", "Plugin"),
        ("skill", "Skill"),
        ("agent", "Agent"),
        ("scheduled_task", "Scheduled task"),
    ]
    for key, label in term_order:
        if key in vocab:
            out.append(f"- **{label}** — {vocab[key]}")
    if "kicker" in vocab:
        out.append("")
        out.append(f"_{vocab['kicker']}_")
    out.append("")
    return out


def _section_roadmap(data: dict) -> list[str]:
    roadmap = data.get("roadmap", []) or []
    if not roadmap:
        return []
    out = ["## The path from here to AI-native", ""]
    for step in roadmap:
        out.append(f"### {step.get('window','')} — {step.get('title','')}")
        out.append("")
        out.append(step.get("body", ""))
        out.append("")
    return out


def _section_path_forward(data: dict) -> list[str]:
    pf = data.get("path_forward", "")
    if not pf:
        return []
    return ["## The path forward", "", pf, ""]


# ---------- Per-dimension findings + standard appendices ----------


def _section_coverage(data: dict) -> list[str]:
    coverage = data.get("coverage", []) or []
    unconnected = data.get("unconnected_tools", "")
    if not coverage:
        return []
    out = ["## The detail", "", "### Coverage", "", _table(coverage), ""]
    if unconnected:
        out.append(
            f"**Not in scope:** {unconnected}. The audit ran on what's connected — "
            "these gaps are flagged in Coverage Gaps below."
        )
        out.append("")
    return out


def _section_dimensions(data: dict) -> list[str]:
    dimensions = data.get("dimensions", []) or []
    if not dimensions:
        return []
    out = []
    for d in dimensions:
        out.append(f"### {d.get('title','')} — {d.get('score','')}/10")
        out.append("")
        for f in d.get("findings", []) or []:
            sev = f.get("severity", "")
            surprise = f.get("surprise", "")
            tag = f"[{sev} · {surprise} surprise]" if sev or surprise else ""
            line = f"- {tag} **{f.get('headline','')}**".strip()
            out.append(line)
            if f.get("recommendation"):
                out.append(f"  - **Fix:** {f['recommendation']}")
        out.append("")
    return out


def _section_conflicts(data: dict) -> list[str]:
    conflicts = data.get("conflicts", []) or []
    if not conflicts:
        return []
    out = ["### Conflicts between sources", ""]
    for c in conflicts:
        out.append(f"- **{c.get('topic','')}:** {c.get('summary','')}")
        if c.get("recommendation"):
            out.append(f"  - **Recommendation:** {c['recommendation']}")
        if c.get("needed_decision"):
            out.append(f"  - **Need from you:** {c['needed_decision']}")
    out.append("")
    return out


def _section_gaps(data: dict) -> list[str]:
    gaps = data.get("coverage_gaps", []) or []
    if not gaps:
        return []
    out = ["### Coverage gaps", ""]
    for g in gaps:
        out.append(f"- **{g.get('gap','')}:** {g.get('impact','')} **Fix:** {g.get('fix','')}")
    out.append("")
    return out


def _section_open_questions(data: dict) -> list[str]:
    qs = data.get("open_questions", []) or []
    if not qs:
        return []
    out = ["### Open questions", ""]
    for i, q in enumerate(qs, start=1):
        out.append(f"{i}. **{q.get('question','')}**")
        if q.get("recommended_answer"):
            out.append(f"   - Recommended answer: {q['recommended_answer']}")
        if q.get("needed_decision"):
            out.append(f"   - Need from you: {q['needed_decision']}")
    out.append("")
    return out


# ---------- v0.8 NEW appendices ----------


def _appendix_entity_map(data: dict) -> list[str]:
    entity_map = data.get("entity_map", []) or []
    web_research = data.get("web_research", {}) or {}
    if not entity_map and not web_research:
        return []
    out = ["## Appendix: Entity map (web research)", ""]
    out.append(
        "_The open-web view of the company. From `audit-web-search`. Each entity got its own "
        "research pass; secondary entities are explicitly named where they show up in the synthesis._"
    )
    out.append("")
    if entity_map:
        out.append("| Entity | Type | Domain | Relationship |")
        out.append("|---|---|---|---|")
        for e in entity_map:
            out.append(
                f"| {e.get('name','')} | {e.get('type','')} | {e.get('domain','—')} | "
                f"{e.get('relationship') or e.get('parent') or '—'} |"
            )
        out.append("")
    individual_flag = web_research.get("individual_operator_flag", False)
    if individual_flag:
        out.append(
            "_Individual-operator persona detected. Web research degraded gracefully — "
            "findings rely on connector-internal signal rather than open-web context._"
        )
        out.append("")
    return out


def _appendix_voice_samples(data: dict) -> list[str]:
    samples = data.get("voice_samples", []) or []
    voice_pattern = data.get("voice_pattern", {}) or {}
    if not samples and not voice_pattern:
        return []
    out = ["## Appendix: Voice samples", ""]
    out.append(
        "_Verbatim text excerpts that demonstrate the buyer's tone-of-voice. From `audit-email` "
        "and `audit-drive`. Used downstream by `/kb-build` to anchor draft-skill outputs against "
        "the buyer's actual voice. Sensitive content redacted at source._"
    )
    out.append("")
    if voice_pattern:
        out.append("### Voice pattern (quantified)")
        out.append("")
        for key, label in [
            ("formality", "Formality"),
            ("median_length_words", "Median sentence length (words)"),
            ("em_dash_density_per_100w", "Em-dash density per 100 words"),
            ("sign_off_pattern", "Sign-off pattern"),
            ("lead_pattern", "Lead pattern"),
        ]:
            if key in voice_pattern:
                out.append(f"- **{label}:** {voice_pattern[key]}")
        out.append("")
    if samples:
        out.append("### Verbatim samples")
        out.append("")
        for i, s in enumerate(samples, start=1):
            src = s.get("source", "unknown")
            ref = s.get("source_ref", "")
            excerpt = s.get("excerpt", "")
            out.append(f"**Sample {i} ({src} · {ref})**")
            out.append("")
            out.append(f"> {excerpt}")
            out.append("")
    return out


def _appendix_tool_stack(data: dict) -> list[str]:
    raw = data.get("raw_subagent_dumps", {}) or {}
    stack = raw.get("audit-stack", {}) or {}
    classification_surface = stack.get("classification_surface", {}) or {}
    if not stack:
        return []
    out = ["## Appendix: Tool stack matrix", ""]
    out.append("_Per-connector AI-readiness scoring. From `audit-stack`._")
    out.append("")
    if classification_surface:
        out.append("### Classification surface")
        out.append("")
        out.append("| Connector | Classification |")
        out.append("|---|---|")
        for connector, classification in classification_surface.items():
            out.append(f"| {connector} | {classification} |")
        out.append("")
    findings = stack.get("findings", []) or []
    if findings:
        out.append("### Per-connector findings")
        out.append("")
        for f in findings:
            head = f.get("headline", "")
            rec = f.get("recommendation", "")
            out.append(f"- **{head}**")
            if rec:
                out.append(f"  - **Fix:** {rec}")
        out.append("")
    return out


def _appendix_email_matrix(data: dict) -> list[str]:
    em = data.get("email_matrix", {}) or {}
    if not em:
        return []
    out = ["## Appendix: Email behavior matrix", ""]
    out.append(
        "_Top-20 senders × volume × sent-vs-received-ratio × response-time-median. "
        "Recurring-pattern catalog. From `audit-email`._"
    )
    out.append("")
    inbound = em.get("top_inbound_senders", []) or []
    if inbound:
        out.append("### Top inbound senders (12-month volume)")
        out.append("")
        out.append("| Sender | Volume (12mo) | Domain type |")
        out.append("|---|---|---|")
        for s in inbound[:20]:
            out.append(f"| {s.get('sender','')} | {s.get('volume_12mo','')} | {s.get('domain_type','')} |")
        out.append("")
    outbound = em.get("top_outbound_domains", []) or []
    if outbound:
        out.append("### Top outbound recipient domains")
        out.append("")
        out.append("| Domain | Volume (12mo) | Dominant thread type |")
        out.append("|---|---|---|")
        for d in outbound[:20]:
            out.append(f"| {d.get('domain','')} | {d.get('volume_12mo','')} | {d.get('dominant_thread_type','')} |")
        out.append("")
    workflows = em.get("recurring_workflows", []) or []
    if workflows:
        out.append("### Recurring workflow patterns")
        out.append("")
        for w in workflows:
            out.append(
                f"- **{w.get('pattern','')}** — subject `{w.get('subject_template','')}`, "
                f"frequency {w.get('frequency','')}, recipients {w.get('recipients',[])}"
            )
        out.append("")
    attachments = em.get("attachment_patterns", []) or []
    if attachments:
        out.append("### Attachment patterns")
        out.append("")
        for a in attachments:
            out.append(
                f"- To **{a.get('to_domain','')}**: {a.get('volume','')}× `{a.get('file_type','')}` — "
                f"common subject pattern: {a.get('common_subject_pattern','')}"
            )
        out.append("")
    return out


def _appendix_drive_taxonomy(data: dict) -> list[str]:
    dt = data.get("drive_taxonomy", {}) or {}
    if not dt:
        return []
    out = ["## Appendix: Drive taxonomy", ""]
    out.append(
        "_Folder-structure tree, authority clusters, doctrine pages, stale pages. "
        "From `audit-drive`._"
    )
    out.append("")
    if dt.get("root_label"):
        out.append(f"**Root:** `{dt['root_label']}`")
        out.append("")
    top_folders = dt.get("top_folders", []) or []
    if top_folders:
        out.append("### Top folders")
        out.append("")
        out.append("| Path | File count | Depth | Authority score | Last modified |")
        out.append("|---|---|---|---|---|")
        for f in top_folders[:20]:
            out.append(
                f"| `{f.get('path','')}` | {f.get('file_count','')} | {f.get('depth','')} | "
                f"{f.get('authority_score','')} | {f.get('last_modified','')} |"
            )
        out.append("")
    clusters = dt.get("authority_clusters", []) or []
    if clusters:
        out.append("### Authority clusters")
        out.append("")
        for c in clusters:
            out.append(
                f"- **{c.get('name','')}** ({c.get('page_count','')} pages) — "
                f"patterns: {c.get('patterns',[])}"
            )
        out.append("")
    doctrine = dt.get("doctrine_pages", []) or []
    if doctrine:
        out.append("### Doctrine pages (canonical, worth promoting)")
        out.append("")
        for p in doctrine:
            out.append(
                f"- `{p.get('path','')}` — owner: {p.get('owner','')}, "
                f"last-modified: {p.get('last_modified','')}"
            )
        out.append("")
    stale = dt.get("stale_pages", []) or []
    if stale:
        out.append("### Stale pages (>2 years)")
        out.append("")
        for p in stale:
            out.append(
                f"- `{p.get('path','')}` — last-modified: {p.get('last_modified','')}, "
                f"still-referenced: {p.get('still_referenced', False)}"
            )
        out.append("")
    return out


def _appendix_comms_patterns(data: dict) -> list[str]:
    cp = data.get("comms_patterns", {}) or {}
    if not cp:
        return []
    out = ["## Appendix: Calendar / chat patterns", ""]
    out.append("_Calendar density, recurring meeting cadences, chat top-spaces, cross-channel decision flow. From `audit-comms`._")
    out.append("")
    cal = cp.get("calendar_meeting_density", {}) or {}
    if cal:
        out.append("### Calendar meeting density")
        out.append("")
        out.append(f"- **Weekly avg meetings:** {cal.get('weekly_avg_meetings','')}")
        out.append(f"- **Weekly avg meeting hours:** {cal.get('weekly_avg_meeting_hours','')}")
        if cal.get("by_quarter"):
            out.append(f"- **By quarter:** {cal['by_quarter']}")
        out.append("")
    cadences = cp.get("recurring_meeting_cadences", []) or []
    if cadences:
        out.append("### Recurring meeting cadences")
        out.append("")
        for c in cadences:
            out.append(
                f"- **{c.get('title_pattern','')}** — {c.get('frequency','')}, "
                f"{c.get('attendee_count','')} attendees"
            )
        out.append("")
    spaces = cp.get("chat_top_spaces", []) or []
    if spaces:
        out.append("### Chat top spaces")
        out.append("")
        for s in spaces[:20]:
            out.append(
                f"- **{s.get('space','')}** — 30d volume: {s.get('30d_message_volume','')}, "
                f"active participants: {s.get('active_participants','')}"
            )
        out.append("")
    flow = cp.get("cross_channel_decision_flow", "")
    if flow:
        out.append("### Cross-channel decision flow")
        out.append("")
        out.append(flow)
        out.append("")
    return out


def _appendix_meeting_transcripts(data: dict) -> list[str]:
    mi = data.get("meeting_inventory", {}) or {}
    deep_reads = data.get("transcript_deep_reads", []) or []
    if not mi and not deep_reads:
        return []
    out = ["## Appendix: Meeting transcripts", ""]
    out.append(
        "_Meeting inventory across 12 months + transcript deep-reads on high-signal meetings. "
        "From `audit-meeting-transcripts`. Very-deep mode pulls full transcripts on ~12 selected meetings._"
    )
    out.append("")
    total = mi.get("total_meetings_12mo", 0)
    if total:
        out.append(f"**Total meetings (12 months):** {total}")
        out.append("")
    by_counterparty = mi.get("by_counterparty", []) or []
    if by_counterparty:
        out.append("### By counterparty")
        out.append("")
        out.append("| Counterparty | Meeting count | Cadence | First seen | Last seen |")
        out.append("|---|---|---|---|---|")
        for c in by_counterparty:
            out.append(
                f"| {c.get('counterparty','')} | {c.get('meeting_count','')} | "
                f"{c.get('cadence','')} | {c.get('first_seen','—')} | {c.get('last_seen','—')} |"
            )
        out.append("")
    by_type = mi.get("by_type", []) or []
    if by_type:
        out.append("### By meeting type")
        out.append("")
        for t in by_type:
            out.append(f"- **{t.get('type','')}**: {t.get('count','')}")
        out.append("")
    cadences = mi.get("cadence_patterns", []) or []
    if cadences:
        out.append("### Cadence patterns")
        out.append("")
        for c in cadences:
            out.append(f"- **{c.get('pattern','')}** — {c.get('frequency','')}, first observed {c.get('first_observed','—')}")
        out.append("")
    if deep_reads:
        out.append("### Transcript deep-reads (very-deep mode)")
        out.append("")
        for r in deep_reads:
            out.append(f"#### {r.get('title','')} — {r.get('date','')} ({r.get('counterparty','—')})")
            out.append("")
            out.append(f"- **Duration:** {r.get('duration_min','')} min")
            out.append(f"- **Why selected:** {r.get('why_selected','')}")
            extract = r.get("key_extract", "")
            if extract:
                out.append("- **Key extract:**")
                out.append("")
                out.append("> " + extract.replace("\n", "\n> "))
            out.append("")
    return out


def _appendix_session_history(data: dict) -> list[str]:
    raw = data.get("raw_subagent_dumps", {}) or {}
    sessions = raw.get("audit-sessions", {}) or {}
    if not sessions:
        return []
    out = ["## Appendix: Session history", ""]
    out.append(
        "_Behavioral patterns from the user's Cowork session log. From `audit-sessions`. "
        "Patterns + counts only — never verbatim user content._"
    )
    out.append("")
    findings = sessions.get("findings", []) or []
    if findings:
        out.append("### Session findings")
        out.append("")
        for f in findings:
            head = f.get("headline", "")
            detail = f.get("detail", "")
            out.append(f"- **{head}** — {detail}")
            if f.get("recommendation"):
                out.append(f"  - **Fix:** {f['recommendation']}")
        out.append("")
    behavioral = sessions.get("behavioral_trace_findings", []) or []
    if behavioral:
        out.append("### Behavioral patterns")
        out.append("")
        for b in behavioral:
            out.append(
                f"- **{b.get('pattern','')}** _(confidence: {b.get('confidence','')})_"
            )
            if b.get("evidence"):
                out.append(f"  - Evidence: {b['evidence']}")
        out.append("")
    return out


def _appendix_web_research(data: dict) -> list[str]:
    wr = data.get("web_research", {}) or {}
    if not wr:
        return []
    out = ["## Appendix: Web research deep-pull", ""]
    out.append("_Per-entity summaries from the open web. From `audit-web-search`. Up to 60 web queries per audit run._")
    out.append("")
    summaries = wr.get("per_entity_summaries", []) or []
    for e in summaries:
        out.append(f"### {e.get('entity','')}")
        out.append("")
        if e.get("description"):
            out.append(e["description"])
            out.append("")
        if e.get("customer_segments"):
            out.append(f"**Customer segments:** {', '.join(e['customer_segments'])}")
        if e.get("products"):
            out.append(f"**Products:** {', '.join(e['products'])}")
        if e.get("recent_moves"):
            out.append("**Recent moves:**")
            for m in e["recent_moves"]:
                out.append(f"- {m.get('date','—')}: {m.get('headline','')} (tier {m.get('tier','—')})")
        if e.get("team_signals"):
            out.append(f"**Team signals:** {', '.join(e['team_signals'])}")
        if e.get("risk_signals"):
            risk = e["risk_signals"]
            out.append(f"**Risk signals:** {', '.join(risk) if risk else 'None observed.'}")
        out.append("")
    return out


def _appendix_resume_calls(data: dict) -> list[str]:
    rt = data.get("resume_trace", []) or []
    if not rt:
        return []
    out = ["## Appendix: Resume calls", ""]
    out.append(
        "_Master gap-detection follow-up calls to specific subagents. v0.8 quality lever — "
        "the master scores each subagent for thin spots after Wave 1 and resumes targeted "
        "subagents to deepen findings. Adaptive cap by depth: 1/3/6 follow-ups per subagent for "
        "Standard/Medium/Very-deep._"
    )
    out.append("")
    out.append("| Round | Subagent | Follow-up prompt | Refined finding |")
    out.append("|---|---|---|---|")
    pipe_escape = "\\|"
    for r in rt:
        prompt = (r.get("follow_up_prompt", "") or "").replace("|", pipe_escape)
        refined = (r.get("refined_finding_summary", "") or "").replace("|", pipe_escape)
        out.append(
            f"| {r.get('round','')} | {r.get('subagent','')} | {prompt} | {refined} |"
        )
    out.append("")
    return out


def _appendix_citations(data: dict) -> list[str]:
    cites = data.get("citations", []) or []
    if not cites:
        return []
    out = ["## Appendix: Citations", ""]
    out.append("_Web sources cited per finding. From `audit-web-search`. Tier ratings: 1=Authoritative, 2=Owned, 3=Trade press, 4=LinkedIn, 5=Community._")
    out.append("")
    out.append("| Finding | Source | Title | Retrieved | Tier |")
    out.append("|---|---|---|---|---|")
    for c in cites:
        out.append(
            f"| {c.get('finding_id','')} | {c.get('url','')} | {c.get('title','')} | "
            f"{c.get('retrieved','')} | {c.get('tier','')} |"
        )
    out.append("")
    return out


def _appendix_behavioral_history(data: dict) -> list[str]:
    bh = data.get("behavioral_history_findings", []) or []
    if not bh:
        return []
    out = ["## Appendix: Behavioral history", ""]
    out.append(
        "> _Patterns derived from your Cowork session log — workflows you keep running, where "
        "you correct AI output, prompts you re-paste. Surfaces in this appendix only; never in "
        "the buyer-facing deck._"
    )
    out.append("")
    for b in bh:
        line = f"- **{b.get('pattern','')}**"
        if b.get("confidence"):
            line += f" _(confidence: {b['confidence']})_"
        out.append(line)
        if b.get("evidence"):
            out.append(f"  - **Evidence:** {b['evidence']}")
    out.append("")
    return out


def _appendix_raw_subagent_json(data: dict) -> list[str]:
    """v0.8 LOAD-BEARING — fenced ```json blocks per subagent.

    /kb-build --from-discover ingests this section to mine every finding,
    not just the synthesized Top 3.
    """
    raw = data.get("raw_subagent_dumps", {}) or {}
    if not raw:
        return []
    out = ["## Appendix: Raw subagent JSON", ""]
    out.append(
        "_The full per-lane subagent JSON returns. Load-bearing for `/kb-build --from-discover` "
        "ingestion — lets the mining subagents see EVERY finding, not just the synthesized Top 3 + "
        "losing_time + dimensions. Each subagent's `_trace[]` array shows every tool call._"
    )
    out.append("")
    for subagent in SUBAGENT_ORDER:
        if subagent in raw:
            out.append(f"### `{subagent}`")
            out.append("")
            out.append("```json")
            out.append(json.dumps(raw[subagent], indent=2))
            out.append("```")
            out.append("")
    return out


# ---------- Persona-tailored next-steps (v0.8 verbose) ----------


def _section_recommended_next_steps(data: dict) -> list[str]:
    """v0.8: 5-10 lines per persona, naming specific people / connectors / workflows."""
    role = (data.get("user_role") or "founder").lower()
    next_role = data.get("next_steps_role_aware", "")
    next_conn = data.get("next_steps_connector_aware", "")
    md_path_hint = "Run `/kb-build --from-discover` with this report as the input."

    out = ["## Recommended next steps", ""]

    if role in ("founder", "cfo"):
        out.append("**For founders/CFOs:**")
        out.append("")
        out.append(
            f"1. **{md_path_hint}** Scaffolds the wiki, mines your connectors, hands back the "
            "persistent context layer that compounds across every Claude session, every employee, "
            "every quarter."
        )
        out.append("2. Review the Top 3 wins above with your senior team this week. Each names a concrete AI mechanism (skill / scheduled task / custom plugin / durable agent) and an estimated time-back metric.")
        out.append("3. The roadmap shows what compounds beyond the Top 3. Year-1 path: knowledge base → custom skills → scheduled tasks → durable agents.")
        if next_role:
            out.append(f"4. {next_role}")
        if next_conn:
            out.append(f"5. {next_conn}")
        out.append("6. If the audit pointed at a structural pattern (single-point-of-failure on key workflows, missing knowledge layer, integration debt), that's the priority — the Top 3 is the entry point, not the destination.")
    elif role in ("sales", "marketing"):
        out.append("**For sales/marketing leads:**")
        out.append("")
        out.append(f"1. **{md_path_hint}** The mining pass surfaces your top-N counterparty patterns, recurring email workflows, and deal-stage-to-conversation drift.")
        out.append("2. Review the Top 3 wins — each is scoped to a recurring workflow your team already runs, where the AI mechanism is a one-step skill or scheduled task rather than a multi-quarter rebuild.")
        out.append("3. The Email behavior matrix appendix shows which counterparties produce email-loop urgency and which response-times matter — feed that into the next sales-ops review.")
        out.append("4. The Meeting transcripts appendix shows recurring counterparty patterns — Tuesday standups, monthly reviews, QBR cadences — automation candidates if they're deterministic.")
        if next_role:
            out.append(f"5. {next_role}")
        if next_conn:
            out.append(f"6. {next_conn}")
    elif role in ("ops", "operations"):
        out.append("**For ops leads:**")
        out.append("")
        out.append(f"1. **{md_path_hint}** Mines your connectors and surfaces the deterministic-workflow candidates — the recurring patterns where a skill or scheduled task replaces manual repetition.")
        out.append("2. The Top 3 is the proof — each is a named workflow you can ship in days. The roadmap shows what compounds beyond.")
        out.append("3. The Drive taxonomy appendix shows your authority clusters and stale pages — input for a 30-min /wiki:review session this quarter.")
        out.append("4. The Calendar/chat patterns appendix surfaces recurring meeting cadences and cross-channel decision flow — automation candidates and visibility gaps.")
        if next_role:
            out.append(f"5. {next_role}")
        if next_conn:
            out.append(f"6. {next_conn}")
    elif role in ("product", "engineering"):
        out.append("**For product/engineering leads:**")
        out.append("")
        out.append(f"1. **{md_path_hint}** Builds the persistent context layer your team's AI tools currently lack. Every Claude session today runs cold; the knowledge base fixes that.")
        out.append("2. Review the Top 3 — each names a concrete integration (skill / scheduled task / custom plugin / durable agent). The AI mechanism is named explicitly so it's scopable.")
        out.append("3. The Tool stack matrix appendix shows your AI-readiness per connector — which already have plugin support, which need integration, which are blocking.")
        out.append("4. The roadmap shows the compound path: knowledge base → custom skills → scheduled tasks → durable agents. Each tier earns the next.")
        if next_role:
            out.append(f"5. {next_role}")
        if next_conn:
            out.append(f"6. {next_conn}")
    else:
        # Default: founder framing
        out.append(f"1. **{md_path_hint}**")
        if next_role:
            out.append(f"2. {next_role}")
        if next_conn:
            out.append(f"3. {next_conn}")

    out.append("")
    return out


# ---------- Main render ----------


def render(data: dict) -> str:
    blocks: list[list[str]] = []

    # Header sections
    blocks.append(_frontmatter(data))
    blocks.append(_section_title_block(data))
    blocks.append(_section_lane_health(data))
    blocks.append(_section_tyler_brief(data))
    blocks.append(_section_answer(data))
    blocks.append(_section_top_3(data))
    blocks.append(_section_why_now(data))
    blocks.append(_section_vocabulary(data))   # v0.8 NEW
    blocks.append(_section_losing_time(data))
    blocks.append(_section_roadmap(data))
    blocks.append(_section_path_forward(data))

    # The Detail (existing)
    blocks.append(_section_coverage(data))
    blocks.append(_section_dimensions(data))
    blocks.append(_section_conflicts(data))
    blocks.append(_section_gaps(data))
    blocks.append(_section_open_questions(data))

    # v0.8 NEW appendices
    blocks.append(_appendix_entity_map(data))
    blocks.append(_appendix_voice_samples(data))
    blocks.append(_appendix_tool_stack(data))
    blocks.append(_appendix_email_matrix(data))
    blocks.append(_appendix_drive_taxonomy(data))
    blocks.append(_appendix_comms_patterns(data))
    blocks.append(_appendix_meeting_transcripts(data))
    blocks.append(_appendix_session_history(data))
    blocks.append(_appendix_web_research(data))
    blocks.append(_appendix_resume_calls(data))
    blocks.append(_appendix_citations(data))
    blocks.append(_appendix_behavioral_history(data))

    # Recommended next steps (v0.8 verbose persona-tailored)
    blocks.append(_section_recommended_next_steps(data))

    # Raw subagent JSON dump — last section, load-bearing for /kb-build
    blocks.append(_appendix_raw_subagent_json(data))

    # Flatten
    all_lines: list[str] = []
    for b in blocks:
        if b:
            all_lines.extend(b)

    return "\n".join(all_lines)


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
    size_kb = len(rendered.encode("utf-8")) / 1024
    print(f"rendered → {output_path}  ({size_kb:.1f} KB)")
    return 0


if __name__ == "__main__":
    sys.exit(main())
