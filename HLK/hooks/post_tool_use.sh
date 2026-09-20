#!/bin/bash
# Post-tool-use hook for opencode — cross-platform (Windows git-bash + macOS/Linux)
# Applies compression, masking, and runs compensation layers

set -uo pipefail

TOOL="${1:-}"
ARGS="${2:-}"
OUTPUT="${3:-}"
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

# Load context
if [[ ! -f "$CONTEXT_FILE" ]]; then
  echo "$OUTPUT"
  exit 0
fi

COMPRESS=$($PYTHON -c "import json; print(json.load(open('$CONTEXT_FILE')).get('compress', False))" 2>/dev/null || echo "False")
MASK=$($PYTHON -c "import json; print(json.load(open('$CONTEXT_FILE')).get('mask', False))" 2>/dev/null || echo "False")
CMD=$($PYTHON -c "import json; print(json.load(open('$CONTEXT_FILE')).get('args', ''))" 2>/dev/null || echo "")

# Apply terminal compression (U-H17)
if [[ "$COMPRESS" == "True" && -n "$OUTPUT" ]]; then
  OUTPUT=$(echo "$OUTPUT" | $PYTHON -c "
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
    import re
    lines = data.split('\n')
    skip = [re.compile(p, re.I) for p in [
        r'^\s*(added|removed|updated|audited)\s+\d+\s+package',
        r'^\s*\d+\s+(package|vulnerabilit)',
        r'^\s*(found|fixed)\s+\d+\s+(vulnerabilit|issue)',
        r'^\s*npm\s+(notice|WARN|ERR!)',
        r'^\s*(deprecated|warning|notice)',
        r'^\s*[│├└─]\s',
        r'^\s*[#▓░▒░]+\s+\d+%',
        r'^\s*[⠋⠙⠹⠸⠼⠴⠦⠧⠇⠏]',
        r'^\s*reify:',
        r'^\s*timing\s+',
    ]]
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
        print(f'[git status: {", ".join(parts)}]')
    else:
        print('[git status: clean]')
else:
    print(data, end='')
" 2>/dev/null || echo "$OUTPUT")
fi

# Apply observation masking (U-H18) — cross-platform cleanup
if [[ "$MASK" == "True" && ${#OUTPUT} -gt 1000 ]]; then
  HANDLE="tool_output:$(date +%s):$(openssl rand -hex 4 2>/dev/null || echo "$(date +%s%N)")"
  # Store full output
  mkdir -p ".opencode/session_state/tool_outputs"
  echo "$OUTPUT" > ".opencode/session_state/tool_outputs/${HANDLE}.txt"
  OUTPUT="[MASKED: $HANDLE] (original ${#OUTPUT} chars stored)"

  # Auto-cleanup: giữ tối đa 50 file (cross-platform, không dùng ls|xargs)
  if [ -n "$PYTHON" ]; then
    $PYTHON -c "
import os, time
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
fi

# Fable-judge on done declarations
if echo "$OUTPUT" | grep -qiE '\b(done|complete|completed|finished|all (tests|checks) pass)\b'; then
  if [ -n "$PYTHON" ] && [ -f ".devin/scripts/fable_judge_compensation.py" ]; then
    $PYTHON .devin/scripts/fable_judge_compensation.py "test-session" >/dev/null 2>&1 || true
  fi
fi

echo "$OUTPUT"
