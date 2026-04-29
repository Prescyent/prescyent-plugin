#!/usr/bin/env python3
"""
validate-frontmatter.py — Prescyent KB page frontmatter validator.

Reads a markdown file, extracts its YAML frontmatter, and validates it against
the Prescyent universal envelope + the appropriate page-type schema.

Usage:
    python3 validate-frontmatter.py <path-to-md-file>
    python3 validate-frontmatter.py --test

Exit 0 on valid, exit 1 on invalid (with a diff printed to stdout).

Schemas live in `references/page-types/` next to this script. The hard-coded
required-field map below is the source of truth for the validator; the markdown
schema files are the source of truth for human authors. They must stay in sync —
if you change one, grep the other.

Uses PyYAML when available; falls back to a minimal handwritten parser that
handles the subset of YAML the KB envelope uses (scalars, flow lists, block
lists, and nested maps up to one level). The fallback is intentionally strict;
if a page uses a YAML feature the fallback can't parse, install PyYAML:
    pip install pyyaml
"""

from __future__ import annotations

import sys
import os
import argparse
from pathlib import Path

# -----------------------------------------------------------------------------
# YAML loader — PyYAML preferred, handwritten fallback
# -----------------------------------------------------------------------------

try:
    import yaml as _yaml  # type: ignore

    def load_yaml(text: str) -> dict:
        return _yaml.safe_load(text) or {}

    YAML_IMPL = "pyyaml"
except ImportError:

    def load_yaml(text: str) -> dict:
        return _fallback_parse(text)

    YAML_IMPL = "fallback"


def _fallback_parse(text: str) -> dict:
    """
    Minimal YAML-ish parser. Handles:
      - `key: value` scalars (strings, ints, booleans, null)
      - `key: [a, b, c]` inline/flow lists
      - `key:` followed by `  - item` block lists
      - `key:` followed by nested `  subkey: value` maps (one level deep)
      - Quoted strings (single or double)
      - `# comment` to end of line
    Does NOT handle: multi-line strings, anchors/aliases, deep nesting,
    flow mappings. Good enough for Prescyent envelopes.
    """
    result: dict = {}
    lines = text.splitlines()
    i = 0
    while i < len(lines):
        raw = lines[i]
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            i += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent != 0:
            # unexpected indentation at top level; skip
            i += 1
            continue
        if ":" not in stripped:
            i += 1
            continue
        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            # Look ahead — either a block list or a nested map
            block_items, consumed = _collect_block(lines, i + 1)
            result[key] = block_items
            i += 1 + consumed
            continue
        if rest.startswith("["):
            result[key] = _parse_flow_list(rest)
            i += 1
            continue
        result[key] = _coerce_scalar(rest)
        i += 1
    return result


def _strip_comment(line: str) -> str:
    # Only strip `#` when it is clearly a comment (preceded by space or at start)
    out = []
    in_single = False
    in_double = False
    for ch in line:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch == "#" and not in_single and not in_double:
            break
        out.append(ch)
    return "".join(out)


def _collect_block(lines: list[str], start: int):
    """Collect either a block list or a nested map starting at lines[start]."""
    items: list | dict = []
    is_list = None
    consumed = 0
    j = start
    while j < len(lines):
        raw = lines[j]
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            j += 1
            consumed += 1
            continue
        indent = len(raw) - len(raw.lstrip(" "))
        if indent == 0:
            break
        body = raw.strip()
        if body.startswith("- "):
            if is_list is None:
                is_list = True
                items = []
            item_text = body[2:].strip()
            if ":" in item_text and not item_text.startswith("'") and not item_text.startswith('"'):
                # Dict-in-list: `- name: foo`
                d = {}
                k, _, v = item_text.partition(":")
                d[k.strip()] = _coerce_scalar(v.strip())
                # Look ahead for more keys at deeper indent
                k2 = j + 1
                consumed2 = 0
                child_indent = None
                while k2 < len(lines):
                    raw2 = lines[k2]
                    s2 = _strip_comment(raw2).rstrip()
                    if not s2.strip():
                        k2 += 1
                        consumed2 += 1
                        continue
                    ind2 = len(raw2) - len(raw2.lstrip(" "))
                    if ind2 <= indent:
                        break
                    if child_indent is None:
                        child_indent = ind2
                    if ind2 != child_indent:
                        break
                    b2 = raw2.strip()
                    if b2.startswith("- "):
                        break
                    if ":" in b2:
                        kk, _, vv = b2.partition(":")
                        d[kk.strip()] = _coerce_scalar(vv.strip())
                    k2 += 1
                    consumed2 += 1
                items.append(d)
                j = k2
                consumed += 1 + consumed2
                continue
            items.append(_coerce_scalar(item_text))
            j += 1
            consumed += 1
            continue
        if is_list is None:
            is_list = False
            items = {}
        if ":" in body:
            k, _, v = body.partition(":")
            if isinstance(items, dict):
                items[k.strip()] = _coerce_scalar(v.strip())
        j += 1
        consumed += 1
    if is_list is None:
        return [], 0
    return items, consumed


