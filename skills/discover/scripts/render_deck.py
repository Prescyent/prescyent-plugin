#!/usr/bin/env python3
"""
render_deck.py — render the buyer-facing HTML deck from the synthesizer JSON.

Input:  structured JSON produced by the master discover skill's Phase 5a synthesis
        (shape per skills/discover/references/subagent-output-contract.md
         section "Synthesizer output contract").
Output: self-contained HTML using the Prescyent dark-mode design system at
        skills/discover/references/report-template.html.

Usage:
  python3 render_deck.py \
    --input  ~/.../baseline-payments-discovery.json \
    --output ~/.../baseline-payments-discovery-deck.html

Design contract (every section is built in Python from structured fields, NOT
via a markdown→HTML middleman):

  Hero          ← company_name, audit_date, depth
  Answer card   ← the_answer, scores.{stack,workflow_integration,overall,interpretation}
  Hero CTA      ← static (mailto + booking link)
  3 wins        ← wins_top_3[]
  Mid CTA       ← static
  Why now       ← why_now (NO Garry Tan attribution in buyer copy)
  Losing time   ← losing_time[]
  Roadmap       ← roadmap[] (4 windows)
  Lanes         ← lanes[]
  Appendix      ← coverage[] + dimensions[] + conflicts[] + coverage_gaps[] + open_questions[]
                  rendered inside <details> (collapsed by default)
  Footer        ← canonical Prescyent close
"""

from __future__ import annotations

import argparse
import html
import json
import os
import re
import sys
import urllib.parse
from pathlib import Path

PLUGIN_VERSION = "0.8.0"
BOOKING_LINK = "https://calendar.app.google/wwabJHCKHufyqW7Q6"
TYLER_EMAIL = "tyler@prescyent.ai"

SEVERITY_CLASS = {
    "critical": "tag-critical",
    "high": "tag-high",
    "medium": "tag-medium",
    "low": "tag-low",
}

ALLOWED_ROADMAP_ACCENTS = ("green", "cyan", "purple", "brass")
ROADMAP_ACCENT_HEX = {
    "green": "#34d399",
    "cyan": "#22d3ee",
    "purple": "#a78bfa",
    "brass": "#d4af78",
}


# ---------- helpers ----------


def esc(text: str | int | None) -> str:
    if text is None:
        return ""
    return html.escape(str(text))


def mailto_url(company: str, topic_suffix: str = "discovery audit follow-up") -> str:
    subject = urllib.parse.quote(f"{company} {topic_suffix}")
    return f"mailto:{TYLER_EMAIL}?subject={subject}"


def cta_buttons_inner(company: str, primary_label: str = "Email us", ghost_label: str = "Book 30 min") -> str:
    """Just the two anchor buttons — caller wraps in a .cta-row div as needed."""
    return (
        f'<a class="cta primary" href="{mailto_url(company)}">'
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<path d="M3 7l9 6 9-6"/><rect x="3" y="5" width="18" height="14" rx="2"/>'
        f'</svg>{esc(primary_label)} <span class="arrow">→</span></a>'
        f'<a class="cta ghost" href="{BOOKING_LINK}" target="_blank" rel="noopener">'
        '<svg class="icon" viewBox="0 0 24 24" aria-hidden="true">'
        '<rect x="3" y="5" width="18" height="16" rx="2"/><path d="M3 9h18M8 3v4M16 3v4"/>'
        f'</svg>{esc(ghost_label)} <span class="arrow">↗</span></a>'
    )


def cta_row_html(company: str, *, extra_class: str = "", primary_label: str = "Email us", ghost_label: str = "Book 30 min") -> str:
    classes = "cta-row" + (f" {extra_class}" if extra_class else "")
    return f'<div class="{classes}">{cta_buttons_inner(company, primary_label, ghost_label)}</div>'


# ---------- section builders ----------


