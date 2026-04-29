"""init-kb.py — scaffold the canonical Prescyent KB structure.

Idempotent by design: re-running on an existing scaffold is a no-op unless
--reset is passed. Champion detection is the caller's job (SKILL.md checks
for MANIFEST.md before invoking this).

Usage:
    python3 init-kb.py --kb-root-label prescyent-kb --user-email tyler@acme.com
    python3 init-kb.py --kb-root-label prescyent-kb --user-email tyler@acme.com --dry-run
    python3 init-kb.py --kb-root-label prescyent-kb --user-email tyler@acme.com --reset

Requires storage.py as a sibling. Does NOT import storage for folder creation
(storage's write() is for single-file writes with frontmatter; scaffold makes
directories too). Uses storage only for root discovery.
"""

from __future__ import annotations

import argparse
import os
import re
import shutil
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).parent))
from storage import KBStorage  # noqa: E402

try:
    from storage import slug_email as _storage_slug_email  # noqa: E402
except ImportError:  # STORAGE agent may not have landed yet in parallel session
    _storage_slug_email = None


def slug_email(email: str) -> str:
    """Dot-preserving email slug. Mirrors storage.slug_email when present.

    Canonical form matches kb-writer.py + kb-compliance.py — preserves dots so
    `tyler@prescyent.ai` slugs to `tyler-prescyent.ai` (not `tyler-prescyent-ai`,
    which collides with `tyler@prescyent-ai.com`).
    """
    if _storage_slug_email is not None:
        return _storage_slug_email(email)
    return re.sub(r"[^a-z0-9.-]+", "-", email.lower()).strip("-") or "anonymous"


try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _yaml = None
    _HAS_YAML = False


# ---------------------------------------------------------------- structure

PUBLIC_FOLDERS = [
    ("00-meta", "KB about itself — taxonomy, review cadence, contribution rules."),
    ("01-company", "Company identity — mission, history, org chart, values, locations."),
    ("02-products", "Product catalog — each product as its own page with version and owner."),
    ("03-customers", "Customer segments, ICPs, personas. Redact individuals unless public."),
    ("04-gtm", "Go-to-market — positioning, pricing, channels, competitive intel, playbooks."),
    ("05-operations", "How the company runs — core Processes like lead-to-cash, order-to-cash."),
    ("06-people", "Roles and functions. The Role page type. Not individual people."),
    ("07-systems", "Every tool the company runs on. `records_authoritative_for` names the SOR."),
    ("08-projects", "In-flight initiatives. Link to Decisions, Systems, and Roles they touch."),
    ("09-decisions", "ADRs. Immutable. Supersede chains track change over time."),
    ("10-glossary", "Company dialect, preserved exactly. `do_not_confuse_with` is the point."),
    ("11-playbooks", "Step-by-step runbooks, each linked to the Process or Role it serves."),
    ("12-external", "Public-domain context that shapes this company — regulations, market reports."),
]

META_SUBFOLDERS = ["team", "interviews", "build-log", "proposed-updates", "gaps"]
RAW_SUBFOLDERS = ["interviews", "connector-dumps", "documents"]

# _meta children preserved across --reset. Identity + history — never nuked.
RESET_PRESERVE = [
    "preflight.md",
    "team",
    "interviews",
    "build-log",
    "proposed-updates",
    "gaps",
]


# ---------------------------------------------------------------- templates

def agents_md(folder_slug: str, purpose: str) -> str:
    """Per-folder AGENTS.md — ~30 lines, folder-specific instructions."""
    typical_types = _page_types_for(folder_slug)
    return f"""# AGENTS.md — {folder_slug}/

## What belongs here
{purpose}

## Typical page types
{typical_types}

## Voice and specificity
- Write in the company's own language. Pull phrasing from transcripts and docs.
- One topic per page. If a page runs past ~500 words, split it.
- Name owners. Every page has a human owner in frontmatter — not a team alias unless no individual fits.
- State `confidence: low` when the source is thin. Do not guess to fill a blank.

## Required frontmatter
Every page opens with the universal envelope (see `skills/kb-builder/references/universal-frontmatter-envelope.md`). Page-type-specific fields stack on top (see `skills/kb-builder/references/page-types/`).

## Linking
- Reference Glossary terms with `[[company.glossary.<term-slug>]]`.
- Reference other pages by their `id`, not by file path.
- When this folder's content depends on another folder's page, link out.

## What never belongs here
- Raw transcripts or connector dumps — those live under `_raw/`.
- Individual employees — those live under `_meta/team/`.
- Proposals to change someone else's page — those live under `_meta/proposed-updates/`.

## When to split to another folder
If you start writing a page here that is really about a different concern (a System about a tool, a Decision about an ADR), stop and write it in the right folder instead. Cross-link.
"""


