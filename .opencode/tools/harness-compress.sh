#!/bin/bash
# Harness Compress Tool - Terminal Output Compression (U-H17)

set -euo pipefail
source "$(dirname "$0")/../hooks/find_python.sh"

COMMAND="${1:-}"
INPUT="${2:-}"

if [[ -z "$INPUT" ]]; then
  INPUT=$(cat)
fi

if [[ -n "$PYTHON" && -f ".devin/hooks/compress_terminal_output.py" ]]; then
  echo "$INPUT" | $PYTHON -c "
import sys, json, re
data = sys.stdin.read()
cmd = '$COMMAND'
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
        print(f'[git status: {\", \".join(parts)}]')
    else:
        print('[git status: clean]')
else:
    print(data, end='')
" 2>/dev/null
else
  cat
fi