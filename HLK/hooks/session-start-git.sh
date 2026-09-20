#!/usr/bin/env bash
# cmdc SessionStart hook — inject current branch + uncommitted state as
# additionalContext, so the model sees the workspace status before it starts.
#
# Pattern mirrors .opencode/plugins/harness.ts git-context bridge.
set -euo pipefail

# Skip if not in a git repo.
if ! git rev-parse --show-toplevel >/dev/null 2>&1; then
  exit 0
fi

branch=$(git branch --show-current 2>/dev/null || echo "unknown")
status=$(git status --porcelain 2>/dev/null | head -20 || true)

if [ -n "$status" ]; then
  ctx="Current git branch: ${branch}.
Uncommitted changes:
${status}"
else
  ctx="Current git branch: ${branch}. Working tree is clean."
fi

jq -n --arg ctx "$ctx" '{
  systemMessage: "cmdc harness bridge active (.devin + .opencode)",
  hookSpecificOutput: {
    hookEventName: "SessionStart",
    additionalContext: $ctx
  }
}'
