#!/bin/bash
# Harness Compact Tool - Context Compaction (U-H9)

set -euo pipefail
source "$(dirname "$0")/../hooks/find_python.sh"

SESSION="${1:-test-session}"
LEVEL="${2:-full}"

if [[ -n "$PYTHON" && -f ".devin/hooks/context_compaction.py" ]]; then
  $PYTHON .devin/hooks/context_compaction.py "$SESSION" "$LEVEL"
else
  echo "Harness compaction not installed"
  exit 1
fi