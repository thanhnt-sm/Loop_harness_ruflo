#!/bin/bash
# Harness Consensus Tool - C2/C3 Self-Consistency + Ranked Voting

set -euo pipefail
source "$(dirname "$0")/../hooks/find_python.sh"

SESSION="${1:-test-session}"

if [[ -n "$PYTHON" && -f ".devin/scripts/fable_judge_compensation.py" ]]; then
  $PYTHON .devin/scripts/fable_judge_compensation.py "$SESSION"
else
  echo "Harness compensation not installed"
  exit 1
fi