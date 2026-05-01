#!/usr/bin/env python3
"""
render-report.py — convert a synthesized audit markdown into the Prescyent dark-mode HTML report.

Input:  markdown file produced by the master audit skill's Phase 6 synthesis.
Output: self-contained HTML file using Inter + the Prescyent dark-mode design system.

Usage:
  python3 render-report.py \
    --input  ~/prescyent-audits/2026-04-16-acme.md \
    --output ~/prescyent-audits/2026-04-16-acme.html \
    --company "Acme Inc"

No external dependencies — pure stdlib. The markdown parser is intentionally
minimal: the synthesis phase writes a predictable shape, and the template
slots are simple string substitutions rather than a full markdown-to-HTML
pipeline. If the synthesis phase deviates from the shape, the script falls
back to wrapping raw markdown in <pre> blocks rather than crashing.
"""

from __future__ import annotations

import argparse
import html
import os
import re
import sys
from datetime import date
from pathlib import Path

PLUGIN_VERSION = "0.4.0"

SEVERITY_CLASS = {
    "critical": "tag-critical",
    "high": "tag-high",
    "medium": "tag-medium",
    "low": "tag-low",
}


def load_template(script_dir: Path) -> str:
    template_path = script_dir.parent / "references" / "report-template.html"
    if not template_path.exists():
        sys.exit(f"error: template not found at {template_path}")
    return template_path.read_text(encoding="utf-8")


