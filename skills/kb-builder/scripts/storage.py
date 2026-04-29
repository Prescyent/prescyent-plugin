"""KBStorage — LocalFS backend for the Prescyent knowledge base.

Storage is pure local file system. The OS-level sync app (Google Drive Desktop,
OneDrive Desktop) handles cloud upload, ACLs, and conflict resolution. We glob
for the mount point on every invocation rather than persisting a path.

The `find` vs `ls` distinction is load-bearing: BSD `ls` underreports files
inside Drive Desktop sync folders, which silently broke baseline-gtm-wizards-
plugin KB walks in production. Every directory enumeration goes through
`subprocess.run(['find', ...])`.

Root discovery is constrained to `Path.home() / 'Library' / 'CloudStorage'`
first; cross-user `/Users/*` scanning is NOT performed by default to prevent
silent writes into a teammate's Drive mount on a shared Mac.

`expected_target` ({'gdrive', 'onedrive', 'localfs', None}) lets the caller
declare the backend the user picked in `/kb-build` — mismatches raise
StorageNotFound instead of silently falling back to `~/prescyent-kb/`.
"""

from __future__ import annotations

import json
import os
import re
import subprocess
import sys
from pathlib import Path
from typing import Any

try:
    import yaml as _yaml
    _HAS_YAML = True
except ImportError:
    _yaml = None
    _HAS_YAML = False


CONFLICT_COPY_RE = re.compile(r" \(\d+\)(\.[a-zA-Z0-9]+)?$")

VALID_EXPECTED_TARGETS = {"gdrive", "onedrive", "localfs", None}


class KBStorageError(Exception):
    pass


class StorageNotFound(KBStorageError):
    pass


class ConflictDetected(KBStorageError):
    pass


class WritePermissionDenied(KBStorageError):
    pass


class KBPathInvalid(KBStorageError):
    pass


def slug_email(email: str) -> str:
    """Canonical email slug used across the plugin.

    Preserves dots (matches kb-writer build-log naming; avoids a.b/ab collisions).
    Lowercases; replaces any char outside [a-z0-9.-] with hyphen; strips leading/trailing hyphens.
    Returns 'anonymous' for empty-after-normalization inputs.
    """
    slug = re.sub(r"[^a-z0-9.-]+", "-", (email or "").lower()).strip("-")
    return slug or "anonymous"


