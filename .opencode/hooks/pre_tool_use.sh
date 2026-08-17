#!/bin/bash
# Pre-tool-use hook for opencode
# Applies terminal compression and observation masking

set -euo pipefail

TOOL="$1"
ARGS="$2"
CONTEXT_FILE="/tmp/opencode_context_$$.json"
PYTHON=".venv/bin/python"

# Save context for post-tool-use
$PYTHON -c "
import json, sys
context = {'tool': '$TOOL', 'args': '$ARGS', 'compress': False, 'mask': False}
with open('$CONTEXT_FILE', 'w') as f:
    json.dump(context, f)
"

# Apply compression for terminal commands
if [[ "$TOOL" == "bash" || "$TOOL" == "git" ]]; then
    $PYTHON -c "
import json
with open('$CONTEXT_FILE') as f:
    context = json.load(f)
context['compress'] = True
with open('$CONTEXT_FILE', 'w') as f:
    json.dump(context, f)
"
fi

# Apply masking for read tools
if [[ "$TOOL" == "read" || "$TOOL" == "grep" || "$TOOL" == "glob" || "$TOOL" == "ls" ]]; then
    $PYTHON -c "
import json
with open('$CONTEXT_FILE') as f:
    context = json.load(f)
context['mask'] = True
with open('$CONTEXT_FILE', 'w') as f:
    json.dump(context, f)
"
fi

# Run pre-tool-use verification (C1)
if [[ -f ".venv/bin/python" && -f ".devin/scripts/hook_integrity.py" ]]; then
  .venv/bin/python .devin/scripts/hook_integrity.py --verify >/dev/null 2>&1 || true
fi

# Output context for opencode
cat "$CONTEXT_FILE"