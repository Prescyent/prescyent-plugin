#!/usr/bin/env python3
"""kb-compliance.py — shared read-only helper for the 3 user-rights commands.

Produces a JSON payload used by:
  - /kb-my-pages   (right to access, GDPR art 15 / CCPA)
  - /kb-edit-mine  (right to rectify, GDPR art 16)
  - /kb-forget-me  (right to erasure, GDPR art 17)

Pure reader. Never writes. Never deletes. Writes go through kb-writer.py;
deletes go through direct storage.py calls in the command file.

Mention rule (a page "mentions the user" if ANY of these match):
  * frontmatter owner/created_by/last_edited_by == user_email
  * frontmatter audience[] or informal_goto_for[] contains user_email or name
  * body contains user_email (case-insensitive) OR name as whole-word match
  * path contains the email slug
  * source_artifacts[] contains the email slug

Classification-aware read filter (matches kb-writer.py::user_ceiling):
  * no groups          -> ceiling=internal      (sees public + internal)
  * exec / leadership  -> ceiling=exec-only
  * legal / finance    -> ceiling=confidential
  * department-only    -> user's groups must include the department
"""

from __future__ import annotations

import argparse
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# storage.py lives in the kb-builder scripts dir. Add that to sys.path so the
# shared KBStorage class is the same code that kb-writer.py uses.
_HERE = Path(__file__).resolve().parent
_KB_BUILDER_SCRIPTS = _HERE.parent.parent / "kb-builder" / "scripts"
sys.path.insert(0, str(_KB_BUILDER_SCRIPTS))
from storage import KBStorage, slug_email  # noqa: E402

TIER_ORDER = ["public", "internal", "department-only", "exec-only", "confidential"]


def user_ceiling(user_groups: set[str]) -> str:
    has_lf = bool(user_groups & {"legal-finance@", "legal@", "finance@"})
    has_exec = bool(user_groups & {"exec@", "leadership@"}) or has_lf
    if has_lf:
        return "confidential"
    if has_exec:
        return "exec-only"
    return "internal"


def access_allowed(classification: str, audience: list[str], user_groups: set[str]) -> bool:
    if classification not in TIER_ORDER:
        # Unknown tier -> be safe, refuse.
        return False
    ceiling = user_ceiling(user_groups)
    if classification == "department-only":
        dept_groups = {g.lower() for g in user_groups}
        for dept in audience or []:
            d = str(dept).lower()
            if d in dept_groups or f"{d}@" in dept_groups:
                return True
        return False
    return TIER_ORDER.index(classification) <= TIER_ORDER.index(ceiling)


def read_preflight(store: KBStorage) -> dict[str, Any]:
    """Return parsed _meta/preflight.md frontmatter, or {} if absent/unreadable."""
    try:
        fm, _body = store.read("_meta/preflight.md")
        return fm or {}
    except Exception:
        return {}


def resolve_name(store: KBStorage, user_email: str) -> str:
    """Prefer _meta/team/{slug}.md frontmatter name; fall back to local-part of email."""
    slug = slug_email(user_email)
    candidates = [f"_meta/team/{slug}.md", f"_meta/team/{user_email}.md"]
    for path in candidates:
        try:
            if store.exists(path):
                fm, _body = store.read(path)
                name = (fm or {}).get("name")
                if name:
                    return str(name)
        except Exception:
            continue
    return user_email.split("@", 1)[0]


def _load_aliases(store: KBStorage, user_email: str) -> list[str]:
    """Return user aliases from _meta/team/{slug}.md frontmatter, if any.

    Aliases let nicknames ('TJ', 'T.M.') match in page bodies alongside the
    canonical name — useful when team notes call someone something short that
    normal name detection would miss.
    """
    slug = slug_email(user_email)
    for path in (f"_meta/team/{slug}.md", f"_meta/team/{user_email}.md"):
        try:
            if store.exists(path):
                fm, _body = store.read(path)
                aliases = (fm or {}).get("aliases") or []
                if isinstance(aliases, list):
                    return [str(a).strip() for a in aliases if str(a).strip()]
        except Exception:
            continue
    return []


# --- mention detection -------------------------------------------------------


def _as_list(val: Any) -> list[str]:
    if val is None:
        return []
    if isinstance(val, list):
        return [str(v) for v in val]
    return [str(val)]


def _whole_word_search(haystack: str, needle: str) -> bool:
    if not needle or len(needle) < 2:
        return False
    pattern = r"\b" + re.escape(needle) + r"\b"
    return bool(re.search(pattern, haystack, re.IGNORECASE))


def _name_safe_for_body_match(name: str) -> bool:
    """Gate body matches on names with a space OR at least 5 characters.

    Prevents false positives on short English local-parts that also mean
    ordinary words (`may`, `will`, `bill`, `can`, `mark`, `dan`). A name like
    "Tyler" (5 chars) or "T.M." (multi-part) is safe to whole-word match; a
    name like "may" is not.
    """
    if not name:
        return False
    if " " in name:
        return True
    return len(name) >= 5


