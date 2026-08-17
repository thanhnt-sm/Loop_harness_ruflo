#!/bin/bash
# Post-tool-use hook for opencode
# Applies compression, masking, and runs compensation layers

set -euo pipefail

TOOL="$1"
ARGS="$2"
OUTPUT="$3"
CONTEXT_FILE="/tmp/opencode_context_$$.json"

# Load context
if [[ ! -f "$CONTEXT_FILE" ]]; then
  echo "$OUTPUT"
  exit 0
fi

COMPRESS=$(jq -r '.compress // false' "$CONTEXT_FILE")
MASK=$(jq -r '.mask // false' "$CONTEXT_FILE")
CMD=$(jq -r '.args // ""' "$CONTEXT_FILE")

# Apply terminal compression (U-H17)
if [[ "$COMPRESS" == "true" && -n "$OUTPUT" ]]; then
  OUTPUT=$(echo "$OUTPUT" | .venv/bin/python -c "
import sys, json, re
data = sys.stdin.read()
cmd = '$CMD'
if cmd.startswith('git diff'):
    lines = data.split('\n')
    result = []
    unchanged = 0
    for line in lines:
        if line.startswith(' ') and not line.startswith(('+++', '---', '@@')):
            unchanged += 1
            if unchanged == 1:
                result.append('  [... unchanged context collapsed ...]')
        else:
            if unchanged > 1:
                result.append(f'  [... {unchanged - 1} more unchanged lines ...]')
            unchanged = 0
            result.append(line)
    if unchanged > 1:
        result.append(f'  [... {unchanged - 1} more unchanged lines ...]')
    print('\n'.join(result))
elif re.match(r'^(npm|yarn|pnpm)\s+(install|ci|add)', cmd):
    lines = data.split('\n')
    skip = [r'^\s*(added|removed|updated|audited)\s+\d+\s+package',
            r'^\s*\d+\s+(package|vulnerabilit)',
            r'^\s*(found|fixed)\s+\d+\s+(vulnerabilit|issue)',
            r'^\s*npm\s+(notice|WARN|ERR!)',
            r'^\s*(deprecated|warning|notice)',
            r'^\s*[│├└─]\s',
            r'^\s*[#▓░▒░]+\s+\d+%',
            r'^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]',
            r'^\s*reify:',
            r'^\s*timing\s+']
    import re
    skip = [re.compile(p, re.I) for p in skip]
    filtered = [l for l in data.split('\n') if not any(r.search(l) for r in skip)]
    print('\n'.join(filtered))
elif cmd.startswith('ls') and '-l' in cmd:
    lines = data.split('\n')
    result = []
    for line in lines:
        parts = line.split()
        if len(parts) >= 9:
            result.append(' '.join(parts[8:]))
        else:
            result.append(line)
    print('\n'.join(result))
elif cmd.startswith('git status'):
    lines = data.split('\n')
    staged = unstaged = untracked = 0
    for line in lines:
        stripped = line.lstrip()
        if re.match(r'^[MADRC]', stripped) and not line.startswith((' ', '\t')):
            staged += 1
        elif re.match(r'^[MADRC]', stripped) and line.startswith((' ', '\t')):
            unstaged += 1
        elif stripped.startswith('??'):
            untracked += 1
    parts = []
    if staged: parts.append(f'{staged} staged')
    if unstaged: parts.append(f'{unstaged} unstaged')
    if untracked: parts.append(f'{untracked} untracked')
    if parts:
        print(f'[git status: {\", \".join(parts)}]')
    else:
        print('[git status: clean]')
else:
    print(data, end='')
" 2>/dev/null || echo "$OUTPUT")
fi

# Apply observation masking (U-H18)
if [[ "$MASK" == "true" && ${#OUTPUT} -gt 1000 ]]; then
  HANDLE="tool_output:$(date +%s):$(openssl rand -hex 4)"
  echo "[MASKED: $HANDLE] (original ${#OUTPUT} chars stored)"
  # Store full output
  mkdir -p ".opencode/session_state/tool_outputs"
  echo "$OUTPUT" > ".opencode/session_state/tool_outputs/${HANDLE}.txt"
  OUTPUT="[MASKED: $HANDLE] (original ${#OUTPUT} chars stored)"
fi

# Fable-judge on done declarations
if echo "$OUTPUT" | grep -qiE '\b(done|complete|completed|finished|all (tests|checks) pass)\b'; then
  .venv/bin/python .devin/scripts/fable_judge_compensation.py "test-session" >/dev/null 2>&1 || true
fi

echo "$OUTPUT"