#!/usr/bin/env python3
"""Coverage enforce — hook theo dõi coverage matrix cho plan items.

Hook loại PostToolUse: chạy sau mỗi Write/Edit, theo dõi xem các task trong
IMPLEMENTATION_PLAN.md đã được thực thi chưa. Advisory (không block, chỉ log gap).

Nhận JSON trên stdin:
  {"tool_name": "Write", "tool_input": {"file_path": "..."}, "tool_output": {...}, "session_id": "..."}

Cơ chế:
  1. Đọc IMPLEMENTATION_PLAN.md để lấy coverage matrix kỳ vọng
  2. Sau mỗi Write/Edit: kiểm tra file vừa sửa có khớp task nào trong plan không
  3. Cập nhật state: .devin/plan_state/<plan_name>_coverage.json
  4. Grep symbol (hàm) kỳ vọng trong file mới — nếu có -> mark "executed"
  5. Khi session kết thúc: nếu task vẫn "planned" (chưa executed) -> flag gap

State schema:
  {
    "plan_name": "IMPLEMENTATION_PLAN",
    "tasks": {
      "<task_id>": {
        "file": "src/foo.py",
        "function": "bar",
        "status": "planned|executed|verified|missing"
      }
    }
  }

Output (stdout): JSON {"coverage_pct": float, "executed": int, "total": int, "gaps": list}
Exit code: 0 luôn (advisory, không block)
"""
from __future__ import annotations

import json
import os
import re
import subprocess
import sys
import threading
from pathlib import Path

# Import ahd_session từ cùng thư mục hooks để dùng file-lock cho coverage state.
try:
    import ahd_session
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    ahd_session = None  # type: ignore[assignment]

# T4.13: Import shared path_zones (single source of truth cho blocked/safe zones).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from path_zones import is_blocked as _pathzones_is_blocked, is_safe as _pathzones_is_safe
except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
    _pathzones_is_blocked = None
    _pathzones_is_safe = None

# U15: Timeout nội bộ — coverage_enforce chạy grep nên cần dư thời gian.
HOOK_TIMEOUT_SECONDS = 4.0

# Tool ghi file mà hook theo dõi
WRITE_TOOLS = {"Write", "write", "Edit", "edit", "notebook_edit", "NotebookEdit"}

# Thư mục lưu coverage state
PLAN_STATE_DIR = ".devin" / "plan_state" if False else None  # placeholder, dùng Path runtime


def _get_plan_state_dir(root: Path) -> Path:
    """Trả đường dẫn thư mục plan_state (tạo nếu thiếu)."""
    # Ưu tiên config root của ahd_session, fallback về root/.devin
    config_root = root / ".devin"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ahd_session
        config_root = ahd_session.get_config_root(root)
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
        pass
    except Exception as e:
        print(f"[coverage_enforce] unexpected exception: {e}", file=sys.stderr)
        pass
    state_dir = config_root / "plan_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    return state_dir


def _find_plan_file(root: Path) -> Path | None:
    """Tìm file IMPLEMENTATION_PLAN.md (ưu tiên docs/plans/, sau đó root)."""
    candidates = [
        root / "docs" / "plans" / "IMPLEMENTATION_PLAN.md",
        root / "IMPLEMENTATION_PLAN.md",
    ]
    # Cũng tìm các plan khác trong docs/plans/
    plans_dir = root / "docs" / "plans"
    if plans_dir.is_dir():
        for p in sorted(plans_dir.glob("*PLAN*.md")):
            if p not in candidates:
                candidates.append(p)
    for c in candidates:
        if c.exists():
            return c
    return None


def _parse_plan(plan_path: Path) -> dict:
    """Parse IMPLEMENTATION_PLAN.md thành coverage matrix.

    Trích các task dạng:
      - [ ] T01: src/foo.py (functions: bar, baz)
      - [x] T02: scripts/util.py (functions: run)
      ## T03 — src/qux.py: functions: quux

    Trả về: {"plan_name": str, "tasks": {task_id: {file, function, status}}}
    """
    plan_name = plan_path.stem  # tên file không extension
    tasks: dict[str, dict] = {}
    try:
        text = plan_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return {"plan_name": plan_name, "tasks": {}}

    # Pattern 1: "- [ ] T01: src/foo.py (functions: bar, baz)"
    line_pattern = re.compile(
        r"(?:^|\n)\s*(?:-\s*\[[ xX]\]\s*|##\s*)"
        r"(?P<task_id>[A-Za-z0-9_\-]+)\s*[:—-]\s*"
        r"(?P<file>[^\s\(]+)"
        r"(?:\s*\((?i:functions?|symbols?)\s*[:=]\s*(?P<symbols>[^\)]+)\))?"
    )
    for m in line_pattern.finditer(text):
        task_id = m.group("task_id")
        file_path = m.group("file").strip().strip("`")
        symbols_str = m.group("symbols") or ""
        symbols = [s.strip().strip("`*") for s in symbols_str.split(",") if s.strip()]
        # Trạng thái: nếu dòng có [x] -> executed, ngược lại planned
        raw_line = m.group(0)
        status = "executed" if re.search(r"\[[xX]\]", raw_line) else "planned"
        tasks[task_id] = {
            "file": file_path.replace("\\", "/"),
            "function": symbols[0] if symbols else "",
            "symbols": symbols,
            "status": status,
        }
    return {"plan_name": plan_name, "tasks": tasks}


