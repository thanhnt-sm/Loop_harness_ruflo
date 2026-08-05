#!/usr/bin/env python3
"""Post-tool-use hook — logs tool usage, detects context overload, and captures micro-memory.

Called by the AI tool after executing any tool. Receives JSON on stdin:
  {"tool_name": "Edit", "tool_input": {...}, "tool_response": {...}, "session_id": "..."}

Exit codes:
  0 = success (always — post-hooks never block)

Writes per-session:
- .devin/session_state/<session_id>.json — heartbeat, last_tool, last_file
- .devin/session_state/<session_id>/candidate_memory.jsonl — repeated failure patterns
- .devin/context_flags/<session_id>.json — context_oversized flag
- .devin/session_state/<session_id>/journal.jsonl — audit trail

This creates a persistent audit trail and helps the harness avoid the context dumb zone.
"""
from __future__ import annotations

import json
import re
import sys
import threading
from datetime import datetime, timezone
from pathlib import Path

# U15: Internal timeout — post-hook is non-blocking, fail silently if too slow.
# Config timeout is 5s; internal 4s (1s margin) to exit before config kills us.
HOOK_TIMEOUT_SECONDS = 4.0

# U64: In-memory cache for context_flags (read once per session)
_CONTEXT_FLAGS_CACHE: dict[str, dict] = {}
_CONTEXT_FLAGS_LOADED: set[str] = set()

# U64: Batch state writes — only write every 5th call
_STATE_WRITE_COUNTER: dict[str, int] = {}
_STATE_WRITE_BATCH = 5

import ahd_session

CONTEXT_OVERSIZE_THRESHOLD = 3000  # characters in response
CANDIDATE_MEMORY_MAX = 50

# Simple secret redaction patterns
_SECRET_PATTERNS = [
    re.compile(r"ghp_[a-zA-Z0-9]{36}", re.IGNORECASE),
    re.compile(r"sk-[a-zA-Z0-9_-]{20,}", re.IGNORECASE),
    re.compile(r"\b(token|key|password|api_key|secret)\s*=\s*[^\s&;|]+", re.IGNORECASE),
]


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


def _compute_sha256(file_path: str, root: Path) -> str:
    """U20: Compute SHA-256 of a file. Returns empty string if file doesn't exist."""
    import hashlib
    try:
        full_path = (root / file_path) if not Path(file_path).is_absolute() else Path(file_path)
        if full_path.exists() and full_path.is_file():
            # U20 redteam: chunked reading for large files (64KB chunks)
            sha256 = hashlib.sha256()
            with open(full_path, "rb") as f:
                for chunk in iter(lambda: f.read(65536), b""):
                    sha256.update(chunk)
            return sha256.hexdigest()
    except Exception:
        pass
    return ""


def _track_file_sha(session_id: str, file_path: str, tool_name: str, root: Path) -> None:
    """U20: Track file SHA + invalidate verification status on write.

    For write/edit tools: compute SHA after write, store in session_state,
    and invalidate previous verify_status for that file.
    """
    if not file_path or not session_id:
        return

    write_tools = {"Write", "Edit", "write", "edit", "notebook_edit", "NotebookEdit"}
    if tool_name not in write_tools:
        return

    sha = _compute_sha256(file_path, root)
    if not sha:
        return

    try:
        state = ahd_session.read_session_state(session_id, root)
        file_shas = state.get("file_shas", {})
        verify_status = state.get("verify_status", {})

        # Update SHA
        file_shas[file_path] = {
            "sha": sha,
            "updated_at": ahd_session.now_utc(),
        }

        # Invalidate verification status for this file (always set on write)
        verify_status[file_path] = {
            "verified": False,
            "invalidated_at": ahd_session.now_utc(),
            "reason": "file modified after verification",
        }

        ahd_session.update_session_state(session_id, {
            "file_shas": file_shas,
            "verify_status": verify_status,
        }, root)
    except Exception:
        pass


def _extract_command(tool_input: dict) -> str:
    """Extract a command (truncated + redacted) for Bash-like tools."""
    cmd = tool_input.get("command", "")
    if not cmd:
        return ""
    redacted = _redact(cmd[:200])
    return redacted


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
            except Exception:
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
    except Exception:
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
    except Exception:
        return None


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
    except Exception:
        pass