def parse_markdown(md: str) -> dict:
    """Parse the synthesized audit markdown into structured fields.

    Expected shape (v0.4 Minto pyramid — loose, we tolerate deviation):

        # {Company}
        **AI Readiness Audit · YYYY-MM-DD · {Standard|Deep}**

        ## The answer
        > {Minto Level 1 sentence}
        **Overall AI Readiness Score: NN** · {one-line interpretation}

        ## Top 3 moves
        1. **{headline}** — ...
        2. **{headline}** — ...
        3. **{headline}** — ...

        ## Why this matters now
        {boil-the-ocean framing paragraphs}

        ## Where you're losing time today
        - **{blind spot}** — ...

        ## The path forward
        {KB Builder upsell paragraphs}

        ## The detail
        ### Coverage
        | ... |
        ### GTM & Systems Readiness — N/10
        - ...
        ### Knowledge & Document Readiness — N/10
        - ...
        ### Communications Readiness — N/10
        - ...
        ### AI Stack Readiness — N/10
        - ...
        ### Conflicts Between Sources
        ### Coverage Gaps
        ### Open Questions

        ## Recommended next steps
        1. ...

    The parser also tolerates the legacy v0.3 shape (Executive Summary +
    per-dimension H2s + Top 3 Opportunities at the bottom) — older reports
    still render correctly.
    """
    data: dict = {
        "audit_date": date.today().isoformat(),
        "depth": "Standard",
        "overall_score": "—",
        "overall_interpretation": "",
        "the_answer_html": "",
        "top_3_moves_html": "",
        "why_now_html": "",
        "where_losing_time_html": "",
        "path_forward_html": "",
        "executive_bullets_html": "",  # legacy fallback
        "sections": [],
        "opportunities_html": "",  # legacy fallback
        "next_steps_html": "",
        "coverage_gaps_html": "",
        "open_questions_html": "",
        "conflicts_html": "",
        "coverage_table_html": "",
        "scorecards": [],
    }

    # Overall score
    m = re.search(r"Overall AI Readiness Score(?:[*:\s]+)(\d{1,3})", md, re.IGNORECASE)
    if m:
        data["overall_score"] = m.group(1)
        data["overall_interpretation"] = interpret_score(int(m.group(1)))

    # Date
    m = re.search(r"(?:^Date:\s*|·\s*)(\d{4}-\d{2}-\d{2})", md, re.MULTILINE)
    if m:
        data["audit_date"] = m.group(1)

    # Depth
    m = re.search(r"·\s*(Standard|Deep)\s*(?:scope|·|$)", md, re.IGNORECASE | re.MULTILINE)
    if m:
        data["depth"] = m.group(1).capitalize()

    # H2 sections (Minto-level)
    h2_blocks = split_by_heading(md, "##")

    for title, body in h2_blocks.items():
        lower = title.lower().strip()
        if lower.startswith("the answer"):
            data["the_answer_html"] = render_blockquote_or_paragraph(body)
        elif lower.startswith("top 3 moves") or lower.startswith("top 3 ai opportunities"):
            data["top_3_moves_html"] = render_opportunities(body)
            # legacy alias
            if not data["opportunities_html"]:
                data["opportunities_html"] = data["top_3_moves_html"]
        elif lower.startswith("why this matters now"):
            data["why_now_html"] = render_markdown_block(body)
        elif lower.startswith("where you're losing time") or lower.startswith("where you are losing time"):
            data["where_losing_time_html"] = render_markdown_block(body)
        elif lower.startswith("the path forward") or lower.startswith("path forward"):
            data["path_forward_html"] = render_markdown_block(body)
        elif lower.startswith("the detail") or lower.startswith("detail"):
            # The Detail section contains H3 sub-sections — parse them
            h3_blocks = split_by_heading(body, "###")
            for h3_title, h3_body in h3_blocks.items():
                h3_lower = h3_title.lower().strip()
                if h3_lower.startswith("coverage") and "gaps" not in h3_lower:
                    data["coverage_table_html"] = render_markdown_block(h3_body)
                elif "conflicts" in h3_lower:
                    data["conflicts_html"] = render_markdown_block(h3_body)
                elif "coverage gaps" in h3_lower:
                    data["coverage_gaps_html"] = render_markdown_block(h3_body)
                elif "open questions" in h3_lower:
                    data["open_questions_html"] = render_markdown_block(h3_body)
                elif "readiness" in h3_lower:
                    score = extract_section_score(h3_title)
                    data["sections"].append({
                        "title": strip_score(h3_title),
                        "score": score,
                        "findings_html": render_findings(h3_body),
                    })
                    data["scorecards"].append({
                        "label": short_label(h3_title),
                        "value": score or "—",
                        "meta": "/10",
                    })
        elif lower.startswith("recommended next steps") or "next steps" in lower:
            data["next_steps_html"] = render_markdown_block(body)
        # Legacy v0.3 shape support
        elif "executive summary" in lower:
            data["executive_bullets_html"] = render_bullets(body)
            if not data["the_answer_html"]:
                data["the_answer_html"] = data["executive_bullets_html"]
        elif "opportunities" in lower and not data["top_3_moves_html"]:
            data["opportunities_html"] = render_opportunities(body)
            data["top_3_moves_html"] = data["opportunities_html"]
        elif "coverage gaps" in lower and not data["coverage_gaps_html"]:
            data["coverage_gaps_html"] = render_markdown_block(body)
        elif "open questions" in lower and not data["open_questions_html"]:
            data["open_questions_html"] = render_markdown_block(body)
        elif "readiness" in lower:
            # Legacy v0.3 — H2 readiness sections (we now expect them under H3 of "## The detail")
            score = extract_section_score(title)
            data["sections"].append({
                "title": strip_score(title),
                "score": score,
                "findings_html": render_findings(body),
            })
            data["scorecards"].append({
                "label": short_label(title),
                "value": score or "—",
                "meta": "/10",
            })

    return data


def render_blockquote_or_paragraph(body: str) -> str:
    """Render the 'The answer' section. Prefer the blockquote content; fall back to first paragraph."""
    quote_lines = []
    for line in body.splitlines():
        stripped = line.strip()
        if stripped.startswith(">"):
            quote_lines.append(stripped.lstrip(">").strip())
        elif quote_lines:
            break
    if quote_lines:
        text = " ".join(quote_lines)
        return f'<blockquote class="answer">{inline_md(text)}</blockquote>'
    # Fall back to the rest of the body
    return render_markdown_block(body)


def interpret_score(score: int) -> str:
    if score >= 80:
        return "Ready for advanced agentic workflows."
    if score >= 60:
        return "Ready for Phase 1 plugins — automate workflows as-is."
    if score >= 40:
        return "Foundation work first. Subtract before adding AI."
    if score >= 20:
        return "AI is premature. Fix data hygiene + process first."
    return "Do not deploy AI yet. Stabilize the company first."


def split_by_heading(md: str, marker: str) -> dict[str, str]:
    """Split markdown into {heading: body} pairs for the given heading level."""
    pattern = re.compile(rf"^{re.escape(marker)}\s+(.+?)$", re.MULTILINE)
    blocks: dict[str, str] = {}
    matches = list(pattern.finditer(md))
    for i, m in enumerate(matches):
        title = m.group(1).strip()
        start = m.end()
        end = matches[i + 1].start() if i + 1 < len(matches) else len(md)
        blocks[title] = md[start:end].strip()
    return blocks


