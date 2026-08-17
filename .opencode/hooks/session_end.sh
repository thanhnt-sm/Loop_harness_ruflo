#!/bin/bash
# Session end hook - generate cost dashboard

set -euo pipefail

SESSION_ID="${1:-session_$(date +%s)}"

# Generate cost dashboard
if [[ -f ".venv/bin/python" && -f ".devin/scripts/cost_dashboard.py" ]]; then
  .venv/bin/python .devin/scripts/cost_dashboard.py >/dev/null 2>&1 || true
  echo "Harness: Cost dashboard generated"
fi

# Cleanup old tool outputs (keep last 100)
if [[ -d ".opencode/session_state/tool_outputs" ]]; then
  ls -t ".opencode/session_state/tool_outputs"/*.txt 2>/dev/null | tail -n +101 | xargs rm -f 2>/dev/null || true
fi

echo "Harness: Session $SESSION_ID ended"