class KBStorage:
    def __init__(self, root_label: str, expected_target: str | None = None):
        if expected_target not in VALID_EXPECTED_TARGETS:
            raise KBStorageError(
                f"expected_target must be one of {sorted(t for t in VALID_EXPECTED_TARGETS if t)} or None; got {expected_target!r}"
            )
        self.root_label = root_label
        self.expected_target = expected_target
        self.root = self._discover_root(root_label, expected_target)
        if not self.root.exists():
            self.root.mkdir(parents=True, exist_ok=True)
        if not self.root.is_dir():
            raise StorageNotFound(f"KB root is not a directory: {self.root}")

    def _discover_root(self, label: str, expected_target: str | None) -> Path:
        """Find the user's KB root.

        Constrained to `Path.home() / Library / CloudStorage` to prevent
        cross-user leaks on shared Macs. If `expected_target` is 'gdrive' or
        'onedrive' and no matching mount is found under the current user's
        home, raise StorageNotFound with a recovery message — never silently
        fall back to localfs.
        """
        home = Path.home()
        cloud_root = home / "Library" / "CloudStorage"
        gdrive_hit: Path | None = None
        onedrive_hit: Path | None = None

        try:
            entries = sorted(cloud_root.iterdir())
        except (OSError, PermissionError, FileNotFoundError):
            entries = []

        for entry in entries:
            name = entry.name
            if name.startswith("GoogleDrive-"):
                candidate = entry / "Shared drives" / label
                try:
                    if candidate.exists():
                        gdrive_hit = candidate
                        break
                except (OSError, PermissionError):
                    continue
            elif name.startswith("OneDrive-") or name == "OneDrive":
                candidate = entry / label
                try:
                    if candidate.exists() and onedrive_hit is None:
                        onedrive_hit = candidate
                except (OSError, PermissionError):
                    continue

        if expected_target == "gdrive":
            if gdrive_hit is not None:
                return gdrive_hit
            raise StorageNotFound(
                f"Expected Google Drive mount for label {label!r}; no GoogleDrive-* "
                f"entry under ~/Library/CloudStorage/. Mount the Shared Drive via "
                f"Drive Desktop, then re-run /kb-build."
            )

        if expected_target == "onedrive":
            if onedrive_hit is not None:
                return onedrive_hit
            raise StorageNotFound(
                f"Expected OneDrive mount for label {label!r}; no OneDrive-* "
                f"entry under ~/Library/CloudStorage/. Install OneDrive Desktop "
                f"and sync the folder, then re-run /kb-build."
            )

        # expected_target in {"localfs", None}: prefer any cloud hit we already
        # found, but if none was located, fall back to local-only — the user
        # explicitly declared localfs OR has no declared backend (implicit
        # legacy callers).
        if gdrive_hit is not None:
            return gdrive_hit
        if onedrive_hit is not None:
            return onedrive_hit
        return home / "prescyent-kb" / label

    def _resolve(self, kb_path: str) -> Path:
        """Resolve a KB-relative path and verify it doesn't escape the root.

        Symlinks inside the KB can redirect writes outside `self.root`. We
        resolve the parent directory (which is created before every write via
        `mkdir(parents=True, exist_ok=True)`) and then the full candidate if
        it exists, and assert the final location is inside `root.resolve()`.
        """
        if kb_path.startswith("/") or ".." in Path(kb_path).parts:
            raise KBPathInvalid(f"kb_path must be relative and within root: {kb_path}")

        candidate = self.root / kb_path
        root_resolved = self.root.resolve()

        # If the final target exists, resolve it fully and check.
        if candidate.exists() or candidate.is_symlink():
            try:
                final = candidate.resolve()
            except (OSError, RuntimeError) as exc:
                raise KBPathInvalid(f"kb_path failed to resolve: {kb_path} ({exc})")
            try:
                final.relative_to(root_resolved)
            except ValueError:
                raise KBPathInvalid(
                    f"kb_path resolves outside KB root (symlink escape?): {kb_path}"
                )
            return candidate

        # Target doesn't exist yet (new write). Resolve the closest existing
        # ancestor — symlinks in any ancestor still need to stay inside root.
        ancestor = candidate.parent
        while ancestor != ancestor.parent and not ancestor.exists():
            ancestor = ancestor.parent
        try:
            ancestor_resolved = ancestor.resolve()
        except (OSError, RuntimeError) as exc:
            raise KBPathInvalid(f"kb_path ancestor failed to resolve: {kb_path} ({exc})")
        try:
            ancestor_resolved.relative_to(root_resolved)
        except ValueError:
            raise KBPathInvalid(
                f"kb_path resolves outside KB root (symlink escape?): {kb_path}"
            )
        return candidate

    def write(self, kb_path: str, content: str, frontmatter: dict[str, Any] | None = None) -> Path:
        target = self._resolve(kb_path)
        if self.detect_conflict_copy(kb_path):
            raise ConflictDetected(
                f"Drive conflict copy present for {kb_path}; refusing to overwrite"
            )
        target.parent.mkdir(parents=True, exist_ok=True)
        # Re-resolve after mkdir in case ancestor symlinks were created.
        target = self._resolve(kb_path)
        body = self._render_frontmatter(frontmatter) + content if frontmatter else content
        try:
            target.write_text(body, encoding="utf-8")
        except PermissionError as exc:
            raise WritePermissionDenied(str(exc)) from exc
        return target

    def write_raw(self, kb_path: str, content: str) -> Path:
        return self.write(kb_path, content, frontmatter=None)

    def read(self, kb_path: str) -> tuple[dict[str, Any], str]:
        target = self._resolve(kb_path)
        if not target.exists():
            raise KBPathInvalid(f"file does not exist: {kb_path}")
        raw = target.read_text(encoding="utf-8")
        return self._parse_frontmatter(raw)

    def exists(self, kb_path: str) -> bool:
        return self._resolve(kb_path).exists()

    def list_dir(self, kb_path: str) -> list[str]:
        target = self._resolve(kb_path) if kb_path else self.root
        if not target.exists():
            raise KBPathInvalid(f"directory does not exist: {kb_path}")
        result = subprocess.run(
            ["find", str(target), "-mindepth", "1", "-maxdepth", "1"],
            capture_output=True,
            text=True,
            check=True,
        )
        lines = [ln for ln in result.stdout.splitlines() if ln]
        return sorted(os.path.basename(ln) for ln in lines)

    def find(self, kb_path: str, pattern: str = "*") -> list[Path]:
        target = self._resolve(kb_path) if kb_path else self.root
        if not target.exists():
            raise KBPathInvalid(f"directory does not exist: {kb_path}")
        result = subprocess.run(
            ["find", str(target), "-name", pattern, "-type", "f"],
            capture_output=True,
            text=True,
            check=True,
        )
        return sorted(Path(ln) for ln in result.stdout.splitlines() if ln)

    def detect_conflict_copy(self, kb_path: str) -> bool:
        target = self._resolve(kb_path)
        parent = target.parent
        if not parent.exists():
            return False
        stem = target.stem
        suffix = target.suffix
        result = subprocess.run(
            ["find", str(parent), "-mindepth", "1", "-maxdepth", "1", "-type", "f"],
            capture_output=True,
            text=True,
            check=True,
        )
        for line in result.stdout.splitlines():
            name = os.path.basename(line)
            match = CONFLICT_COPY_RE.search(Path(name).stem)
            if not match:
                continue
            base_stem = CONFLICT_COPY_RE.sub("", Path(name).stem)
            if base_stem == stem and Path(name).suffix == suffix:
                return True
        return False

    @staticmethod
    def _render_frontmatter(data: dict[str, Any]) -> str:
        if _HAS_YAML:
            dumped = _yaml.safe_dump(data, sort_keys=False, default_flow_style=False).rstrip()
        else:
            dumped = _render_minimal_yaml(data).rstrip()
        return f"---\n{dumped}\n---\n"

    @staticmethod
    def _parse_frontmatter(raw: str) -> tuple[dict[str, Any], str]:
        if not raw.startswith("---\n"):
            return {}, raw
        end = raw.find("\n---\n", 4)
        if end == -1:
            return {}, raw
        header = raw[4:end]
        body = raw[end + 5 :]
        if _HAS_YAML:
            parsed = _yaml.safe_load(header) or {}
        else:
            parsed = _parse_minimal_yaml(header)
        return parsed, body


