#!/bin/bash
# Harness Mask Tool - Observation Masking (U-H18)

set -euo pipefail

INPUT="${1:-}"

if [[ -z "$INPUT" ]]; then
  INPUT=$(cat)
fi

if [[ ${#INPUT} -le 1000 ]]; then
  echo "$INPUT"
  exit 0
fi

HANDLE="tool_output_$(date +%s)_$(openssl rand -hex 4)"
mkdir -p ".opencode/session_state/tool_outputs"
echo "$INPUT" > ".opencode/session_state/tool_outputs/${HANDLE}.txt"
echo "[MASKED: $HANDLE] (original ${#INPUT} chars stored)"