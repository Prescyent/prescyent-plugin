#!/bin/bash
#
# lint-background-safe.sh — pre-commit check for the background_safe contract.
#
# Exits non-zero if:
#   1. Any agents/*.md contains "AskUserQuestion" anywhere in the body
#      (subagents run in background contexts and cannot call AskUserQuestion).
#   2. Any skill or command with "background_safe: true" in the frontmatter
#      contains "AskUserQuestion" anywhere in the body.
#
# Output: a human-readable list of violations, one per line.

set -u

# Resolve repo root from this script's location (skills/kb-builder/scripts/ → repo root).
SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
REPO_ROOT="$(cd "${SCRIPT_DIR}/../../.." && pwd)"

violations=0

# Rule 1 — no AskUserQuestion in any agent.
for f in "${REPO_ROOT}"/agents/*.md; do
  [ -f "$f" ] || continue
  if grep -q "AskUserQuestion" "$f"; then
    line_nums=$(grep -n "AskUserQuestion" "$f" | cut -d: -f1 | tr '\n' ',' | sed 's/,$//')
    echo "VIOLATION: agent file contains AskUserQuestion — agents run in background contexts"
    echo "  file:  $f"
    echo "  lines: $line_nums"
    violations=$((violations + 1))
  fi
done

# Rule 2 — no AskUserQuestion in any skill/command with background_safe: true.
for f in "${REPO_ROOT}"/skills/*/SKILL.md "${REPO_ROOT}"/commands/*.md; do
  [ -f "$f" ] || continue
  # Frontmatter is between the first two lines that are exactly "---".
  # Pull the frontmatter and look for background_safe: true.
  fm=$(awk '/^---$/{c++; next} c==1{print} c==2{exit}' "$f")
  if echo "$fm" | grep -qE "^background_safe:[[:space:]]+true[[:space:]]*$"; then
    # Body is everything after the second "---".
    body=$(awk '/^---$/{c++; next} c>=2{print}' "$f")
    if echo "$body" | grep -q "AskUserQuestion"; then
      line_nums=$(grep -n "AskUserQuestion" "$f" | cut -d: -f1 | tr '\n' ',' | sed 's/,$//')
      echo "VIOLATION: background_safe:true file contains AskUserQuestion"
      echo "  file:  $f"
      echo "  lines: $line_nums"
      violations=$((violations + 1))
    fi
  fi
done

if [ "$violations" -gt 0 ]; then
  echo ""
  echo "${violations} violation(s). Fix by flipping background_safe to false, or by removing the AskUserQuestion reference."
  exit 1
fi

echo "lint-background-safe: pass (0 violations)"
exit 0