def _load_coverage_state(state_path: Path, plan_name: str) -> dict:
    """Đọc coverage state từ file JSON. Tạo mới nếu không có hoặc bị hỏng."""
    if state_path.exists():
        try:
            data = json.loads(state_path.read_text(encoding="utf-8"))
            if isinstance(data, dict) and "tasks" in data:
                return data
        except (json.JSONDecodeError, TypeError, ValueError):
            pass  # state hỏng -> tạo mới
    return {"plan_name": plan_name, "tasks": {}}


def _save_coverage_state(state_path: Path, state: dict) -> None:
    """Ghi coverage state ra file JSON (atomic + lock để tránh race giữa các hook).

    Dùng ahd_session._locked_json_update để đảm bảo chỉ có một tiến trình ghi tại một thời điểm.
    Fallback: ghi tạm + rename với tên file tmp duy nhất theo pid/thread.
    """
    try:
        if ahd_session is not None:
            ahd_session._locked_json_update(
                state_path,
                lambda _existing: state,
                default=state,
                session_id="",
            )
            return
    except (TimeoutError, OSError, FileExistsError):
        pass
    # Fallback: ghi tạm với tên duy nhất để tránh đè nhau giữa các hook song song.
    try:
        tmp_name = f"{state_path.stem}_{os.getpid()}_{threading.current_thread().ident or 0}.tmp"
        tmp = state_path.with_name(tmp_name)
        tmp.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")
        tmp.replace(state_path)
    except (json.JSONDecodeError, TypeError, ValueError):
        pass
    except Exception as e:
        print(f"[coverage_enforce] unexpected exception: {e}", file=sys.stderr)


def _grep_symbol_in_file(file_path: Path, symbol: str) -> bool:
    """Grep symbol (tên hàm/class) trong file bằng subprocess.

    Trả True nếu tìm thấy định nghĩa def/class/function symbol.
    """
    if not file_path.exists() or not symbol:
        return False
    # Dùng regex trực tiếp thay vì subprocess (đơn giản, không phụ thuộc platform)
    try:
        content = file_path.read_text(encoding="utf-8", errors="ignore")
    except (OSError, UnicodeDecodeError):
        return False
    except Exception as e:
        print(f"[coverage_enforce] unexpected exception: {e}", file=sys.stderr)
        return False
    pattern = re.compile(
        rf"\b(def|class|function|const)\s+{re.escape(symbol)}\b",
        re.IGNORECASE,
    )
    return bool(pattern.search(content))


def _normalize_path(p: str) -> str:
    """Chuẩn hóa đường dẫn để so khớp.

    Pentest fix: dùng while loop thay lstrip để chỉ bỏ prefix './' thay vì mọi ký tự '.'/'/'.
    """
    norm = p.replace("\\", "/")
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _is_path_in_safe_zone(file_path: str) -> bool:
    """T4.13: Kiểm tra file edit có nằm trong safe zone (dùng shared path_zones).

    Advisory-only — không block, chỉ dùng cho logging/coverage tracking.
    Trả True nếu file nằm trong safe zone hoặc path_zones không khả dụng.
    """
    if _pathzones_is_safe is None:
        return True  # fallback: không path_zones -> mặc định an toàn
    try:
        return _pathzones_is_safe(file_path)
    except Exception as e:
        print(f"[coverage_enforce] unexpected exception: {e}", file=sys.stderr)
        return True


def _is_path_blocked(file_path: str) -> bool:
    """T4.13: Kiểm tra file edit có nằm trong blocked zone (dùng shared path_zones).

    Advisory-only — không block (schema_gate đã block), chỉ dùng cho logging.
    """
    if _pathzones_is_blocked is None:
        return False
    try:
        return _pathzones_is_blocked(file_path)
    except (TimeoutError, OSError, FileExistsError):
        return False
    except Exception as e:
        print(f"[coverage_enforce] unexpected exception: {e}", file=sys.stderr)
        return False