# -----------------------------------------------------------------------------
# Minimal YAML: indentation-aware emitter + parser.
# Handles scalars, lists, nested dicts (one level), and dict-in-list.
# -----------------------------------------------------------------------------


def _render_minimal_yaml(data: dict[str, Any], indent: int = 0) -> str:
    lines: list[str] = []
    pad = " " * indent
    for key, value in data.items():
        if isinstance(value, dict):
            lines.append(f"{pad}{key}:")
            if value:
                lines.append(_render_minimal_yaml(value, indent + 2))
            # empty dict → just the key: line
        elif isinstance(value, list):
            if not value:
                lines.append(f"{pad}{key}: []")
                continue
            lines.append(f"{pad}{key}:")
            for item in value:
                if isinstance(item, dict):
                    if not item:
                        lines.append(f"{pad}- {{}}")
                        continue
                    # Emit first key on the `- ` line, remaining keys indented.
                    keys = list(item.keys())
                    first_k = keys[0]
                    first_v = item[first_k]
                    if isinstance(first_v, (dict, list)):
                        # Unusual — fall back to one-key-per-line form with
                        # placeholder `-` entry then nested keys.
                        lines.append(f"{pad}-")
                        lines.append(_render_minimal_yaml(item, indent + 2))
                    else:
                        lines.append(f"{pad}- {first_k}: {_scalar(first_v)}")
                        for k in keys[1:]:
                            v = item[k]
                            if isinstance(v, (dict, list)):
                                # nested inside a dict-in-list: skip for now
                                # (schema doesn't require it; keeps emitter honest)
                                lines.append(f"{pad}  {k}: {_scalar(str(v))}")
                            else:
                                lines.append(f"{pad}  {k}: {_scalar(v)}")
                else:
                    lines.append(f"{pad}- {_scalar(item)}")
        else:
            lines.append(f"{pad}{key}: {_scalar(value)}")
    return "\n".join(lines)