def _page_types_for(slug: str) -> str:
    """Map folder → likely page types. Used in AGENTS.md."""
    mapping = {
        "00-meta": "- Concept (this KB's own taxonomy and conventions)\n- Playbook (how to contribute, how to review)",
        "01-company": "- Concept (mission, values, company history)\n- Role (exec roles, at a high level)",
        "02-products": "- Concept (each product as a named concept)\n- System (if the product is internal tooling)",
        "03-customers": "- Concept (segments, ICPs, personas)\n- Playbook (how we talk to each segment)",
        "04-gtm": "- Process (lead-to-cash, outbound motion)\n- Playbook (sales play, objection handling)\n- Concept (positioning, messaging)",
        "05-operations": "- Process (order-to-cash, hire-to-retire, close-the-books)\n- Playbook (operational runbooks)",
        "06-people": "- Role (job function, responsibilities, informal go-to-for)",
        "07-systems": "- System (every tool with SOR pointers via `records_authoritative_for`)",
        "08-projects": "- Concept (project brief)\n- Decision (ADRs scoped to the project)",
        "09-decisions": "- Decision (ADR — immutable, supersede chains)",
        "10-glossary": "- Glossary (one page per term; preserves company dialect)",
        "11-playbooks": "- Playbook (step-by-step runbook with inputs, outputs, owner)",
        "12-external": "- Concept (regulatory frameworks, market context, industry reports)",
    }
    return mapping.get(slug, "- See `skills/kb-builder/references/page-types/`")


ROOT_CLAUDE_MD_TEMPLATE = """# {kb_root_label}

This folder is the company knowledge base. It is markdown on your drive. You own it. Any AI session — Claude Cowork, Claude Code, or a future client — can read it and answer questions about your company with specifics, not generalities.

Created: {created_at}
Champion: {champion_email}

## What this KB is

A typed, atomic, hyperlinked wiki. Every page has a page type (Process, System, Role, Decision, Concept, Playbook, Glossary). Every page has frontmatter: an owner, a confidence level, a last-verified date, a confidentiality class. Pages are short on purpose — an agent reading the KB should be able to hold one page fully in context and follow links outward.

## How to read this KB (if you are an AI agent)

1. Start at `MANIFEST.md` to find which folder owns the topic you care about.
2. Open `_meta/preflight.md` for the company basics and the champion's goals.
3. Every page is self-describing via frontmatter. Trust the frontmatter; it is the contract.
4. Every folder under `public/` has an `AGENTS.md` with domain-specific instructions. Read it before writing into that folder.
5. Do not edit any page under `_raw/`. Those are immutable source artifacts. Read them; synthesize from them; never rewrite them.
6. To update a page that a human owns, write a proposal to `_meta/proposed-updates/` instead of editing in place.

## Folder map

- `public/00-meta/` — this KB about itself.
- `public/01-company/` — identity, mission, history, org chart.
- `public/02-products/` — product catalog.
- `public/03-customers/` — customer segments, ICPs, personas.
- `public/04-gtm/` — positioning, pricing, channels, competitive intel.
- `public/05-operations/` — the core processes the company runs on.
- `public/06-people/` — roles and functions (Role pages). Not individuals.
- `public/07-systems/` — every tool the company runs on, with SOR pointers.
- `public/08-projects/` — in-flight initiatives.
- `public/09-decisions/` — ADRs. Immutable; supersede chains record change.
- `public/10-glossary/` — company dialect, preserved exactly.
- `public/11-playbooks/` — step-by-step runbooks.
- `public/12-external/` — public-domain context that shapes this company.
- `_meta/` — plugin operational metadata. Interviews, build logs, team files.
- `_raw/` — source artifacts. Immutable.

## Page types

Seven types, each with its own schema. See `skills/kb-builder/references/page-types/` in the plugin repo:

- **Process** — a workflow with inputs, outputs, steps, owner.
- **System** — a tool, with what records it is authoritative for.
- **Role** — a function, with responsibilities and informal go-to patterns.
- **Decision** — an ADR. Alternatives, rationale, tradeoffs. Immutable.
- **Concept** — a noun the company uses, with aliases.
- **Playbook** — a runbook.
- **Glossary** — company dialect, preserved exactly.

Every page opens with the universal frontmatter envelope (see `skills/kb-builder/references/universal-frontmatter-envelope.md`).

## Confidentiality tiers

Every page has a `classification` field. Pages route to folders based on this:

- `public` — everyone in the company reads.
- `internal` — employees only. Most pages land here.
- `department-only` — scoped to one department's folder.
- `exec-only` — board, execs, champion only.
- `confidential` — legal / finance / hr only.

The `kb-classifier` subagent assigns this on write. When the classifier is uncertain (<0.9 confidence), it defaults to the most-restrictive tier.

## How to add content

- Run `/kb-build` to have the plugin mine your connectors and populate the wiki.
- Run `/kb-interview me` to capture knowledge that lives only in your head.
- Edit a page by hand — keep the frontmatter intact, update `last_edited_by` and `last_verified`.
- Propose an edit to someone else's page via `_meta/proposed-updates/`.

Every write passes through `kb-writer`, which runs PII redaction, classification, and an audit log entry. Do not sidestep it.

## Voice

Pages read like a careful internal writer wrote them. Direct. Specific. No hedging. No process narration. Terms the company actually uses, not sanitized synonyms. When you don't know something, say "unknown" in the frontmatter's `confidence` field — don't guess.

## AGENTS.md per folder

Each folder under `public/` has an `AGENTS.md` with folder-specific expectations: what page types belong there, what depth is right, what to never write. Read the folder's `AGENTS.md` before writing into it.

## If something looks wrong

- Gaps and broken links are logged to `_meta/gaps/`. Fix them or flag them.
- Conflict copies (`page (1).md`) mean Drive sync caught a simultaneous edit. Merge them by hand; never let the writer overwrite.
- Supersede chains must be bidirectional. If a page's `status` is `superseded`, its `superseded_by` names the successor, and the successor's `supersedes` names it.
- `kb-graph` runs after every `/kb-build` and catches most of this automatically.

## Questions

Ask the champion ({champion_email}). For plugin bugs, check the plugin repo on GitHub.
"""