def build_hero(data: dict) -> str:
    company = esc(data.get("company_name", ""))
    date_str = esc(data.get("audit_date", ""))
    depth = esc(data.get("depth", "Standard"))
    return (
        '<section class="hero reveal">'
        '<div class="eyebrow">Prescyent · AI Readiness Audit</div>'
        f'<h1>{company}</h1>'
        f'<p class="meta">{date_str} · {depth} scope</p>'
        "</section>"
    )


def _score_bar_svg(value: int | float, denominator: int, accent: str = "purple") -> str:
    """Inline SVG horizontal bar for a score. Pure SVG, no JS."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    if denominator <= 0:
        return ""
    pct = max(0.0, min(1.0, v / denominator))
    filled = round(pct * 200, 1)  # viewBox width 200
    accent_color = "#a78bfa" if accent == "purple" else "#22d3ee"
    return (
        '<svg class="score-bar" viewBox="0 0 200 8" preserveAspectRatio="none" aria-hidden="true">'
        '<rect class="score-bar-track" x="0" y="0" width="200" height="8" rx="4"/>'
        f'<rect class="score-bar-fill" x="0" y="0" width="{filled}" height="8" rx="4" fill="{accent_color}"/>'
        "</svg>"
    )


def _score_bar_overall_svg(value: int | float) -> str:
    """Inline SVG for the overall 0-100 score with a gradient fill."""
    try:
        v = float(value)
    except (TypeError, ValueError):
        return ""
    pct = max(0.0, min(1.0, v / 100.0))
    filled = round(pct * 200, 1)
    return (
        '<svg class="score-bar overall" viewBox="0 0 200 10" preserveAspectRatio="none" aria-hidden="true">'
        '<defs><linearGradient id="overallGrad" x1="0%" y1="0%" x2="100%" y2="0%">'
        '<stop offset="0%" stop-color="#a78bfa"/><stop offset="100%" stop-color="#22d3ee"/>'
        "</linearGradient></defs>"
        '<rect class="score-bar-track" x="0" y="0" width="200" height="10" rx="5"/>'
        f'<rect x="0" y="0" width="{filled}" height="10" rx="5" fill="url(#overallGrad)"/>'
        "</svg>"
    )


def build_answer(data: dict) -> str:
    answer = esc(data.get("the_answer", ""))
    scores = data.get("scores", {}) or {}
    stack = scores.get("stack")
    workflow = scores.get("workflow_integration")
    overall = scores.get("overall")
    interp = esc(scores.get("interpretation", ""))

    score_row_parts = []
    if stack is not None:
        score_row_parts.append(
            '<div class="score-cell">'
            '<div class="label">AI stack</div>'
            f'<div class="value">{esc(stack)}<span class="value-suffix">/10</span></div>'
            f"{_score_bar_svg(stack, 10, accent='purple')}"
            "</div>"
        )
    if workflow is not None:
        score_row_parts.append(
            '<div class="score-cell">'
            '<div class="label">Workflow integration</div>'
            f'<div class="value">{esc(workflow)}<span class="value-suffix">/10</span></div>'
            f"{_score_bar_svg(workflow, 10, accent='cyan')}"
            "</div>"
        )
    if overall is not None:
        score_row_parts.append(
            '<div class="score-cell overall">'
            '<div class="label">Overall readiness</div>'
            f'<div class="value">{esc(overall)}<span class="value-suffix">/100</span></div>'
            f"{_score_bar_overall_svg(overall)}"
            f'<div class="interpretation">{interp}</div>'
            "</div>"
        )

    score_row = ""
    if score_row_parts:
        score_row = '<div class="score-row">' + "".join(score_row_parts) + "</div>"

    return (
        '<section class="answer-card reveal delay-1">'
        '<div class="label">The answer</div>'
        f'<blockquote class="answer">{answer}</blockquote>'
        f"{score_row}"
        "</section>"
    )


def build_hero_cta(data: dict) -> str:
    company = data.get("company_name", "")
    return cta_row_html(company, extra_class="reveal delay-2")


def build_wins(data: dict) -> str:
    wins = data.get("wins_top_3", []) or []
    if not wins:
        return ""
    cards = []
    for w in wins[:3]:
        rank = esc(w.get("rank", ""))
        head = esc(w.get("headline", ""))
        one_liner = esc(w.get("one_liner", ""))
        ai_mech = esc(w.get("ai_mechanism", ""))
        impact = esc(w.get("impact_metric", ""))
        cards.append(
            '<div class="win">'
            f'<div class="rank">{rank}</div>'
            f'<h3>{head}</h3>'
            f'<p class="one-liner">{one_liner}</p>'
            f'<p class="ai-mechanism">{ai_mech}</p>'
            f'<span class="impact">{impact}</span>'
            "</div>"
        )
    return (
        '<section class="reveal">'
        '<h2 class="section">The 3 wins</h2>'
        f'<div class="wins-grid">{"".join(cards)}</div>'
        "</section>"
    )


def build_mid_cta(data: dict) -> str:
    company = data.get("company_name", "")
    return (
        '<div class="banner-cta reveal">'
        '<div class="copy">Ready to ship these three? We help companies move from problem to deployed automation in days, not quarters.</div>'
        f"{cta_row_html(company)}"
        "</div>"
    )


def build_why_now(data: dict) -> str:
    why_now = data.get("why_now", "")
    if not why_now:
        return ""
    # Render as paragraph(s). Split on double-newline to support multi-paragraph.
    paragraphs = [p.strip() for p in why_now.split("\n\n") if p.strip()]
    para_html = "".join(f"<p>{esc(p)}</p>" for p in paragraphs)
    split_box = (
        '<div class="split">'
        '<div class="split-item">Use AI to do the same things slightly cheaper.</div>'
        '<div class="split-item">Use AI to do things that were impossible last quarter.</div>'
        "</div>"
    )
    return (
        '<section class="reveal">'
        '<h2 class="section">Why this matters now</h2>'
        '<div class="why-now">'
        f"{para_html if para_html else ''}"
        f"{split_box}"
        "</div>"
        "</section>"
    )


def build_vocabulary_primer(data: dict) -> str:
    """v0.8 EM-52: vocabulary primer between why-now and losing-time.

    6-term plain-English glossary using Tyler's cookbook/recipe analogy.
    Renders as 6 term-definition rows + a kicker line.
    """
    vocab = data.get("vocabulary_primer", {}) or {}
    if not vocab:
        return ""
    # Ordered terms — the cookbook progression
    term_order = [
        ("knowledge_base", "Knowledge base"),
        ("plugin", "Plugin"),
        ("skill", "Skill"),
        ("agent", "Agent"),
        ("scheduled_task", "Scheduled task"),
    ]
    rows = []
    for key, label in term_order:
        definition = vocab.get(key, "")
        if not definition:
            continue
        rows.append(
            '<div class="vocabulary-row">'
            f'<div class="vocabulary-term">{esc(label)}</div>'
            f'<div class="vocabulary-definition">{esc(definition)}</div>'
            "</div>"
        )
    kicker = vocab.get("kicker", "")
    kicker_html = f'<p class="vocabulary-kicker">{esc(kicker)}</p>' if kicker else ""
    return (
        '<section class="reveal">'
        '<h2 class="section">A quick vocabulary</h2>'
        '<p class="vocabulary-subtitle">The terms used across the audit, in plain English.</p>'
        '<div class="vocabulary-primer">'
        f"{''.join(rows)}"
        "</div>"
        f"{kicker_html}"
        "</section>"
    )


def _parse_hours_per_week(time_cost: str) -> float:
    """Extract a leading number from a time_cost string like '2.5 hrs/week'.

    Returns 0.0 if no number can be parsed. Forgiving — accepts integers, decimals,
    and ranges like '1-2 hrs/week' (averages the range).
    """
    if not time_cost:
        return 0.0
    nums = re.findall(r"\d+\.?\d*", str(time_cost))
    if not nums:
        return 0.0
    try:
        if len(nums) >= 2 and "-" in str(time_cost):
            return (float(nums[0]) + float(nums[1])) / 2
        return float(nums[0])
    except ValueError:
        return 0.0


def _hour_bar_svg(hours: float, max_hours: float) -> str:
    """Inline SVG horizontal bar for a pain row's time cost. Width is relative."""
    if max_hours <= 0:
        return ""
    pct = max(0.0, min(1.0, hours / max_hours))
    filled = round(pct * 100, 1)  # viewBox width 100
    return (
        '<svg class="hour-bar" viewBox="0 0 100 6" preserveAspectRatio="none" aria-hidden="true">'
        '<rect class="hour-bar-track" x="0" y="0" width="100" height="6" rx="3"/>'
        f'<rect class="hour-bar-fill" x="0" y="0" width="{filled}" height="6" rx="3"/>'
        "</svg>"
    )


