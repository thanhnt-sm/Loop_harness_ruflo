#!/bin/bash
# Harness Verify Tool - C1 Deterministic Verification

set -euo pipefail

# Tìm Python interpreter (.venv/bin/python, .venv/Scripts/python.exe, hoặc python3)
PYTHON=""
if [[ -f ".venv/bin/python" ]]; then
  PYTHON=".venv/bin/python"
elif [[ -f ".venv/Scripts/python.exe" ]]; then
  PYTHON=".venv/Scripts/python.exe"
elif command -v python3 &>/dev/null; then
  PYTHON="python3"
elif command -v python &>/dev/null; then
  PYTHON="python"
fi

if [[ -n "$PYTHON" && -f ".devin/scripts/hook_integrity.py" ]]; then
  $PYTHON .devin/scripts/hook_integrity.py --verify
  exit $?
else
  echo "Harness not installed"
  exit 1
fi