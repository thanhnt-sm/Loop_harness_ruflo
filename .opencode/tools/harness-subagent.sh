#!/bin/bash
# Harness Sub-Agent Tool - C6 Sub-Agent Isolation

set -euo pipefail

TASK="${1:-}"
BUDGET="${2:-3000}"
EXECUTOR="${3:-glm-executor}"

if [[ -z "$TASK" ]]; then
  echo "Usage: harness-subagent.sh <task> [budget] [executor]"
  exit 1
fi

if [[ -f ".venv/bin/python" && -f ".devin/scripts/subagent_isolation.py" ]]; then
  .venv/bin/python .devin/scripts/subagent_isolation.py "$TASK" "$BUDGET" "$EXECUTOR"
else
  echo "Harness subagent not installed"
  exit 1
fi