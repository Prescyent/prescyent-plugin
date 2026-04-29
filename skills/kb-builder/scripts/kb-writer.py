#!/usr/bin/env python3
"""kb-writer.py — the single funnel every KB write passes through.

Pipeline (strict order):
    identity assertion log -> redact (Haiku) -> regex post-scan -> classify
    (Opus, with source metadata) -> source-path floor -> access check -> path
    ACL -> merge frontmatter -> write via KBStorage -> log to per-user JSONL.

Every error path also writes a JSONL log entry. Nothing about a write — success
or failure — should ever be invisible.

No subagent dispatch. Subagents can't be invoked from a Python script
called via Bash, and nested subagent spawning is prohibited by the runtime.
All LLM calls are inline `anthropic.messages.create` calls.
"""

from __future__ import annotations

import argparse
import datetime as _dt
import fcntl
import json
import os
import re
import sys
from pathlib import Path
from typing import Any

# storage.py is a sibling file; import from the same directory.
sys.path.insert(0, str(Path(__file__).resolve().parent))
from storage import (  # noqa: E402
    ConflictDetected,
    KBStorage,
    KBStorageError,
    WritePermissionDenied,
    slug_email,
)


# Tier ordering — index = access level. Bumping "up" means higher index.
TIER_ORDER = ["public", "internal", "department-only", "exec-only", "confidential"]

# Envelope fields kb-writer is responsible for populating / enforcing.
ENVELOPE_REQUIRED = [
    "id",
    "title",
    "type",
    "owner",
    "confidence",
    "source_artifacts",
    "last_verified",
    "review_cycle_days",
    "created_by",
]

# Fields the script adds or overwrites on every write.
WRITER_CONTROLLED = [
    "classification",
    "audience",
    "redactions_applied",
    "classification_decided_by",
    "status",
    "last_edited_by",
]

# Source path prefixes that force a minimum classification tier regardless of
# body text. Protects against prompt-injection down-tiering of HRIS / finance /
# legal connector dumps.
SOURCE_PATH_FLOORS: list[tuple[str, str]] = [
    ("_raw/connector-dumps/hris/", "exec-only"),
    ("_raw/connector-dumps/finance/", "confidential"),
    ("_raw/connector-dumps/legal/", "confidential"),
]

# Deterministic regex safety net. Run AFTER Haiku returns. If any pattern fires
# the write is refused — we do NOT trust Haiku to have caught everything.
PII_POST_SCAN_PATTERNS = {
    "ssn": re.compile(r"\b\d{3}-\d{2}-\d{4}\b"),
    "phone_us": re.compile(r"\b(?:\+?1[-.\s]?)?\(?\d{3}\)?[-.\s]?\d{3}[-.\s]?\d{4}\b"),
    "email": re.compile(r"\b[A-Za-z0-9._%+-]+@[A-Za-z0-9.-]+\.[A-Za-z]{2,}\b"),
    # Loose credit-card catcher — gated by Luhn below to cut false positives.
    "cc_16": re.compile(r"\b(?:\d[ -]*?){13,19}\b"),
    "iban": re.compile(r"\b[A-Z]{2}\d{2}[A-Z0-9]{10,30}\b"),
}


class PipelineAbort(Exception):
    """Raised when a pipeline step fails unrecoverably. `code` is the exit code."""

    def __init__(self, code: int, status: str, message: str, extra: dict | None = None):
        super().__init__(message)
        self.code = code
        self.status = status
        self.message = message
        self.extra = extra or {}


# ---------------------------------------------------------------------------
# Access control
# ---------------------------------------------------------------------------


def user_ceiling(user_groups: set[str]) -> str:
    """Highest tier the user is allowed to write to.

    Allow-list defaults: empty groups == employee with no elevated access ==
    `internal` ceiling. We refuse to silently promote an anonymous caller into
    tiers that would leak.
    """
    has_legal_finance = bool(user_groups & {"legal-finance@", "legal@", "finance@"})
    has_exec = bool(user_groups & {"exec@", "leadership@"}) or has_legal_finance
    if has_legal_finance:
        return "confidential"
    if has_exec:
        return "exec-only"
    # department-only check handled per-audience (see access_allowed).
    return "internal"