def _parse_flow_list(text: str) -> list:
    text = text.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return []
    inner = text[1:-1].strip()
    if not inner:
        return []
    parts = []
    buf = []
    depth = 0
    in_single = False
    in_double = False
    for ch in inner:
        if ch == "'" and not in_double:
            in_single = not in_single
        elif ch == '"' and not in_single:
            in_double = not in_double
        elif ch in "[{" and not in_single and not in_double:
            depth += 1
        elif ch in "]}" and not in_single and not in_double:
            depth -= 1
        if ch == "," and depth == 0 and not in_single and not in_double:
            parts.append("".join(buf).strip())
            buf = []
        else:
            buf.append(ch)
    if buf:
        parts.append("".join(buf).strip())
    return [_coerce_scalar(p) for p in parts]


def _coerce_scalar(text: str):
    text = text.strip()
    if text == "" or text.lower() == "null" or text == "~":
        return None
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if (text.startswith('"') and text.endswith('"')) or (
        text.startswith("'") and text.endswith("'")
    ):
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        return _parse_flow_list(text)
    try:
        if "." in text:
            return float(text)
        return int(text)
    except ValueError:
        return text


# -----------------------------------------------------------------------------
# Schema — hard-coded required fields per type (source of truth for validator).
# Page-type schema markdown files are source of truth for humans; keep in sync.
# -----------------------------------------------------------------------------

ENVELOPE_REQUIRED = [
    "id",
    "title",
    "type",
    "owner",
    "confidence",
    "source_artifacts",
    "last_verified",
    "review_cycle_days",
    "status",
    "created_by",
    "last_edited_by",
    "classification",
    "audience",
    "redactions_applied",
    "classification_decided_by",
]

ENVELOPE_OPTIONAL = [
    "pcf",
    "bian",
    "togaf",
    "zachman",
    "dmbok",
    "supersedes",
    "superseded_by",
]

VALID_TYPES = {
    "Process",
    "System",
    "Role",
    "Decision",
    "Concept",
    "Playbook",
    "Glossary",
}

VALID_CLASSIFICATIONS = {
    "public",
    "internal",
    "department-only",
    "exec-only",
    "confidential",
}

VALID_CONFIDENCE = {"high", "medium", "low"}
VALID_STATUS = {"draft", "published", "superseded"}

TYPE_REQUIRED: dict[str, list[str]] = {
    "Process": [
        "value_stream",
        "inputs",
        "outputs",
        "actors",
        "systems",
        "decision_points",
        "failure_modes",
    ],
    "System": [
        "system_type",
        "vendor",
        "sor_for",
        "consumes_from",
        "feeds_into",
        "gotchas",
        "auth_method",
        "mcp_available",
    ],
    "Role": [
        "reports_to",
        "direct_reports",
        "informal_goto_for",
        "processes_owned",
        "systems_owned",
        "tenure_at_company",
        "domain_expertise",
    ],
    "Decision": [
        "decision_date",
        "alternatives_considered",
        "rationale",
        "expected_tradeoffs",
        "outcome",
        "decision_maker",
        "affected_teams",
    ],
    "Concept": ["aliases", "related_concepts", "examples"],
    "Playbook": [
        "trigger",
        "objective",
        "steps",
        "success_criteria",
        "failure_modes",
        "time_to_execute",
        "practiced_by",
    ],
    "Glossary": [
        "term",
        "definition",
        "aliases",
        "do_not_confuse_with",
        "customer_facing_equivalent",
        "preferred_phrasing",
        "usage_examples",
    ],
}


# -----------------------------------------------------------------------------
# Core validator
# -----------------------------------------------------------------------------


def split_frontmatter(text: str) -> tuple[str, str] | None:
    """Return (frontmatter_text, body_text) or None if no frontmatter."""
    lines = text.splitlines()
    if not lines or lines[0].strip() != "---":
        return None
    end = None
    for i in range(1, len(lines)):
        if lines[i].strip() == "---":
            end = i
            break
    if end is None:
        return None
    fm = "\n".join(lines[1:end])
    body = "\n".join(lines[end + 1 :])
    return fm, body