MANIFEST_MD_TEMPLATE = """# MANIFEST.md — agent routing

This file tells each subagent which folders it owns. Updated by `/kb-build` as counts change.

## Folder ownership

| Folder | Owning subagent | Page types |
|---|---|---|
| `public/00-meta/` | kb-company | Concept, Playbook |
| `public/01-company/` | kb-company | Concept, Role |
| `public/02-products/` | kb-company | Concept, System |
| `public/03-customers/` | kb-gtm | Concept, Playbook |
| `public/04-gtm/` | kb-gtm | Process, Playbook, Concept |
| `public/05-operations/` | kb-ops | Process, Playbook |
| `public/06-people/` | kb-ops | Role |
| `public/07-systems/` | kb-ops | System |
| `public/08-projects/` | kb-ops | Concept, Decision |
| `public/09-decisions/` | kb-ops | Decision |
| `public/10-glossary/` | kb-company | Glossary |
| `public/11-playbooks/` | kb-ops | Playbook |
| `public/12-external/` | kb-company | Concept |

## Rules

- `kb-classifier` runs on every write before the page lands. No subagent writes directly; all writes funnel through `kb-writer`.
- `kb-graph` runs once at the end of `/kb-build` to compute typed links and flag broken supersede chains.
- `_meta/` is plugin-owned. Subagents write interviews and build logs there via `kb-writer`.
- `_raw/` is write-once. Subagents read; they never mutate.

## Page counts

Auto-populated by `kb-graph` after each `/kb-build` run. Empty at scaffold.

| Folder | Pages | Last updated |
|---|---|---|
| (empty — run `/kb-build` to populate) | 0 | — |
"""


INDEX_MD_TEMPLATE = """# index.md — human catalog

One-line summary per page. Auto-updated by `kb-graph` after `/kb-build`.

Empty at scaffold. Run `/kb-build` to populate this KB from your connectors, or `/kb-interview me` to capture what is in your head first.
"""


LOG_MD_TEMPLATE = """# log.md — append-only audit trail

## {created_at}
- Action: scaffold
- User: {champion_email}
- Champion: {champion_email}
- Folders created: {public_count} public/ + {meta_count} _meta/ + {raw_count} _raw/
- KB root label: {kb_root_label}
"""


GITKEEP_TEMPLATE = "# Immutable source material. Subagents read; they never rewrite. Do not delete or edit by hand.\n"


