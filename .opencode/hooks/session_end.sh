#!/bin/bash
# Session end hook - cleanup + cost dashboard (cross-platform)

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

# Generate cost dashboard
if [ -n "$PYTHON" ] && [ -f ".devin/scripts/cost_dashboard.py" ]; then
  $PYTHON .devin/scripts/cost_dashboard.py >/dev/null 2>&1 || true
  echo "Harness: Cost dashboard generated"
fi

# Cleanup old tool outputs (cross-platform — Python thay ls|xargs)
# Giữ tối đa 50 file mới nhất, xóa rest
if [ -n "$PYTHON" ]; then
  $PYTHON -c "
import os
d = '.opencode/session_state/tool_outputs'
if os.path.isdir(d):
    files = [(os.path.join(d, f), os.path.getmtime(os.path.join(d, f)))
             for f in os.listdir(d) if f.endswith('.txt')]
    files.sort(key=lambda x: x[1], reverse=True)
    for f, _ in files[50:]:
        try: os.remove(f)
        except OSError: pass
" 2>/dev/null || true
fi

echo "Harness: Session $SESSION_ID ended"
