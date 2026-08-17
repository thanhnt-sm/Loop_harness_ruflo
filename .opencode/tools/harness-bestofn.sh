#!/bin/bash
# Harness Best-of-N Tool - C4 Best-of-N + Reward Model

set -euo pipefail

TASK="${1:-}"
N="${2:-5}"

if [[ -z "$TASK" ]]; then
  echo "Usage: harness-bestofn.sh <task> [n_candidates]"
  exit 1
fi

if [[ -f ".venv/bin/python" && -f ".devin/scripts/best_of_n.py" ]]; then
  .venv/bin/python -c "
import sys
sys.path.insert(0, '.devin/scripts')
from best_of_n import best_of_n

def mock_generator():
    # In real usage, this would call the model
    return 'generated code for: $TASK'

result = best_of_n(mock_generator, n=$N)
print(f'Best score: {result[\"best_score\"]}')
print(f'Best index: {result[\"best_index\"]}')
"
else
  echo "Harness best-of-n not installed"
  exit 1
fi