# ---------------------------------------------------------------- frontmatter helpers

def _split_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
    """Return (frontmatter_dict, body). Empty dict when no frontmatter."""
    if not raw.startswith("---\n"):
        return {}, raw
    end = raw.find("\n---\n", 4)
    if end == -1:
        # try trailing without newline
        end = raw.find("\n---", 4)
        if end == -1:
            return {}, raw
        header = raw[4:end]
        body = raw[end + 4:]
    else:
        header = raw[4:end]
        body = raw[end + 5:]
    if _HAS_YAML:
        parsed = _yaml.safe_load(header) or {}
        if not isinstance(parsed, dict):
            return {}, raw
        return parsed, body
    return _minimal_yaml_parse(header), body


def _render_frontmatter(data: dict[str, Any]) -> str:
    if _HAS_YAML:
        dumped = _yaml.safe_dump(data, sort_keys=False, default_flow_style=False).rstrip()
    else:
        dumped = _minimal_yaml_render(data).rstrip()
    return f"---\n{dumped}\n---\n"


def _minimal_yaml_parse(header: str) -> dict[str, Any]:
    data: dict[str, Any] = {}
    current_key: str | None = None
    for line in header.splitlines():
        stripped = line.strip()
        if not stripped or stripped.startswith("#"):
            continue
        if stripped.startswith("- ") and current_key is not None:
            data.setdefault(current_key, []).append(_unscalar(stripped[2:]))
            continue
        if ":" not in stripped:
            continue
        key, _, rest = stripped.partition(":")
        key = key.strip()
        rest = rest.strip()
        if rest == "":
            current_key = key
            data[key] = []
        else:
            current_key = None
            data[key] = _unscalar(rest)
    return data


def _minimal_yaml_render(data: dict[str, Any]) -> str:
    lines: list[str] = []
    for key, value in data.items():
        if isinstance(value, list):
            if not value:
                lines.append(f"{key}: []")
            else:
                lines.append(f"{key}:")
                for item in value:
                    lines.append(f"  - {_scalar(item)}")
        else:
            lines.append(f"{key}: {_scalar(value)}")
    return "\n".join(lines)


def _scalar(value: Any) -> str:
    import json
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    text = str(value)
    if any(ch in text for ch in ":#\n\"'") or text.strip() != text:
        return json.dumps(text)
    return text


def _unscalar(text: str) -> Any:
    import json
    text = text.strip()
    if text == "" or text.lower() == "null" or text == "~":
        return None
    if text.lower() == "true":
        return True
    if text.lower() == "false":
        return False
    if (text.startswith('"') and text.endswith('"')) or (text.startswith("'") and text.endswith("'")):
        return json.loads(text) if text.startswith('"') else text[1:-1]
    try:
        return int(text) if "." not in text else float(text)
    except ValueError:
        return text


# ---------------------------------------------------------------- core

def now_iso() -> str:
    return datetime.now(timezone.utc).strftime("%Y-%m-%d %H:%M:%S UTC")


def scaffold(root: Path, champion_email: str, kb_root_label: str, dry_run: bool = False) -> list[str]:
    """Create the canonical structure. Returns a list of paths written."""
    writes: list[str] = []

    def ensure_dir(rel: str) -> None:
        target = root / rel
        writes.append(f"DIR   {target}")
        if not dry_run:
            target.mkdir(parents=True, exist_ok=True)

    def write_file(rel: str, content: str) -> None:
        target = root / rel
        writes.append(f"FILE  {target}")
        if not dry_run:
            target.parent.mkdir(parents=True, exist_ok=True)
            target.write_text(content, encoding="utf-8")

    # _meta subfolders
    for sub in META_SUBFOLDERS:
        ensure_dir(f"_meta/{sub}")

    # public 12-folder tree with AGENTS.md stubs
    for slug, purpose in PUBLIC_FOLDERS:
        ensure_dir(f"public/{slug}")
        write_file(f"public/{slug}/AGENTS.md", agents_md(slug, purpose))

    # _raw immutable source tree with .gitkeep markers
    for sub in RAW_SUBFOLDERS:
        ensure_dir(f"_raw/{sub}")
        write_file(f"_raw/{sub}/.gitkeep", GITKEEP_TEMPLATE)

    created_at = now_iso()

    # top-level files
    write_file(
        "CLAUDE.md",
        ROOT_CLAUDE_MD_TEMPLATE.format(
            kb_root_label=kb_root_label,
            created_at=created_at,
            champion_email=champion_email,
        ),
    )
    write_file("MANIFEST.md", MANIFEST_MD_TEMPLATE)
    write_file("index.md", INDEX_MD_TEMPLATE)
    write_file(
        "log.md",
        LOG_MD_TEMPLATE.format(
            created_at=created_at,
            champion_email=champion_email,
            kb_root_label=kb_root_label,
            public_count=len(PUBLIC_FOLDERS),
            meta_count=len(META_SUBFOLDERS),
            raw_count=len(RAW_SUBFOLDERS),
        ),
    )

    return writes


