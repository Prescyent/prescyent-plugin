#!/usr/bin/env python3
"""generate-mermaid-concept-map.py — emit a Mermaid diagram from interview state.

Two modes:

1. --from-json <path>   : read {"tasks": [...], "tools": [...], "decisions": [...],
                          "handoffs": [...]} and emit a Mermaid flowchart string.
2. --from-transcript <path> : read a kb-interview transcript markdown file and
                          extract tasks + tools via regex + simple heuristics.
                          Good enough for alpha; kb-graph (WP-09) will do more.

Optional: --correction "<text>" — append a user correction as a commented node
at the bottom of the diagram so the interviewer can see what the user asked to
change. The human-in-the-loop is the validator, not this script.

Stdlib only. ~120 LOC cap.

Exit 0 on success (diagram printed to stdout). Exit 1 on usage error.
Exit 2 if the input JSON / transcript is unparseable.

Self-test: --self-test exercises the 3 load-bearing paths (from-json, from-
transcript, off-record-stripping in from-transcript).
"""

from __future__ import annotations

import argparse
import json
import re
import sys
from pathlib import Path


def _sanitise_label(text: str) -> str:
    """Mermaid node labels: strip newlines, quote if needed, cap length."""
    s = re.sub(r"\s+", " ", text).strip()
    if len(s) > 48:
        s = s[:45] + "..."
    # Quote to allow punctuation without breaking the flowchart parser.
    return '"' + s.replace('"', "'") + '"'


def _node_id(prefix: str, idx: int) -> str:
    return f"{prefix}{idx}"


def emit_from_state(state: dict, correction: str | None = None) -> str:
    tasks = list(state.get("tasks") or [])
    tools = list(state.get("tools") or [])
    decisions = list(state.get("decisions") or [])
    handoffs = list(state.get("handoffs") or [])

    lines = ["flowchart TD"]

    # Tasks — primary nodes.
    for i, t in enumerate(tasks):
        lines.append(f"    {_node_id('T', i)}[{_sanitise_label(t)}]")

    # Tools — rounded nodes.
    for i, tool in enumerate(tools):
        lines.append(f"    {_node_id('S', i)}([{_sanitise_label(tool)}])")

    # Decisions — diamond nodes.
    for i, d in enumerate(decisions):
        lines.append(f"    {_node_id('D', i)}{{{_sanitise_label(d)}}}")

    # Handoffs — edges between task i and task j (or tool), optionally labelled.
    for h in handoffs:
        if not isinstance(h, dict):
            continue
        src = h.get("from")
        dst = h.get("to")
        label = h.get("label", "")
        if src is None or dst is None:
            continue
        edge = f"    {src} -- {_sanitise_label(label)} --> {dst}" if label else f"    {src} --> {dst}"
        lines.append(edge)

    # Default chain: each task flows to the next if no explicit handoffs.
    if not handoffs and len(tasks) >= 2:
        for i in range(len(tasks) - 1):
            lines.append(f"    T{i} --> T{i + 1}")

    if correction:
        safe = correction.strip().replace("\n", " ")
        if len(safe) > 200:
            safe = safe[:197] + "..."
        lines.append(f"    %% user correction: {safe}")

    return "\n".join(lines) + "\n"


# Transcript parsing — regex heuristics. Designed for the markdown format
# written by the kb-interview skill (Phase 8a).

_TASK_PATTERNS = [
    re.compile(r"(?im)^\s*\d+[\.)]\s+(.+)$"),             # "1. run pipeline reviews"
    re.compile(r"(?im)^\s*[-*]\s+(?:task:?\s*)?(.+)$"),  # "- task: run reviews"
]
_TOOL_PATTERNS = [
    re.compile(r"(?i)\btool[s]?\s*(?:used)?\s*[:=]\s*([^\n]+)"),
    re.compile(r"(?i)\b(?:in|via|using)\s+([A-Z][A-Za-z0-9]{1,})\b"),  # "in HubSpot"
]