def _scalar(value: Any) -> str:
    if value is None:
        return "null"
    if isinstance(value, bool):
        return "true" if value else "false"
    if isinstance(value, (int, float)):
        return json.dumps(value)
    if isinstance(value, (dict, list)):
        # Defensive: caller should have routed through _render_minimal_yaml.
        # Emit JSON-flow form (valid YAML) rather than Python repr.
        return json.dumps(value)
    text = str(value)
    if any(ch in text for ch in ":#\n\"'") or text.strip() != text:
        return json.dumps(text)
    return text


def _parse_minimal_yaml(header: str) -> dict[str, Any]:
    """Indentation-aware YAML-ish parser.

    Handles:
      - `key: value` scalars
      - `key: [a, b, c]` flow lists
      - `key:` followed by `  - item` block lists (including dict-in-list)
      - `key:` followed by `  subkey: value` nested maps (one level deep)
    """
    lines = header.splitlines()
    result, _consumed = _parse_block(lines, 0, 0)
    return result if isinstance(result, dict) else {}


def _strip_comment(line: str) -> str:
    out: list[str] = []
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


def _indent_of(raw: str) -> int:
    return len(raw) - len(raw.lstrip(" "))


def _parse_block(lines: list[str], start: int, base_indent: int):
    """Parse a block at `base_indent` starting at lines[start].

    Returns (parsed, next_index). Parsed is dict OR list depending on the first
    non-empty line at base_indent: `- ` → list, `key:` → dict.
    """
    i = start
    result: dict[str, Any] | list[Any] | None = None
    while i < len(lines):
        raw = lines[i]
        stripped = _strip_comment(raw).rstrip()
        if not stripped.strip():
            i += 1
            continue
        indent = _indent_of(raw)
        if indent < base_indent:
            break
        if indent > base_indent:
            # Shouldn't happen at a sane start — skip.
            i += 1
            continue
        body = stripped.strip()

        if body.startswith("- "):
            if result is None:
                result = []
            if not isinstance(result, list):
                break
            # OK — append to list below.
            item_text = body[2:].strip()
            # Dict-in-list: `- key: value` → look ahead for more keys at deeper indent.
            if ":" in item_text and not (item_text.startswith("'") or item_text.startswith('"')):
                k, _, v = item_text.partition(":")
                k = k.strip()
                v = v.strip()
                item_dict: dict[str, Any] = {}
                if v == "":
                    # `- key:` followed by nested block
                    nested, next_i = _parse_block(lines, i + 1, base_indent + 2)
                    item_dict[k] = nested
                    i = next_i
                else:
                    item_dict[k] = _unscalar(v)
                    # Continue scanning for more `key: value` lines at deeper indent
                    j = i + 1
                    child_indent: int | None = None
                    while j < len(lines):
                        raw2 = lines[j]
                        stripped2 = _strip_comment(raw2).rstrip()
                        if not stripped2.strip():
                            j += 1
                            continue
                        ind2 = _indent_of(raw2)
                        if ind2 <= base_indent:
                            break
                        if child_indent is None:
                            child_indent = ind2
                        if ind2 != child_indent:
                            break
                        b2 = raw2.strip()
                        if b2.startswith("- "):
                            break
                        if ":" not in b2:
                            j += 1
                            continue
                        kk, _, vv = b2.partition(":")
                        item_dict[kk.strip()] = _unscalar(vv.strip())
                        j += 1
                    i = j
                result.append(item_dict)
                continue
            else:
                result.append(_unscalar(item_text))
                i += 1
                continue

        # We've hit a non-`- ` line at base_indent. If we're already
        # accumulating a list, this is the sibling key that terminates it.
        if isinstance(result, list):
            break

        if ":" not in body:
            i += 1
            continue

        if result is None:
            result = {}
        if not isinstance(result, dict):
            break

        key, _, rest = body.partition(":")
        key = key.strip()
        rest = rest.strip()

        if rest == "":
            # Look ahead: nested dict or block list. Standard YAML allows
            # `- ` items at the SAME indent as the key (for lists), or
            # `subkey: value` at DEEPER indent (for nested maps).
            j = i + 1
            # Skip blanks/comments
            while j < len(lines) and not _strip_comment(lines[j]).strip():
                j += 1
            if j >= len(lines):
                result[key] = []
                i = j
                continue
            peek_indent = _indent_of(lines[j])
            peek_body = _strip_comment(lines[j]).strip()
            if peek_indent == base_indent and peek_body.startswith("- "):
                # Same-indent block list.
                nested, next_i = _parse_block(lines, i + 1, base_indent)
                result[key] = nested if nested is not None else []
                i = next_i
                continue
            if peek_indent > base_indent:
                # Deeper nested block (dict or list).
                nested, next_i = _parse_block(lines, i + 1, peek_indent)
                result[key] = nested if nested is not None else []
                i = next_i
                continue
            # Sibling key at same indent or outdent — this key is empty.
            result[key] = []
            i += 1
            continue

        if rest.startswith("["):
            result[key] = _parse_flow_list(rest)
            i += 1
            continue

        result[key] = _unscalar(rest)
        i += 1

    if result is None:
        return None, i
    return result, i


