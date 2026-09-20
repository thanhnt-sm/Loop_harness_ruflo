#!/bin/bash
# User prompt submit hook - detect corrections for memory (cross-platform)

set -uo pipefail

PROMPT="${1:-}"

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

# Pass PROMPT qua env var (anti-injection — không dùng string interpolation)
export OC_PROMPT="$PROMPT"

# Detect corrections in prompt
if echo "$PROMPT" | grep -qiE '\b(fix|correct|actually|wrong|mistake|typo)\b'; then
  if [ -n "$PYTHON" ] && [ -f ".devin/hooks/ahd_session.py" ]; then
    $PYTHON -c "
import sys, json, os
sys.path.insert(0, '.devin/hooks')
import ahd_session
prompt = os.environ.get('OC_PROMPT', '')
ts = os.environ.get('OC_TS', '')
state = ahd_session.read_session_state('test', '.')
corrections = state.get('corrections', [])
corrections.append({'prompt': prompt, 'ts': ts})
ahd_session.update_session_state('test', {'corrections': corrections[-10:]}, '.')
" 2>/dev/null || true
  fi
fi
