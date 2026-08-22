#!/bin/bash
# Pre-tool-use hook for opencode — cross-platform (Windows git-bash + macOS/Linux)
# Delegate sang .devin/hooks/pre_tool_use.py để thừa hưởng 9 gates enforcement:
#   - Workspace layout (chặn file rác/sai chỗ)
#   - Plan enforcement (chặn code không plan)
#   - Dangerous command (rm -rf, force-push...)
#   - Risk contract (chặn sửa hooks/canon/config)
#   - SSRF, encoding bypass, cost cap, call-graph, sandbox

# KHÔNG dùng set -e — pipe exit code cần được xử lý thủ công để tránh bypass 9 gates
set -uo pipefail

TOOL="${1:-}"
ARGS="${2:-}"
CONTEXT_FILE="/tmp/opencode_context_$$.json"

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

# Pass TOOL/ARGS qua environment variables (anti-injection — không dùng string interpolation)
export OC_TOOL="$TOOL"
export OC_ARGS="$ARGS"
export OC_CONTEXT_FILE="$CONTEXT_FILE"

# Save context for post-tool-use
if [ -n "$PYTHON" ]; then
    $PYTHON -c "
import json, os
context = {'tool': os.environ.get('OC_TOOL', ''), 'args': os.environ.get('OC_ARGS', ''), 'compress': False, 'mask': False}
with open(os.environ.get('OC_CONTEXT_FILE', '/tmp/oc_ctx.json'), 'w') as f:
    json.dump(context, f)
" 2>/dev/null || true
fi

# Apply compression for terminal commands
if [[ "$TOOL" == "bash" || "$TOOL" == "git" ]]; then
    $PYTHON -c "
import json, os
ctx_file = os.environ.get('OC_CONTEXT_FILE', '/tmp/oc_ctx.json')
with open(ctx_file) as f:
    context = json.load(f)
context['compress'] = True
with open(ctx_file, 'w') as f:
    json.dump(context, f)
" 2>/dev/null || true
fi

# Apply masking for read tools
if [[ "$TOOL" == "read" || "$TOOL" == "grep" || "$TOOL" == "glob" || "$TOOL" == "ls" ]]; then
    $PYTHON -c "
import json, os
ctx_file = os.environ.get('OC_CONTEXT_FILE', '/tmp/oc_ctx.json')
with open(ctx_file) as f:
    context = json.load(f)
context['mask'] = True
with open(ctx_file, 'w') as f:
    json.dump(context, f)
" 2>/dev/null || true
fi

# --- Delegate sang Devin pre_tool_use.py (9 gates enforcement) ---
# Dùng environment variables thay string interpolation để chống injection
if [ -n "$PYTHON" ] && [ -f ".devin/hooks/pre_tool_use.py" ]; then
    # Convert opencode args sang Devin hook format, pipe sang Devin hook
    # KHÔNG suppress stderr — block reason cần hiển thị cho user
    hook_output=$($PYTHON -c "
import json, sys, os
tool = os.environ.get('OC_TOOL', '')
args = os.environ.get('OC_ARGS', '')
hook_input = {
    'tool_name': tool,
    'tool_input': {},
    'session_id': 'opencode-session'
}
try:
    hook_input['tool_input'] = json.loads(args)
except (json.JSONDecodeError, TypeError):
    if tool in ('bash', 'git', 'shell', 'execute'):
        hook_input['tool_input'] = {'command': args}
    else:
        hook_input['tool_input'] = {'input': args}
json.dump(hook_input, sys.stdout)
" 2>/dev/null | $PYTHON .devin/hooks/pre_tool_use.py 2>&1)
    exit_code=$?
    if [ $exit_code -eq 2 ]; then
        echo "[opencode guard] BLOCKED by Devin pre_tool_use.py" >&2
        echo "$hook_output" >&2
        exit 2
    fi
fi

# Run hook integrity check (C1) — best-effort
if [ -n "$PYTHON" ] && [ -f ".devin/scripts/hook_integrity.py" ]; then
    $PYTHON .devin/scripts/hook_integrity.py --verify >/dev/null 2>&1 || true
fi

# Output context for post-tool-use
cat "$CONTEXT_FILE" 2>/dev/null || echo "{}"