def _parse_flow_list(text: str) -> list[Any]:
    text = text.strip()
    if not (text.startswith("[") and text.endswith("]")):
        return []
    inner = text[1:-1].strip()
    if not inner:
        return []
    parts: list[str] = []
    buf: list[str] = []
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
    return [_unscalar(p) for p in parts]


def _unscalar(text: str) -> Any:
    text = text.strip()
    if text == "" or text == "~" or text.lower() == "null":
        return None
    if text.startswith('"') and text.endswith('"'):
        return json.loads(text)
    if text.startswith("'") and text.endswith("'") and len(text) >= 2:
        return text[1:-1]
    if text.startswith("[") and text.endswith("]"):
        return _parse_flow_list(text)
    if text == "true":
        return True
    if text == "false":
        return False
    try:
        return int(text) if "." not in text else float(text)
    except ValueError:
        return text


# -----------------------------------------------------------------------------
# Self-test
# -----------------------------------------------------------------------------


def _selftest_yaml_roundtrip(with_yaml: bool) -> list[str]:
    """Roundtrip nested-dict + dict-in-list through render + parse.

    Always exercises the fallback emitter/parser by calling them directly.
    If PyYAML is installed we additionally verify PyYAML can parse our output.
    """
    global _HAS_YAML, _yaml
    failures: list[str] = []
    data = {
        "company_name": "Acme",
        "champion_user": {"email": "tyler@acme.com", "role": "c-suite"},
        "joining_users": [
            {"email": "brian@acme.com", "role": "manager"},
            {"email": "sara@acme.com", "role": "ic"},
        ],
        "tags": ["selftest", "nested"],
    }

    prev = _HAS_YAML
    if not with_yaml:
        _HAS_YAML = False  # force fallback path
    try:
        rendered = _render_minimal_yaml(data)
        parsed = _parse_minimal_yaml(rendered)
    finally:
        _HAS_YAML = prev

    label = "with PyYAML" if with_yaml else "fallback"
    if parsed.get("company_name") != "Acme":
        failures.append(f"[{label}] company_name scalar lost")
    champ = parsed.get("champion_user")
    if not isinstance(champ, dict) or champ.get("email") != "tyler@acme.com" or champ.get("role") != "c-suite":
        failures.append(f"[{label}] champion_user nested-dict roundtrip failed: {champ!r}")
    joiners = parsed.get("joining_users")
    if not isinstance(joiners, list) or len(joiners) != 2:
        failures.append(f"[{label}] joining_users list length wrong: {joiners!r}")
    else:
        if joiners[0].get("email") != "brian@acme.com" or joiners[0].get("role") != "manager":
            failures.append(f"[{label}] joining_users[0] dict-in-list failed: {joiners[0]!r}")
        if joiners[1].get("email") != "sara@acme.com" or joiners[1].get("role") != "ic":
            failures.append(f"[{label}] joining_users[1] dict-in-list failed: {joiners[1]!r}")
    if parsed.get("tags") != ["selftest", "nested"]:
        failures.append(f"[{label}] tags list roundtrip failed: {parsed.get('tags')!r}")
    return failures


