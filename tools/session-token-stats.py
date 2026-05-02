#!/usr/bin/env python3
"""
session-token-stats.py — extract subagent token consumption from a Cowork session audit log.

Reads `~/Library/Application Support/Claude/local-agent-mode-sessions/{global}/{cowork}/local_{session}/audit.jsonl`
and summarizes each Task (subagent) dispatch — prompt size, result size, and a
char-count-based token estimate.

Useful for ongoing dogfood + understanding subagent costs as we add new lanes
(e.g., the audit-sessions subagent in v0.7).

Usage:
  python3 tools/session-token-stats.py {session_id}
  python3 tools/session-token-stats.py local_8dfa6c46-75a1-496a-8377-0e5c4aee2677
  python3 tools/session-token-stats.py {session_id} --raw   # also dump tool_use_id + truncated input/output

Auto-resolves the audit.jsonl path by walking the local-agent-mode-sessions tree
to find the matching session_id directory. Token estimate uses chars/4 heuristic
(close enough for budgeting; exact counts would need a tokenizer).
"""

from __future__ import annotations

import argparse
import json
import os
import sys
from pathlib import Path


SESSIONS_ROOT = Path("~/Library/Application Support/Claude/local-agent-mode-sessions").expanduser()


def find_audit_log(session_id: str) -> Path:
    """Walk the sessions tree and find the audit.jsonl for the given session_id."""
    if not SESSIONS_ROOT.exists():
        sys.exit(f"error: sessions root not found at {SESSIONS_ROOT}")
    for path in SESSIONS_ROOT.glob(f"*/*/{session_id}/audit.jsonl"):
        return path
    sys.exit(f"error: no audit.jsonl found for session_id={session_id} under {SESSIONS_ROOT}")


def trunc(s: str, n: int = 80) -> str:
    return s if len(s) <= n else s[: n - 3] + "..."


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("session_id", help="Cowork session ID, e.g. local_8dfa6c46-...")
    parser.add_argument("--raw", action="store_true", help="Include tool_use_ids + input previews per call")
    parser.add_argument("--trace", action="store_true", help="Surface _trace[] per-tool-call rollup from each subagent's JSON return (v0.8 contract 3.0)")
    args = parser.parse_args()

    log_path = find_audit_log(args.session_id)
    lines = [json.loads(l) for l in log_path.read_text().splitlines() if l.strip()]

    task_calls: dict[str, dict] = {}  # tool_use_id -> meta
    task_results: dict[str, int] = {}  # tool_use_id -> result chars

    for e in lines:
        if e.get("type") == "assistant":
            msg = e.get("message") or {}
            for blk in msg.get("content", []) or []:
                if isinstance(blk, dict) and blk.get("type") == "tool_use" and blk.get("name") == "Agent":
                    tid = blk.get("id", "")
                    inp = blk.get("input", {}) or {}
                    task_calls[tid] = {
                        "agent": inp.get("subagent_type", "?"),
                        "desc": inp.get("description", "")[:80],
                        "prompt_chars": len(str(inp.get("prompt", ""))),
                        "prompt_preview": trunc(str(inp.get("prompt", "")), 200),
                    }
        elif e.get("type") == "user":
            msg = e.get("message") or {}
            for blk in msg.get("content", []) or []:
                if isinstance(blk, dict) and blk.get("type") == "tool_result":
                    tid = blk.get("tool_use_id", "")
                    if tid in task_calls:
                        inner = blk.get("content", "")
                        if isinstance(inner, list):
                            chars = sum(
                                len(str(ib.get("text", "")))
                                for ib in inner
                                if isinstance(ib, dict)
                            )
                        else:
                            chars = len(str(inner))
                        task_results[tid] = chars

    print(f"Session: {args.session_id}")
    print(f"Audit log: {log_path}")
    print(f"Total audit lines: {len(lines)}")
    print()

    if not task_calls:
        print("No subagent (Task) dispatches found in this session.")
        return 0

    print(f"{'Subagent':<36} {'Prompt chars':>13} {'Result chars':>13}  {'Description'}")
    print("-" * 100)
    total_p = total_r = 0
    for tid, info in task_calls.items():
        rc = task_results.get(tid, 0)
        total_p += info["prompt_chars"]
        total_r += rc
        print(
            f"{info['agent']:<36} {info['prompt_chars']:>13,} {rc:>13,}  {info['desc']}"
        )
    print("-" * 100)
    print(f"{'TOTAL':<36} {total_p:>13,} {total_r:>13,}")
    print()
    print(f"Token estimate (chars/4 heuristic):")
    print(f"  prompts: ~{total_p // 4:,} tokens")
    print(f"  results: ~{total_r // 4:,} tokens")
    print(f"  combined: ~{(total_p + total_r) // 4:,} tokens")

    if args.raw:
        print()
        print("=== Raw per-call detail ===")
        for tid, info in task_calls.items():
            rc = task_results.get(tid, 0)
            print()
            print(f"  tool_use_id: {tid}")
            print(f"    agent: {info['agent']}")
            print(f"    description: {info['desc']}")
            print(f"    prompt chars: {info['prompt_chars']:,}")
            print(f"    result chars: {rc:,}")
            print(f"    prompt preview: {info['prompt_preview']}")

    if args.trace:
        print()
        print("=== Subagent _trace[] rollup (v3.0 contract) ===")
        # Re-walk the lines and look for tool_result blocks that carry parseable JSON
        # with a _trace[] array (the v0.8 contract requirement).
        for tid, info in task_calls.items():
            for e in lines:
                if e.get("type") != "user":
                    continue
                msg = e.get("message") or {}
                for blk in msg.get("content", []) or []:
                    if not isinstance(blk, dict) or blk.get("type") != "tool_result":
                        continue
                    if blk.get("tool_use_id") != tid:
                        continue
                    inner = blk.get("content", "")
                    text = ""
                    if isinstance(inner, list):
                        text = "".join(
                            str(ib.get("text", ""))
                            for ib in inner
                            if isinstance(ib, dict)
                        )
                    else:
                        text = str(inner)
                    # Look for the _trace block inside the JSON return.
                    try:
                        # The subagent return may be wrapped in prose; find a JSON object.
                        start = text.find("{")
                        end = text.rfind("}")
                        if start >= 0 and end > start:
                            parsed = json.loads(text[start : end + 1])
                            trace = parsed.get("_trace", [])
                            if trace:
                                print()
                                print(f"  {info['agent']} ({len(trace)} tool calls):")
                                total_ms = sum(t.get("ms", 0) for t in trace)
                                total_tokens = sum(t.get("tokens_est", 0) for t in trace)
                                for t in trace:
                                    print(
                                        f"    - {t.get('tool','?')} "
                                        f"({t.get('ms',0)}ms, ~{t.get('tokens_est',0):,}t)"
                                        f"  {trunc(t.get('args_summary',''), 60)}"
                                    )
                                print(f"    TOTAL: {total_ms}ms, ~{total_tokens:,} tokens")
                    except (json.JSONDecodeError, ValueError):
                        pass

    return 0


if __name__ == "__main__":
    sys.exit(main())
