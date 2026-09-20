#!/bin/bash
# Harness Cost Dashboard Tool

set -euo pipefail
source "$(dirname "$0")/../hooks/find_python.sh"

if [[ -n "$PYTHON" && -f ".devin/scripts/cost_dashboard.py" ]]; then
  $PYTHON .devin/scripts/cost_dashboard.py
else
  echo "Harness cost dashboard not installed"
  exit 1
fi