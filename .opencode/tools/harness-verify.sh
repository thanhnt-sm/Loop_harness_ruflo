#!/bin/bash
# Harness Verify Tool - C1 Deterministic Verification

set -euo pipefail

if [[ -f ".venv/bin/python" && -f ".devin/scripts/hook_integrity.py" ]]; then
  .venv/bin/python .devin/scripts/hook_integrity.py --verify
  exit $?
else
  echo "Harness not installed"
  exit 1
fi