_PRIVATE_BLOCK = re.compile(r"---private-start---.*?---private-end---", re.DOTALL)


def parse_transcript(text: str) -> dict:
    # Strip off-record blocks BEFORE extracting anything. Private content must
    # never feed the public diagram.
    clean = _PRIVATE_BLOCK.sub("", text)

    tasks: list[str] = []
    for pat in _TASK_PATTERNS:
        for m in pat.finditer(clean):
            candidate = m.group(1).strip()
            if len(candidate) < 3 or len(candidate) > 120:
                continue
            if candidate.lower() not in {t.lower() for t in tasks}:
                tasks.append(candidate)
        if tasks:
            break

    tools: list[str] = []
    for pat in _TOOL_PATTERNS:
        for m in pat.finditer(clean):
            raw = m.group(1).strip().rstrip(".,;:")
            for piece in re.split(r"[,/]| and ", raw):
                piece = piece.strip()
                if not piece or len(piece) > 40:
                    continue
                if piece.lower() not in {t.lower() for t in tools}:
                    tools.append(piece)

    return {"tasks": tasks[:8], "tools": tools[:10], "decisions": [], "handoffs": []}


def _self_test() -> int:
    passed = 0
    total = 0

    # Case 1 — from-json emits a valid flowchart.
    total += 1
    out = emit_from_state({
        "tasks": ["pipeline review", "deal sync", "forecast call"],
        "tools": ["HubSpot", "Gmail"],
        "decisions": ["approve deal?"],
        "handoffs": [{"from": "T0", "to": "T1", "label": "handoff"}],
    })
    if "flowchart TD" in out and "T0" in out and "HubSpot" in out and "approve deal?" in out:
        print("  PASS  from-json emits valid flowchart"); passed += 1
    else:
        print(f"  FAIL  from-json — got:\n{out}")

    # Case 2 — from-transcript extracts tasks + tools, strips off-record.
    total += 1
    transcript = """
User: my tasks are:
1. pipeline review
2. deal sync
3. forecast call

User: I do this in HubSpot, using Gmail.

---private-start---
User: [off the record] I use CursedCRM for the real data
Interviewer: acknowledged
---private-end---

User: back on the record.
"""
    state = parse_transcript(transcript)
    if ("pipeline review" in state["tasks"]
            and "HubSpot" in state["tools"]
            and not any("CursedCRM" in t for t in state["tools"])):
        print("  PASS  from-transcript extracts + strips off-record"); passed += 1
    else:
        print(f"  FAIL  from-transcript — got {state}")

    # Case 3 — correction renders as a Mermaid comment (doesn't break the diagram).
    total += 1
    out3 = emit_from_state({"tasks": ["one"], "tools": [], "decisions": [], "handoffs": []},
                           correction="missing the Q4 step")
    if "%% user correction: missing the Q4 step" in out3:
        print("  PASS  correction renders as comment"); passed += 1
    else:
        print(f"  FAIL  correction missing — got:\n{out3}")

    print(f"\nRESULT: {passed}/{total} passed")
    return 0 if passed == total else 1


def main() -> int:
    ap = argparse.ArgumentParser()
    ap.add_argument("--from-json", help="Path to JSON state file")
    ap.add_argument("--from-transcript", help="Path to transcript markdown file")
    ap.add_argument("--correction", help="User-supplied correction text")
    ap.add_argument("--self-test", action="store_true")
    args = ap.parse_args()

    if args.self_test:
        return _self_test()

    if not args.from_json and not args.from_transcript:
        print("error: need --from-json or --from-transcript", file=sys.stderr)
        return 1

    try:
        if args.from_json:
            state = json.loads(Path(args.from_json).read_text(encoding="utf-8"))
        else:
            state = parse_transcript(Path(args.from_transcript).read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"error: cannot parse input: {exc}", file=sys.stderr)
        return 2

    sys.stdout.write(emit_from_state(state, correction=args.correction))
    return 0


if __name__ == "__main__":
    sys.exit(main())
