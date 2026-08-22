#!/usr/bin/env python3
"""self_heal.py — Hook tu chua tri (self-healing) PostToolUse.

Vong lap 4 giai doan: Monitor -> Detect -> Diagnose -> Recover.
Chay khi tool tra ve loi, chon hanh dong phuc hoi phu hop.

4 giai doan:
  1. Monitor: Quan sat pattern thuc thi va tinh nhat quan cua output.
  2. Detect: Nhan dien hanh vi bat thuong qua tin hieu loi
     (error, timeout, empty output, crash).
  3. Diagnose: Phan loai loi thanh 7 lop:
     timeout, malformed_args, stale_context, permission_denied,
     rate_limit, dependency_error, unknown.
  4. Recover: Chon hanh dong phuc hoi:
     retry_with_backoff, replan_from_checkpoint, fallback_tool, escalate_to_human.

Ngan sach phuc hoi: 3 lan (co the cau hinh). Het ngan sach -> escalate human.
Repair memory: ghi loi + phuc hoi vao .devin/telemetry/repair_memory.json
de tranh lap lai.

Dau vao (JSON stdin tu hook system):
  {"tool_name": str, "tool_input": dict, "error": str, "session_id": str}

Dau ra (JSON stdout):
  {"action": "retry|replan|fallback|escalate", "reason": str,
   "attempt": int, "budget_remaining": int}

Trang thai:
  .devin/telemetry/self_heal_state.json
  .devin/telemetry/repair_memory.json
"""
from __future__ import annotations

import json
import os
import sys
import time
from pathlib import Path

# Cau hinh
TELEMETRY_DIR = ".devin/telemetry"
STATE_FILE = f"{TELEMETRY_DIR}/self_heal_state.json"
REPAIR_MEMORY_FILE = f"{TELEMETRY_DIR}/repair_memory.json"

# Ngan sach phuc hoi mac dinh (so lan thu)
DEFAULT_RECOVERY_BUDGET = 3

# T14 fix: Max recursion depth cho self-heal (chống infinite loop)
MAX_SELF_HEAL_DEPTH = 2

# Anh xa tin hieu loi -> lop loi (failure class)
FAILURE_SIGNALS = {
    "timeout": ["timeout", "timed out", "deadline exceeded", "hang"],
    "malformed_args": ["invalid argument", "wrong type", "missing", "keyerror", "typeerror", "valueerror"],
    "stale_context": ["stale", "out of date", "no longer exists", "not found", "filenotfound"],
    "permission_denied": ["permission denied", "forbidden", "403", "unauthorized", "401"],
    "rate_limit": ["rate limit", "too many requests", "429", "throttle", "quota"],
    "dependency_error": ["importerror", "modulenotfound", "dependency", "no module", "pip", "package"],
}

# Anh xa lop loi -> hanh dong phuc hoi mac dinh
RECOVERY_ACTIONS = {
    "timeout": "retry_with_backoff",
    "malformed_args": "replan_from_checkpoint",
    "stale_context": "replan_from_checkpoint",
    "permission_denied": "escalate_to_human",
    "rate_limit": "retry_with_backoff",
    "dependency_error": "fallback_tool",
    "unknown": "retry_with_backoff",
}

# Rut gon action cho output JSON
ACTION_SHORT = {
    "retry_with_backoff": "retry",
    "replan_from_checkpoint": "replan",
    "fallback_tool": "fallback",
    "escalate_to_human": "escalate",
}


def _repo_root() -> Path:
    """Tim thu muc goc repo (co .devin)."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def _load_json(path: Path, default):
    """Doc JSON an toan (tra ve default neu loi/khong ton tai)."""
    try:
        if path.exists():
            data = json.loads(path.read_text(encoding="utf-8"))
            if isinstance(data, type(default)) if default is not None else True:
                return data
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    except Exception as e:
        print(f"[self_heal] unexpected exception: {e}", file=sys.stderr)
        pass
    return default


def _save_json(path: Path, data) -> None:
    """Ghi JSON an toan (atomic tmp + rename, tên tmp duy nhất theo pid)."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        pid = os.getpid()
        tmp = path.with_suffix(f"{path.suffix}.{pid}.tmp")
        tmp.write_text(json.dumps(data, indent=2), encoding="utf-8")
        tmp.replace(path)
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(f"[self_heal] khong the ghi {path}: {e}", file=sys.stderr)


# --- Giai doan 1 + 2: Monitor & Detect ---

    except Exception as e:
        print(f"[self_heal] khong the ghi {path}: {e}", file=sys.stderr)


# --- Giai doan 1 + 2: Monitor & Detect ---

def detect_failure(data: dict) -> str | None:
    """Giai doan 2: Nhan dien tin hieu loi tu du lieu hook.

    Tra ve chuoi loi (None neu khong co loi).
    """
    error = data.get("error")
    if error:
        return str(error)
    # Kiem tra output rong / crash qua tool_output
    tool_output = data.get("tool_output", "")
    if isinstance(tool_output, dict):
        out_str = str(tool_output.get("content", tool_output))
    else:
        out_str = str(tool_output)
    low = out_str.lower()
    if not out_str.strip():
        return "empty output"
    for marker in ("error", "exception", "traceback", "crash", "failed"):
        if marker in low:
            return out_str
    return None


# --- Giai doan 3: Diagnose ---

def diagnose_failure(error_text: str) -> str:
    """Giai doan 3: Phan loai loi thanh 1 trong 7 lop.

    Tra ve ten lop loi (mac dinh 'unknown').
    """
    low = error_text.lower()
    for failure_class, signals in FAILURE_SIGNALS.items():
        for sig in signals:
            if sig in low:
                return failure_class
    return "unknown"


