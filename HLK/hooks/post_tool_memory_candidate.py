"""Phat hien va ghi nhan candidate memory tu cac loi lap lai (CVE-2026-AHD-015).
"""
from __future__ import annotations

import json
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)
from post_tool_helpers import _redact

def _repeated_failure_count(journal_path: Path, tool_name: str, command: str, session_id: str) -> int:
    """Count how many times this tool/command has failed in the session journal."""
    count = 0
    if not journal_path.exists():
        return 0
    try:
        for line in journal_path.read_text(encoding="utf-8").splitlines():
            if not line:
                continue
            try:
                entry = json.loads(line)
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
            except Exception as e:
                print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
                continue
            if entry.get("session_id") != session_id:
                continue
            if entry.get("tool") != tool_name:
                continue
            if entry.get("ok"):
                continue
            entry_cmd = entry.get("command", "")
            if command and entry_cmd != command:
                continue
            count += 1
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    return count

def _extract_candidate_memory(tool_name: str, tool_input: dict, tool_response, ts: str, ok: bool = True) -> dict | None:
    """Detect repeated failure patterns and turn them into candidate memory."""
    try:
        # Check if the tool failed
        if ok:
            return None

        # Heuristic: shell command errors with a clear pattern
        if tool_name in ("Bash", "bash", "Shell", "Execute", "exec"):
            cmd = tool_input.get("command", "")
            resp_text = ""
            if isinstance(tool_response, dict):
                resp_text = str(tool_response.get("content", ""))
            elif isinstance(tool_response, str):
                resp_text = tool_response

            lower = resp_text.lower()
            if "permission denied" in lower:
                return {
                    "trigger": "shell command fails with 'Permission denied'",
                    "correct_action": "check file permissions or use a command that does not require elevation",
                    "counter": _redact(cmd[:200]),
                    "ts": ts,
                }
            if "not found" in lower or "no such file" in lower:
                return {
                    "trigger": "shell command fails with 'not found' or 'no such file'",
                    "correct_action": "verify the path exists before running the command",
                    "counter": _redact(cmd[:200]),
                    "ts": ts,
                }
            if "invalid" in lower or "unrecognized" in lower:
                return {
                    "trigger": "shell command fails with invalid argument/parameter",
                    "correct_action": "recheck the command syntax and flags",
                    "counter": _redact(cmd[:200]),
                    "ts": ts,
                }
        return None
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        return None

def _memory_rate_limited(candidate_path: Path) -> bool:
    """CVE-2026-AHD-015: rate limit — max 5 candidate memories/session/giờ."""
    if not candidate_path.exists():
        return False
    now = time.time()
    recent = 0
    try:
        for line in candidate_path.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                record = json.loads(line)
                ts = record.get("ts", "")
                try:
                    t = datetime.fromisoformat(ts).timestamp()
                except (TypeError, ValueError):
                    continue
                if now - t <= CANDIDATE_MEMORY_WINDOW_SECONDS:
                    recent += 1
            except (json.JSONDecodeError, TypeError, ValueError):
                continue
    except (OSError, UnicodeDecodeError):
        return False
    return recent >= CANDIDATE_MEMORY_PER_HOUR

def _audit_candidate(root: Path, candidate: dict, session_id: str) -> None:
    """CVE-2026-AHD-015: log candidate memory ra telemetry để audit."""
    try:
        from datetime import datetime as _dt
        audit_path = ahd_session.get_config_root(root) / "telemetry" / "candidate_memory_audit.jsonl"
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        record = {
            "ts": _dt.now(timezone.utc).isoformat(),
            "session_id": session_id,
            "trigger": candidate.get("trigger", ""),
            "correct_action": candidate.get("correct_action", ""),
            "human_confirmed": False,
        }
        with open(audit_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(record, ensure_ascii=False) + "\n")
    except Exception as e:
        print(f"[post_tool_use] candidate audit lỗi: {e}", file=sys.stderr)