def extract_section_score(title: str) -> str:
    m = re.search(r"(\d{1,2})\s*/\s*10", title)
    return m.group(1) if m else ""


def strip_score(title: str) -> str:
    return re.sub(r"\s*—\s*\d+\s*/\s*10\s*$", "", title).strip()


def short_label(title: str) -> str:
    t = strip_score(title)
    for suffix in (" Readiness", " & Document Readiness", " Readiness"):
        if t.endswith(suffix):
            t = t[: -len(suffix)]
            break
    return t.strip()


def render_bullets(body: str) -> str:
    """Render a numbered or bulleted list as <ol><li>...</li></ol>."""
    items = []
    for line in body.splitlines():
        line = line.strip()
        if re.match(r"^\d+\.\s+", line):
            items.append(re.sub(r"^\d+\.\s+", "", line))
        elif line.startswith(("- ", "* ")):
            items.append(line[2:])
    if not items:
        return f"<p>{html.escape(body.strip())}</p>"
    return "<ol>" + "".join(f"<li>{inline_md(i)}</li>" for i in items) + "</ol>"


def render_opportunities(body: str) -> str:
    """Render top-3 opportunities as cards."""
    cards = []
    items = re.split(r"^\s*(?:\d+\.)\s+", body, flags=re.MULTILINE)
    items = [i.strip() for i in items if i.strip()]
    for rank, item in enumerate(items[:3], start=1):
        first_line, _, rest = item.partition("\n")
        cards.append(
            f'<div class="opp"><div class="rank">{rank}</div>'
            f'<h3>{inline_md(first_line)}</h3>'
            f'<p>{inline_md(rest).replace(chr(10), "<br>")}</p></div>'
        )
    return "".join(cards) if cards else f"<p>{html.escape(body)}</p>"


def render_findings(body: str) -> str:
    """Render a findings block. Expects lines like:
       - [High] Headline — detail. **Recommendation:** fix.
    """
    out = []
    for line in body.splitlines():
        line = line.strip()
        if not line or not line.startswith(("- ", "* ")):
            continue
        line = line[2:]
        sev_match = re.match(r"\[(Critical|High|Medium|Low)\]\s*", line, re.IGNORECASE)
        sev = "medium"
        if sev_match:
            sev = sev_match.group(1).lower()
            line = line[sev_match.end():]
        head, _, rest = line.partition(" — ")
        rec_match = re.search(r"\*\*Recommendation:\*\*\s*(.+)", rest)
        rec_html = f'<div class="rec">{inline_md(rec_match.group(1))}</div>' if rec_match else ""
        detail = rest if not rec_match else rest[:rec_match.start()]
        out.append(
            f'<div class="finding">'
            f'<div class="tag {SEVERITY_CLASS.get(sev, "tag-medium")}">{sev}</div>'
            f'<div class="body"><h3>{inline_md(head)}</h3>'
            f'<p>{inline_md(detail)}</p>{rec_html}</div>'
            f"</div>"
        )
    if not out:
        return render_markdown_block(body)
    return "".join(out)


def render_markdown_block(body: str) -> str:
    """Light-touch renderer: paragraphs + bullet lists."""
    if not body.strip():
        return ""
    parts = []
    buf = []
    in_list = False
    for line in body.splitlines():
        s = line.strip()
        if s.startswith(("- ", "* ")):
            if not in_list:
                if buf:
                    parts.append(f"<p>{inline_md(' '.join(buf))}</p>")
                    buf = []
                parts.append("<ul>")
                in_list = True
            parts.append(f"<li>{inline_md(s[2:])}</li>")
        elif not s:
            if in_list:
                parts.append("</ul>")
                in_list = False
            if buf:
                parts.append(f"<p>{inline_md(' '.join(buf))}</p>")
                buf = []
        else:
            if in_list:
                parts.append("</ul>")
                in_list = False
            buf.append(s)
    if buf:
        parts.append(f"<p>{inline_md(' '.join(buf))}</p>")
    if in_list:
        parts.append("</ul>")
    return "".join(parts)


