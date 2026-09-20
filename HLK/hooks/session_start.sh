#!/bin/bash
# Session start hook - initialize harness (cross-platform)

set -uo pipefail

SESSION_ID="${1:-session_$(date +%s)}"

# --- Cross-platform python detection ---
find_python() {
    if [ -f ".venv/Scripts/python.exe" ]; then
        echo ".venv/Scripts/python.exe"
    elif [ -f ".venv/bin/python" ]; then
        echo ".venv/bin/python"
    elif command -v python3 >/dev/null 2>&1; then
        echo "python3"
    elif command -v python >/dev/null 2>&1; then
        echo "python"
    else
        echo ""
    fi
}

PYTHON=$(find_python)

# Initialize skill index for progressive loading
if [[ -f ".opencode/skills/skill_index.json" ]]; then
  echo "Harness: Skill index loaded"
fi

# Initialize prompt cache metrics
if [ -n "$PYTHON" ] && [ -f ".devin/hooks/prompt_cache_metrics.py" ]; then
  $PYTHON .devin/hooks/prompt_cache_metrics.py "$SESSION_ID" >/dev/null 2>&1 || true
fi

# Initialize cost tracking + session state dirs
mkdir -p ".opencode/session_state" ".opencode/session_state/tool_outputs" ".opencode/session_state/compaction"

echo "Harness initialized for session: $SESSION_ID"
