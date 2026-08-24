"""Ghi jsonl co gioi han va quay vong (rotate) file log.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)

def _append_bounded_jsonl(path: Path, record: dict, max_records: int = CANDIDATE_MEMORY_MAX) -> None:
    """Append a record to a jsonl file, keeping the file bounded."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if len(lines) >= max_records:
                lines = lines[-(max_records - 1):]
                path.write_text("\n".join(lines) + "\n" if lines else "", encoding="utf-8")
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except (json.JSONDecodeError, TypeError, ValueError):
        pass


    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

def _rotate(path: Path, max_lines: int = 1000) -> None:
    """Rotate a jsonl file if it exceeds max_lines."""
    try:
        if path.exists() and path.read_text(encoding="utf-8").count("\n") >= max_lines:
            backup = path.with_suffix(".1.jsonl")
            if backup.exists():
                backup.unlink()
            path.rename(backup)
    except (OSError, UnicodeDecodeError):
        pass


    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
