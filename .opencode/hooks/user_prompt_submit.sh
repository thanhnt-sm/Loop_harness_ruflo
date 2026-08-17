#!/bin/bash
# User prompt submit hook - detect corrections for memory

set -euo pipefail

PROMPT="${1:-}"

# Detect corrections in prompt
if echo "$PROMPT" | grep -qiE '\b(fix|correct|actually|wrong|mistake|typo)\b'; then
  # Store correction in aide-memory
  if [[ -f ".venv/bin/python" && -f ".devin/hooks/ahd_session.py" ]]; then
    .venv/bin/python -c "
import sys, json
sys.path.insert(0, '.devin/hooks')
import ahd_session
state = ahd_session.read_session_state('test', '.')
corrections = state.get('corrections', [])
corrections.append({'prompt': '''$PROMPT''', 'ts': '$(date -Iseconds)'})
ahd_session.update_session_state('test', {'corrections': corrections[-10:]}, '.')
" 2>/dev/null || true
  fi
fi