def build_losing_time(data: dict) -> str:
    items = data.get("losing_time", []) or []
    if not items:
        return ""
    parsed_hours = [_parse_hours_per_week(it.get("time_cost", "")) for it in items]
    max_hours = max(parsed_hours) if parsed_hours else 0.0
    rows = []
    for it, hours in zip(items, parsed_hours):
        head = esc(it.get("headline", ""))
        detail = esc(it.get("one_liner", ""))
        time_cost = esc(it.get("time_cost", ""))
        ai_fix = esc(it.get("ai_fix", ""))
        bar = _hour_bar_svg(hours, max_hours) if max_hours > 0 else ""
        rows.append(
            '<div class="pain-row">'
            f'<p class="pain-headline">{head}</p>'
            f'<p class="pain-detail">{detail}</p>'
            '<div class="pain-meta">'
            f'<span class="time-cost">{time_cost}</span>'
            f"{bar}"
            f'<span class="ai-fix">{ai_fix}</span>'
            "</div>"
            "</div>"
        )
    return (
        '<section class="reveal">'
        '<h2 class="section">Where you\'re losing time today</h2>'
        f'<div class="pain-list">{"".join(rows)}</div>'
        "</section>"
    )


def _gantt_track_svg(items: list[dict]) -> str:
    """Inline SVG horizontal Gantt-style track. 4 segments, equal-width.

    Uses a 1000-unit viewBox width (so each segment is 250 units wide) and a
    50-unit height. Tick labels sit above each segment with the window text;
    the colored bar sits in the middle; segment titles sit below.
    """
    if not items:
        return ""
    n = min(len(items), 4)
    seg_w = 1000 / n
    pad = 6  # internal padding between segments to show separation

    segments = []
    ticks = []
    titles = []
    for i, it in enumerate(items[:n]):
        accent = it.get("accent", "cyan")
        if accent not in ALLOWED_ROADMAP_ACCENTS:
            accent = "cyan"
        color = ROADMAP_ACCENT_HEX.get(accent, ROADMAP_ACCENT_HEX["cyan"])
        x = i * seg_w
        seg_x = x + pad
        seg_width = seg_w - 2 * pad
        cx = x + seg_w / 2
        window = esc(it.get("window", ""))
        title = esc(it.get("title", ""))
        # Colored segment
        segments.append(
            f'<rect x="{seg_x:.1f}" y="22" width="{seg_width:.1f}" height="14" '
            f'rx="7" fill="{color}" class="gantt-segment {accent}"/>'
        )
        # Tick label above (the window: "Now → 3 months")
        ticks.append(
            f'<text x="{cx:.1f}" y="14" class="gantt-tick" text-anchor="middle">{window}</text>'
        )
        # Title label below segment
        titles.append(
            f'<text x="{cx:.1f}" y="50" class="gantt-title-label" text-anchor="middle">{title}</text>'
        )
    # Chevron-like progression markers between segments (small triangles)
    chevrons = []
    for i in range(1, n):
        cx = i * seg_w
        chevrons.append(
            f'<path d="M {cx - 3:.1f} 25 L {cx + 3:.1f} 29 L {cx - 3:.1f} 33 Z" '
            'class="gantt-chevron" fill="rgba(230,232,236,0.45)"/>'
        )
    return (
        '<svg class="gantt-track" viewBox="0 0 1000 60" preserveAspectRatio="none" aria-hidden="true">'
        + "".join(segments)
        + "".join(chevrons)
        + "".join(ticks)
        + "".join(titles)
        + "</svg>"
    )


