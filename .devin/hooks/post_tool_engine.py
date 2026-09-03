"""Ham main() dieu phoi toan bo post-tool-use hook.
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

import ahd_session

from post_tool_config import (
    HOOK_TIMEOUT_SECONDS,
    MAX_ITERATIONS_WITHOUT_STATE_WRITE,
    MIN_COMPRESSION_THRESHOLD,
    MAX_OUTPUT_SIZE_COMPRESSION,
    DEFAULT_COMPRESSION_THRESHOLD,
    MAX_FAILURE_THRESHOLD,
    _CONTEXT_FLAGS_CACHE,
    _CONTEXT_FLAGS_LOADED,
    _STATE_WRITE_COUNTER,
    _STATE_WRITE_BATCH,
    CONTEXT_OVERSIZE_THRESHOLD,
    CANDIDATE_MEMORY_MAX,
    VALID_CORRECT_ACTIONS,
    CANDIDATE_MEMORY_PER_HOUR,
    CANDIDATE_MEMORY_WINDOW_SECONDS,
    _SECRET_PATTERNS,
    MAX_TOOL_CALLS_PER_TASK,
    REPETITION_THRESHOLD,
    CONTEXT_BUDGET_ALERT_PCT,
    CONTEXT_BUDGET_KILL_PCT,
    PROGRESSIVE_TOOL_LIMIT,
)
from post_tool_helpers import (_redact, _response_size, _extract_file_path, _extract_command)
from post_tool_sha import (_compute_sha256, _track_file_sha)
from post_tool_memory_candidate import (
    _repeated_failure_count,
    _extract_candidate_memory,
    _memory_rate_limited,
    _audit_candidate,
)
from post_tool_bounded import (_append_bounded_jsonl, _rotate)
from post_tool_enforce_quality import (
    _u57_auto_quality_checks,
    _u58_done_detection,
    _u59_skill_auto_router,
)
from post_tool_enforce_loop import (
    _u60_loop_enforcement,
    _u61_state_write_verification,
    _u62_memory_confidence,
)
from post_tool_mcp_guard import mcp_guard_call


def main():
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError, Exception) as e:
        # Fail-open: khong chan tool neu payload loi
        if isinstance(e, Exception) and not isinstance(e, (json.JSONDecodeError, TypeError, ValueError)):
            print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_response = data.get("tool_response", {})

    # P1-02: MCP Guard — enforce SERF + circuit breaker cho mcp__* tools
    if tool_name.startswith("mcp__"):
        parts = tool_name.split("__", 2)
        if len(parts) >= 3:
            server_name = parts[1]
            mcp_tool_name = parts[2]
            try:
                from post_tool_mcp_guard import enforce_structured_response

                tool_response = enforce_structured_response(server_name, mcp_tool_name, tool_response)
            except Exception as e:
                print(f"[post_tool_use] MCP guard error: {e}", file=sys.stderr)

    session_id = ahd_session.get_session_id(data)
    root = ahd_session.get_repo_root()

    # P1-03: Loop + Context Guards
    try:
        from context_budget import check_all_guards

        task_id = data.get("task_id", "")
        guard_results = check_all_guards(session_id, tool_name, tool_input, tool_response, task_id)

        if guard_results["context_budget"]["alert"]:
            usage = guard_results["context_budget"]["usage_pct"]
            print(
                f"[P1-03 CONTEXT BUDGET] ALERT: {usage:.1f}% context used "
                f"(threshold: {CONTEXT_BUDGET_ALERT_PCT}%)",
                file=sys.stderr,
            )

        if (
            guard_results["step_limit"]["triggered"]
            or guard_results["repetition"]["triggered"]
            or guard_results["context_budget"]["kill"]
        ):
            print(
                f"[P1-03 KILL SWITCH] Step limit: {guard_results['step_limit']['triggered']}, "
                f"Repetition: {guard_results['repetition']['triggered']}, "
                f"Context kill: {guard_results['context_budget']['kill']}",
                file=sys.stderr,
            )
            ahd_session._locked_json_update(
                ahd_session.get_session_state_path(session_id, root),
                lambda existing: {
                    **(existing or {}),
                    "kill_switch_triggered": True,
                    "kill_reason": {
                        "step_limit": guard_results["step_limit"]["triggered"],
                        "repetition": guard_results["repetition"]["triggered"],
                        "context_kill": guard_results["context_budget"]["kill"],
                    },
                },
                default={},
                session_id=session_id,
            )
    except ImportError:
        pass
    except Exception as e:
        print(f"[post_tool_use] P1-03 guard error: {e}", file=sys.stderr)

    ts = ahd_session.now_utc()
    file_path = _extract_file_path(tool_input)
    command = _extract_command(tool_input) if tool_name in ("Bash", "bash", "Shell", "Execute", "exec") else ""

    # Determine success
    ok = True
    failure_markers = [
        "permission denied",
        "no such file or directory",
        "not found",
        "unrecognized",
        "invalid",
        "command not found",
        "exit code",
        "fatal",
        "failed",
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

    try:
        current_state = ahd_session.read_session_state(session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
        current_state = {}

    if ok:
        _track_file_sha(session_id, file_path, tool_name, root)

    update = {
        "session_id": session_id,
        "status": "in_progress",
        "last_heartbeat": ts,
        "last_tool": tool_name,
    }
    if file_path:
        update["last_file"] = file_path
    update["last_error"] = not ok
    if current_state.get("status"):
        update.pop("status")

    # U17: Track cumulative cost
    cost = 0.0
    cumulative = float(current_state.get("cumulative_cost", 0.0))
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
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError) as e:
        # Giu cost/cumulative mac dinh neu tracker chua san sang
        pass
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)

    try:
        ahd_session.update_session_state(session_id, update, root)
    except Exception as e:
        try:
            fallback_dir = ahd_session.get_config_root(root) / "loop_state_fallback"
            fallback_dir.mkdir(parents=True, exist_ok=True)
            fallback_path = fallback_dir / f"{session_id}.heartbeat.json"
            fallback_data = {**update, "fallback": True, "error": str(e)[:200]}
            fallback_path.write_text(json.dumps(fallback_data, ensure_ascii=False), encoding="utf-8")
        except (json.JSONDecodeError, TypeError, ValueError):
            pass
        except Exception as fallback_e:
            print(f"[post_tool_use] fallback error: {fallback_e}", file=sys.stderr)

    # U17: Check cost cap after state write
    try:
        from cost_tracker import check_cost_cap_session

        exceeded, cost_msg = check_cost_cap_session(root, session_id)
        if exceeded:
            print(f"[U17 COST CAP] {cost_msg}", file=sys.stderr)
        elif cost_msg:
            print(f"[U17 COST] {cost_msg}", file=sys.stderr)
    except (ValueError, TypeError, KeyError, AttributeError, ImportError, ModuleNotFoundError):
        pass
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)

    # CVE-2026-AHD-013: cost ledger append-only + HMAC (best-effort)
    try:
        from cost_ledger import append_entry

        append_entry(root, session_id, tool_name, cost, cumulative)
    except Exception as e:
        print(f"[post_tool_use] WARNING: cost_ledger append loi: {e}", file=sys.stderr)

    # P1-05: Emit tool receipt with idempotency key (best-effort)
    try:
        if ok and tool_response is not None:
            ahd_session.emit_tool_receipt(
                root, session_id, tool_name, tool_input, tool_response, "success" if ok else "failed"
            )
    except Exception as e:
        print(f"[post_tool_use] P1-05 receipt emission error: {e}", file=sys.stderr)

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

    # Detect oversized context
    try:
        oversized = _response_size(tool_response) > CONTEXT_OVERSIZE_THRESHOLD
        if oversized:
            flags = ahd_session.read_context_flags(session_id, root)
            counter = flags.get("oversized_tool_calls_since_flag", 0)
            ahd_session.write_context_flags(
                session_id,
                {
                    "context_oversized": True,
                    "oversized_tool_calls_since_flag": counter,
                    "oversized_first_detected": ts,
                },
                root,
            )
            print(
                f"[Agent Harness Deploy] context_oversized detected "
                f"(response > {CONTEXT_OVERSIZE_THRESHOLD} chars). "
                f"Run context-compactor skill before continuing: "
                f"offload full output to .devin/tmp/, keep head+tail+path in context. "
                f"Read .devin/context_flags/{session_id}.json for details.",
                file=sys.stderr,
            )
        elif ahd_session.read_context_flags(session_id, root).get("context_oversized"):
            flags = ahd_session.read_context_flags(session_id, root)
            counter = flags.get("oversized_tool_calls_since_flag", 0) + 1
            ahd_session.write_context_flags(
                session_id,
                {"oversized_tool_calls_since_flag": counter},
                root,
            )
    except (ValueError, TypeError, KeyError, AttributeError) as e:
        print(f"[post_tool_use] context flag error: {e}", file=sys.stderr)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)

    # Detect candidate memory (chi ghi sau khi cung command fail 2+ lan)
    try:
        candidate = _extract_candidate_memory(tool_name, tool_input, tool_response, ts, ok=ok)
        if candidate and candidate.get("correct_action") not in VALID_CORRECT_ACTIONS:
            print(
                "[CVE-015] candidate memory bi tu choi: correct_action ngoai allowlist",
                file=sys.stderr,
            )
            candidate = None
        if candidate:
            fail_count = _repeated_failure_count(journal_path, tool_name, command, session_id)
            if fail_count >= 2:
                candidate_path = (
                    ahd_session.get_config_root(root) / "session_state" / session_id / "candidate_memory.jsonl"
                )
                if _memory_rate_limited(candidate_path):
                    print(
                        f"[CVE-015] candidate memory bi bo: vuot rate limit {CANDIDATE_MEMORY_PER_HOUR}/gio/session",
                        file=sys.stderr,
                    )
                else:
                    candidate["session_id"] = session_id
                    candidate["human_confirmed"] = False
                    _append_bounded_jsonl(candidate_path, candidate)
                    _audit_candidate(root, candidate, session_id)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)

    # U57-U62: Enforcement hooks (non-blocking)
    try:
        _u57_auto_quality_checks(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
    try:
        _u58_done_detection(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
    try:
        _u59_skill_auto_router(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
    try:
        _u60_loop_enforcement(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
    try:
        _u61_state_write_verification(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)
    try:
        _u62_memory_confidence(data, session_id, root)
    except Exception as e:
        print(f"[post_tool_use] unexpected exception: {e}", file=sys.stderr)

    sys.exit(0)
