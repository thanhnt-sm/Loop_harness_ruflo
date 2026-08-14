#!/usr/bin/env python3
"""loop_memory_sync.py — regenerate loop_state.md registry from session_state.

This is the single machine writer of `.devin/loop_state.md`. It reads:
- `.devin/session_state/*.json` for active session metadata
- `.devin/loop_state/<session_id>.md` for human-readable GoalSpec and subtasks

It writes:
- `.devin/loop_state.md` registry (active + recent 3 completed)
- `.devin/loop_state_archive.md` event summaries for archived sessions
- moves completed session files to `.devin/loop_state_archive/<session_id>.md`
"""
from __future__ import annotations

import argparse
import hashlib
import json
import os
import re
import shutil
import sys
import threading
import time
import traceback
from datetime import datetime, timezone
from pathlib import Path

try:
    import ahd_session
except ImportError:  # pragma: no cover
    sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "hooks"))
    import ahd_session

MAX_REGISTRY_COMPLETED = 3
MAX_ACTIVE_SESSIONS = 3
MAX_LOOP_STATE_FILES = 10
STALE_THRESHOLD_SECONDS = 1800  # 30 minutes
ACTIVE_STATUSES = ("in_progress", "crashed", "suspected_crashed")

# U06: Fallback paths for Memory Keeper single-point-of-failure
FALLBACK_DIR_NAME = "loop_state_fallback"
FALLBACK_REGISTRY_NAME = "loop_state_fallback.md"

# ---------------------------------------------------------------------------
# Task 3.9: Immutable state log (append-only Merkle chain) + Ed25519 signing
# ---------------------------------------------------------------------------

STATE_LOG_NAME = "state_log.jsonl"


def _state_log_path(root: Path) -> Path:
    return ahd_session.get_config_root(root) / "telemetry" / STATE_LOG_NAME


def _telemetry_signing_key(root: Path) -> bytes | None:
    """Key ký telemetry: secrets.env TELEMETRY_SIGN_KEY -> env AHD_TELEMETRY_SIGN_KEY
    -> <config_root>/state/.telemetry_key. Không có key -> None (unsigned)."""
    try:
        secrets_env = Path(__file__).resolve().parent.parent.parent / "HLK" / "config" / "secrets.env"
        if secrets_env.exists():
            for line in secrets_env.read_text(encoding="utf-8").splitlines():
                if line.startswith("TELEMETRY_SIGN_KEY="):
                    val = line.split("=", 1)[1].strip().strip('"')
                    if val:
                        return val.encode("utf-8")
        env_val = os.environ.get("AHD_TELEMETRY_SIGN_KEY", "")
        if env_val:
            return env_val.encode("utf-8")
        key_file = ahd_session.get_config_root(root) / "state" / ".telemetry_key"
        if key_file.exists():
            return key_file.read_text(encoding="utf-8").strip().encode("utf-8")
    except OSError:
        pass
    return None


def _sign_entry(entry: dict, key: bytes | None) -> str:
    """Ed25519 sign entry (cryptography lib). Không key -> 'unsigned'."""
    if key is None:
        return "unsigned"
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey
        body = json.dumps({k: v for k, v in entry.items() if k != "sig"},
                          sort_keys=True, ensure_ascii=False).encode("utf-8")
        priv = Ed25519PrivateKey.from_private_bytes(key[:32].ljust(32, b"\0"))
        return priv.sign(body).hex()
    except Exception:
        return "unsigned"


def _verify_entry_sig(entry: dict, key: bytes | None) -> bool:
    sig = entry.get("sig", "")
    if not sig or sig == "unsigned":
        return sig == "unsigned"  # unsigned hợp lệ khi không cấu hình key
    if key is None:
        return False
    try:
        from cryptography.hazmat.primitives.asymmetric.ed25519 import Ed25519PrivateKey, Ed25519PublicKey
        body = json.dumps({k: v for k, v in entry.items() if k != "sig"},
                          sort_keys=True, ensure_ascii=False).encode("utf-8")
        priv = Ed25519PrivateKey.from_private_bytes(key[:32].ljust(32, b"\0"))
        pub = priv.public_key()
        pub.verify(bytes.fromhex(sig), body)
        return True
    except Exception:
        return False


def _chain_hash(prev_hash: str, payload: dict, seq: int) -> str:
    body = json.dumps(payload, sort_keys=True, ensure_ascii=False).encode("utf-8")
    return hashlib.sha256(f"{prev_hash}|{seq}|".encode() + body).hexdigest()


