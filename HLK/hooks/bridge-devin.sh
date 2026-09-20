#!/usr/bin/env bash
# cmdc generic bridge — forwards every cmdc hook event to the matching
# .devin/hooks/<event>.py (if it exists). Fail-open: any error is logged
# to stderr and the hook returns no opinion (exit 0, empty stdout).
#
# Usage: bridge-devin.sh <event> <tool>
#   event: SessionStart | PreToolUse | PostToolUse | Stop
#   tool:  shell | write | edit | "" (empty for non-tool events)
#
# This mirrors .opencode/plugins/harness.ts semantics (best-effort + fail-open).
set -uo pipefail

event="${1:-}"
tool="${2:-}"

# Map cmdc event → Devin hook script.
case "$event" in
  SessionStart)  script=".devin/hooks/session_start.py" ;;
  PreToolUse)
    case "$tool" in
      shell) script=".devin/hooks/pre_tool_use.py" ;;
      write|edit) script=".devin/hooks/pre_tool_use.py" ;;
      *) script=".devin/hooks/pre_tool_use.py" ;;
    esac
    ;;
  PostToolUse)
    case "$tool" in
      shell) script=".devin/hooks/post_tool_use.py" ;;
      write|edit) script=".devin/hooks/post_tool_use.py" ;;
      *) script=".devin/hooks/post_tool_use.py" ;;
    esac
    ;;
  Stop)          script=".devin/hooks/stop.py" ;;
  *)             script="" ;;
esac

if [ -z "$script" ] || [ ! -f "$script" ]; then
  exit 0
fi

# Resolve Python (Windows + Unix venv + system).
py=""
for cand in "${CMDCODE_PYTHON:-}" ".venv/Scripts/python.exe" ".venv/bin/python" "python" "python3"; do
  if [ -n "$cand" ] && command -v "$cand" >/dev/null 2>&1; then
    py="$cand"; break
  fi
  if [ -n "$cand" ] && [ -f "$cand" ]; then
    py="$cand"; break
  fi
done

if [ -z "$py" ]; then
  echo "[bridge-devin.sh] no python — skipped $script" >&2
  exit 0
fi

payload=$(cat)

# Fire-and-forget: don't block cmdc on Python hook latency.
(
  printf '%s' "$payload" | \
    COMMANDCODE_PROJECT_DIR="${COMMANDCODE_PROJECT_DIR:-$PWD}" \
    COMMANDCODE_SESSION_ID="${COMMANDCODE_SESSION_ID:-cmdc-bridge}" \
    COMMANDCODE_HOOK_EVENT="$event" \
    timeout 3 "$py" "$script" >/dev/null 2>&1 || true
) &

# Always succeed (fail-open contract). Return no opinion.
exit 0