def move_first_artifact(root: Path, slug: str, champion_email: str, dry_run: bool = False) -> str | None:
    """Move ~/.prescyent/{slug}/first-artifact.md → {root}/public/10-glossary/glossary.md.

    Always merges the universal envelope onto whatever frontmatter the source had,
    so the seeded glossary validates on first scaffold.
    """
    src = Path.home() / ".prescyent" / slug / "first-artifact.md"
    if not src.exists():
        return None
    dst = root / "public" / "10-glossary" / "glossary.md"
    if dry_run:
        return f"MOVE  {src} -> {dst} (merging envelope)"
    dst.parent.mkdir(parents=True, exist_ok=True)
    raw = src.read_text(encoding="utf-8")
    existing_fm, body = _split_frontmatter(raw)
    merged_fm = _merge_glossary_envelope(existing_fm, champion_email)
    dst.write_text(_render_frontmatter(merged_fm) + body, encoding="utf-8")
    src.unlink()
    return f"MOVE  {src} -> {dst}"


def _merge_glossary_envelope(existing: dict[str, Any], owner_email: str) -> dict[str, Any]:
    """Ensure the universal envelope + Glossary type fields are present.

    Preserves any fields the source already set; fills every missing slot with a
    safe default so `validate-frontmatter.py` passes on the seeded glossary.
    """
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    envelope_defaults: dict[str, Any] = {
        "id": "company.glossary.starter",
        "title": "Company glossary — starter",
        "type": "Glossary",
        "owner": owner_email,
        "confidence": "low",
        "source_artifacts": ["start-here://first-artifact"],
        "last_verified": today,
        "review_cycle_days": 30,
        "status": "draft",
        "created_by": owner_email,
        "last_edited_by": owner_email,
        "classification": "internal",
        "audience": ["all-company"],
        "redactions_applied": [],
        "classification_decided_by": "kb-scaffold",
        # Glossary type-specific fields
        "term": "starter",
        "definition": "Starter index of company terms captured by `/discover` (and split by `/kb-build`). Split into per-term Glossary pages by `/kb-build`.",
        "aliases": [],
        "do_not_confuse_with": [],
        "customer_facing_equivalent": "n/a",
        "preferred_phrasing": "starter glossary",
        "usage_examples": [],
    }
    # Existing source fields win for any key they already set — but only if the
    # existing value is meaningful. Drop None/empty-string scalars so defaults apply.
    filtered_existing: dict[str, Any] = {}
    for k, v in existing.items():
        if v is None:
            continue
        if isinstance(v, str) and v == "":
            continue
        filtered_existing[k] = v
    merged = {**envelope_defaults, **filtered_existing}
    # Enforce invariants: type must be Glossary, classification_decided_by names this step.
    merged["type"] = "Glossary"
    merged.setdefault("classification_decided_by", "kb-scaffold")
    return merged


def move_preflight(root: Path, slug: str, dry_run: bool = False) -> str | None:
    """Move ~/.prescyent/{slug}/preflight.md → {root}/_meta/preflight.md."""
    src = Path.home() / ".prescyent" / slug / "preflight.md"
    if not src.exists():
        return None
    dst = root / "_meta" / "preflight.md"
    if dry_run:
        return f"MOVE  {src} -> {dst}"
    dst.parent.mkdir(parents=True, exist_ok=True)
    shutil.move(str(src), str(dst))
    return f"MOVE  {src} -> {dst}"