def append_state_log(root: Path, session_id: str, event: str,
                     payload: dict | None = None, loop_id: str = "") -> dict | None:
    """Append-only Merkle-chained state log entry (Task 3.9).

    Entry: {seq, ts, loop_id, session_id, event, payload, prev_hash, hash, sig}.
    hash = SHA256(prev_hash | seq | payload) — mỗi entry commit toàn bộ lịch sử.
    sig = Ed25519 (nếu key cấu hình). Không bao giờ ghi đè/ghi giữa file.
    """
    try:
        path = _state_log_path(root)
        path.parent.mkdir(parents=True, exist_ok=True)
        prev_hash = "0" * 64
        seq = 0
        if path.exists():
            lines = path.read_text(encoding="utf-8").splitlines()
            if lines:
                try:
                    last = json.loads(lines[-1])
                    prev_hash = last.get("hash", prev_hash)
                    seq = int(last.get("seq", 0)) + 1
                except (json.JSONDecodeError, TypeError, ValueError):
                    prev_hash = hashlib.sha256(b"corrupt|" + lines[-1].encode()).hexdigest()
                    seq = len(lines)
        entry = {
            "seq": seq,
            "ts": datetime.now(timezone.utc).isoformat(),
            "loop_id": loop_id or os.environ.get("AHD_LOOP_ID", ""),
            "session_id": session_id,
            "event": event,
            "payload": payload or {},
        }
        entry["prev_hash"] = prev_hash
        entry["hash"] = _chain_hash(prev_hash, entry["payload"], seq)
        entry["sig"] = _sign_entry(entry, _telemetry_signing_key(root))
        with open(path, "a", encoding="utf-8") as f:
            f.write(json.dumps(entry, ensure_ascii=False) + "\n")
        return entry
    except Exception:
        return None


def verify_state_log(root: Path) -> dict:
    """Verify chuỗi Merkle + chữ ký toàn bộ state log.

    Trả về {total, valid, invalid, unsigned, merkle_ok, key_configured, path}.
    """
    path = _state_log_path(root)
    result = {"total": 0, "valid": 0, "invalid": 0, "unsigned": 0,
              "merkle_ok": True, "key_configured": False, "path": str(path)}
    if not path.exists():
        return result
    key = _telemetry_signing_key(root)
    result["key_configured"] = key is not None
    prev_hash = "0" * 64
    lines = path.read_text(encoding="utf-8").splitlines()
    result["total"] = len(lines)
    for i, line in enumerate(lines):
        line = line.strip()
        if not line:
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            result["invalid"] += 1
            result["merkle_ok"] = False
            continue
        seq = int(entry.get("seq", -1))
        if entry.get("prev_hash", "") != prev_hash:
            result["merkle_ok"] = False
        expected = _chain_hash(prev_hash, entry.get("payload", {}), seq)
        if entry.get("hash", "") != expected:
            result["merkle_ok"] = False
        prev_hash = entry.get("hash", prev_hash)
        if _verify_entry_sig(entry, key):
            if entry.get("sig", "") == "unsigned":
                result["unsigned"] += 1
            else:
                result["valid"] += 1
        else:
            result["invalid"] += 1
    return result


def watchdog_status(root: Path, stale_seconds: int = STALE_THRESHOLD_SECONDS) -> dict:
    """Task 3.9: dead man's switch — báo cáo heartbeat status các loop đang chạy."""
    sessions = {}
    state_dir = ahd_session.get_config_root(root) / "session_state"
    if not state_dir.exists():
        return {"loops": 0, "stale": [], "ok": True}
    now = time.time()
    stale = []
    for f in sorted(state_dir.glob("*.json")):
        try:
            data = json.loads(f.read_text(encoding="utf-8"))
        except (OSError, json.JSONDecodeError):
            continue
        ts = data.get("last_heartbeat", "") or data.get("last_state_write", "")
        if not ts:
            continue
        try:
            age = now - datetime.fromisoformat(ts).timestamp()
        except (TypeError, ValueError):
            continue
        sid = f.stem
        sessions[sid] = {"age_seconds": round(age, 1), "stale": age > stale_seconds}
        if age > stale_seconds:
            stale.append(sid)
    return {"loops": len(sessions), "stale": stale, "ok": not stale}