def access_allowed(
    classification: str, audience: list[str], user_groups: set[str]
) -> tuple[bool, str]:
    """Check whether this user can write this page. Returns (ok, reason)."""
    if classification not in TIER_ORDER:
        return False, f"unknown classification {classification!r}"
    ceiling = user_ceiling(user_groups)
    if classification == "department-only":
        # Department pages need the user to be in that specific department group.
        dept_groups = {g.lower() for g in user_groups}
        for dept in audience:
            if dept.lower() in dept_groups or f"{dept.lower()}@" in dept_groups:
                return True, "department match"
        return False, f"user not in any of departments {audience}"
    if TIER_ORDER.index(classification) <= TIER_ORDER.index(ceiling):
        return True, "within ceiling"
    return False, f"ceiling={ceiling} < classification={classification}"


def suggest_alternative(classification: str, ceiling: str) -> str:
    """Nudge the caller toward a tier they CAN write. Never widens beyond ceiling."""
    if TIER_ORDER.index(classification) <= TIER_ORDER.index(ceiling):
        return classification
    return ceiling


def source_path_floor(source_artifacts: list[str] | None) -> str | None:
    """Return the highest (most restrictive) floor tier for any source path match, or None."""
    floors: list[str] = []
    for artifact in source_artifacts or []:
        if not isinstance(artifact, str):
            continue
        for prefix, tier in SOURCE_PATH_FLOORS:
            if prefix in artifact:
                floors.append(tier)
    if not floors:
        return None
    return max(floors, key=TIER_ORDER.index)


def check_path_acl(
    path: str, user_email: str, champion_email: str | None
) -> str | None:
    """Return None if write allowed, or an error message if denied.

    Enforces:
      - `_meta/interviews/{email}/...` is writable only by `{email}` or champion.

    The segment is accepted in either raw-email or slug form — callers in the
    wild use both (`_meta/interviews/tyler@acme.com/...` AND
    `_meta/interviews/tyler-acme.com/...`).
    """
    if not path.startswith("_meta/interviews/"):
        return None
    parts = path.split("/", 3)
    # parts = ["_meta", "interviews", "{email-or-slug}", "rest..."]
    if len(parts) < 3 or not parts[2]:
        return None
    target_segment = parts[2]
    target_raw = target_segment.lower()
    target_slug = slug_email(target_segment)

    caller_raw = (user_email or "").lower()
    caller_slug = slug_email(user_email or "")

    if caller_raw == target_raw or caller_slug == target_slug:
        return None  # subject writing their own file — allowed.

    if champion_email:
        champ_raw = champion_email.lower()
        champ_slug = slug_email(champion_email)
        if caller_raw == champ_raw or caller_slug == champ_slug:
            return None  # champion override — allowed.

    return (
        f"Path ACL denied: _meta/interviews/{target_segment}/ is writable only by "
        f"{target_segment} or the champion. Current user: {user_email}."
    )


# ---------------------------------------------------------------------------
# Regex post-scan
# ---------------------------------------------------------------------------


def _luhn_valid(num: str) -> bool:
    digits = [int(c) for c in re.sub(r"\D", "", num)]
    if not 13 <= len(digits) <= 19:
        return False
    checksum = 0
    for i, d in enumerate(reversed(digits)):
        if i % 2 == 1:
            d *= 2
            if d > 9:
                d -= 9
        checksum += d
    return checksum % 10 == 0


def pii_post_scan(content: str) -> list[str]:
    """Return list of category names where a PII pattern survived redaction."""
    hits: list[str] = []
    for name, pattern in PII_POST_SCAN_PATTERNS.items():
        for match in pattern.finditer(content):
            if name == "cc_16" and not _luhn_valid(match.group()):
                continue
            hits.append(name)
            break  # one hit per category is enough
    return hits


# ---------------------------------------------------------------------------
# LLM calls (Anthropic SDK, inline)
# ---------------------------------------------------------------------------


def _anthropic_client():
    # Lazy import — only fail if we actually need the SDK. --self-test can skip it.
    try:
        import anthropic
    except ImportError as exc:
        raise PipelineAbort(
            3,
            "sdk_missing",
            "anthropic SDK not installed (pip install anthropic)",
        ) from exc
    if not os.environ.get("ANTHROPIC_API_KEY"):
        raise PipelineAbort(
            3,
            "api_key_missing",
            "ANTHROPIC_API_KEY not set; refusing to continue",
        )
    return anthropic.Anthropic()


def _load_prompt(name: str) -> str:
    # Prompts live alongside the script under references/.
    base = Path(__file__).resolve().parent.parent / "references"
    return (base / name).read_text(encoding="utf-8")


