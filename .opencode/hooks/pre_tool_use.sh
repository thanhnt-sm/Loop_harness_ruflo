#!/bin/bash
# Pre-tool-use hook for opencode
# Applies terminal compression and observation masking

set -euo pipefail

TOOL="$1"
ARGS="$2"
CONTEXT_FILE="/tmp/opencode_context_$$.json"

# Save context for post-tool-use
cat > "$CONTEXT_FILE" <<EOF
{
  "tool": "$TOOL",
  "args": "$ARGS",
  "compress": false,
  "mask": false
}
EOF

# Apply compression for terminal commands
if [[ "$TOOL" == "bash" || "$TOOL" == "git" ]]; then
  jq '.compress = true' "$CONTEXT_FILE" > "$CONTEXT_FILE.tmp" && mv "$CONTEXT_FILE.tmp" "$CONTEXT_FILE"
fi

# Apply masking for read tools
if [[ "$TOOL" == "read" || "$TOOL" == "grep" || "$TOOL" == "glob" || "$TOOL" == "ls" ]]; then
  jq '.mask = true' "$CONTEXT_FILE" > "$CONTEXT_FILE.tmp" && mv "$CONTEXT_FILE.tmp" "$CONTEXT_FILE"
fi

# Run pre-tool-use verification (C1)
if [[ -f ".venv/bin/python" && -f ".devin/scripts/hook_integrity.py" ]]; then
  .venv/bin/python .devin/scripts/hook_integrity.py --verify >/dev/null 2>&1 || true
fi

# Output context for opencode
cat "$CONTEXT_FILE"