def detect_mention(
    *,
    rel_path: str,
    frontmatter: dict[str, Any],
    body: str,
    user_email: str,
    user_name: str,
    aliases: list[str] | None = None,
) -> tuple[bool, str, bool, bool]:
    """Return (mentioned, reason, is_owner, is_transcript).

    `reason` is the first matching signal — short string for the output table.
    `is_owner` is True when the user is owner / created_by.
    `is_transcript` is True when the path sits under interviews/ or transcripts/.
    """
    email_lc = user_email.lower()
    email_slug = slug_email(user_email)
    path_lc = rel_path.lower()
    aliases = aliases or []

    is_transcript = (
        "/interviews/" in f"/{path_lc}"
        or path_lc.startswith("interviews/")
        or "/transcripts/" in f"/{path_lc}"
        or path_lc.startswith("transcripts/")
    )

    fm = frontmatter or {}
    owner = str(fm.get("owner", "")).lower()
    created_by = str(fm.get("created_by", "")).lower()
    last_edited_by = str(fm.get("last_edited_by", "")).lower()
    is_owner = owner == email_lc or created_by == email_lc

    if owner == email_lc:
        return True, "owner", True, is_transcript
    if created_by == email_lc:
        return True, "created by you", True, is_transcript
    if last_edited_by == email_lc:
        return True, "last edited by you", False, is_transcript

    for field in ("audience", "informal_goto_for"):
        values = [v.lower() for v in _as_list(fm.get(field))]
        if email_lc in values:
            return True, f"in frontmatter.{field}", False, is_transcript
        if user_name and user_name.lower() in values:
            return True, f"in frontmatter.{field}", False, is_transcript

    for sa in _as_list(fm.get("source_artifacts")):
        if email_slug in sa.lower() or email_lc in sa.lower():
            return True, "source artifact references you", False, is_transcript

    if email_slug and email_slug in path_lc:
        return True, "path references you", False, is_transcript

    body_lc = body.lower() if body else ""
    if body_lc and email_lc in body_lc:
        return True, "email in body", False, is_transcript

    # Body-name matches gate on multi-word-or-len>=5 to prevent false positives
    # on short English local-parts (may, will, bill, dan, can, mark).
    if body and user_name and _name_safe_for_body_match(user_name):
        if _whole_word_search(body, user_name):
            return True, f"name '{user_name}' in body", False, is_transcript

    for alias in aliases:
        if not alias or not _name_safe_for_body_match(alias):
            continue
        if body and _whole_word_search(body, alias):
            return True, f"alias '{alias}' in body", False, is_transcript

    return False, "", False, is_transcript


# --- walk --------------------------------------------------------------------


def walk_kb(
    store: KBStorage,
    user_email: str,
    user_name: str,
    user_groups: set[str],
    aliases: list[str] | None = None,
) -> list[dict[str, Any]]:
    matches: list[dict[str, Any]] = []
    aliases = aliases or []
    for abs_path in store.find("", "*.md"):
        try:
            rel = abs_path.relative_to(store.root).as_posix()
        except ValueError:
            continue
        # Skip the build log itself; it's an audit artifact not a KB page.
        if rel.startswith("_meta/build-log/"):
            continue
        # Skip _raw/ — un-redacted source material must never surface via DSAR.
        if rel.startswith("_raw/"):
            continue
        try:
            fm, body = store.read(rel)
        except Exception:
            continue

        mentioned, reason, is_owner, is_transcript = detect_mention(
            rel_path=rel,
            frontmatter=fm,
            body=body,
            user_email=user_email,
            user_name=user_name,
            aliases=aliases,
        )
        if not mentioned:
            continue

        classification = str((fm or {}).get("classification") or "internal")
        audience = _as_list((fm or {}).get("audience"))
        if not access_allowed(classification, audience, user_groups):
            # Classification-aware read filter: do not surface pages the user
            # can't read. Surfacing them would itself be a classification bypass.
            continue

        matches.append(
            {
                "path": rel,
                "type": str((fm or {}).get("type") or "Unknown"),
                "classification": classification,
                "last_edited": str((fm or {}).get("last_edited") or (fm or {}).get("last_verified") or ""),
                "owner": str((fm or {}).get("owner") or ""),
                "created_by": str((fm or {}).get("created_by") or ""),
                "reason": reason,
                "is_owner": is_owner,
                "is_transcript": is_transcript,
                "audience": audience,
            }
        )

    matches.sort(key=lambda m: m["path"])
    return matches


# --- CLI ---------------------------------------------------------------------


def main() -> int:
    parser = argparse.ArgumentParser(description="Prescyent KB compliance walker (read-only).")
    parser.add_argument("--user-email", required=True)
    parser.add_argument("--user-groups", default="", help="Comma-separated group memberships")
    parser.add_argument("--kb-root-label", default=None, help="Override KB root label")
    args = parser.parse_args()

    kb_root_label = (
        args.kb_root_label
        or os.environ.get("CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL")
        or "prescyent-kb"
    )
    user_groups = {g.strip() for g in args.user_groups.split(",") if g.strip()}

    store = KBStorage(kb_root_label)
    preflight = read_preflight(store)
    champion_email = ""
    champ = preflight.get("champion_user")
    if isinstance(champ, dict):
        champion_email = str(champ.get("email") or "")
    company_slug = str(preflight.get("company_slug") or "")
    company_name = str(preflight.get("company_name") or "")

    resolved_name = resolve_name(store, args.user_email)
    aliases = _load_aliases(store, args.user_email)
    is_champion = champion_email.lower() == args.user_email.lower() if champion_email else False
    matches = walk_kb(store, args.user_email, resolved_name, user_groups, aliases=aliases)

    payload = {
        "user_email": args.user_email,
        "user_name": resolved_name,
        "kb_root": str(store.root),
        "kb_root_label": kb_root_label,
        "champion_email": champion_email,
        "is_champion": is_champion,
        "user_ceiling": user_ceiling(user_groups),
        "company_slug": company_slug,
        "company_name": company_name,
        "pages": matches,
    }
    print(json.dumps(payload, indent=2))
    return 0


if __name__ == "__main__":
    sys.exit(main())
