#!/usr/bin/env python3
"""
spike-test-subagent-budget.py — pre-impl spike test runner for the v0.8 architecture.

Drives 4 quick experiments inside Claude Code to validate the v0.8 architecture
assumptions BEFORE the full 9-lane fan-out locks in. Each test surfaces a
specific question whose answer affects whether v0.8's design holds or needs
adjustment.

This script doesn't run the experiments itself — Claude Code does. The script
prints the exact prompts to copy into a fresh Claude Code session, plus a
checklist for capturing results.

Tyler runs this once before the v0.8 architecture locks. Results inform whether
we run subagents at 200K or 1M context, whether the 9-lane fan-out is within the
parallel cap, whether per-Task model override works in Cowork, and whether the
resumption pattern works in Cowork desktop (docs say it works in CLI).

Usage:
  python3 tools/spike-test-subagent-budget.py
  python3 tools/spike-test-subagent-budget.py --test 1   # print one test
  python3 tools/spike-test-subagent-budget.py --check    # checklist only
"""

from __future__ import annotations

import argparse
import sys


SPIKE_TESTS = {
    1: {
        "name": "1M-flag propagation",
        "question": "Do spawned subagents inherit the master's 1M context window?",
        "if_passes": "Subagents at 1M each → 8×1M aggregate. Wide-and-deep doable at full scale.",
        "if_fails": "Subagents capped at 200K → keep per-subagent fetch budgets tight; rely more on resumption follow-ups for depth.",
        "prompt": """
Spike Test #1 — 1M-flag propagation.

I want to verify whether a subagent dispatched via the Task tool inherits my 1M context window or is capped at 200K.

Run the following inside Claude Code (a fresh session, model claude-opus-4-7[1m]):

1. Use Task to dispatch a subagent with subagent_type "general-purpose" or any agent definition that doesn't override the model field.
2. The subagent's prompt: "I'm a context-window probe. Claim you have a 1M context window if you do, or 200K if not. Then describe in three sentences how you would tell — what error message you would expect at the 200K boundary."
3. Capture the subagent's return.

Then report:
- Did the subagent claim 1M or 200K?
- Was there any error or warning during dispatch?
- Did the SDK doc page (code.claude.com/docs/en/agent-sdk/subagents) say anything about the [1m] flag propagation we missed?
""",
    },
    2: {
        "name": "Parallel cap (12 concurrent)",
        "question": "What is the actual Cowork-side parallel-Task ceiling?",
        "if_passes": "Confirms 9-lane fan-out is within budget.",
        "if_fails": "If <9, redesign to 2-wave dispatch (Wave 1: 5 lanes; Wave 2: 4 lanes).",
        "prompt": """
Spike Test #2 — Parallel cap probe.

I want to know how many parallel Task calls Cowork will accept in a single message before throttling.

Run the following inside Claude Code:

1. Send a SINGLE assistant message that fires 12 concurrent Task calls. Each task is trivial: subagent_type="general-purpose", prompt="Return the integer N where N is the position of this subagent in the parallel set. Just the integer."
2. Capture how many Task calls actually started, how many completed, how many were rejected/queued.

Report:
- Number of Task calls dispatched: 12
- Number that completed in parallel: ?
- Any error messages or rate-limit warnings: ?
""",
    },
    3: {
        "name": "Cross-model dispatch",
        "question": "Does per-Task model override work in Cowork?",
        "if_passes": "Tyler can revert to model: sonnet per-agent for the alpha-cohort variant via single sed-pass.",
        "if_fails": "Plugin needs separate Sonnet branch before alpha distribution.",
        "prompt": """
Spike Test #3 — Cross-model dispatch.

I want to verify that a Task call with an explicit model override works in Cowork (docs say it works in CLI).

Run the following inside Claude Code:

1. Dispatch a Task with subagent_type="general-purpose" and explicit model="haiku" (or "sonnet" if haiku isn't accepted at the per-Task level).
2. Subagent prompt: "What model are you running? Reply with just the model name string."

Report:
- Did the Task accept the model parameter?
- What did the subagent claim its model was?
- Any error? (e.g. "model parameter not supported in Cowork environment")
""",
    },
    4: {
        "name": "Resumption pattern (resume: sessionId)",
        "question": "Does bidirectional dialogue work in Cowork desktop? (Docs say it works in CLI.)",
        "if_passes": "Gap-detection pass design holds. 6 follow-ups per subagent doable in very-deep mode.",
        "if_fails": "v0.8 §A5 scope drops to static fan-out + master synthesis only (still good — just less depth).",
        "prompt": """
Spike Test #4 — Resumption (resume: sessionId).

I want to verify that the resume: sessionId pattern works inside Cowork desktop. Per the SDK doc, a master can send a NEW prompt to a paused subagent that retains its full prior conversation, all tool calls, and all reasoning, triggered from a new query() with resume: sessionId.

Run the following inside Claude Code:

1. Dispatch a Task with subagent_type="general-purpose" and prompt="Pick a number between 1 and 100. Don't tell me what it is yet. Reply with the literal string SESSION_ID:<your_session_id>."
2. Capture the session_id from the return.
3. Dispatch a NEW query() with resume: sessionId from step 2 and prompt="Now tell me the number you picked."
4. Capture the response.

Report:
- Did the resumption work (the subagent remembered the picked number)?
- Did the subagent claim to retain prior context?
- Was there any error specific to Cowork desktop vs CLI? (e.g. "resume not supported in this environment")
""",
    },
}