def build_roadmap(data: dict) -> str:
    items = data.get("roadmap", []) or []
    if not items:
        return ""
    steps = []
    for it in items[:4]:
        accent = it.get("accent", "cyan")
        if accent not in ALLOWED_ROADMAP_ACCENTS:
            accent = "cyan"
        window = esc(it.get("window", ""))
        title = esc(it.get("title", ""))
        body = esc(it.get("body", ""))
        steps.append(
            f'<div class="roadmap-step {accent}">'
            f'<div class="window">{window}</div>'
            f'<h3>{title}</h3>'
            f'<p class="body">{body}</p>'
            "</div>"
        )
    gantt = _gantt_track_svg(items[:4])
    return (
        '<section class="reveal">'
        '<h2 class="section">The path from here to AI-native</h2>'
        f'<div class="roadmap-gantt">{gantt}</div>'
        f'<div class="roadmap-grid">{"".join(steps)}</div>'
        '<p class="roadmap-footnote">This is the Prescyent ladder. You don\'t climb it all at once — most companies start with the wiki, add three skills, and feel the difference inside two weeks.</p>'
        "</section>"
    )


def build_lanes(data: dict) -> str:
    lanes = data.get("lanes", []) or []
    if not lanes:
        return ""
    company = data.get("company_name", "")
    cards = []
    for i, lane in enumerate(lanes[:3]):
        name = esc(lane.get("name", ""))
        head = esc(lane.get("headline", ""))
        body = esc(lane.get("body", ""))
        cta_label = esc(lane.get("cta_label", "Talk to Tyler"))
        # Featured = middle lane (Light-touch), styled differently
        featured = "featured" if i == 1 else ""
        # DIY lane links to /kb-build doc; others to mailto
        if name.lower() == "diy":
            cta_href = "https://github.com/Prescyent/prescyent-plugin#kb-build"
            cta_html = f'<a class="cta ghost lane-cta" href="{cta_href}" target="_blank" rel="noopener">{cta_label} <span class="arrow">↗</span></a>'
        else:
            cta_html = f'<a class="cta primary lane-cta" href="{mailto_url(company)}">{cta_label} <span class="arrow">→</span></a>'
        cards.append(
            f'<div class="lane {featured}">'
            f'<div class="lane-name">{name}</div>'
            f'<h3>{head}</h3>'
            f'<p class="lane-body">{body}</p>'
            f'{cta_html}'
            "</div>"
        )
    return (
        '<section class="reveal">'
        '<h2 class="section">How to climb the ladder</h2>'
        f'<div class="lanes-grid">{"".join(cards)}</div>'
        "</section>"
    )


