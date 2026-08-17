#!/bin/bash
# Harness Route Tool - Model Routing (U-H12)

set -euo pipefail

TASK="${1:-}"

if [[ -z "$TASK" ]]; then
  echo "Usage: harness-route.sh <task_description>"
  exit 1
fi

if [[ -f ".venv/bin/python" && -f ".devin/scripts/auto_model_router.py" ]]; then
  .venv/bin/python .devin/scripts/auto_model_router.py "$TASK" --estimate-cost
else
  echo "Harness router not installed"
  exit 1
fi