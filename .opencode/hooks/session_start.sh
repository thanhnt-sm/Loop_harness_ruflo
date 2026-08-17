#!/bin/bash
# Session start hook - initialize harness

set -euo pipefail

SESSION_ID="${1:-session_$(date +%s)}"

# Initialize skill index for progressive loading
if [[ -f ".opencode/skills/skill_index.json" ]]; then
  echo "Harness: Skill index loaded"
fi

# Initialize prompt cache metrics
if [[ -f ".venv/bin/python" && -f ".devin/hooks/prompt_cache_metrics.py" ]]; then
  .venv/bin/python .devin/hooks/prompt_cache_metrics.py "$SESSION_ID" >/dev/null 2>&1 || true
fi

# Initialize cost tracking
mkdir -p ".opencode/session_state" ".opencode/session_state/tool_outputs" ".opencode/session_state/compaction"

echo "Harness initialized for session: $SESSION_ID"