def validate_frontmatter(fm: dict) -> tuple[list[str], list[str]]:
    """Return (errors, warnings)."""
    errors: list[str] = []
    warnings: list[str] = []

    if not isinstance(fm, dict):
        return ["frontmatter is not a mapping"], []

    for field in ENVELOPE_REQUIRED:
        if field not in fm or fm[field] is None or fm[field] == "":
            errors.append(f"missing required envelope field: {field}")

    ptype = fm.get("type")
    if ptype is not None:
        if ptype not in VALID_TYPES:
            errors.append(
                f"invalid type: {ptype!r} (expected one of {sorted(VALID_TYPES)})"
            )
        else:
            for field in TYPE_REQUIRED[ptype]:
                if field not in fm:
                    errors.append(
                        f"missing required field for type={ptype}: {field}"
                    )
                elif fm[field] is None and field not in ("supersedes", "superseded_by"):
                    # Type-specific fields cannot be null; use [] for empty lists.
                    errors.append(
                        f"type-specific field {field} is null (use [] for empty list, or remove if truly absent)"
                    )

    classification = fm.get("classification")
    if classification is not None and classification not in VALID_CLASSIFICATIONS:
        errors.append(
            f"invalid classification: {classification!r} (expected one of {sorted(VALID_CLASSIFICATIONS)})"
        )

    confidence = fm.get("confidence")
    if confidence is not None and confidence not in VALID_CONFIDENCE:
        errors.append(
            f"invalid confidence: {confidence!r} (expected one of {sorted(VALID_CONFIDENCE)})"
        )

    status = fm.get("status")
    if status is not None and status not in VALID_STATUS:
        errors.append(
            f"invalid status: {status!r} (expected one of {sorted(VALID_STATUS)})"
        )

    # Unknown fields -> warnings, not errors
    known = set(ENVELOPE_REQUIRED) | set(ENVELOPE_OPTIONAL)
    if ptype in TYPE_REQUIRED:
        known |= set(TYPE_REQUIRED[ptype])
    for key in fm.keys():
        if key not in known:
            warnings.append(f"unknown field (not in envelope or type schema): {key}")

    # Supersede chain sanity
    if status == "superseded" and not fm.get("superseded_by"):
        errors.append("status is 'superseded' but superseded_by is empty")

    return errors, warnings


def validate_file(path: Path) -> int:
    if not path.exists():
        print(f"ERROR: file not found: {path}", file=sys.stderr)
        return 1
    text = path.read_text(encoding="utf-8")
    split = split_frontmatter(text)
    if split is None:
        print(f"INVALID {path}")
        print("  no frontmatter block found (expected `---` delimited YAML at top)")
        return 1
    fm_text, _body = split
    try:
        fm = load_yaml(fm_text)
    except Exception as exc:
        print(f"INVALID {path}")
        print(f"  YAML parse error: {exc}")
        return 1
    errors, warnings = validate_frontmatter(fm)
    if errors:
        print(f"INVALID {path}")
        for e in errors:
            print(f"  ERROR: {e}")
        for w in warnings:
            print(f"  WARN:  {w}")
        return 1
    print(f"VALID   {path}")
    for w in warnings:
        print(f"  WARN: {w}")
    return 0


# -----------------------------------------------------------------------------
# --test harness: synthetic valid + invalid fixtures per type
# -----------------------------------------------------------------------------


def _envelope_ok(ptype: str) -> dict:
    return {
        "id": f"test.{ptype.lower()}.sample",
        "title": f"Sample {ptype}",
        "type": ptype,
        "owner": "test@acme.com",
        "confidence": "high",
        "source_artifacts": ["gdrive://test"],
        "last_verified": "2026-04-24",
        "review_cycle_days": 90,
        "status": "draft",
        "created_by": "test@acme.com",
        "last_edited_by": "test@acme.com",
        "classification": "internal",
        "audience": ["engineering"],
        "redactions_applied": [],
        "classification_decided_by": "kb-classifier",
    }