def _coverage_table_html(coverage: list[dict]) -> str:
    if not coverage:
        return ""
    rows = []
    for c in coverage:
        rows.append(
            "<tr>"
            f"<td>{esc(c.get('category',''))}</td>"
            f"<td>{esc(c.get('platforms',''))}</td>"
            f"<td>{esc(c.get('records_analyzed',''))}</td>"
            f"<td>{esc(c.get('confidence',''))}</td>"
            "</tr>"
        )
    return (
        "<h3>Coverage</h3>"
        "<table>"
        "<thead><tr><th>Category</th><th>Platforms</th><th>Records analyzed</th><th>Confidence</th></tr></thead>"
        f"<tbody>{''.join(rows)}</tbody>"
        "</table>"
    )


def _dimensions_html(dimensions: list[dict]) -> str:
    if not dimensions:
        return ""
    blocks = []
    for d in dimensions:
        title = esc(d.get("title", ""))
        score = d.get("score", "")
        score_html = f'<span class="score-pill">{esc(score)}/10</span>' if score != "" and score is not None else ""
        finding_blocks = []
        for f in d.get("findings", []) or []:
            sev_raw = (f.get("severity") or "medium").lower()
            sev_class = SEVERITY_CLASS.get(sev_raw, "tag-medium")
            sev_label = sev_raw.capitalize()
            head = esc(f.get("headline", ""))
            rec = esc(f.get("recommendation", ""))
            rec_block = f'<span class="recommendation"><strong>Fix:</strong> {rec}</span>' if rec else ""
            finding_blocks.append(
                '<div class="finding">'
                f'<span class="tag {sev_class}">{esc(sev_label)}</span>'
                f'<strong>{head}</strong>'
                f"{rec_block}"
                "</div>"
            )
        blocks.append(
            '<div class="dimension">'
            '<div class="dimension-header">'
            f'<h4>{title}</h4>'
            f"{score_html}"
            "</div>"
            f"{''.join(finding_blocks)}"
            "</div>"
        )
    return "<h3>Per-dimension findings</h3>" + "".join(blocks)