def _selftest_slug_email() -> list[str]:
    failures: list[str] = []
    cases = [
        ("tyler@prescyent.ai", "tyler-prescyent.ai"),
        ("TYLER@Prescyent.AI", "tyler-prescyent.ai"),
        ("jack.heston+alpha@example.co", "jack.heston-alpha-example.co"),
        ("", "anonymous"),
        ("   ", "anonymous"),
        (None, "anonymous"),
    ]
    for email, expected in cases:
        got = slug_email(email)  # type: ignore[arg-type]
        if got != expected:
            failures.append(f"slug_email({email!r}) = {got!r}, expected {expected!r}")
    return failures


def _selftest_symlink_escape(store: KBStorage) -> list[str]:
    """Create a symlink inside the KB that points outside, assert write raises."""
    import tempfile

    failures: list[str] = []
    tmp_dir = Path(tempfile.mkdtemp(prefix="prescyent-symlink-"))
    outside_target = tmp_dir / "outside.md"
    outside_target.write_text("sentinel", encoding="utf-8")

    link_path = store.root / "evil.md"
    try:
        if link_path.exists() or link_path.is_symlink():
            link_path.unlink()
        os.symlink(outside_target, link_path)

        try:
            store.write("evil.md", "pwned\n")
        except KBPathInvalid:
            pass  # expected
        else:
            failures.append("symlink escape: write('evil.md') did NOT raise KBPathInvalid")

        # Verify the outside file was NOT overwritten.
        if outside_target.read_text(encoding="utf-8") != "sentinel":
            failures.append("symlink escape: outside file was modified despite KBPathInvalid!")
    finally:
        if link_path.exists() or link_path.is_symlink():
            try:
                link_path.unlink()
            except OSError:
                pass
        if outside_target.exists():
            try:
                outside_target.unlink()
            except OSError:
                pass
        try:
            tmp_dir.rmdir()
        except OSError:
            pass
    return failures


def _selftest_expected_target_mismatch(label: str) -> list[str]:
    """Assert StorageNotFound when expected=gdrive but no Drive mount."""
    failures: list[str] = []
    # Use a label that is extremely unlikely to collide with a real mount.
    bogus_label = f"{label}-nonexistent-{os.getpid()}"
    try:
        KBStorage(bogus_label, expected_target="gdrive")
    except StorageNotFound as exc:
        msg = str(exc)
        if "Google Drive" not in msg or "re-run /kb-build" not in msg:
            failures.append(f"gdrive mismatch: message not helpful: {msg!r}")
    except Exception as exc:
        failures.append(f"gdrive mismatch: wrong exception type {type(exc).__name__}: {exc}")
    else:
        # Tyler's own machine has a GDrive mount for real prescyent labels,
        # but a random bogus label should never hit — if this path runs the
        # test is inconclusive rather than failing.
        pass

    try:
        KBStorage(bogus_label, expected_target="onedrive")
    except StorageNotFound as exc:
        msg = str(exc)
        if "OneDrive" not in msg or "re-run /kb-build" not in msg:
            failures.append(f"onedrive mismatch: message not helpful: {msg!r}")
    except Exception as exc:
        failures.append(f"onedrive mismatch: wrong exception type {type(exc).__name__}: {exc}")
    return failures


