#!/bin/bash
# Harness Consensus Tool - C2/C3 Self-Consistency + Ranked Voting

set -euo pipefail

SESSION="${1:-test-session}"

if [[ -f ".venv/bin/python" && -f ".devin/scripts/fable_judge_compensation.py" ]]; then
  .venv/bin/python .devin/scripts/fable_judge_compensation.py "$SESSION"
else
  echo "Harness compensation not installed"
  exit 1
fi