def _rotate(path: Path, max_lines: int = 1000) -> None:
    """Rotate a jsonl file if it exceeds max_lines."""
    try:
        if path.exists() and path.read_text(encoding="utf-8").count("\n") >= max_lines:
            backup = path.with_suffix(".1.jsonl")
            if backup.exists():
                backup.unlink()
            path.rename(backup)
    except Exception:
        pass


def main():
    try:
        data = json.load(sys.stdin)
    except Exception:
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
    except Exception:
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
        from cost_tracker import _estimate_cost, check_cost_cap
        response_size = len(str(tool_response)) if tool_response else 0
        cost = _estimate_cost(tool_name, response_size)
        cumulative = round(current_state.get("cumulative_cost", 0.0) + cost, 6)
        cost_cap = current_state.get("cost_cap", 5.0)
        call_count = current_state.get("cost_tracked_calls", 0) + 1
        update["cumulative_cost"] = cumulative
        update["cost_cap"] = cost_cap
        update["cost_tracked_calls"] = call_count
        update["last_tool_cost"] = cost
    except Exception:
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
        except Exception:
            pass

    # U17: Check cost cap after state write (separate check, not write)
    try:
        exceeded, cost_msg = check_cost_cap(root, session_id)
        if exceeded:
            print(f"[U17 COST CAP] {cost_msg}", file=sys.stderr)
        elif cost_msg:
            print(f"[U17 COST] {cost_msg}", file=sys.stderr)
    except Exception:
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
    except Exception:
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
    except Exception:
        pass

    # Detect candidate memory (only record after the same command fails 2+ times)
    try:
        candidate = _extract_candidate_memory(tool_name, tool_input, tool_response, ts, ok=ok)
        if candidate:
            # The current failure has already been appended to the journal
            fail_count = _repeated_failure_count(journal_path, tool_name, command, session_id)
            if fail_count >= 2:
                candidate["session_id"] = session_id
                candidate_path = ahd_session.get_config_root(root) / "session_state" / session_id / "candidate_memory.jsonl"
                _append_bounded_jsonl(candidate_path, candidate)
    except Exception:
        pass

    # U57-U62: Enforcement hooks (non-blocking, append to session_state)
    try:
        _u57_auto_quality_checks(data, session_id, root)
    except Exception:
        pass
    try:
        _u58_done_detection(data, session_id, root)
    except Exception:
        pass
    try:
        _u59_skill_auto_router(data, session_id, root)
    except Exception:
        pass
    try:
        _u60_loop_enforcement(data, session_id, root)
    except Exception:
        pass
    try:
        _u61_state_write_verification(data, session_id, root)
    except Exception:
        pass
    try:
        _u62_memory_confidence(data, session_id, root)
    except Exception:
        pass

    sys.exit(0)