def _write_fallback(root: Path, operation: str, error: str) -> None:
    """U06: Write fallback registry when primary write fails.

    If loop_memory_sync fails to write the main registry, this function
    writes a minimal fallback to loop_state_fallback.md so the harness
    can still recover session state.
    """
    try:
        fallback_dir = ahd_session.get_config_root(root) / FALLBACK_DIR_NAME
        fallback_dir.mkdir(parents=True, exist_ok=True)

        # Write individual session snapshots from session_state
        session_dir = ahd_session.get_config_root(root) / "session_state"
        if session_dir.exists():
            for f in session_dir.glob("*.json"):
                try:
                    data = json.loads(f.read_text(encoding="utf-8"))
                    sid = data.get("session_id", f.stem)
                    snap = {
                        "session_id": sid,
                        "status": data.get("status", "unknown"),
                        "goal": data.get("goal", ""),
                        "last_heartbeat": data.get("last_heartbeat", ""),
                        "last_state_write": data.get("last_state_write", ""),
                        "tags": data.get("tags", []),
                        "owned_files": data.get("owned_files", []),
                    }
                    snap_path = fallback_dir / f"{sid}.json"
                    snap_path.write_text(json.dumps(snap, ensure_ascii=False, indent=2), encoding="utf-8")
                except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
                    pass

        # Write fallback registry
        fallback_reg = fallback_dir.parent / FALLBACK_REGISTRY_NAME
        ts = datetime.now(timezone.utc).isoformat()
        lines = [
            "---",
            f"fallback: true",
            f"generated: {ts}",
            f"reason: {operation} failed",
            "---",
            "",
            "# Loop State Registry (FALLBACK)",
            "",
            f"> Primary registry write failed at {ts}.",
            f"> Error: {error[:200]}",
            f"> This fallback was generated by loop_memory_sync.py U06 fallback mechanism.",
            "",
            "## Session snapshots",
            "| session_id | status | goal | last_heartbeat |",
            "|---|---|---|---|",
        ]
        if fallback_dir.exists():
            for snap_file in sorted(fallback_dir.glob("*.json")):
                try:
                    snap = json.loads(snap_file.read_text(encoding="utf-8"))
                    sid = snap.get("session_id", snap_file.stem)
                    status = snap.get("status", "unknown")
                    goal = snap.get("goal", "")[:30]
                    hb = snap.get("last_heartbeat", "")
                    lines.append(f"| {sid} | {status} | {goal} | {hb} |")
                except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
                    pass
        lines.append("")
        lines.append(f"## Recovery instructions")
        lines.append(f"- Check error: {error[:200]}")
        lines.append(f"- Individual session snapshots in .devin/{FALLBACK_DIR_NAME}/")
        lines.append(f"- Fix primary write issue, then re-run loop_memory_sync.py")
        lines.append(f"- Fallback snapshots can be merged back manually if needed")

        fallback_reg.write_text("\n".join(lines) + "\n", encoding="utf-8")
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        # Last resort: can't even write fallback
        print(f"[loop_memory_sync] fallback write failed: {e}", file=sys.stderr)
        pass


    except Exception as e:
        # Last resort: can't even write fallback
        print(f"[loop_memory_sync] fallback write failed: {e}", file=sys.stderr)
        pass


def _safe_regenerate(root: Path, session_id: str = "", status: str = "") -> None:
    """U06: Wrapper around regenerate() with fallback on failure."""
    try:
        regenerate(root, session_id, status)
    except Exception as e:
        tb = traceback.format_exc()
        _write_fallback(root, "regenerate", f"{e}: {tb[:500]}")
        # Re-raise so caller knows it failed, but fallback is written
        raise


def _parse_front_matter(text: str) -> dict:
    """Parse a YAML front matter block into a dict (simple)."""
    result = {}
    if not text.startswith("---"):
        return result
    end = text.find("---", 3)
    if end == -1:
        return result
    fm = text[3:end].strip()
    for line in fm.splitlines():
        if ":" in line:
            key, val = line.split(":", 1)
            key = key.strip()
            val = val.strip()
            try:
                result[key] = json.loads(val)
            except (json.JSONDecodeError, TypeError, ValueError):
                result[key] = val
    return result


def _read_loop_state_md(path: Path) -> tuple[dict, str]:
    """Read per-session loop_state markdown, return (front_matter, body)."""
    if not path.exists():
        return {}, ""
    text = path.read_text(encoding="utf-8")
    fm = _parse_front_matter(text)
    body = text
    if text.startswith("---"):
        end = text.find("---", 3)
        if end != -1:
            body = text[end + 3:].lstrip()
    return fm, body


