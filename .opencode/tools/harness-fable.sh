#!/bin/bash
# Harness Fable-Judge Tool - Adversarial Verification Gate

set -euo pipefail

SESSION="${1:-test-session}"
FAST="${2:-}"

if [[ -f ".venv/bin/python" && -f ".devin/scripts/fable_judge_compensation.py" ]]; then
  if [[ "$FAST" == "--fast" ]]; then
    .venv/bin/python .devin/scripts/fable_judge_compensation.py "$SESSION" --fast
  else
    .venv/bin/python .devin/scripts/fable_judge_compensation.py "$SESSION"
  fi
else
  echo "Harness fable-judge not installed"
  exit 1
fi