# --- Giai doan 4: Recover ---

def select_recovery(failure_class: str, attempt: int, budget: int) -> tuple:
    """Giai doan 4: Chon hanh dong phuc hoi.

    Tra ve (action_full, action_short, reason).
    """
    # Het ngan sach -> luon escalate
    if attempt >= budget:
        return "escalate_to_human", "escalate", "het_ngan_sach_phuc_hoi"
    action = RECOVERY_ACTIONS.get(failure_class, "retry_with_backoff")
    reason = f"lop_loi={failure_class}, lan_thu={attempt + 1}/{budget}"
    return action, ACTION_SHORT[action], reason


def _log_repair_memory(root: Path, entry: dict) -> None:
    """Ghi vao repair memory de tranh lap lai loi tuong tu."""
    memory = _load_json(root / REPAIR_MEMORY_FILE, {"entries": []})
    if not isinstance(memory, dict):
        memory = {"entries": []}
    memory.setdefault("entries", []).append(entry)
    # Gioi han 200 entry
    if len(memory["entries"]) > 200:
        memory["entries"] = memory["entries"][-200:]
    _save_json(root / REPAIR_MEMORY_FILE, memory)


def self_heal(root: Path, data: dict) -> dict:
    """Vong lap chinh: Monitor -> Detect -> Diagnose -> Recover.

    Tra ve dict output cho hook.
    """
    # Giai doan 1 (Monitor): kiem tra co loi khong
    error_text = detect_failure(data)
    if error_text is None:
        # Khong co loi -> bo qua
        return {
            "action": "retry",
            "reason": "khong_co_loi",
            "attempt": 0,
            "budget_remaining": DEFAULT_RECOVERY_BUDGET,
        }

    # Tai trang thai (xu ly state hong/thieu)
    state = _load_json(root / STATE_FILE, {})
    if not isinstance(state, dict):
        state = {}
    budget = state.get("recovery_budget", DEFAULT_RECOVERY_BUDGET)
    attempts = state.get("attempts", {})

    # Giai doan 3 (Diagnose): phan loai loi
    failure_class = diagnose_failure(error_text)
    tool_name = str(data.get("tool_name", "unknown"))

    # Dem so lan thu cho tool nay
    attempt = attempts.get(tool_name, 0)

    # Giai doan 4 (Recover): chon hanh dong
    action_full, action_short, reason = select_recovery(failure_class, attempt, budget)

    # Cap nhat state
    if action_short == "escalate":
        # Pentest fix: không reset attempts về 0 để tránh retry storm / livelock.
        # Giữ attempts ở budget để lần sau tiếp tục escalate.
        attempts[tool_name] = budget
    else:
        attempts[tool_name] = attempt + 1
    state["attempts"] = attempts
    state["last_failure_class"] = failure_class
    state["last_action"] = action_full
    _save_json(root / STATE_FILE, state)

    # Ghi repair memory
    _log_repair_memory(root, {
        "timestamp": time.time(),
        "tool_name": tool_name,
        "failure_class": failure_class,
        "error": error_text[:500],
        "action": action_full,
        "attempt": attempt + 1,
        "budget_remaining": budget - (attempt + 1) if action_short != "escalate" else 0,
    })

    budget_remaining = max(0, budget - (attempt + 1)) if action_short != "escalate" else 0

    return {
        "action": action_short,
        "reason": reason,
        "attempt": attempt + 1,
        "budget_remaining": budget_remaining,
    }


def _check_recursion_depth(data: dict) -> dict:
    """T14 fix: Kiểm tra recursion depth — chặn self-heal infinite loop.

    Đếm self_heal_depth trong session_state. Nếu >= MAX_SELF_HEAL_DEPTH → escalate.

    Pentest V14 fix: handle session_state=None (explicit null) không crash.

    Returns:
        {"blocked": bool, "result": dict}
    """
    session_state = data.get("session_state") or {}
    depth = session_state.get("self_heal_depth", 0)

    if depth >= MAX_SELF_HEAL_DEPTH:
        return {
            "blocked": True,
            "result": {
                "action": "escalate",
                "reason": f"self_heal_recursion_limit: depth={depth} >= max={MAX_SELF_HEAL_DEPTH}",
                "attempt": depth,
                "budget_remaining": 0,
            },
        }
    return {"blocked": False, "result": {}}


def main() -> int:
    """Doc JSON stdin, chay self-heal, in ket qua JSON stdout."""
    try:
        raw = sys.stdin.read()
        data = json.loads(raw) if raw.strip() else {}
    except (json.JSONDecodeError, TypeError, ValueError) as e:
        print(json.dumps({
            "action": "escalate",
            "reason": f"input_khong_hop_le: {e}",
            "attempt": 0,
            "budget_remaining": 0,
        }))
        return 0

    except Exception as e:
        print(json.dumps({
            "action": "escalate",
            "reason": f"input_khong_hop_le: {e}",
            "attempt": 0,
            "budget_remaining": 0,
        }))
        return 0

    # T14 fix: Check recursion depth trước khi self-heal
    depth_check = _check_recursion_depth(data)
    if depth_check["blocked"]:
        print(json.dumps(depth_check["result"]))
        return 0

    root = _repo_root()
    try:
        result = self_heal(root, data)
    except Exception as e:
        result = {
            "action": "escalate",
            "reason": f"loi_xu_ly: {e}",
            "attempt": 0,
            "budget_remaining": 0,
        }
    print(json.dumps(result))
    return 0


if __name__ == "__main__":
    sys.exit(main())