def _conflicts_html(conflicts: list[dict]) -> str:
    if not conflicts:
        return ""
    items = []
    for c in conflicts:
        topic = esc(c.get("topic", ""))
        summary = esc(c.get("summary", ""))
        rec = esc(c.get("recommendation", ""))
        decision = esc(c.get("needed_decision", ""))
        items.append(
            "<li>"
            f"<strong>{topic}.</strong> {summary} "
            f"<em>Recommendation:</em> {rec} "
            f"<em>Decision needed:</em> {decision}"
            "</li>"
        )
    return f"<h3>Conflicts between sources</h3><ul>{''.join(items)}</ul>"


def _gaps_html(gaps: list[dict]) -> str:
    if not gaps:
        return ""
    items = []
    for g in gaps:
        gap = esc(g.get("gap", ""))
        impact = esc(g.get("impact", ""))
        fix = esc(g.get("fix", ""))
        items.append(f"<li><strong>{gap}.</strong> {impact} <em>Fix:</em> {fix}</li>")
    return f"<h3>Coverage gaps</h3><ul>{''.join(items)}</ul>"


def _open_questions_html(qs: list[dict]) -> str:
    if not qs:
        return ""
    items = []
    for q in qs:
        question = esc(q.get("question", ""))
        rec = esc(q.get("recommended_answer", ""))
        decision = esc(q.get("needed_decision", ""))
        items.append(
            "<li>"
            f"<strong>{question}</strong><br>"
            f"<em>Recommended answer:</em> {rec}<br>"
            f"<em>Decision needed:</em> {decision}"
            "</li>"
        )
    return f"<h3>Open questions</h3><ul>{''.join(items)}</ul>"


def build_appendix(data: dict) -> str:
    coverage = data.get("coverage", []) or []
    dimensions = data.get("dimensions", []) or []
    conflicts = data.get("conflicts", []) or []
    gaps = data.get("coverage_gaps", []) or []
    qs = data.get("open_questions", []) or []
    if not any([coverage, dimensions, conflicts, gaps, qs]):
        return ""
    body = (
        _coverage_table_html(coverage)
        + _dimensions_html(dimensions)
        + _conflicts_html(conflicts)
        + _gaps_html(gaps)
        + _open_questions_html(qs)
    )
    # v0.6 (EM-32): appendix is no longer a collapsed <details> element.
    # It renders as a normal <section> below the footer signoff so deep
    # readers see the data without hunting for a click affordance.
    return (
        '<section class="appendix reveal">'
        '<h2 class="section appendix-title">The detail</h2>'
        '<p class="appendix-subtitle">Per-dimension findings, conflicts, gaps, and open questions.</p>'
        f'<div class="appendix-body">{body}</div>'
        "</section>"
    )


