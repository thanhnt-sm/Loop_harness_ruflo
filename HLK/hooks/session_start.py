#!/usr/bin/env python3
"""U56 + T2.8: SessionStart hook — BOOT enforcement + HLK status check.

Verifies that BOOT protocol steps are completed before allowing work tools.
Sets boot_complete in session_state. Blocks work tools until BOOT complete.
Kiểm tra HLK config: nếu HLK bị tắt, in cảnh báo và ghi audit log.

Usage: Called by Devin CLI SessionStart hook event.
Stdin: {"session_id": "...", "prompt_id": "..."}
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Add hooks dir to path for ahd_session
sys.path.insert(0, str(Path(__file__).parent))
from ahd_session import get_session_state_path, get_repo_root, _locked_json_update


def _now_iso() -> str:
    """Trả về timestamp ISO với timezone UTC."""
    return datetime.now(timezone.utc).isoformat()


def _hlk_config_path(root: Path) -> Path:
    """Đường dẫn đến HLK config."""
    return root / "HLK" / "config" / "hlk.config.json"


def _load_hlk_config(root: Path) -> dict:
    """Đọc HLK config, mặc định enabled nếu file lỗi hoặc thiếu."""
    try:
        config_path = _hlk_config_path(root)
        if config_path.exists():
            return json.loads(config_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    except Exception as e:
        print(f"[session_start] unexpected exception: {e}", file=sys.stderr)
        pass
    return {"hlk_enabled": True}


def _audit_log_path(root: Path) -> Path:
    """Đường dẫn audit log cho HLK status."""
    return root / ".devin" / "audit" / "hlk_status.log"


def _write_hlk_audit(root: Path, message: str) -> None:
    """Ghi dòng audit log về trạng thái HLK."""
    try:
        audit_path = _audit_log_path(root)
        audit_path.parent.mkdir(parents=True, exist_ok=True)
        with audit_path.open("a", encoding="utf-8") as fh:
            fh.write(f"{_now_iso()} - {message}\n")
    except (OSError, UnicodeDecodeError):
        pass


    except Exception as e:
        print(f"[session_start] unexpected exception: {e}", file=sys.stderr)
        pass


def check_hlk_status(config: dict) -> bool:
    """T2.8: Kiểm tra HLK có đang bật không.

    Nếu hlk_enabled=false: in cảnh báo stderr + ghi audit log.
    Trả về True nếu HLK được bật, False nếu bị tắt.
    """
    if not config.get("hlk_enabled", True):
        msg = "HLK (Harness & Logic Knowledge layer) is disabled — security protection reduced."
        print(f"[session_start] WARNING: {msg}", file=sys.stderr)
        try:
            root = get_repo_root()
            _write_hlk_audit(root, msg)
        except Exception as e:
            print(f"[session_start] unexpected exception: {e}", file=sys.stderr)
            pass
        return False
    return True


def main() -> None:
    """U56: On session start, initialize boot_complete=false in session_state."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        return  # can't parse, don't block

    except Exception as e:
        print(f"[session_start] unexpected exception: {e}", file=sys.stderr)
        return  # can't parse, don't block

    session_id = data.get("session_id", "unknown")
    root = get_repo_root()

    # T2.8: Kiểm tra trạng thái HLK
    hlk_config = _load_hlk_config(root)
    check_hlk_status(hlk_config)

    # Initialize boot_complete=false — must be set true by BOOT protocol
    # Pentest fix: chỉ reset boot_complete khi session mới hoặc chưa có; giữ nguyên nếu session đang resume.
    prompt_id = data.get("prompt_id", "")
    state_path = get_session_state_path(session_id, root)

    def _boot_update(existing: dict | None) -> dict:
        existing = existing or {}
        is_fresh = not state_path.exists()
        # Nếu prompt_id đổi -> session mới -> reset boot_complete.
        if existing.get("prompt_id") != prompt_id:
            is_fresh = True
        return {
            **existing,
            "boot_complete": False if is_fresh else existing.get("boot_complete", False),
            "prompt_id": prompt_id,
            "boot_started_at": _now_iso(),
            "boot_steps_verified": existing.get("boot_steps_verified", []) if not is_fresh else [],
        }

    _locked_json_update(
        state_path,
        _boot_update,
        default={},
        session_id=session_id,
    )

    # Output: inject context to remind agent of BOOT protocol
    output = {
        "hookSpecificOutput": {
            "SessionStart": {
                "additionalContext": (
                    "[U56 BOOT Enforcement] Session started. "
                    "BOOT protocol MUST be completed before work tools. "
                    "Set boot_complete=true in session_state after BOOT steps verified. "
                    "Work tools (exec, write, edit) will be blocked until boot_complete=true."
                )
            }
        }
    }
    print(json.dumps(output))


if __name__ == "__main__":
    main()
