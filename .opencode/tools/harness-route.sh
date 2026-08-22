#!/bin/bash
# Harness Route Tool - Model Routing (U-H12)

set -euo pipefail
source "$(dirname "$0")/../hooks/find_python.sh"

TASK="${1:-}"

if [[ -z "$TASK" ]]; then
  echo "Usage: harness-route.sh <task_description>"
  exit 1
fi

if [[ -n "$PYTHON" && -f ".devin/scripts/auto_model_router.py" ]]; then
  $PYTHON .devin/scripts/auto_model_router.py "$TASK" --estimate-cost
else
  echo "Harness router not installed"
  exit 1
fi