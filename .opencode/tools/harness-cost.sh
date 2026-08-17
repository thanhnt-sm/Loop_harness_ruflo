#!/bin/bash
# Harness Cost Dashboard Tool

set -euo pipefail

if [[ -f ".venv/bin/python" && -f ".devin/scripts/cost_dashboard.py" ]]; then
  .venv/bin/python .devin/scripts/cost_dashboard.py
else
  echo "Harness cost dashboard not installed"
  exit 1
fi