def _is_stale(s: dict) -> bool:
    """Return True if a session's last heartbeat or state write is older than the threshold."""
    now = datetime.now(timezone.utc).timestamp()
    timestamps = [s.get("last_heartbeat", ""), s.get("last_state_write", "")]
    max_ts = 0.0
    for ts in timestamps:
        if ts:
            try:
                t = datetime.fromisoformat(ts).timestamp()
                if t > max_ts:
                    max_ts = t
            except (ValueError, TypeError):
                pass
    if max_ts == 0.0:
        # No timestamp information; treat as stale
        return True
    return (now - max_ts) > STALE_THRESHOLD_SECONDS


def _mark_stale_sessions(root: Path, sessions: list[dict]) -> None:
    """Mark in_progress sessions without recent heartbeat as suspected_crashed."""
    for s in sessions:
        if s.get("status") != "in_progress":
            continue
        if _is_stale(s):
            sid = s.get("session_id", "")
            if not sid:
                continue
            ahd_session.update_session_state(sid, {"status": "suspected_crashed"}, root)
            s["status"] = "suspected_crashed"


def _build_registry(root: Path) -> tuple[list[dict], list[dict]]:
    """Build active/recent session list from session_state/*.json."""
    session_dir = ahd_session.get_config_root(root) / "session_state"
    state_files = []
    if session_dir.exists():
        for f in session_dir.glob("*.json"):
            sid = f.stem
            if sid in ("current_session", ""):
                continue
            try:
                data = json.loads(f.read_text(encoding="utf-8"))
                if data.get("session_id") == sid:
                    state_files.append(data)
            except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
                pass

    # Detect stale in-progress sessions before classifying
    _mark_stale_sessions(root, state_files)

    # Sort by last_state_write then last_heartbeat
    def _sort_key(s):
        for k in ("last_state_write", "last_heartbeat"):
            ts = s.get(k, "")
            if ts:
                try:
                    return datetime.fromisoformat(ts).timestamp()
                except (ValueError, TypeError):
                    pass
        return 0.0

    state_files.sort(key=_sort_key, reverse=True)

    active = [s for s in state_files if s.get("status") in ACTIVE_STATUSES]
    completed = [s for s in state_files if s.get("status") == "completed"]
    # Keep most recent 3 completed in registry
    completed = completed[:MAX_REGISTRY_COMPLETED]

    return active + completed, active


def _enforce_active_session_limit(root: Path, sessions: list[dict]) -> list[dict]:
    """If there are more than MAX_ACTIVE_SESSIONS active sessions, queue the oldest.

    Active sessions are sorted by most recent heartbeat/state write. The newest
    MAX_ACTIVE_SESSIONS keep active; the rest are marked `queued`.
    """
    active = [s for s in sessions if s.get("status") in ACTIVE_STATUSES]
    if len(active) <= MAX_ACTIVE_SESSIONS:
        return sessions

    # Sort by recency (most recent first)
    def _sort_key(s):
        for k in ("last_state_write", "last_heartbeat"):
            ts = s.get(k, "")
            if ts:
                try:
                    return datetime.fromisoformat(ts).timestamp()
                except (ValueError, TypeError):
                    pass
        return 0.0

    active.sort(key=_sort_key, reverse=True)
    overflow = active[MAX_ACTIVE_SESSIONS:]
    for s in overflow:
        sid = s.get("session_id", "")
        if not sid:
            continue
        ahd_session.update_session_state(sid, {"status": "queued"}, root)
        s["status"] = "queued"
    return sessions


def _archive_session(root: Path, session_id: str, body: str, front: dict) -> None:
    """Move a completed per-session loop_state md to archive."""
    archive_dir = ahd_session.get_config_root(root) / "loop_state_archive"
    archive_dir.mkdir(parents=True, exist_ok=True)
    src = ahd_session.get_config_root(root) / "loop_state" / f"{session_id}.md"
    dst = archive_dir / f"{session_id}.md"
    if src.exists():
        shutil.copy2(src, dst)
        src.unlink()

    # Append summary to archive
    archive_md = ahd_session.get_config_root(root) / "loop_state_archive.md"
    try:
        ts = ahd_session.now_utc()
        goal = front.get("goal", "") or ""
        summary = f"\n- archived session `{session_id}` at {ts}: {goal[:80]}\n"
        with open(archive_md, "a", encoding="utf-8") as f:
            f.write(summary)
    except (OSError, UnicodeDecodeError, AttributeError):
        pass


