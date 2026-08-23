"""Ham main() dieu phoi toan bo post-tool-use hook.
"""
from __future__ import annotations

import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

from post_tool_config import (HOOK_TIMEOUT_SECONDS, MAX_ITERATIONS_WITHOUT_STATE_WRITE, MIN_COMPRESSION_THRESHOLD, MAX_OUTPUT_SIZE_COMPRESSION, DEFAULT_COMPRESSION_THRESHOLD, MAX_FAILURE_THRESHOLD, _CONTEXT_FLAGS_CACHE, _CONTEXT_FLAGS_LOADED, _STATE_WRITE_COUNTER, _STATE_WRITE_BATCH, CONTEXT_OVERSIZE_THRESHOLD, CANDIDATE_MEMORY_MAX, VALID_CORRECT_ACTIONS, CANDIDATE_MEMORY_PER_HOUR, CANDIDATE_MEMORY_WINDOW_SECONDS, _SECRET_PATTERNS)
from post_tool_helpers import (_redact, _response_size, _extract_file_path, _extract_command)
from post_tool_sha import (_compute_sha256, _track_file_sha)
from post_tool_memory_candidate import (
    _repeated_failure_count, _extract_candidate_memory,
    _memory_rate_limited, _audit_candidate,
)
from post_tool_bounded import (_append_bounded_jsonl, _rotate)
from post_tool_enforce_quality import (
    _u57_auto_quality_checks, _u58_done_detection, _u59_skill_auto_router,
)
from post_tool_enforce_loop import (
    _u60_loop_enforcement, _u61_state_write_verification, _u62_memory_confidence,
)