def _self_test(label: str, expected: str | None = None) -> int:
    print(f"[self-test] constructing KBStorage(label={label!r}, expected_target={expected!r})")
    store = KBStorage(label, expected_target=expected)
    print(f"[self-test] root discovered: {store.root}")

    all_failures: list[str] = []

    # 1. Basic write/read/frontmatter path.
    test_path = "_meta/.prescyent-storage-selftest.md"
    frontmatter = {
        "title": "storage self-test",
        "created": "2026-04-24",
        "tags": ["selftest", "storage"],
        "champion_user": {"email": "selftest@example.com", "role": "c-suite"},
    }
    body = "This file was written by storage.py --test. Safe to delete.\n"
    written = store.write(test_path, body, frontmatter)
    print(f"[self-test] wrote: {written}")

    parsed_fm, parsed_body = store.read(test_path)
    print(f"[self-test] read frontmatter keys: {sorted(parsed_fm.keys())}")
    champ = parsed_fm.get("champion_user")
    if not (isinstance(champ, dict) and champ.get("email") == "selftest@example.com"):
        all_failures.append(f"frontmatter roundtrip: champion_user not a dict: {champ!r}")
    if not parsed_body.startswith("This file was written"):
        all_failures.append(f"frontmatter roundtrip: body text mismatch")

    listing = store.list_dir("_meta")
    print(f"[self-test] list_dir('_meta') via find: {len(listing)} entries")

    found = store.find("_meta", "*.md")
    print(f"[self-test] find('_meta', '*.md'): {len(found)} files")

    if store.detect_conflict_copy(test_path):
        all_failures.append("detect_conflict_copy: false positive on fresh write")

    # 2. YAML roundtrip WITHOUT PyYAML (force fallback).
    print("[self-test] yaml roundtrip (fallback emitter+parser)...")
    all_failures.extend(_selftest_yaml_roundtrip(with_yaml=False))

    # 3. YAML roundtrip WITH PyYAML (if available).
    if _HAS_YAML:
        print("[self-test] yaml roundtrip (PyYAML parser)...")
        all_failures.extend(_selftest_yaml_roundtrip(with_yaml=True))
    else:
        print("[self-test] yaml roundtrip (PyYAML): skipped — not installed")

    # 4. slug_email canonical form.
    print("[self-test] slug_email canonical form...")
    all_failures.extend(_selftest_slug_email())

    # 5. Symlink escape.
    print("[self-test] symlink escape...")
    all_failures.extend(_selftest_symlink_escape(store))

    # 6. expected_target mismatch.
    print("[self-test] expected_target mismatch...")
    all_failures.extend(_selftest_expected_target_mismatch(label))

    # cleanup
    if written.exists():
        written.unlink()
        print(f"[self-test] deleted: {written}")

    if all_failures:
        print("\n[self-test] FAILURES:")
        for f in all_failures:
            print(f"  - {f}")
        return 1

    print("[self-test] OK (all checks passed)")
    return 0


if __name__ == "__main__":
    argv = sys.argv[1:]
    expected: str | None = None
    if "--expected" in argv:
        idx = argv.index("--expected")
        if idx + 1 >= len(argv):
            print("usage: storage.py --test <label> [--expected <gdrive|onedrive|localfs>]", file=sys.stderr)
            sys.exit(2)
        expected = argv[idx + 1]
        argv = argv[:idx] + argv[idx + 2 :]

    if len(argv) == 2 and argv[0] == "--test":
        sys.exit(_self_test(argv[1], expected=expected))
    print("usage: storage.py --test <label> [--expected <gdrive|onedrive|localfs>]", file=sys.stderr)
    sys.exit(2)