CHECKLIST = """
=== v0.8 spike test checklist ===

For each test, capture:
  [ ] Pass / Fail
  [ ] Quantitative result (token count, model name, parallel count, etc.)
  [ ] Qualitative observation (errors, warnings, doc-vs-reality gaps)
  [ ] What the result implies for the v0.8 architecture

After all 4 tests, decide:
  [ ] Run subagents at 1M (test 1 passes) or 200K (test 1 fails)?
  [ ] Single-message 9-lane fan-out (test 2 passes ≥9 concurrent) or 2-wave dispatch (fails)?
  [ ] Per-Task Sonnet override path (test 3 passes) or separate branch (fails)?
  [ ] Resumption-based gap-detection holds (test 4 passes) or static synthesis only (fails)?

Tyler 2026-05-02: spike during impl, not before. Course-correct branches at natural pause-points.
"""


def main() -> int:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--test", type=int, help="Print only the specified test number (1-4)")
    parser.add_argument("--check", action="store_true", help="Print the post-test checklist only")
    args = parser.parse_args()

    if args.check:
        print(CHECKLIST)
        return 0

    if args.test:
        if args.test not in SPIKE_TESTS:
            sys.exit(f"error: unknown test {args.test}; valid: 1-4")
        t = SPIKE_TESTS[args.test]
        print(f"=== Spike Test #{args.test} — {t['name']} ===")
        print(f"Question: {t['question']}")
        print(f"If passes: {t['if_passes']}")
        print(f"If fails:  {t['if_fails']}")
        print()
        print(t["prompt"])
        return 0

    # Print all 4 tests.
    print("=" * 78)
    print("v0.8 Pre-impl spike tests — 4 experiments")
    print("=" * 78)
    print()
    print("Run inside a fresh Claude Code session at the plugin repo.")
    print("Each test is a copy-pasteable prompt that drives one experiment.")
    print()
    for i in sorted(SPIKE_TESTS):
        t = SPIKE_TESTS[i]
        print(f"=== Spike Test #{i} — {t['name']} ===")
        print(f"Question: {t['question']}")
        print(f"If passes: {t['if_passes']}")
        print(f"If fails:  {t['if_fails']}")
        print()
        print(t["prompt"])
        print()
        print("-" * 78)
        print()

    print(CHECKLIST)
    return 0


if __name__ == "__main__":
    sys.exit(main())