def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        sys.exit(0)

    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})

    session_id = ahd_session.get_session_id(data)
    root = ahd_session.get_repo_root()

    ts = ahd_session.now_utc()
    file_path = _extract_file_path(tool_input)
    command = _extract_command(tool_input) if tool_name in ("Bash", "bash", "Shell", "Execute", "exec") else ""

    # U20: Track file SHA + invalidate verification on write (moved after success check below)

    # Determine success
    ok = True
    failure_markers = [
        "permission denied", "no such file or directory", "not found", "unrecognized",
        "invalid", "command not found", "exit code", "fatal", "failed",
    ]
    if isinstance(tool_response, dict):
        if "error" in tool_response and tool_response["error"]:
            ok = False
        elif "ok" in tool_response and not tool_response["ok"]:
            ok = False
        elif tool_response.get("exit_code", 0) not in (0, None, ""):
            ok = False
        elif tool_response.get("status", "").lower() not in ("", "success", "ok"):
            ok = False
        else:
            content = str(tool_response.get("content", "")).lower()
            if "error" in content or any(p in content for p in failure_markers):
                ok = False
    elif isinstance(tool_response, str):
        content = tool_response.lower()
        if "error" in content or any(p in content for p in failure_markers):
            ok = False

    # Read current session state to preserve current_subtask and goal for the journal
    try:
        current_state = ahd_session.read_session_state(session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        current_state = {}

    # U20: Track file SHA + invalidate verification on write (only if tool succeeded)
    if ok:
        _track_file_sha(session_id, file_path, tool_name, root)

    # Update session_state heartbeat (merge, don't overwrite current_subtask)
    # U06: Fallback to file write if primary session_state write fails
    update = {
        "session_id": session_id,
        "status": "in_progress",
        "last_heartbeat": ts,
        "last_tool": tool_name,
    }
    if file_path:
        update["last_file"] = file_path
    update["last_error"] = not ok
    # Only set status if not already present (avoid overwriting completed)
    if current_state.get("status"):
        update.pop("status")
    # U17: Track cumulative cost — merge into same update dict (avoid double write)
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
        from cost_tracker import _estimate_cost, check_cost_cap_session
        response_size = len(str(tool_response)) if tool_response else 0
        cost = _estimate_cost(tool_name, response_size)
        cumulative = round(current_state.get("cumulative_cost", 0.0) + cost, 6)
        cost_cap = current_state.get("cost_cap", 5.0)
        call_count = current_state.get("cost_tracked_calls", 0) + 1
        update["cumulative_cost"] = cumulative
        update["cost_cap"] = cost_cap
        update["cost_tracked_calls"] = call_count
        update["last_tool_cost"] = cost
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
        pass

    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

    try:
        ahd_session.update_session_state(session_id, update, root)
    except Exception as e:
        # U06: Fallback — write heartbeat to loop_state_fallback directory
        try:
            fallback_dir = ahd_session.get_config_root(root) / "loop_state_fallback"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / f"{session_id}.heartbeat.json"
            fallback_data = {**update, "fallback": True, "error": str(e)[:200]}
            fallback_path.write_text(json.dumps(fallback_data, ensure_ascii=False), encoding="utf-8")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass

    # U17: Check cost cap after state write (separate check, not write)
        except Exception as e:
            print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
            pass

    # U17: Check cost cap after state write (separate check, not write)
    try:
        exceeded, cost_msg = check_cost_cap_session(root, session_id)
        if exceeded:
            print(f"[U17 COST CAP] {cost_msg}", file=sys.stderr)
        elif cost_msg:
            print(f"[U17 COST] {cost_msg}", file=sys.stderr)
    except (ValueError, TypeError, KeyError, AttributeError):
        pass

    # CVE-2026-AHD-013: append entry vào cost ledger (append-only + HMAC).
    # Lỗi ledger KHÔNG chặn tool call — chỉ best-effort (fail mềm, log stderr).
    try:
        from cost_ledger import append_entry
        append_entry(root, session_id, tool_name, cost, cumulative)
    except Exception as e:
        print(f"[post_tool_use] WARNING: cost_ledger append lỗi: {e}", file=sys.stderr)

    # Write per-session journal
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

    # Write per-session journal
    journal_path = ahd_session.get_config_root(root) / "session_state" / session_id / "journal.jsonl"
    try:
        _rotate(journal_path)
        journal_entry = {
            "ts": ts,
            "tool": tool_name,
            "session_id": session_id,
            "ok": ok,
        }
        if file_path:
            journal_entry["file"] = file_path
        if command:
            journal_entry["command"] = command
        current_subtask = current_state.get("current_subtask", "")
        if current_subtask:
            journal_entry["current_subtask"] = current_subtask
        ahd_session.append_jsonl(journal_path, journal_entry)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

    # Detect oversized context and enforce compaction
    try:
        oversized = _response_size(tool_response) > CONTEXT_OVERSIZE_THRESHOLD
        if oversized:
            flags = ahd_session.read_context_flags(session_id, root)
            counter = flags.get("oversized_tool_calls_since_flag", 0)
            ahd_session.write_context_flags(session_id, {
                "context_oversized": True,
                "oversized_tool_calls_since_flag": counter,
                "oversized_first_detected": ts,
            }, root)
            # Print directive to stderr — most tools feed hook stderr back to the agent.
            print(
                f"[Agent Harness Deploy] context_oversized detected "
                f"(response > {CONTEXT_OVERSIZE_THRESHOLD} chars). "
                f"Run context-compactor skill before continuing: "
                f"offload full output to .devin/tmp/, keep head+tail+path in context. "
                f"Read .devin/context_flags/{session_id}.json for details.",
                file=sys.stderr,
            )
        elif ahd_session.read_context_flags(session_id, root).get("context_oversized"):
            # Flag still set from a prior call — agent hasn't compacted yet. Increment counter.
            flags = ahd_session.read_context_flags(session_id, root)
            counter = flags.get("oversized_tool_calls_since_flag", 0) + 1
            ahd_session.write_context_flags(session_id, {
                "oversized_tool_calls_since_flag": counter,
            }, root)
    except (ValueError, TypeError, KeyError, AttributeError):
        pass

    # Detect candidate memory (only record after the same command fails 2+ times)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

    # Detect candidate memory (only record after the same command fails 2+ times)
    try:
        candidate = _extract_candidate_memory(tool_name, tool_input, tool_response, ts, ok=ok)
        if candidate:
            # CVE-2026-AHD-015: chỉ accept correct_action trong allowlist
            if candidate.get("correct_action") not in VALID_CORRECT_ACTIONS:
                print(
                    f"[CVE-015] candidate memory bị từ chối: correct_action ngoài allowlist",
                    file=sys.stderr,
                )
                candidate = None
        if candidate:
            # The current failure has already been appended to the journal
            fail_count = _repeated_failure_count(journal_path, tool_name, command, session_id)
            if fail_count >= 2:
                candidate_path = ahd_session.get_config_root(root) / "session_state" / session_id / "candidate_memory.jsonl"
                # CVE-2026-AHD-015: rate limit 5/session/giờ
                if _memory_rate_limited(candidate_path):
                    print(
                        f"[CVE-015] candidate memory bị bỏ: vượt rate limit "
                        f"{CANDIDATE_MEMORY_PER_HOUR}/giờ/session",
                        file=sys.stderr,
                    )
                else:
                    # CVE-2026-AHD-015: human confirmation bắt buộc để promote
                    # lên long-term memory (memory_audit.py skip nếu chưa confirm)
                    candidate["session_id"] = session_id
                    candidate["human_confirmed"] = False
                    _append_bounded_jsonl(candidate_path, candidate)
                    # CVE-2026-AHD-015: telemetry audit log
                    _audit_candidate(root, candidate, session_id)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

    # U57-U62: Enforcement hooks (non-blocking, append to session_state)
    try:
        _u57_auto_quality_checks(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    try:
        _u58_done_detection(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    try:
        _u59_skill_auto_router(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    try:
        _u60_loop_enforcement(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    try:
        _u61_state_write_verification(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass
    try:
        _u62_memory_confidence(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        pass

    sys.exit(0)