def _update_coverage(
    state: dict,
    plan: dict,
    edited_file: str,
    root: Path,
) -> dict:
    """Cập nhật coverage state sau khi file được edit.

    - Ghép task từ plan vào state (nếu chưa có)
    - Nếu file edit khớp task -> mark "executed", grep symbol để xác nhận
    """
    plan_tasks = plan.get("tasks", {})
    state_tasks = state.setdefault("tasks", {})
    norm_edited = _normalize_path(edited_file)

    # Đồng bộ task từ plan vào state (giữ status đã có)
    for task_id, task_info in plan_tasks.items():
        if task_id not in state_tasks:
            state_tasks[task_id] = {
                "file": task_info["file"],
                "function": task_info.get("function", ""),
                "symbols": task_info.get("symbols", []),
                "status": task_info.get("status", "planned"),
            }

    # Kiểm tra file edit khớp task nào
    for task_id, task in state_tasks.items():
        task_file = _normalize_path(task.get("file", ""))
        if not task_file:
            continue
        # Khớp nếu đường dẫn giống nhau hoặc file edit kết thúc bằng task_file
        matched = (
            norm_edited == task_file
            or norm_edited.endswith(task_file)
            or task_file.endswith(norm_edited)
        )
        if not matched:
            continue
        # Đã verified rồi thì giữ nguyên
        if task.get("status") == "verified":
            continue
        # Grep symbol kỳ vọng trong file mới ghi
        symbols = task.get("symbols") or ([task["function"]] if task.get("function") else [])
        full_path = (root / edited_file) if not Path(edited_file).is_absolute() else Path(edited_file)
        all_symbols_found = True
        if symbols:
            for sym in symbols:
                if sym and not _grep_symbol_in_file(full_path, sym):
                    all_symbols_found = False
                    break
        if all_symbols_found and symbols:
            task["status"] = "verified"
        else:
            task["status"] = "executed"
        task["last_edited"] = edited_file

    return state


def _compute_gaps(state: dict) -> list[str]:
    """Tính danh sách task_id vẫn ở trạng thái 'planned' (chưa executed)."""
    gaps = []
    for task_id, task in state.get("tasks", {}).items():
        if task.get("status") == "planned":
            gaps.append(task_id)
    return gaps


def _compute_coverage(state: dict) -> tuple[float, int, int]:
    """Tính coverage percentage, số executed, tổng số task."""
    tasks = state.get("tasks", {})
    total = len(tasks)
    if total == 0:
        return 0.0, 0, 0
    executed = sum(
        1 for t in tasks.values() if t.get("status") in ("executed", "verified")
    )
    pct = round((executed / total) * 100, 2)
    return pct, executed, total


def main():
    """Điểm vào chính: đọc stdin, cập nhật coverage, xuất kết quả."""
    try:
        data = json.load(sys.stdin)
    except (json.JSONDecodeError, TypeError, ValueError):
        # Không parse được -> skip silently (advisory)
        print(json.dumps({"coverage_pct": 0.0, "executed": 0, "total": 0, "gaps": []}))
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}

    # Xác định repo root
    root = Path.cwd()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ahd_session
        root = ahd_session.get_repo_root()
    except (ImportError, ModuleNotFoundError, SyntaxError, ValueError):
        pass

    # Tìm plan file — nếu không có -> skip silently
    plan_path = _find_plan_file(root)
    if plan_path is None:
        print(json.dumps({"coverage_pct": 0.0, "executed": 0, "total": 0, "gaps": []}))
        sys.exit(0)

    plan = _parse_plan(plan_path)
    plan_name = plan.get("plan_name", "IMPLEMENTATION_PLAN")

    # Đường dẫn state file
    state_dir = _get_plan_state_dir(root)
    state_path = state_dir / f"{plan_name}_coverage.json"
    state = _load_coverage_state(state_path, plan_name)

    # Chỉ cập nhật khi tool là Write/Edit
    if tool_name in WRITE_TOOLS:
        edited_file = ""
        for key in ("file_path", "path", "notebook_path", "file"):
            if key in tool_input:
                edited_file = str(tool_input[key])
                break
        if edited_file:
            state = _update_coverage(state, plan, edited_file, root)

    # Lưu state
    _save_coverage_state(state_path, state)

    # Tính coverage và gaps
    pct, executed, total = _compute_coverage(state)
    gaps = _compute_gaps(state)

    # Xuất kết quả JSON ra stdout
    result = {
        "coverage_pct": pct,
        "executed": executed,
        "total": total,
        "gaps": gaps,
    }
    print(json.dumps(result, ensure_ascii=False))

    # Log gaps ra stderr (advisory, không block)
    if gaps:
        print(
            f"[coverage_enforce] WARNING: {len(gaps)} task(s) not executed: {', '.join(gaps)}",
            file=sys.stderr,
        )

    sys.exit(0)


if __name__ == "__main__":
    # U15: Timeout nội bộ — advisory, fail-open luôn
    result = {"code": 0}

    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception as e:
            print(f"[coverage_enforce] unexpected exception: {e}", file=sys.stderr)
            # Lỗi không ngờ -> exit 0 (advisory, không block)
            result["code"] = 0

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[coverage_enforce] timeout - exit 0 (advisory)", file=sys.stderr)
        result["code"] = 0
    sys.exit(result["code"])
