#!/bin/bash
# Harness Compact Tool - Context Compaction (U-H9)

set -euo pipefail

SESSION="${1:-test-session}"
LEVEL="${2:-full}"

if [[ -f ".venv/bin/python" && -f ".devin/hooks/context_compaction.py" ]]; then
  .venv/bin/python .devin/hooks/context_compaction.py "$SESSION" "$LEVEL"
else
  echo "Harness compaction not installed"
  exit 1
fi