def _type_extras_ok(ptype: str) -> dict:
    return {
        "Process": {
            "value_stream": "test-stream",
            "inputs": ["a"],
            "outputs": ["b"],
            "actors": [{"role": "tester"}],
            "systems": ["TestSys"],
            "decision_points": [],
            "failure_modes": [],
        },
        "System": {
            "system_type": "Test",
            "vendor": "TestCo",
            "sor_for": ["thing"],
            "consumes_from": [],
            "feeds_into": [],
            "gotchas": ["watch out"],
            "auth_method": "SSO",
            "mcp_available": False,
        },
        "Role": {
            "reports_to": "ceo@acme.com",
            "direct_reports": [],
            "informal_goto_for": ["testing"],
            "processes_owned": [],
            "systems_owned": [],
            "tenure_at_company": "1 year",
            "domain_expertise": ["qa"],
        },
        "Decision": {
            "decision_date": "2026-01-01",
            "alternatives_considered": [
                {"name": "Alt", "rejected_because": "because"}
            ],
            "rationale": "because reasons",
            "expected_tradeoffs": ["cost"],
            "outcome": "pending",
            "decision_maker": "ceo@acme.com",
            "affected_teams": ["eng"],
        },
        "Concept": {
            "aliases": ["a"],
            "related_concepts": [],
            "examples": ["example"],
        },
        "Playbook": {
            "trigger": "alert fires",
            "objective": "restore",
            "steps": ["step 1"],
            "success_criteria": "green",
            "failure_modes": [],
            "time_to_execute": "10 min",
            "practiced_by": ["sre"],
        },
        "Glossary": {
            "term": "TTV",
            "definition": "time to value",
            "aliases": ["t2v"],
            "do_not_confuse_with": ["TTL"],
            "customer_facing_equivalent": "value realization",
            "preferred_phrasing": "TTV",
            "usage_examples": ["cut our TTV in half"],
        },
    }[ptype]


def _run_tests() -> int:
    passes = 0
    fails = 0
    lines: list[str] = []
    for ptype in [
        "Process",
        "System",
        "Role",
        "Decision",
        "Concept",
        "Playbook",
        "Glossary",
    ]:
        # Valid fixture: envelope + type extras should pass with 0 errors.
        fm = {**_envelope_ok(ptype), **_type_extras_ok(ptype)}
        errors, _w = validate_frontmatter(fm)
        if not errors:
            passes += 1
            lines.append(f"  PASS  {ptype:<9} valid fixture")
        else:
            fails += 1
            lines.append(f"  FAIL  {ptype:<9} valid fixture -> {errors}")

        # Invalid fixture #1: missing a required type-specific field.
        missing_field = TYPE_REQUIRED[ptype][0]
        fm_missing = {**_envelope_ok(ptype), **_type_extras_ok(ptype)}
        del fm_missing[missing_field]
        errors, _w = validate_frontmatter(fm_missing)
        if any(missing_field in e for e in errors):
            passes += 1
            lines.append(
                f"  PASS  {ptype:<9} rejects missing required field '{missing_field}'"
            )
        else:
            fails += 1
            lines.append(
                f"  FAIL  {ptype:<9} did NOT reject missing '{missing_field}'; got {errors}"
            )

    # Extra check: invalid classification
    fm_bad_class = {**_envelope_ok("Process"), **_type_extras_ok("Process")}
    fm_bad_class["classification"] = "top-secret-ultra"
    errors, _w = validate_frontmatter(fm_bad_class)
    if any("classification" in e for e in errors):
        passes += 1
        lines.append("  PASS  Extra    rejects invalid classification value")
    else:
        fails += 1
        lines.append(f"  FAIL  Extra    did NOT reject invalid classification; got {errors}")

    # Extra check: invalid type
    fm_bad_type = {**_envelope_ok("Process"), **_type_extras_ok("Process")}
    fm_bad_type["type"] = "Manifesto"
    errors, _w = validate_frontmatter(fm_bad_type)
    if any("invalid type" in e for e in errors):
        passes += 1
        lines.append("  PASS  Extra    rejects invalid type value")
    else:
        fails += 1
        lines.append(f"  FAIL  Extra    did NOT reject invalid type; got {errors}")

    # Extra check: missing envelope field
    fm_bad_env = {**_envelope_ok("Concept"), **_type_extras_ok("Concept")}
    del fm_bad_env["owner"]
    errors, _w = validate_frontmatter(fm_bad_env)
    if any("owner" in e for e in errors):
        passes += 1
        lines.append("  PASS  Extra    rejects missing envelope field 'owner'")
    else:
        fails += 1
        lines.append(f"  FAIL  Extra    did NOT reject missing envelope field; got {errors}")

    print(f"validate-frontmatter self-test (YAML impl: {YAML_IMPL})")
    for ln in lines:
        print(ln)
    total = passes + fails
    print(f"\nRESULT: {passes}/{total} passed, {fails} failed")
    return 0 if fails == 0 else 1


# -----------------------------------------------------------------------------
# CLI
# -----------------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(
        description="Validate a Prescyent KB page's YAML frontmatter."
    )
    parser.add_argument(
        "path",
        nargs="?",
        help="Path to a markdown file. Omit when using --test.",
    )
    parser.add_argument(
        "--test",
        action="store_true",
        help="Run built-in synthetic fixture tests and report pass/fail counts.",
    )
    args = parser.parse_args()

    if args.test:
        return _run_tests()
    if not args.path:
        parser.print_help(sys.stderr)
        return 1
    return validate_file(Path(args.path))


if __name__ == "__main__":
    sys.exit(main())