_SAFE_LINK_SCHEMES = ("http://", "https://", "mailto:", "#", "/")
_SCHEME_RE = re.compile(r"^[a-z][a-z0-9+.\-]*:", re.IGNORECASE)


def _safe_link_replace(match: re.Match) -> str:
    """Render a markdown link as HTML, dropping unsafe URL schemes.

    Only `http://`, `https://`, `mailto:`, and scheme-less (relative or
    fragment) hrefs render as anchors. Everything else (notably
    `javascript:` and `data:`) renders as plain link text — the URL is
    discarded. Defense-in-depth against attacker-controlled markdown
    surviving the audit-subagent → synthesis chain.
    """
    text, url = match.group(1), match.group(2).strip()
    url_lower = url.lower()
    if url_lower.startswith(_SAFE_LINK_SCHEMES) or not _SCHEME_RE.match(url_lower):
        return f'<a href="{url}">{text}</a>'
    return text


def inline_md(text: str) -> str:
    """Inline markdown → HTML (bold, italic, code, links). Escapes HTML first."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    out = re.sub(r"\[([^\]]+)\]\(([^)]+)\)", _safe_link_replace, out)
    return out


def render_scorecards(cards: list[dict]) -> str:
    return "".join(
        f'<div class="score-card">'
        f'<div class="label">{html.escape(c["label"])}</div>'
        f'<div class="value">{html.escape(str(c["value"]))}</div>'
        f'<div class="meta">{html.escape(c["meta"])}</div>'
        f"</div>"
        for c in cards
    )


def render_sections(sections: list[dict]) -> str:
    """Render per-dimension findings sections — landed under '## The detail' as H3 sub-sections."""
    return "".join(
        f'<section class="detail-section reveal">'
        f'<h3>{html.escape(s["title"])} <span class="score-badge">{html.escape(s["score"] or "—")}/10</span></h3>'
        f'<div class="card">{s["findings_html"]}</div>'
        f"</section>"
        for s in sections
    )


def build_html(template: str, company: str, data: dict) -> str:
    scorecards_html = render_scorecards(data["scorecards"])
    sections_html = render_sections(data["sections"])

    # Extract a one-line lead — prefer The Answer's blockquote text, fall back to first executive bullet
    lead = "An AI readiness plan built from your actual data."
    if data.get("the_answer_html"):
        m = re.search(r"<blockquote[^>]*>(.+?)</blockquote>", data["the_answer_html"], re.DOTALL)
        if m:
            lead = m.group(1).strip()
    if lead == "An AI readiness plan built from your actual data." and data.get("executive_bullets_html"):
        m = re.search(r"<li>(.+?)</li>", data["executive_bullets_html"])
        if m:
            lead = m.group(1)

    # URL-encode the company name for the mailto subject
    import urllib.parse
    deck_topic = urllib.parse.quote(f"{company} discovery audit follow-up")

    # Use simple token substitution (not Mustache — avoid dependencies)
    out = template
    out = out.replace("{{COMPANY_NAME}}", html.escape(company))
    out = out.replace("{{AUDIT_DATE}}", html.escape(data["audit_date"]))
    out = out.replace("{{DEPTH}}", html.escape(data.get("depth", "Standard")))
    out = out.replace("{{OVERALL_SCORE}}", html.escape(str(data["overall_score"])))
    out = out.replace("{{OVERALL_INTERPRETATION}}", html.escape(data["overall_interpretation"]))
    out = out.replace("{{EXECUTIVE_SUMMARY_LEAD}}", lead)
    out = out.replace("{{THE_ANSWER}}", data.get("the_answer_html") or data.get("executive_bullets_html") or "")
    out = out.replace("{{TOP_3_MOVES}}", data.get("top_3_moves_html") or data.get("opportunities_html") or "")
    out = out.replace("{{WHY_NOW}}", data.get("why_now_html", ""))
    out = out.replace("{{WHERE_LOSING_TIME}}", data.get("where_losing_time_html", ""))
    out = out.replace("{{PATH_FORWARD}}", data.get("path_forward_html", ""))
    out = out.replace("{{COVERAGE_TABLE}}", data.get("coverage_table_html", ""))
    out = out.replace("{{CONFLICTS}}", data.get("conflicts_html", ""))
    # Legacy aliases
    out = out.replace("{{EXECUTIVE_BULLETS}}", data["executive_bullets_html"])
    out = out.replace("{{OPPORTUNITIES}}", data["opportunities_html"] or data.get("top_3_moves_html", ""))
    out = out.replace("{{NEXT_STEPS}}", data["next_steps_html"])
    out = out.replace("{{PLUGIN_VERSION}}", PLUGIN_VERSION)
    out = out.replace("{{DECK_TOPIC_URL}}", deck_topic)

    # Sections: replace the Mustache-style SECTIONS block with rendered HTML.
    out = re.sub(
        r"\{\{#SECTIONS\}\}.*?\{\{/SECTIONS\}\}",
        sections_html.replace("\\", r"\\"),
        out,
        flags=re.DOTALL,
    )

    # Scorecards block
    out = re.sub(
        r"\{\{#SCORECARDS\}\}.*?\{\{/SCORECARDS\}\}",
        scorecards_html.replace("\\", r"\\"),
        out,
        flags=re.DOTALL,
    )

    # Why-now conditional
    _conditional_block(out_ref := [out], "WHY_NOW_BLOCK", data.get("why_now_html"))
    out = out_ref[0]

    # Where-losing-time conditional
    _conditional_block(out_ref := [out], "WHERE_LOSING_TIME_BLOCK", data.get("where_losing_time_html"))
    out = out_ref[0]

    # Path-forward conditional
    _conditional_block(out_ref := [out], "PATH_FORWARD_BLOCK", data.get("path_forward_html"))
    out = out_ref[0]

    # Conflicts conditional
    _conditional_block(out_ref := [out], "CONFLICTS_BLOCK", data.get("conflicts_html"))
    out = out_ref[0]

    # Coverage gaps conditional
    if data["coverage_gaps_html"]:
        out = re.sub(
            r"\{\{#COVERAGE_GAPS\}\}(.*?)\{\{/COVERAGE_GAPS\}\}",
            r"\1",
            out,
            flags=re.DOTALL,
        )
        out = out.replace("{{COVERAGE_GAPS_CONTENT}}", data["coverage_gaps_html"])
    else:
        out = re.sub(r"\{\{#COVERAGE_GAPS\}\}.*?\{\{/COVERAGE_GAPS\}\}", "", out, flags=re.DOTALL)

    # Open questions conditional
    if data["open_questions_html"]:
        out = re.sub(
            r"\{\{#OPEN_QUESTIONS\}\}(.*?)\{\{/OPEN_QUESTIONS\}\}",
            r"\1",
            out,
            flags=re.DOTALL,
        )
        out = out.replace("{{OPEN_QUESTIONS_CONTENT}}", data["open_questions_html"])
    else:
        out = re.sub(r"\{\{#OPEN_QUESTIONS\}\}.*?\{\{/OPEN_QUESTIONS\}\}", "", out, flags=re.DOTALL)

    return out


def _conditional_block(out_ref: list, marker: str, has_content) -> None:
    """In-place: keep the inner block if has_content is truthy, else strip it.

    Templates use {{#MARKER}}...{{/MARKER}} as the conditional fence.
    """
    pattern_keep = rf"\{{\{{#{marker}\}}\}}(.*?)\{{\{{/{marker}\}}\}}"
    pattern_drop = rf"\{{\{{#{marker}\}}\}}.*?\{{\{{/{marker}\}}\}}"
    if has_content:
        out_ref[0] = re.sub(pattern_keep, r"\1", out_ref[0], flags=re.DOTALL)
    else:
        out_ref[0] = re.sub(pattern_drop, "", out_ref[0], flags=re.DOTALL)


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--input", required=True, help="Path to synthesized audit markdown")
    parser.add_argument("--output", required=True, help="Output HTML path")
    parser.add_argument("--company", required=True, help="Company name for title + header")
    args = parser.parse_args()

    input_path = Path(os.path.expanduser(args.input)).resolve()
    output_path = Path(os.path.expanduser(args.output)).resolve()
    script_dir = Path(__file__).resolve().parent

    if not input_path.exists():
        sys.exit(f"error: input markdown not found: {input_path}")

    md = input_path.read_text(encoding="utf-8")
    template = load_template(script_dir)
    data = parse_markdown(md)
    rendered = build_html(template, args.company, data)

    output_path.parent.mkdir(parents=True, exist_ok=True)
    output_path.write_text(rendered, encoding="utf-8")
    print(f"rendered → {output_path}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
