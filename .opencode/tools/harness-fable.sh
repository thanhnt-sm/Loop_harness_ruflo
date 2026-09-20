#!/bin/bash
# Harness Fable-Judge Tool - Adversarial Verification Gate

set -euo pipefail

SESSION="${1:-test-session}"
FAST="${2:-}"

# Source find_python helper
source "$(dirname "$0")/../hooks/find_python.sh"

if [[ -n "$PYTHON" && -f ".devin/scripts/fable_judge_compensation.py" ]]; then
  if [[ "$FAST" == "--fast" ]]; then
    $PYTHON .devin/scripts/fable_judge_compensation.py "$SESSION" --fast
  else
    $PYTHON .devin/scripts/fable_judge_compensation.py "$SESSION"
  fi
else
  echo "Harness fable-judge not installed"
  exit 1
fi