def reset_wiki(root: Path, dry_run: bool = False) -> list[str]:
    """Wipe public/ fully; wipe _meta/ but preserve identity + history.

    Stashes the preserved `_meta/` children to a sibling temp dir, wipes, then
    restores. Champion running `--reset` keeps preflight + team stubs +
    interview transcripts + build-log + proposed-updates + gaps.
    """
    actions: list[str] = []
    if dry_run:
        actions.append(f"RESET {root}/public (full wipe)")
        actions.append(
            f"RESET {root}/_meta (wipe, preserve: {', '.join(RESET_PRESERVE)})"
        )
        return actions

    stash = root.parent / f".prescyent-kb-reset-stash-{os.getpid()}"
    try:
        meta = root / "_meta"
        public = root / "public"

        # Stash preserved _meta children before wipe.
        if meta.exists():
            stash.mkdir(parents=True, exist_ok=True)
            for name in RESET_PRESERVE:
                src = meta / name
                if src.exists():
                    shutil.move(str(src), str(stash / name))

        # Wipe.
        if meta.exists():
            actions.append(f"RESET {meta}")
            shutil.rmtree(meta)
        if public.exists():
            actions.append(f"RESET {public}")
            shutil.rmtree(public)

        # Recreate empty _meta (scaffold() will re-create its subdirs).
        meta.mkdir(parents=True, exist_ok=True)

        # Restore preserved children.
        if stash.exists():
            for name in RESET_PRESERVE:
                stashed = stash / name
                if stashed.exists():
                    shutil.move(str(stashed), str(meta / name))
                    actions.append(f"KEEP  {meta / name}")
    finally:
        if stash.exists():
            shutil.rmtree(stash, ignore_errors=True)

    return actions


# ---------------------------------------------------------------- cli

def main() -> int:
    parser = argparse.ArgumentParser(description="Scaffold a Prescyent KB.")
    parser.add_argument("--kb-root-label", required=True, help="Folder name (e.g. prescyent-kb)")
    parser.add_argument("--user-email", required=True, help="Champion email")
    parser.add_argument("--slug", default=None, help="Preflight cache slug (defaults to email-slugified)")
    parser.add_argument("--dry-run", action="store_true", help="Print actions without writing")
    parser.add_argument("--reset", action="store_true", help="Wipe _meta and public before scaffold; preserves identity + history")
    args = parser.parse_args()

    slug = args.slug or slug_email(args.user_email)

    try:
        store = KBStorage(args.kb_root_label)
    except Exception as exc:
        print(f"error: could not resolve KB root for label {args.kb_root_label!r}: {exc}", file=sys.stderr)
        return 2

    root = store.root
    print(f"KB root: {root}")

    manifest = root / "MANIFEST.md"
    if manifest.exists() and not args.reset:
        print("MANIFEST.md already exists — this user is JOINING an existing KB.")
        _write_team_stub(root, args.user_email, dry_run=args.dry_run)
        return 0

    if args.reset:
        print("--reset: wiping _meta/ and public/; preserving identity + history + _raw/")
        for line in reset_wiki(root, dry_run=args.dry_run):
            print(line)

    writes = scaffold(root, args.user_email, args.kb_root_label, dry_run=args.dry_run)
    for line in writes:
        print(line)

    for mv in (move_first_artifact(root, slug, args.user_email, dry_run=args.dry_run),
               move_preflight(root, slug, dry_run=args.dry_run)):
        if mv is not None:
            print(mv)

    public_count = len(PUBLIC_FOLDERS)
    print(
        f"\nscaffold complete: {public_count} public/ + {len(META_SUBFOLDERS)} _meta/ + "
        f"{len(RAW_SUBFOLDERS)} _raw/ subfolders; {public_count} AGENTS.md stubs"
    )
    return 0


def _write_team_stub(root: Path, email: str, dry_run: bool = False) -> None:
    today = datetime.now(timezone.utc).strftime("%Y-%m-%d")
    slug = slug_email(email)
    target = root / "_meta" / "team" / f"{slug}.md"
    body = f"""---
id: company.team.{slug}
title: {email}
type: Role
owner: {email}
confidence: low
source_artifacts: []
last_verified: {today}
review_cycle_days: 180
status: draft
created_by: {email}
last_edited_by: {email}
classification: internal
audience:
  - all-company
redactions_applied: []
classification_decided_by: kb-scaffold
reports_to: unknown
direct_reports: []
informal_goto_for: []
processes_owned: []
systems_owned: []
tenure_at_company: unknown
domain_expertise: []
---

# {email}

Joined the KB as a team member on {today}. Run `/kb-interview me` to fill in `reports_to`, `informal_goto_for`, `processes_owned`, and the rest of the Role schema.
"""
    print(f"FILE  {target}")
    if not dry_run:
        target.parent.mkdir(parents=True, exist_ok=True)
        target.write_text(body, encoding="utf-8")


if __name__ == "__main__":
    sys.exit(main())