def _cleanup_loop_state_dir(root: Path, status_map: dict) -> None:
    """Archive oldest completed loop_state files if directory exceeds limit."""
    loop_dir = ahd_session.get_config_root(root) / "loop_state"
    if not loop_dir.exists():
        return
    files = [f for f in loop_dir.glob("*.md") if f.stem not in ("", "loop_state")]
    if len(files) <= MAX_LOOP_STATE_FILES:
        return
    # Find completed files with their mtime
    completed_files = []
    for f in files:
        fm, body = _read_loop_state_md(f)
        sid = f.stem
        status = fm.get("status") or status_map.get(sid)
        if status == "completed":
            completed_files.append((f, f.stat().st_mtime))
    completed_files.sort(key=lambda x: x[1])
    while len(files) > MAX_LOOP_STATE_FILES and completed_files:
        f, _ = completed_files.pop(0)
        sid = f.stem
        fm, body = _read_loop_state_md(f)
        _archive_session(root, sid, body, fm)
        files = [f for f in loop_dir.glob("*.md") if f.stem not in ("", "loop_state")]


def regenerate(root: Path, session_id: str = "", status: str = "") -> None:
    """Regenerate loop_state.md registry."""
    sessions, active = _build_registry(root)

    # If caller wants to set a specific status, update session_state first
    if session_id and status:
        sid = ahd_session.slugify_session_id(session_id)
        state = ahd_session.read_session_state(sid, root)
        if state:
            state["status"] = status
            if status == "completed":
                state["last_state_write"] = ahd_session.now_utc()
                state["state_written"] = True
            ahd_session.write_session_state(sid, state, root, merge=False)
            # Rebuild
            sessions, active = _build_registry(root)

    # Enforce max active sessions limit
    sessions = _enforce_active_session_limit(root, sessions)
    active = [s for s in sessions if s.get("status") in ACTIVE_STATUSES]

    # Determine active session(s) and front-matter values
    active_sids = [s.get("session_id", "") for s in active if s.get("session_id", "")]
    active_session = active_sids[0] if active_sids else None

    # Determine context fill / caveman level from active session
    context_fill_pct = 0
    caveman_level = "full"
    if active:
        context_fill_pct = active[0].get("context_fill_pct", 0)
        caveman_level = active[0].get("caveman_level", "full")

    registry_path = ahd_session.get_config_root(root) / "loop_state.md"
    registry_path.parent.mkdir(parents=True, exist_ok=True)

    lines = ["---"]
    lines.append(f"context_fill_pct: {context_fill_pct}")
    lines.append(f"caveman_level: {caveman_level}")
    lines.append(f"active_sessions: {json.dumps(active_sids, ensure_ascii=False)}")
    lines.append(f"active_session: {active_session or 'null'}")
    lines.append("---")
    lines.append("")
    lines.append("# Loop State Registry")
    lines.append("")
    lines.append("## Active sessions")
    lines.append("| session_id | goal | status | tags | owned_files | last_heartbeat |")
    lines.append("|---|---|---|---|---|---|")
    for s in sessions:
        if s.get("status") not in ACTIVE_STATUSES:
            continue
        sid = s.get("session_id", "")
        goal = s.get("goal", "")[:30]
        status = s.get("status", "")
        tags = ", ".join(s.get("tags", [])[:5]) or ""
        owned = ", ".join(s.get("owned_files", [])[:5]) or ""
        hb = s.get("last_heartbeat", "")
        lines.append(f"| {sid} | {goal} | {status} | {tags} | {owned} | {hb} |")

    lines.append("")
    lines.append(f"## Recent sessions (last {MAX_REGISTRY_COMPLETED})")
    lines.append("| session_id | goal | status | tags |")
    lines.append("|---|---|---|---|")
    recent = [s for s in sessions if s.get("status") == "completed"][:MAX_REGISTRY_COMPLETED]
    for s in recent:
        sid = s.get("session_id", "")
        goal = s.get("goal", "")[:30]
        status = s.get("status", "")
        tags = ", ".join(s.get("tags", [])[:5]) or ""
        lines.append(f"| {sid} | {goal} | {status} | {tags} |")

    queued = [s for s in sessions if s.get("status") == "queued"]
    if queued:
        lines.append("")
        lines.append("## Queued sessions")
        lines.append("| session_id | goal | tags | reason |")
        lines.append("|---|---|---|---|")
        for s in queued:
            sid = s.get("session_id", "")
            goal = s.get("goal", "")[:30]
            tags = ", ".join(s.get("tags", [])[:5]) or ""
            lines.append(f"| {sid} | {goal} | {tags} | max {MAX_ACTIVE_SESSIONS} active |")

    lines.append("")
    lines.append("## Links")
    lines.append("- knowledge_distill: .agents/knowledge_distill.md")
    lines.append("- handoff_letter: .agents/handoff_letter.md")
    lines.append("- session_archive: .devin/loop_state_archive.md")
    lines.append("- session_archive_dir: .devin/loop_state_archive/")

    # U14 redteam fix: dùng repo-level inter-process lock khi viết registry
    # U21: Retry với backoff nếu lock held (BOOT race condition)
    # U21 redteam: reduced from 3→2 retries, 0.5→0.3s base to keep worst case < 3s
    max_retries = 2
    base_delay = 0.3  # 300ms initial backoff
    lock = None
    for attempt in range(max_retries):
        # U21: short timeout per attempt (1s) — don't block 10s on each try
        lock = ahd_session._acquire_lock(ahd_session._get_lock_path(root), timeout=1.0)
        if lock is not None:
            break
        # Lock held — backoff
        delay = base_delay * (2 ** attempt)  # 0.3s, 0.6s
        time.sleep(delay)
    if lock is None:
        # All retries failed — write fallback registry
        _write_fallback(root, "registry_write", "registry lock held after retries")
        return
    try:
        tmp = registry_path.with_suffix(".tmp")
        tmp.write_text("\n".join(lines) + "\n", encoding="utf-8")
        tmp.replace(registry_path)
    finally:
        ahd_session._release_lock(lock)

    # Build status map for loop_state cleanup
    status_map = {s.get("session_id", ""): s.get("status", "") for s in sessions}
    completed_sids = {s.get("session_id", "") for s in recent}
    loop_dir = ahd_session.get_config_root(root) / "loop_state"
    if loop_dir.exists():
        for f in loop_dir.glob("*.md"):
            sid = f.stem
            if sid == "loop_state":
                continue
            fm, body = _read_loop_state_md(f)
            status = fm.get("status") or status_map.get(sid)
            if status == "completed" and sid not in completed_sids:
                _archive_session(root, sid, body, fm)

    # Archive old session_state files for completed sessions not in recent
    for s in sessions:
        if s.get("status") == "completed" and s.get("session_id", "") not in completed_sids:
            sid = s.get("session_id", "")
            ss = ahd_session.get_config_root(root) / "session_state" / f"{sid}.json"
            if ss.exists():
                # Move to archive
                archive_dir = ahd_session.get_config_root(root) / "loop_state_archive"
                archive_dir.mkdir(parents=True, exist_ok=True)
                shutil.copy2(ss, archive_dir / f"{sid}.json")
                ss.unlink()
            # Also remove per-session runtime directory (journal, candidate_memory, etc.)
            ss_dir = ahd_session.get_config_root(root) / "session_state" / sid
            if ss_dir.exists():
                shutil.rmtree(ss_dir, ignore_errors=True)

    _cleanup_loop_state_dir(root, status_map)