# U57: Auto-invoke slop-detector + comment_checker on Write/Edit
def _u57_auto_quality_checks(data: dict, session_id: str, root: Path) -> None:
    """Auto-run quality checks on Write/Edit tools. Non-blocking warnings."""
    tool_name = data.get("tool_name", "").lower()
    if tool_name not in ("write", "edit", "notebook_edit"):
        return

    tool_input = data.get("tool_input", {})
    file_path = tool_input.get("file_path", tool_input.get("path", ""))
    content = tool_input.get("content", tool_input.get("new_string", ""))

    if not content:
        return

    # U57: Slop detection — check for common AI slop patterns
    slop_score = 0
    slop_patterns = [
        (r"\b(leveraging|utilizing|facilitating|comprehensive|seamless)\b", "AI slop word", 2),
        (r"\b(it['']s worth noting that|it should be noted that)\b", "filler phrase", 1),
        (r"\b(delve into|dive deep into|explore in detail)\b", "verbose phrase", 1),
        (r"\b(robust|scalable|enterprise-grade|production-ready)\b", "buzzword", 1),
    ]
    for pattern, label, weight in slop_patterns:
        matches = re.findall(pattern, content, re.IGNORECASE)
        slop_score += len(matches) * weight

    # U57: Comment quality — check for AI-generated comments
    comment_issues = 0
    comment_patterns = [
        (r"#\s*(TODO|FIXME|HACK|XXX)", "stale comment marker", 2),
        (r"//\s*(TODO|FIXME|HACK|XXX)", "stale comment marker", 2),
        (r"#\s*Step \d+:", "numbered step comment", 1),
        (r"//\s*Step \d+:", "numbered step comment", 1),
    ]
    for pattern, label, weight in comment_patterns:
        matches = re.findall(pattern, content)
        comment_issues += len(matches) * weight

    # Write scores to session_state
    if slop_score > 0 or comment_issues > 0:
        state_path = ahd_session.get_session_state_path(session_id, root)
        ahd_session._locked_json_update(
            state_path,
            lambda existing: {
                **(existing or {}),
                "quality_scores": {
                    **((existing or {}).get("quality_scores", {})),
                    str(file_path): {
                        "slop_score": slop_score,
                        "comment_issues": comment_issues,
                        "checked_at": datetime.now(timezone.utc).isoformat(),
                    },
                },
            },
            default={},
            session_id=session_id,
        )
        if slop_score >= 5:
            print(
                f"[U57] WARNING: High slop score ({slop_score}) in {file_path}. "
                f"Review for AI slop patterns.",
                file=sys.stderr,
            )
        if comment_issues >= 5:
            print(
                f"[U57] WARNING: Comment issues ({comment_issues}) in {file_path}. "
                f"Review comment quality.",
                file=sys.stderr,
            )


# U58: Done-detection — auto-invoke fable-judge on "done" declarations
def _u58_done_detection(data: dict, session_id: str, root: Path) -> None:
    """Detect 'done' declarations in tool output, flag for fable-judge."""
    tool_response = data.get("tool_response", {})
    output = ""
    if isinstance(tool_response, dict):
        output = str(tool_response.get("output", tool_response.get("content", "")))
    elif isinstance(tool_response, str):
        output = tool_response

    done_patterns = [
        r"\b(done|complete|completed|finished|finalized|all (tests|checks) pass)\b",
    ]
    done_detected = False
    for pattern in done_patterns:
        if re.search(pattern, output, re.IGNORECASE):
            done_detected = True
            break

    if done_detected:
        state_path = ahd_session.get_session_state_path(session_id, root)
        ahd_session._locked_json_update(
            state_path,
            lambda existing: {
                **(existing or {}),
                "done_declared": True,
                "done_declared_at": datetime.now(timezone.utc).isoformat(),
                "fable_judge_required": True,
            },
            default={},
            session_id=session_id,
        )
        print(
            "[U58] Done declaration detected. fable-judge verification required "
            "before task complete.",
            file=sys.stderr,
        )


# U59: Skill auto-router — suggest skills based on tool output
def _u59_skill_auto_router(data: dict, session_id: str, root: Path) -> None:
    """Auto-suggest skills based on tool type and output."""
    tool_name = data.get("tool_name", "").lower()
    suggestions = []

    # Map tools to skills
    skill_map = {
        "write": ["harness-sensor", "slop-detector", "comment_checker"],
        "edit": ["harness-sensor", "slop-detector", "comment_checker"],
        "notebook_edit": ["harness-sensor"],
        "exec": ["harness-sensor"],
        "read": [],
        "grep": [],
        "glob": [],
    }

    suggestions = skill_map.get(tool_name, [])
    if not suggestions:
        return

    state_path = ahd_session.get_session_state_path(session_id, root)
    ahd_session._locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "skill_suggestions": suggestions,
            "skill_suggested_at": datetime.now(timezone.utc).isoformat(),
        },
        default={},
        session_id=session_id,
    )


