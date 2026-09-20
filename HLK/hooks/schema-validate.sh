#!/usr/bin/env bash
# cmdc PreToolUse + PostToolUse hook (write|edit) — basic schema + path guard.
#
# Defensive layer bổ sung cho permission deny rules:
#   1. Block write/edit path trỏ ra ngoài workspace (kể cả khi rule miss).
#   2. Reject write vào control surfaces mà deny rule có thể miss do wildcard.
#   3. Fail-closed cho path nghi ngờ, fail-open cho path OK.
#
# Không phải replacement cho settings.json.permissions — chỉ là redundant
# defense-in-depth. Match contract: stdout JSON với permissionDecision.

set -euo pipefail

payload=$(cat)
path=$(printf '%s' "$payload" | jq -r '.tool_input.file_path // .tool_input.absolute_path // ""')

# Allow when no path (e.g. read tool with no target).
if [ -z "$path" ] || [ "$path" = "null" ]; then
  exit 0
fi

# Normalize Windows backslashes to forward for pattern matching.
norm=$(printf '%s' "$path" | tr '\\' '/')

deny_pattern='^(\./)?\.(env|env\.[^/]+|git(/.*)?|mcp\.json|commandcode/settings\.json|commandcode/settings\.local\.json|devin/canon(/.*)?|devin/agents(/.*)?|devin/skills(/.*)?|devin/scripts(/.*)?|devin/hooks(/.*)?|opencode(/.*)?|khuym(/.*)?|aide(/.*)?|claude(/.*)?|bashrc|zshrc|profile|gitignore|gitmodules|gitconfig)$'
deny_pattern+='|^/?(etc|root|home/[^/]+/\.(ssh|aws|gnupg|kube|config/gh)(/.*)?)$'
deny_pattern+='|^/[^/]+(/.*)?$'   # filesystem root

# Allow patterns (override deny for workspace reads).
allow_prefix='./HLK/config/hlk.config.json'  # explicit allow to edit HLK config (after user confirms)

if printf '%s' "$norm" | grep -qiE "$deny_pattern"; then
  if printf '%s' "$norm" | grep -qF "$allow_prefix"; then
    exit 0
  fi
  jq -n --arg path "$path" '{
    systemMessage: "blocked sensitive path (cmdc schema-validate.sh)",
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Path matches sensitive pattern, blocked by cmdc schema-validate.sh: " + $path)
    }
  }'
  exit 0
fi

# Allow (advisory context).
exit 0