_inline_lock = threading.Lock()


def run_inline(root: Path, session_id: str = "", status: str = "") -> tuple[bool, str]:
    """U13: Inline call interface — import and call directly, no subprocess.

    Returns (success, error_message). Use this instead of:
        subprocess.run(["python", ".devin/scripts/loop_memory_sync.py", ...])

    Example:
        from loop_memory_sync import run_inline
        ok, err = run_inline(root, session_id="s-123", status="in_progress")
        if not ok:
            # fallback was written, check loop_state_fallback.md
            print(f"Failed: {err}")
    """
    with _inline_lock:
        try:
            _safe_regenerate(root, session_id, status)
            return True, ""
        except Exception as e:
            error_msg = f"{e}"
            print(f"[loop_memory_sync] ERROR: {error_msg}", file=sys.stderr)
            return False, error_msg


def main() -> int:
    ap = argparse.ArgumentParser(description="Regenerate loop_state.md registry")
    ap.add_argument("--session", default="", help="Session ID to update")
    ap.add_argument("--status", default="", help="Status to set (completed, crashed, in_progress)")
    args = ap.parse_args()

    root = ahd_session.get_repo_root()
    # U06: Use safe wrapper with fallback
    try:
        _safe_regenerate(root, args.session, args.status)
    except Exception as e:
        print(f"[loop_memory_sync] ERROR: primary write failed, fallback written. Detail: {e}", file=sys.stderr)
        return 1
    return 0


if __name__ == "__main__":
    sys.exit(main())
