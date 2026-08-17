#!/usr/bin/env python3
"""Observation Masking Hook — filters tool outputs from history after use.

Complements terminal compression by removing tool results from conversation
history once the agent has read them. This keeps context lean by offloading
used observations to filesystem.

Reference: agentpatterns.ai/context-engineering/observation-masking

Behavior:
- After a tool call completes and agent reads the result, mask the tool output
- Store full output in session_state/tool_outputs/<tool_call_id>.json
- Replace in-context output with a reference handle
- Agent can request full output back by referencing the handle

This is a PostToolUse hook that marks outputs for masking on next turn.
"""
from __future__ import annotations

import json
import os
import sys
import uuid
from pathlib import Path

# Only mask outputs larger than this threshold (chars)
MASK_THRESHOLD = 1000

# Tools whose outputs are safe to mask after first read
MASKABLE_TOOLS = {
    "Read", "read",
    "Grep", "grep",
    "Glob", "glob",
    "LS", "ls",
    "Task", "task",
    "Bash", "bash", "Shell", "Execute", "exec",
    "NotebookRead", "notebook_read",
}

# Tools whose outputs should NEVER be masked (signal-dominated)
NEVER_MASK = {
    "Write", "write",
    "Edit", "edit",
    "NotebookEdit", "notebook_edit",
    "TodoWrite", "todo_write",
    "WebFetch", "webfetch",
    "WebSearch", "websearch",
}


def _get_session_root(root: Path, session_id: str) -> Path:
    """Get session-specific tool outputs directory."""
    out_dir = root / ".devin" / "session_state" / session_id / "tool_outputs"
    out_dir.mkdir(parents=True, exist_ok=True)
    return out_dir


def _should_mask(tool_name: str, output: str) -> bool:
    """Check if tool output should be masked."""
    if tool_name in NEVER_MASK:
        return False
    if tool_name not in MASKABLE_TOOLS:
        return False
    if len(output) < MASK_THRESHOLD:
        return False
    return True


def _store_full_output(root: Path, session_id: str, tool_call_id: str, tool_name: str, output: str) -> str:
    """Store full output to filesystem, return handle."""
    session_root = _get_session_root(root, session_id)
    handle = f"tool_output:{tool_name}:{tool_call_id[:8]}"
    file_path = session_root / f"{tool_call_id}.json"

    record = {
        "handle": handle,
        "tool_name": tool_name,
        "tool_call_id": tool_call_id,
        "output": output,
        "stored_at": __import__("datetime").datetime.now(__import__("datetime").timezone.utc).isoformat(),
        "size_chars": len(output),
    }

    try:
        file_path.write_text(json.dumps(record, ensure_ascii=False, indent=2), encoding="utf-8")
    except Exception as e:
        print(f"[observation_masking] Failed to store output: {e}", file=sys.stderr)
        return ""

    return handle


def _create_masked_output(handle: str, original_size: int) -> str:
    """Create the masked output that replaces the full output in context."""
    return (
        f"[MASKED: {handle}] "
        f"(original {original_size} chars stored in session_state/tool_outputs/). "
        f"To retrieve: ask to read tool output {handle}"
    )


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})
    session_id = data.get("session_id", "")
    tool_call_id = data.get("tool_call_id", str(uuid.uuid4()))

    if not session_id:
        sys.exit(0)

    # Extract output content
    output = ""
    if isinstance(tool_response, dict):
        output = str(tool_response.get("content", tool_response.get("output", "")))
    elif isinstance(tool_response, str):
        output = tool_response

    if not _should_mask(tool_name, output):
        sys.exit(0)

    # Find repo root
    try:
        import subprocess
        result = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=os.getcwd()
        )
        root = Path(result.stdout.strip()) if result.returncode == 0 and result.stdout.strip() else Path.cwd()
    except Exception:
        root = Path.cwd()

    # Store full output and create masked version
    handle = _store_full_output(root, session_id, tool_call_id, tool_name, output)
    if not handle:
        sys.exit(0)

    masked = _create_masked_output(handle, len(output))

    # Return masked output via hookSpecificOutput
    result = {
        "hookSpecificOutput": {
            "hookEventName": "PostToolUse",
            "updatedToolOutput": masked
        }
    }
    print(json.dumps(result, ensure_ascii=False))
    sys.exit(0)


if __name__ == "__main__":
    main()