def build_footer(data: dict) -> str:
    company = data.get("company_name", "")
    return (
        '<section id="signoff">'
        '<div class="reveal"><div class="eyebrow">Why this audit?</div></div>'
        '<h2 class="reveal delay-1">Two reasons.</h2>'
        '<p class="close-lede reveal delay-2">'
        f"<strong>First</strong>, this is the picture we'd want before deciding what to do with AI at {esc(company)}. The roadmap above is the bigger move — building the persistent context layer that compounds across every Claude session, every employee, every quarter."
        "</p>"
        '<p class="close-lede reveal delay-3">'
        "<strong>Second</strong>, as a practical example. We built this audit in about five minutes using the same tools we'd help your team turn into a system. The medium is the message."
        "</p>"
        f'{cta_row_html(company, extra_class="reveal delay-4")}'
        '<div class="sign-off reveal delay-5">'
        '<div class="sig-name">Tyler Massey</div>'
        f'<div class="sig-sub">Prescyent · <a href="https://prescyent.ai" target="_blank" rel="noopener">prescyent.ai</a> · {TYLER_EMAIL} · Generated v{PLUGIN_VERSION}</div>'
        "</div>"
        "</section>"
    )


# ---------- assemble ----------


def render(data: dict, template: str) -> str:
    company = data.get("company_name", "Company")
    og_desc = data.get("the_answer", "AI readiness audit by Prescyent.")[:300]

    out = template
    out = out.replace("{{COMPANY_NAME}}", esc(company))
    out = out.replace("{{OG_DESCRIPTION}}", esc(og_desc))
    out = out.replace("{{HERO_HTML}}", build_hero(data))
    out = out.replace("{{ANSWER_HTML}}", build_answer(data))
    out = out.replace("{{HERO_CTA_HTML}}", build_hero_cta(data))
    out = out.replace("{{WINS_HTML}}", build_wins(data))
    out = out.replace("{{MID_CTA_HTML}}", build_mid_cta(data))
    out = out.replace("{{WHY_NOW_HTML}}", build_why_now(data))
    out = out.replace("{{VOCABULARY_HTML}}", build_vocabulary_primer(data))
    out = out.replace("{{LOSING_TIME_HTML}}", build_losing_time(data))
    out = out.replace("{{ROADMAP_HTML}}", build_roadmap(data))
    out = out.replace("{{LANES_HTML}}", build_lanes(data))
    out = out.replace("{{APPENDIX_HTML}}", build_appendix(data))
    out = out.replace("{{FOOTER_HTML}}", build_footer(data))
    return out


def load_template(script_dir: Path) -> str:
    template_path = script_dir.parent / "references" / "report-template.html"
    if not template_path.exists():
        sys.exit(f"error: template not found at {template_path}")
    return template_path.read_text(encoding="utf-8")


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to synthesizer JSON")
    parser.add_argument("--output", required=True, help="Output HTML path")
    args = parser.parse_args()

    input_path = Path(os.path.expanduser(args.input)).resolve()
    output_path = Path(os.path.expanduser(args.output)).resolve()
    script_dir = Path(__file__).resolve().parent

    if not input_path.exists():
        sys.exit(f"error: input JSON not found: {input_path}")

    raw = input_path.read_text(encoding="utf-8")
    try:
        data = json.loads(raw)
    except json.JSONDecodeError as exc:
        sys.exit(f"error: input is not valid JSON: {exc}")

    template = load_template(script_dir)
    rendered = render(data, template)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"rendered → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
