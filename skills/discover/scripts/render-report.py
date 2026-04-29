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

PLUGIN_VERSION = "0.2.0"

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

    Expected shape (loose — we tolerate deviation):

        # {Company} — AI Discovery Audit
        Date: YYYY-MM-DD
        Audit scope: ...
        Overall AI Readiness Score: NN

        ## Executive Summary
        1. ...
        2. ...
        3. ...

        ## GTM & Systems Readiness — N/10
        ...

        ## Knowledge & Document Readiness — N/10
        ...

        ## Communications Readiness — N/10
        ...

        ## AI Stack Readiness — N/10
        ...

        ## Top 3 AI Opportunities
        1. ...
        2. ...
        3. ...

        ## Recommended Next Steps
        ...

        ## Coverage Gaps
        ...

        ## Open Questions
        ...
    """
    data: dict = {
        "audit_date": date.today().isoformat(),
        "overall_score": "—",
        "overall_interpretation": "",
        "executive_bullets_html": "",
        "sections": [],
        "opportunities_html": "",
        "next_steps_html": "",
        "coverage_gaps_html": "",
        "open_questions_html": "",
        "scorecards": [],
    }

    # Overall score
    m = re.search(r"Overall AI Readiness Score:\s*(\d{1,3})", md, re.IGNORECASE)
    if m:
        data["overall_score"] = m.group(1)
        data["overall_interpretation"] = interpret_score(int(m.group(1)))

    # Date
    m = re.search(r"^Date:\s*(\d{4}-\d{2}-\d{2})", md, re.MULTILINE)
    if m:
        data["audit_date"] = m.group(1)

    # Section bodies by H2
    h2_blocks = split_by_heading(md, "##")

    for title, body in h2_blocks.items():
        lower = title.lower()
        if "executive summary" in lower:
            data["executive_bullets_html"] = render_bullets(body)
        elif "opportunities" in lower:
            data["opportunities_html"] = render_opportunities(body)
        elif "next steps" in lower:
            data["next_steps_html"] = render_markdown_block(body)
        elif "coverage gaps" in lower:
            data["coverage_gaps_html"] = render_markdown_block(body)
        elif "open questions" in lower:
            data["open_questions_html"] = render_markdown_block(body)
        elif "readiness" in lower:
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


def inline_md(text: str) -> str:
    """Inline markdown → HTML (bold, italic, code, links). Escapes HTML first."""
    out = html.escape(text)
    out = re.sub(r"\*\*(.+?)\*\*", r"<strong>\1</strong>", out)
    out = re.sub(r"(?<!\*)\*(?!\*)(.+?)(?<!\*)\*(?!\*)", r"<em>\1</em>", out)
    out = re.sub(r"`(.+?)`", r"<code>\1</code>", out)
    out = re.sub(
        r"\[([^\]]+)\]\(([^)]+)\)",
        r'<a href="\2">\1</a>',
        out,
    )
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
    return "".join(
        f'<section class="reveal">'
        f'<h2>{html.escape(s["title"])} <span class="score-badge">{html.escape(s["score"] or "—")}/10</span></h2>'
        f'<div class="card">{s["findings_html"]}</div>'
        f"</section>"
        for s in sections
    )


def build_html(template: str, company: str, data: dict) -> str:
    scorecards_html = render_scorecards(data["scorecards"])
    sections_html = render_sections(data["sections"])

    # Extract executive summary lead from first bullet if present
    lead_match = re.search(r"<li>(.+?)</li>", data["executive_bullets_html"])
    lead = lead_match.group(1) if lead_match else "An AI readiness plan built from your actual data."

    # Use simple token substitution (not Mustache — avoid dependencies)
    out = template
    out = out.replace("{{COMPANY_NAME}}", html.escape(company))
    out = out.replace("{{AUDIT_DATE}}", html.escape(data["audit_date"]))
    out = out.replace("{{OVERALL_SCORE}}", html.escape(str(data["overall_score"])))
    out = out.replace("{{OVERALL_INTERPRETATION}}", html.escape(data["overall_interpretation"]))
    out = out.replace("{{EXECUTIVE_SUMMARY_LEAD}}", lead)
    out = out.replace("{{EXECUTIVE_BULLETS}}", data["executive_bullets_html"])
    out = out.replace("{{OPPORTUNITIES}}", data["opportunities_html"])
    out = out.replace("{{NEXT_STEPS}}", data["next_steps_html"])
    out = out.replace("{{PLUGIN_VERSION}}", PLUGIN_VERSION)

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