def _extract_json(text: str) -> dict:
    """Pull the first JSON object out of the response. Models occasionally wrap
    JSON in fences or add a short preamble; the retry path handles true failures."""
    text = text.strip()
    if text.startswith("```"):
        text = re.sub(r"^```(?:json)?\s*", "", text)
        text = re.sub(r"\s*```$", "", text)
    start = text.find("{")
    end = text.rfind("}")
    if start == -1 or end == -1 or end <= start:
        raise ValueError("no JSON object in response")
    return json.loads(text[start : end + 1])


def call_redactor(content: str, client) -> dict:
    prompt = _load_prompt("redactor-prompt.md")
    # Two-attempt pattern: first call, then one retry with a stricter reminder
    # if the model strayed from JSON-only output.
    for attempt in range(2):
        user_msg = content if attempt == 0 else (
            content + "\n\n[REMINDER: respond with JSON only, no prose, no fences.]"
        )
        resp = client.messages.create(
            model="claude-haiku-4-5",
            max_tokens=4096,
            system=prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text if resp.content else ""
        try:
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        if "redacted_content" not in data or "redactions_applied" not in data:
            continue
        return data
    raise PipelineAbort(3, "redactor_parse_failure", "redactor returned unparseable output after 2 attempts")


def call_classifier(
    content: str, source_artifacts: list[str] | None, client
) -> dict:
    prompt = _load_prompt("classifier-prompt.md")
    # Pass source_artifacts as structured context alongside the body so the
    # classifier can apply source-metadata signals. The deterministic floor in
    # `source_path_floor` still overrides the classifier if it under-tiers.
    sources_block = json.dumps(source_artifacts or [])
    body_block = (
        f"source_artifacts: {sources_block}\n\n"
        f"---\n\n"
        f"{content}"
    )
    for attempt in range(2):
        user_msg = body_block if attempt == 0 else (
            body_block + "\n\n[REMINDER: respond with JSON only, no prose, no fences.]"
        )
        resp = client.messages.create(
            model="claude-opus-4-7",
            max_tokens=2048,
            system=prompt,
            messages=[{"role": "user", "content": user_msg}],
        )
        raw = resp.content[0].text if resp.content else ""
        try:
            data = _extract_json(raw)
        except (ValueError, json.JSONDecodeError):
            continue
        if not {"classification", "audience", "confidence"}.issubset(data):
            continue
        if data["classification"] not in TIER_ORDER:
            continue
        return data
    raise PipelineAbort(4, "classifier_parse_failure", "classifier returned unparseable output after 2 attempts")


def bump_on_low_confidence(classification: str, confidence: float) -> tuple[str, bool]:
    """Bump tier up on low confidence — security default prefers false positive
    over leak. Returns (new_classification, was_bumped)."""
    if confidence >= 0.9:
        return classification, False
    idx = TIER_ORDER.index(classification)
    if idx + 1 < len(TIER_ORDER):
        return TIER_ORDER[idx + 1], True
    return classification, False


# ---------------------------------------------------------------------------
# Logging
# ---------------------------------------------------------------------------


def _log_dir(store: KBStorage) -> Path:
    return store.root / "_meta" / "build-log"


def log_event(store: KBStorage, user_email: str, payload: dict) -> None:
    # Append-only per-user-per-day log, flock-guarded so concurrent kb-writer
    # runs can't interleave half-lines. Never raise from here — logging must not
    # mask or replace the real pipeline error.
    try:
        today = _dt.date.today().isoformat()
        log_path = _log_dir(store) / f"{today}-{slug_email(user_email)}.jsonl"
        log_path.parent.mkdir(parents=True, exist_ok=True)
        line = json.dumps({"timestamp": _dt.datetime.utcnow().isoformat() + "Z", **payload})
        with log_path.open("a", encoding="utf-8") as fh:
            fcntl.flock(fh.fileno(), fcntl.LOCK_EX)
            try:
                fh.write(line + "\n")
            finally:
                fcntl.flock(fh.fileno(), fcntl.LOCK_UN)
    except Exception as exc:  # noqa: BLE001 — logging is best-effort
        sys.stderr.write(f"[kb-writer] warning: log write failed: {exc}\n")


def _read_champion_from_preflight(store: KBStorage) -> str | None:
    """Best-effort read of champion email from `_meta/preflight.md`.

    Never raises — a missing preflight just means we can't grant champion
    override on path ACL. The caller continues with champion_email=None.
    """
    try:
        fm, _body = store.read("_meta/preflight.md")
    except Exception:  # noqa: BLE001 — preflight is optional
        return None
    if not isinstance(fm, dict):
        return None
    champ = fm.get("champion_email") or fm.get("user_email")
    if isinstance(champ, str) and "@" in champ:
        return champ
    champ_user = fm.get("champion_user")
    if isinstance(champ_user, dict):
        email = champ_user.get("email")
        if isinstance(email, str) and "@" in email:
            return email
    return None


# ---------------------------------------------------------------------------
# Pipeline
# ---------------------------------------------------------------------------


def validate_frontmatter(fm: dict) -> None:
    if not isinstance(fm, dict):
        raise PipelineAbort(2, "frontmatter_invalid", "frontmatter must be a JSON object")
    missing = [f for f in ENVELOPE_REQUIRED if not fm.get(f)]
    if missing:
        raise PipelineAbort(
            2, "frontmatter_invalid", f"missing required fields: {missing}"
        )


def run_pipeline(
    *,
    kb_path: str,
    content: str,
    frontmatter: dict,
    user_email: str,
    user_groups: set[str],
    kb_root_label: str,
    skip_classifier: bool = False,
    skip_redactor: bool = False,
) -> dict:
    validate_frontmatter(frontmatter)

    store = KBStorage(kb_root_label)

    # Step 0 — identity assertion. Logged BEFORE any pipeline work so even a
    # later crash leaves a record of who claimed what. Spoofing leaves a trail.
    log_event(store, user_email, {
        "user": user_email,
        "event": "identity_assertion",
        "claimed_email": user_email,
        "claimed_groups": sorted(user_groups or []),
        "path": kb_path,
        "pid": os.getpid(),
        "cwd": str(Path.cwd()),
    })

    source_artifacts = list(frontmatter.get("source_artifacts") or [])

    # Step 1 — redact. Skip only in self-test paths (CLAUDE_PLUGIN_TEST=1 gated
    # at the CLI); never in production.
    if skip_redactor:
        redacted = content
        redactions: list[str] = []
    else:
        client = _anthropic_client()
        try:
            r = call_redactor(content, client)
        except PipelineAbort as exc:
            log_event(store, user_email, {
                "user": user_email, "path": kb_path, "status": exc.status,
                "error": exc.message, "redactions_count": 0, "bytes_written": 0,
            })
            raise
        redacted = r["redacted_content"]
        redactions = list(r["redactions_applied"])

        # Step 1b — deterministic regex safety net. Haiku can be tricked (prompt
        # injection, adversarial inputs) into leaving PII verbatim. Fail closed
        # if any high-signal pattern survived redaction.
        hits = pii_post_scan(redacted)
        if hits:
            log_event(store, user_email, {
                "user": user_email, "path": kb_path,
                "status": "redactor_post_scan_failure",
                "categories": hits, "redactions_count": len(redactions),
                "bytes_written": 0,
            })
            raise PipelineAbort(
                3,
                "redactor_post_scan_failure",
                f"redactor missed PII categories {hits}; write refused",
                extra={"categories": hits},
            )

    # Step 2 — classify on the redacted content. The classifier must never see
    # the un-redacted original. Pass source_artifacts so the classifier can
    # reason over source signals alongside body text.
    if skip_classifier:
        classification = frontmatter.get("classification") or "internal"
        audience = list(frontmatter.get("audience") or ["all"])
        confidence = 1.0
        bumped = False
    else:
        client = _anthropic_client()
        try:
            c = call_classifier(redacted, source_artifacts, client)
        except PipelineAbort as exc:
            log_event(store, user_email, {
                "user": user_email, "path": kb_path, "status": exc.status,
                "error": exc.message, "redactions_count": len(redactions),
                "bytes_written": 0,
            })
            raise
        classification = c["classification"]
        audience = list(c["audience"])
        confidence = float(c["confidence"])
        classification, bumped = bump_on_low_confidence(classification, confidence)

    # Step 2b — source-path floor. Connector dumps from HRIS / finance / legal
    # get a hard minimum tier regardless of what the classifier said. This is
    # the deterministic backstop against prompt-injection down-tiering.
    classification_decided_by = "kb-writer-opus"
    floor = source_path_floor(source_artifacts)
    if floor is not None:
        floor_idx = TIER_ORDER.index(floor)
        current_idx = TIER_ORDER.index(classification)
        if current_idx < floor_idx:
            classification = floor
            classification_decided_by = "source-path-floor"
            # Narrow audience when we forced a tier up — safer default than
            # inheriting the classifier's wider audience.
            if classification == "exec-only":
                audience = ["exec"]
            elif classification == "confidential":
                # Best-guess group from the first matching prefix.
                for artifact in source_artifacts:
                    if isinstance(artifact, str) and "/hris/" in artifact:
                        audience = ["exec", "hr"]
                        break
                    if isinstance(artifact, str) and "/finance/" in artifact:
                        audience = ["finance"]
                        break
                    if isinstance(artifact, str) and "/legal/" in artifact:
                        audience = ["legal"]
                        break

    # Step 3 — access check. Refuse writes the caller can't read back.
    ok, reason = access_allowed(classification, audience, user_groups)
    if not ok:
        ceiling = user_ceiling(user_groups)
        suggestion = suggest_alternative(classification, ceiling)
        log_event(store, user_email, {
            "user": user_email, "path": kb_path, "status": "access_denied",
            "classification": classification, "audience": audience,
            "reason": reason, "suggested_tier": suggestion,
            "redactions_count": len(redactions), "bytes_written": 0,
        })
        raise PipelineAbort(
            5, "access_denied",
            f"user cannot write {classification}: {reason}",
            extra={
                "classification": classification, "audience": audience,
                "suggested_tier": suggestion, "user_ceiling": ceiling,
            },
        )

    # Step 3b — path ACL. Interview transcripts live at
    # `_meta/interviews/{email}/...` and MUST NOT be written by any user other
    # than the subject or the champion — consent is a code-backed promise.
    champion_email = _read_champion_from_preflight(store)
    acl_error = check_path_acl(kb_path, user_email, champion_email)
    if acl_error:
        log_event(store, user_email, {
            "user": user_email, "path": kb_path, "status": "path_acl_denied",
            "detail": acl_error, "redactions_count": len(redactions),
            "bytes_written": 0,
        })
        raise PipelineAbort(5, "path_acl_denied", acl_error)

    # Step 4 — merge writer-controlled fields into the incoming frontmatter.
    # Caller-provided values for these fields are overwritten; the single funnel
    # owns classification state so downstream agents can't smuggle in overrides.
    merged = dict(frontmatter)
    merged["classification"] = classification
    merged["audience"] = audience
    merged["redactions_applied"] = redactions
    merged["classification_decided_by"] = classification_decided_by
    merged.setdefault("status", "draft")
    merged["last_edited_by"] = user_email

    # Step 5 — write. Storage layer handles conflict-copy detection and ACL errors.
    try:
        written_path = store.write(kb_path, redacted, merged)
    except ConflictDetected as exc:
        log_event(store, user_email, {
            "user": user_email, "path": kb_path, "status": "conflict_copy",
            "error": str(exc), "classification": classification,
            "redactions_count": len(redactions), "bytes_written": 0,
        })
        raise PipelineAbort(6, "conflict_copy", str(exc)) from exc
    except WritePermissionDenied as exc:
        log_event(store, user_email, {
            "user": user_email, "path": kb_path, "status": "write_failure",
            "error": str(exc), "classification": classification,
            "redactions_count": len(redactions), "bytes_written": 0,
        })
        raise PipelineAbort(7, "write_failure", str(exc)) from exc
    except Exception as exc:
        log_event(store, user_email, {
            "user": user_email, "path": kb_path, "status": "write_failure",
            "error": str(exc), "classification": classification,
            "redactions_count": len(redactions), "bytes_written": 0,
        })
        raise PipelineAbort(7, "write_failure", str(exc)) from exc

    bytes_written = written_path.stat().st_size if written_path.exists() else 0
    log_event(store, user_email, {
        "user": user_email, "path": kb_path, "status": "written",
        "classification": classification, "audience": audience,
        "classification_decided_by": classification_decided_by,
        "redactions_count": len(redactions),
        "confidence_bumped": bumped, "bytes_written": bytes_written,
    })

    return {
        "status": "written",
        "path": str(written_path),
        "classification": classification,
        "audience": audience,
        "classification_decided_by": classification_decided_by,
        "redactions_count": len(redactions),
        "redactions_applied": redactions,
        "confidence_bumped": bumped,
    }


# ---------------------------------------------------------------------------
# Self-test
# ---------------------------------------------------------------------------


def _self_test() -> int:
    # Self-test may use --skip-* flags; they are test-only and gated behind
    # CLAUDE_PLUGIN_TEST=1. Set it here so the test itself isn't refused.
    os.environ["CLAUDE_PLUGIN_TEST"] = "1"

    # Synthetic fixtures that exercise the load-bearing pipeline branches:
    # normal write, PII redaction, access denial, regex post-scan backstop,
    # source-path floor, and path ACL. Uses a temp KB root so the real user
    # KB is never touched.
    import tempfile

    with tempfile.TemporaryDirectory() as tmp:
        os.environ["HOME"] = tmp  # forces KBStorage fallback into tmp
        kb_root = "prescyent-kb-selftest"

        base_fm = {
            "id": "test.process.selftest",
            "title": "selftest page",
            "type": "Process",
            "owner": "test@acme.com",
            "confidence": "high",
            "source_artifacts": ["synthetic://selftest"],
            "last_verified": "2026-04-24",
            "review_cycle_days": 90,
            "created_by": "test@acme.com",
        }

        has_api = bool(os.environ.get("ANTHROPIC_API_KEY"))

        results: list[tuple[str, bool, str]] = []

        # Case 1 — plain internal content, no PII, classifier picks internal.
        try:
            if has_api:
                out = run_pipeline(
                    kb_path="_meta/selftest-1.md",
                    content="The sales team uses HubSpot to track deals.",
                    frontmatter=dict(base_fm, id="test.selftest.1"),
                    user_email="test@acme.com",
                    user_groups=set(),
                    kb_root_label=kb_root,
                )
                ok = out["status"] == "written" and out["classification"] in {"public", "internal"}
                results.append(("plain internal content writes successfully", ok, str(out)))
            else:
                out = run_pipeline(
                    kb_path="_meta/selftest-1.md",
                    content="The sales team uses HubSpot to track deals.",
                    frontmatter=dict(base_fm, id="test.selftest.1", classification="internal", audience=["all"]),
                    user_email="test@acme.com",
                    user_groups=set(),
                    kb_root_label=kb_root,
                    skip_classifier=True, skip_redactor=True,
                )
                ok = out["status"] == "written"
                results.append(("plain internal content writes successfully (skip-llm)", ok, str(out)))
        except Exception as exc:
            results.append(("plain internal content writes successfully", False, f"ERROR: {exc}"))

        # Case 2 — planted PII. Redactor must strip it before the page lands.
        try:
            if has_api:
                out = run_pipeline(
                    kb_path="_meta/selftest-2.md",
                    content="Onboarding doc: send W-9 with SSN 123-45-6789 to accounting@acme.com.",
                    frontmatter=dict(base_fm, id="test.selftest.2"),
                    user_email="test@acme.com",
                    user_groups=set(),
                    kb_root_label=kb_root,
                )
                written_body = Path(out["path"]).read_text(encoding="utf-8")
                ok = "123-45-6789" not in written_body and out["redactions_count"] > 0
                results.append(("planted PII is redacted before write", ok, f"redactions={out['redactions_applied']}"))
            else:
                results.append(("planted PII is redacted before write", True, "SKIPPED (no ANTHROPIC_API_KEY)"))
        except Exception as exc:
            results.append(("planted PII is redacted before write", False, f"ERROR: {exc}"))

        # Case 3 — exec-only content, user with no elevated groups. Must refuse.
        try:
            if has_api:
                try:
                    run_pipeline(
                        kb_path="_meta/selftest-3.md",
                        content="Q3 board meeting: finalize the layoff plan. Target: 15% reduction across engineering and sales.",
                        frontmatter=dict(base_fm, id="test.selftest.3"),
                        user_email="junior@acme.com",
                        user_groups=set(),  # no elevated groups = internal ceiling
                        kb_root_label=kb_root,
                    )
                    results.append(("exec-only content denied for junior user", False, "pipeline did not raise"))
                except PipelineAbort as exc:
                    ok = exc.status == "access_denied"
                    results.append(("exec-only content denied for junior user", ok, f"status={exc.status} suggestion={exc.extra.get('suggested_tier')}"))
            else:
                # Without an API, simulate the access check directly.
                ok_allowed, _reason = access_allowed("exec-only", ["exec"], set())
                ok = not ok_allowed
                results.append(("exec-only content denied for junior user (access_allowed unit)", ok, "simulated"))
        except Exception as exc:
            results.append(("exec-only content denied for junior user", False, f"ERROR: {exc}"))

        # Case 4 — regex post-scan backstop. Haiku pretends the SSN isn't there.
        try:
            hits = pii_post_scan("Employee SSN on file: 987-65-4321. Keep on record.")
            ok = "ssn" in hits
            results.append(("pii_post_scan catches SSN in post-redaction body", ok, f"hits={hits}"))
        except Exception as exc:
            results.append(("pii_post_scan catches SSN in post-redaction body", False, f"ERROR: {exc}"))

        # Case 5 — source-path floor forces tier up.
        try:
            floor = source_path_floor(["_raw/connector-dumps/hris/employees.csv"])
            ok = floor == "exec-only"
            results.append(("source_path_floor hris -> exec-only", ok, f"floor={floor}"))
        except Exception as exc:
            results.append(("source_path_floor hris -> exec-only", False, f"ERROR: {exc}"))

        try:
            floor = source_path_floor(["_raw/connector-dumps/finance/cap-table.xlsx"])
            ok = floor == "confidential"
            results.append(("source_path_floor finance -> confidential", ok, f"floor={floor}"))
        except Exception as exc:
            results.append(("source_path_floor finance -> confidential", False, f"ERROR: {exc}"))

        # Case 6 — source-path floor integration: skip-classifier would pick
        # "internal" but the floor must force exec-only.
        try:
            out = run_pipeline(
                kb_path="_raw/connector-dumps/hris/employees.md",
                content="Full HRIS dump, no body-level markers.",
                frontmatter=dict(
                    base_fm,
                    id="test.selftest.hris",
                    classification="internal",
                    audience=["all"],
                    source_artifacts=["_raw/connector-dumps/hris/employees.csv"],
                ),
                user_email="exec@acme.com",
                user_groups={"exec@"},
                kb_root_label=kb_root,
                skip_classifier=True,
                skip_redactor=True,
            )
            ok = (
                out["classification"] == "exec-only"
                and out["classification_decided_by"] == "source-path-floor"
            )
            results.append((
                "source-path floor forces hris dump to exec-only",
                ok,
                f"classification={out['classification']} decided_by={out['classification_decided_by']}",
            ))
        except Exception as exc:
            results.append((
                "source-path floor forces hris dump to exec-only",
                False,
                f"ERROR: {exc}",
            ))

        # Case 7 — path ACL denies cross-user interview write.
        try:
            try:
                run_pipeline(
                    kb_path="_meta/interviews/other@corp.com/session.md",
                    content="Interview notes.",
                    frontmatter=dict(
                        base_fm,
                        id="test.selftest.acl",
                        classification="internal",
                        audience=["all"],
                    ),
                    user_email="tyler@corp.com",
                    user_groups=set(),
                    kb_root_label=kb_root,
                    skip_classifier=True,
                    skip_redactor=True,
                )
                results.append(("path ACL denies cross-user interview write", False, "pipeline did not raise"))
            except PipelineAbort as exc:
                ok = exc.status == "path_acl_denied" and exc.code == 5
                results.append((
                    "path ACL denies cross-user interview write",
                    ok,
                    f"status={exc.status} code={exc.code}",
                ))
        except Exception as exc:
            results.append(("path ACL denies cross-user interview write", False, f"ERROR: {exc}"))

        # Case 8 — CLAUDE_PLUGIN_TEST check: temporarily unset and verify CLI
        # refuses skip flags. We exercise the gate function directly below.
        try:
            prev = os.environ.pop("CLAUDE_PLUGIN_TEST", None)
            try:
                gated = _skip_flags_allowed()
            finally:
                if prev is not None:
                    os.environ["CLAUDE_PLUGIN_TEST"] = prev
            ok = gated is False
            results.append((
                "skip flags refused without CLAUDE_PLUGIN_TEST",
                ok,
                f"_skip_flags_allowed()={gated}",
            ))
        except Exception as exc:
            results.append((
                "skip flags refused without CLAUDE_PLUGIN_TEST",
                False,
                f"ERROR: {exc}",
            ))

        passed = sum(1 for _n, ok, _d in results if ok)
        for name, ok, detail in results:
            status = "PASS" if ok else "FAIL"
            print(f"  {status}  {name} — {detail}")
        print(f"\nRESULT: {passed}/{len(results)} passed")
        return 0 if passed == len(results) else 1


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------


def _skip_flags_allowed() -> bool:
    return os.environ.get("CLAUDE_PLUGIN_TEST") == "1"


def _emit_error(status: str, message: str, extra: dict | None = None) -> None:
    payload = {"status": status, "error": message}
    if extra:
        payload.update(extra)
    # Machine-readable JSON on stdout, plain sanitized message on stderr.
    print(json.dumps(payload))
    sys.stderr.write(f"[kb-writer] {status}: {message}\n")


def _user_error(message: str, recovery: str | None = None) -> None:
    """User-facing error writer — never leaks stack traces or absolute paths.

    Full detail (including paths + exception types) lives in the per-user JSONL.
    Stderr stays short so the plugin voice rules stay intact.
    """
    sys.stderr.write(f"ERROR: {message}\n")
    if recovery:
        sys.stderr.write(f"Recovery: {recovery}\n")


def main() -> int:
    parser = argparse.ArgumentParser(description="Prescyent KB single-funnel writer.")
    parser.add_argument("--path", help="KB-relative path to write (e.g., 01-company/about.md)")
    parser.add_argument("--content-file", help="Path to a file containing the proposed content")
    parser.add_argument("--frontmatter-json", help="JSON string of incoming frontmatter")
    parser.add_argument("--user-email", help="Email of the user initiating the write")
    parser.add_argument("--user-groups", default="", help="Comma-separated group memberships")
    parser.add_argument("--kb-root-label", default=None, help="Override KB root label")
    parser.add_argument("--skip-classifier", action="store_true", help="TEST ONLY — gated behind CLAUDE_PLUGIN_TEST=1")
    parser.add_argument("--skip-redactor", action="store_true", help="TEST ONLY — gated behind CLAUDE_PLUGIN_TEST=1")
    parser.add_argument("--self-test", action="store_true", help="Run the self-test harness")

    args = parser.parse_args()

    if args.self_test:
        return _self_test()

    # Gate test-only flags. Any caller without CLAUDE_PLUGIN_TEST=1 who passes
    # --skip-redactor or --skip-classifier is attempting to bypass the
    # redaction/classification safeguards. Loud refusal + exit 1.
    if args.skip_redactor or args.skip_classifier:
        if not _skip_flags_allowed():
            sys.stderr.write(
                "ERROR: --skip-redactor and --skip-classifier are test-only flags. "
                "Set CLAUDE_PLUGIN_TEST=1 to use them (self-test runs only).\n"
            )
            return 1

    # Argument validation — uniform exit code + JSON so callers can parse.
    for required in ("path", "content_file", "frontmatter_json", "user_email"):
        if not getattr(args, required):
            _emit_error("usage_error", f"missing required arg: --{required.replace('_', '-')}")
            return 1

    user_email = args.user_email
    user_groups = {g.strip() for g in args.user_groups.split(",") if g.strip()}

    # Identity display — first line of stderr on every run. Users see exactly
    # who the pipeline thinks they are; spoofing is visible, not silent.
    groups_display = ", ".join(sorted(user_groups)) if user_groups else "(none — ceiling: internal)"
    sys.stderr.write(f"kb-writer: Running as {user_email} with groups: {groups_display}\n")

    try:
        content = Path(args.content_file).read_text(encoding="utf-8")
    except OSError as exc:
        # Read error on the input file is a caller usage error, not an
        # internal crash — safe to surface `exc` here since the caller
        # supplied the path.
        _emit_error("usage_error", f"cannot read --content-file: {exc}")
        return 1

    try:
        frontmatter = json.loads(args.frontmatter_json)
    except json.JSONDecodeError as exc:
        _emit_error("usage_error", f"invalid --frontmatter-json: {exc}")
        return 1

    kb_root_label = (
        args.kb_root_label
        or os.environ.get("CLAUDE_PLUGIN_OPTION_KB_ROOT_LABEL")
        or "prescyent-kb"
    )

    try:
        result = run_pipeline(
            kb_path=args.path,
            content=content,
            frontmatter=frontmatter,
            user_email=user_email,
            user_groups=user_groups,
            kb_root_label=kb_root_label,
            skip_classifier=args.skip_classifier,
            skip_redactor=args.skip_redactor,
        )
    except PipelineAbort as exc:
        _emit_error(exc.status, exc.message, exc.extra)
        return exc.code
    except KBStorageError as exc:
        # Known storage error — sanitized, recovery nudge.
        try:
            store = KBStorage(kb_root_label)
            log_event(store, user_email, {
                "user": user_email, "path": args.path,
                "status": "storage_error",
                "type": type(exc).__name__, "message": str(exc),
            })
        except Exception:  # noqa: BLE001
            pass
        _user_error(
            "KB storage unavailable. "
            + type(exc).__name__
            + ": "
            + str(exc),
            recovery="See README for storage setup, then re-run.",
        )
        return 7
    except Exception as exc:  # noqa: BLE001 — belt + suspenders
        # Don't leak stack traces or absolute paths to stderr. Log full detail
        # to the JSONL audit trail for debugging.
        try:
            store = KBStorage(kb_root_label)
            log_event(store, user_email, {
                "user": user_email, "path": args.path,
                "status": "unhandled_exception",
                "type": type(exc).__name__, "message": str(exc),
            })
        except Exception:  # noqa: BLE001
            pass
        _user_error(
            "Unexpected error. Full detail in the audit log.",
            recovery="Re-run. If it repeats, check `_meta/build-log/`.",
        )
        return 99

    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
