#!/usr/bin/env bash
# cmdc PreToolUse shell hook — block destructive commands.
# Mirrors the deny list in .commandcode/settings.json + .devin/config.json.
# Mirrors .opencode/plugins/harness.ts logic (fail-open bridge to .devin/hooks).
#
# Input:  stdin = JSON { tool_name, tool_input.command, ... }
# Output: stdout = { hookSpecificOutput: { permissionDecision: "deny" | "allow" } }
set -euo pipefail

payload=$(cat)
cmd=$(printf '%s' "$payload" | jq -r '.tool_input.command // ""')

# Allow when no command (not a shell call).
if [ -z "$cmd" ] || [ "$cmd" = "null" ]; then
  exit 0
fi

# Destructive patterns (compiled from .devin/config.json deny list + AHD canon).
pattern='rm[[:space:]]+-[rR]f?[[:space:]]+/'
pattern+='|rm[[:space:]]+-[rR]f?[[:space:]]+~'
pattern+='|rm[[:space:]]+-[rR]f?[[:space:]]+(\$HOME|\$\{HOME\})'
pattern+='|git[[:space:]]+push[[:space:]]+(-f|--force)'
pattern+='|git[[:space:]]+reset[[:space:]]+--hard'
pattern+='|git[[:space:]]+clean[[:space:]]+-fd'
pattern+='|git[[:space:]]+branch[[:space:]]+-D'
pattern+='|git[[:space:]]+checkout[[:space:]]+--[[:space:]]+\.'
pattern+='|curl[[:space:]]+.*\|.*(sh|bash)'
pattern+='|wget[[:space:]]+.*\|.*(sh|bash)'
pattern+='|:[[:space:]]*\(\)[[:space:]]*\{'
pattern+='|sudo[[:space:]]+(rm|dd|mkfs|fdisk|chmod[[:space:]]+-R[[:space:]]+777)'
pattern+='|mkfs(\.[a-z0-9]+)?[[:space:]]+'
pattern+='|dd[[:space:]]+if='
pattern+='|shred[[:space:]]+'
pattern+='|chmod[[:space:]]+-R[[:space:]]+777'
pattern+='|shutdown|reboot|halt|poweroff'
pattern+='|swapoff|cryptsetup[[:space:]]+(luksFormat|erase|remove)'

if printf '%s' "$cmd" | grep -qiE "$pattern"; then
  jq -n --arg cmd "$cmd" '{
    systemMessage: "blocked destructive command (cmdc deny-dangerous.sh)",
    hookSpecificOutput: {
      hookEventName: "PreToolUse",
      permissionDecision: "deny",
      permissionDecisionReason: ("Command matched destructive pattern. Policy forbids: " + ($cmd | .[0:160]))
    }
  }'
  exit 0
fi

# Allow + add context for the model.
jq -n '{
  hookSpecificOutput: {
    hookEventName: "PreToolUse",
    permissionDecision: "allow",
    additionalContext: "Verified by cmdc deny-dangerous.sh (mirrors .devin/.opencode deny list)"
  }
}'
