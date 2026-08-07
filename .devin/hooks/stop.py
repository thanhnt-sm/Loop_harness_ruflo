#!/usr/bin/env python3
"""Stop hook — clean exit when the agent session ends.

Called by the AI tool when a session stops (agent finishes, user stops, or
context limit hit). Receives JSON on stdin:
  {"session_id": "..."}

Exit codes:
  0 = success (always — stop hooks never block)

What it does:
  1. Resolves session_id.
  2. Reads session_state and determines status:
     - completed if state_written is true and last_state_write is recent
     - crashed otherwise
  3. If completed: runs memory_audit to merge candidate memory, then loop_memory_sync
     to archive session files and update loop_state.md registry.
  4. If crashed: runs loop_memory_sync to mark suspected_crashed without deleting.
  5. Appends a session-end marker to loop_state_archive.md.
  6. Cleans temporary files older than 24h in .devin/tmp/.
"""
import json
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import ahd_session

SESSION_MARKER = "<!-- Agent Harness Deploy-stop-hook -->"


# Thời điểm bắt đầu cleanup, dùng để tính remaining timeout cho từng lệnh con.
_STOP_START_TIME: float = 0.0


def _call_script(root: Path, script: str, *args) -> int:
    """Call a helper script in .devin/scripts/ or scripts/.

    Dùng Popen để có thể kill con khi hết thời gian; trả returncode.
    """
    for script_dir in (ahd_session.get_config_root(root) / "scripts", root / "scripts"):
        candidate = script_dir / script
        if candidate.exists():
            # Tính remaining time dựa trên tổng budget 9s của stop.py.
            global _STOP_START_TIME
            elapsed = time.time() - _STOP_START_TIME
            remaining = max(1.0, 9.0 - elapsed)
            try:
                proc = subprocess.Popen(
                    [sys.executable, str(candidate), *args],
                    cwd=str(root), stdout=subprocess.PIPE, stderr=subprocess.PIPE,
                )
                try:
                    outs, errs = proc.communicate(timeout=remaining)
                    return proc.returncode or 0
                except subprocess.TimeoutExpired:
                    proc.kill()
                    try:
                        proc.communicate(timeout=1)
                    except Exception:
                        pass
                    print(f"[stop.py] WARNING: {script} timed out and was killed", file=sys.stderr)
                    return 124
            except Exception as e:
                print(f"[stop.py] ERROR: cannot run {script}: {e}", file=sys.stderr)
                return 1
    print(f"[stop.py] WARNING: helper script {script} not found", file=sys.stderr)
    return 127


def _clean_tmp(tmp_dir: Path) -> None:
    """Remove temp files older than 24h."""
    if not tmp_dir.exists():
        return
    cutoff = time.time() - 86400
    for f in tmp_dir.iterdir():
        try:
            if f.is_file() and f.stat().st_mtime < cutoff:
                f.unlink()
        except Exception:
            pass


def main():
    global _STOP_START_TIME
    _STOP_START_TIME = time.time()

    try:
        data = json.load(sys.stdin)
    except Exception:
        data = {}

    session_id = ahd_session.get_session_id(data)
    root = ahd_session.get_repo_root()
    ts = ahd_session.now_utc()

    archive_path = ahd_session.get_config_root(root) / "loop_state_archive.md"
    tmp_dir = ahd_session.get_config_root(root) / "tmp"

    session_state = ahd_session.read_session_state(session_id, root)
    state_written = session_state.get("state_written", False)
    last_state_write = session_state.get("last_state_write", "")
    # Pentest fix: ưu tiên flag session_completed thay vì chỉ dựa vào 30 phút.
    session_completed = session_state.get("session_completed", False)

    completed = False
    if session_completed:
        completed = True
    elif state_written and last_state_write:
        try:
            last_ts = datetime.fromisoformat(last_state_write)
            elapsed = (datetime.now(timezone.utc) - last_ts).total_seconds()
            if elapsed < 1800:  # 30 minutes
                completed = True
        except Exception:
            pass

    cleanup_failed = False
    if completed:
        # Merge candidate memory before archiving
        rc1 = _call_script(root, "memory_audit.py", "--session", session_id)
        # Archive and update registry
        rc2 = _call_script(root, "loop_memory_sync.py", "--session", session_id, "--status", "completed")
        cleanup_failed = (rc1 != 0 or rc2 != 0)
    else:
        # Mark as suspected crashed; do not delete session_state
        rc = _call_script(root, "loop_memory_sync.py", "--session", session_id, "--status", "suspected_crashed")
        cleanup_failed = (rc != 0)

    # Ghi nhãn cleanup_failed vào session_state để session sau phát hiện.
    if cleanup_failed:
        try:
            ahd_session.update_session_state(session_id, {"cleanup_failed": True}, root)
        except Exception:
            pass

    # Append session-end marker to cold archive
    try:
        archive_path.parent.mkdir(parents=True, exist_ok=True)
        with open(archive_path, "a", encoding="utf-8") as f:
            f.write(f"\n{SESSION_MARKER} session_end ts={ts} session_id={session_id} status={'completed' if completed else 'crashed'} cleanup_failed={cleanup_failed}\n")
    except Exception:
        pass

    # Clean old temp files
    _clean_tmp(tmp_dir)

    sys.exit(0)


if __name__ == "__main__":
    # U15 redteam: internal timeout — stop.py runs cleanup (memory_audit, loop_memory_sync).
    # Config timeout is 10s; internal timeout 9s ensures we exit before config kills us.
    import threading
    HOOK_TIMEOUT_SECONDS = 9.0

    result = {"code": 0}
    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception:
            result["code"] = 0

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[stop.py] U15 timeout — exiting (cleanup may be incomplete)", file=sys.stderr)
    sys.exit(result["code"])