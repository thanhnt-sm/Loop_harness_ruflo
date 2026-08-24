"""Cac ham tro giup co ban: redact bi mat, uoc luong kich thuoc phan hoi,
trich xuat duong dan file / lenh tu tool_input.
"""
from __future__ import annotations

import re

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)

def _redact(text: str) -> str:
    """Mask common secret patterns in command strings."""
    if not isinstance(text, str):
        return text
    for pat in _SECRET_PATTERNS:
        text = pat.sub(lambda m: m.group(0)[:m.group(0).find("=") + 1] + "***" if "=" in m.group(0) else "***", text)
    return text

def _response_size(response) -> int:
    """Estimate the size of a tool response in characters."""
    if isinstance(response, dict):
        return len(str(response.get("content", response)))
    elif isinstance(response, str):
        return len(response)
    return 0

def _extract_file_path(tool_input: dict) -> str:
    """Try to extract a file path from common tool arguments."""
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            return tool_input[key]
    return ""

def _extract_command(tool_input: dict) -> str:
    """Extract a command (truncated + redacted) for Bash-like tools."""
    cmd = tool_input.get("command", "")
    if not cmd:
        return ""
    redacted = _redact(cmd[:200])
    return redacted
