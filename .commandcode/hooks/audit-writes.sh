#!/usr/bin/env bash
# cmdc PostToolUse hook (write|edit) — append a tab-separated audit line.
# Mirrors the example in command-code-knowledge/reference/hooks.md.
# Observability only; never blocks.
set -euo pipefail

payload=$(cat)
path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // "?"')
timestamp=$(date -u +%FT%TZ 2>/dev/null || echo "unknown")

log_dir="${COMMANDCODE_PROJECT_DIR:-$PWD}/.commandcode"
mkdir -p "$log_dir"
log_file="$log_dir/write-audit.log"

printf '%s\t%s\t%s\n' "$timestamp" "${COMMANDCODE_SESSION_ID:-no-session}" "$path" >> "$log_file"
exit 0