# U60: Loop enforcement — check budget, time, convergence
def _u60_loop_enforcement(data: dict, session_id: str, root: Path) -> None:
    """Enforce loop stop conditions: budget cap, time limit, state write."""
    state = ahd_session.read_session_state(session_id, root)

    # Check budget cap (token cost)
    total_cost = state.get("total_cost", 0)
    budget_cap = state.get("budget_cap", 0)
    if budget_cap > 0 and total_cost > budget_cap:
        print(
            f"[U60] BUDGET EXCEEDED: {total_cost} > {budget_cap}. "
            f"Loop should stop.",
            file=sys.stderr,
        )
        ahd_session._locked_json_update(
            ahd_session.get_session_state_path(session_id, root),
            lambda existing: {**(existing or {}), "budget_exceeded": True},
            default={},
            session_id=session_id,
        )

    # Check time limit
    started_at = state.get("started_at")
    time_limit = state.get("time_limit_seconds", 0)
    if started_at and time_limit > 0:
        try:
            start = datetime.fromisoformat(started_at)
            elapsed = (datetime.now(start.tzinfo) - start).total_seconds()
            if elapsed > time_limit:
                print(
                    f"[U60] TIME LIMIT EXCEEDED: {elapsed:.0f}s > {time_limit}s. "
                    f"Loop should stop.",
                    file=sys.stderr,
                )
        except Exception:
            pass

    # Check iteration count vs state writes
    iteration_count = state.get("iteration_count", 0)
    last_state_write = state.get("last_state_write_iteration", 0)
    if iteration_count - last_state_write > 5:
        print(
            f"[U60] WARNING: {iteration_count - last_state_write} iterations "
            f"without state write. Loop state may be stale.",
            file=sys.stderr,
        )


# U61: State write verification — read-back after write
def _u61_state_write_verification(data: dict, session_id: str, root: Path) -> None:
    """Verify session state write succeeded by reading back."""
    state_path = ahd_session.get_session_state_path(session_id, root)
    if not state_path.exists():
        return

    try:
        content = state_path.read_text(encoding="utf-8")
        if not content.strip():
            # Empty file — write failure
            state = ahd_session.read_session_state(session_id, root)
            fail_count = state.get("state_write_failures", 0) + 1
            ahd_session._locked_json_update(
                state_path,
                lambda existing: {
                    **(existing or {}),
                    "state_write_failures": fail_count,
                },
                default={},
                session_id=session_id,
            )
            if fail_count > 3:
                print(
                    f"[U61] CRITICAL: {fail_count} state write failures. "
                    f"Escalate to human.",
                    file=sys.stderr,
                )
    except Exception:
        pass


# U62: Memory confidence + honest limit
def _u62_memory_confidence(data: dict, session_id: str, root: Path) -> None:
    """Track memory confidence and enforce honest limit thresholds."""
    tool_name = data.get("tool_name", "").lower()

    # Only check on memory-related tools
    if "memory" not in tool_name and "recall" not in tool_name:
        return

    tool_response = data.get("tool_response", {})
    output = str(tool_response.get("output", "")) if isinstance(tool_response, dict) else str(tool_response)

    # Estimate confidence: if output is empty or very short, low confidence
    confidence = 100
    if not output.strip():
        confidence = 0
    elif len(output.strip()) < 50:
        confidence = 30

    # Check for uncertainty markers
    uncertainty_markers = [
        r"\b(might be|possibly|perhaps|maybe|uncertain|not sure|unclear)\b",
        r"\b(approximately|roughly|around)\b",
    ]
    uncertainty_count = 0
    for pattern in uncertainty_markers:
        uncertainty_count += len(re.findall(pattern, output, re.IGNORECASE))

    if uncertainty_count > 3:
        confidence = min(confidence, 50)

    state_path = ahd_session.get_session_state_path(session_id, root)
    ahd_session._locked_json_update(
        state_path,
        lambda existing: {
            **(existing or {}),
            "last_memory_confidence": confidence,
            "last_memory_source": tool_name,
        },
        default={},
        session_id=session_id,
    )

    # U62: Honest limit — auto-escalate if uncertainty > 30%
    if confidence < 70:
        print(
            f"[U62] Memory confidence low ({confidence}%). "
            f"Consider escalating to human. Honest limit threshold: 70%.",
            file=sys.stderr,
        )
    # U15: Internal timeout — post-hook always exits 0, just fail silently if too slow.
    t = threading.Thread(target=main, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[post_tool_use] U15 timeout — exiting (non-blocking)", file=sys.stderr)
    sys.exit(0)