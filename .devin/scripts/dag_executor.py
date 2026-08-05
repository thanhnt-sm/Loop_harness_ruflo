#!/usr/bin/env python3
"""dag_executor.py — Phase D: Bộ thực thi song song dựa trên DAG.

Mô hình LLMCompiler: đọc một workflow đã biên dịch (DAG gồm các task có
tham chiếu phụ thuộc), xác định các task sẵn sàng (không còn phụ thuộc
chưa hoàn thành), lấy một lô (batch) kích thước giới hạn, đánh dấu
"running", và trả về cho hệ thống bên ngoài phân phối (dispatch) song
song. Khi task hoàn thành (callback bên ngoài), đánh dấu complete và
tìm các task mới sẵn sàng.

Lược đồ workflow đầu vào (từ dag_compile.py):
    {
      "workflow_id": str,
      "tasks": [
        {
          "id": str,
          "goal": str,
          "dependencies": [str],   # id các task phải hoàn thành trước
          "agent": str              # agent phụ trách (tuỳ chọn)
        }
      ]
    }

Trạng thái thực thi (lưu file):
    {
      "workflow_id": str,
      "tasks": {
        "<task_id>": {
          "status": "pending|ready|running|complete|failed",
          "result": dict | None,
          "completed_at": str | None
        }
      }
    }

CLI:
    python dag_executor.py <workflow.json> --execute [--batch-size N]
    python dag_executor.py <workflow.json> --status
    python dag_executor.py <workflow.json> --next [--batch-size N]
    python dag_executor.py <workflow.json> --complete <task_id> <result.json>
    python dag_executor.py <workflow.json> --fail <task_id> <reason>

Lưu trữ: .devin/plan_state/<workflow_id>_execution.json

Mã thoát:
    0 — mọi task đã hoàn thành
    1 — có task thất bại hoặc lỗi đầu vào
    2 — vẫn còn task đang chạy/chưa chạy
"""
from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

def _repo_root() -> Path:
    """Tìm thư mục gốc repo (chứa thư mục .devin)."""
    here = Path(__file__).resolve().parent  # .../.devin/scripts
    return here.parent.parent               # repo root


def _state_dir() -> Path:
    """Trả về thư mục .devin/plan_state, tự tạo nếu thiếu."""
    d = _repo_root() / ".devin" / "plan_state"
    d.mkdir(parents=True, exist_ok=True)
    return d


def _state_file(workflow_id: str) -> Path:
    """Trả về đường dẫn file trạng thái thực thi cho workflow."""
    safe_id = workflow_id.replace("/", "_").replace("\\", "_")
    return _state_dir() / f"{safe_id}_execution.json"


# Kích thước lô mặc định (số task tối đa trả về mỗi lần).
DEFAULT_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# Đọc/ghi trạng thái
# ---------------------------------------------------------------------------

def _load_workflow(path: str) -> dict | None:
    """Đọc file workflow đã biên dịch.

    Bước 1: Đọc file JSON. Bước 2: Kiểm tra có workflow_id + tasks.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor] Không đọc được workflow {path}: {exc}",
              file=sys.stderr)
        return None
    if not isinstance(data, dict) or "workflow_id" not in data or "tasks" not in data:
        print(f"[dag_executor] Workflow sai định dạng: thiếu workflow_id hoặc tasks",
              file=sys.stderr)
        return None
    return data


def _load_state(workflow_id: str) -> dict | None:
    """Tải trạng thái thực thi từ file. Nếu lỗi → trả None."""
    f = _state_file(workflow_id)
    if not f.exists():
        return None
    try:
        return json.loads(f.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor] Lỗi đọc trạng thái {workflow_id}: {exc}",
              file=sys.stderr)
        return None


def _save_state(state: dict) -> bool:
    """Lưu trạng thái thực thi vào file."""
    wf_id = state.get("workflow_id", "unknown")
    f = _state_file(wf_id)
    try:
        f.write_text(json.dumps(state, ensure_ascii=False, indent=2),
                     encoding="utf-8")
        return True
    except OSError as exc:
        print(f"[dag_executor] Lỗi lưu trạng thái: {exc}", file=sys.stderr)
        return False


def _init_state(workflow: dict) -> dict:
    """Khởi tạo trạng thái thực thi từ workflow.

    Bước 1: Tạo dict tasks với mọi task ở trạng thái "pending".
    Bước 2: Kiểm tra chu trình (cyclic dependency).
    Bước 3: Đánh dấu các task sẵn sàng (không có phụ thuộc) là "ready".
    """
    wf_id = workflow["workflow_id"]
    tasks_def = workflow.get("tasks", [])
    state = {
        "workflow_id": wf_id,
        "tasks": {},
    }
    for task in tasks_def:
        tid = task.get("id")
        if not tid:
            continue
        state["tasks"][tid] = {
            "status": "pending",
            "result": None,
            "completed_at": None,
            "dependencies": task.get("dependencies", []),
            "goal": task.get("goal", ""),
            "agent": task.get("agent", ""),
        }
    # Kiểm tra chu trình.
    cycle = _detect_cycle(state["tasks"])
    if cycle:
        print(f"[dag_executor] Phát hiện chu trình: {' -> '.join(cycle)}",
              file=sys.stderr)
        return {}
    # Đánh dấu task sẵn sàng.
    _mark_ready(state)
    return state


# ---------------------------------------------------------------------------
# Phân tích DAG
# ---------------------------------------------------------------------------

def _detect_cycle(tasks: dict) -> list[str]:
    """Phát hiện chu trình trong DAG bằng DFS.

    Trả về danh sách task_id tạo thành chu trình, hoặc [] nếu không có.
    """
    WHITE, GRAY, BLACK = 0, 1, 2
    color = {tid: WHITE for tid in tasks}
    stack: list[str] = []

    def dfs(node: str) -> list[str]:
        """DFS từ node, trả về chu trình nếu tìm thấy."""
        color[node] = GRAY
        stack.append(node)
        for dep in tasks.get(node, {}).get("dependencies", []):
            if dep not in tasks:
                continue  # phụ thuộc không tồn tại → bỏ qua
            if color[dep] == GRAY:
                # Tìm thấy chu trình.
                idx = stack.index(dep)
                return stack[idx:] + [dep]
            if color[dep] == WHITE:
                result = dfs(dep)
                if result:
                    return result
        stack.pop()
        color[node] = BLACK
        return []

    for tid in tasks:
        if color[tid] == WHITE:
            cycle = dfs(tid)
            if cycle:
                return cycle
    return []


def _is_ready(tid: str, tasks: dict) -> bool:
    """Kiểm tra task có sẵn sàng (mọi phụ thuộc đã complete)."""
    deps = tasks.get(tid, {}).get("dependencies", [])
    for dep in deps:
        if dep not in tasks:
            return False  # phụ thuộc không tồn tại → không sẵn sàng
        if tasks[dep].get("status") != "complete":
            return False
    return True


def _mark_ready(state: dict) -> None:
    """Đánh dấu các task pending thỏa điều kiện là "ready"."""
    tasks = state.get("tasks", {})
    for tid, info in tasks.items():
        if info.get("status") == "pending":
            if _is_ready(tid, tasks):
                info["status"] = "ready"


def _get_ready_tasks(state: dict, batch_size: int) -> list[str]:
    """Lấy danh sách task sẵn sàng, tối đa batch_size.

    Bước 1: Thu thập tất cả task ở trạng thái "ready".
    Bước 2: Cắt theo batch_size.
    Bước 3: Trả về danh sách task_id.
    """
    tasks = state.get("tasks", {})
    ready = [tid for tid, info in tasks.items() if info.get("status") == "ready"]
    return ready[:batch_size]


def _get_status_summary(state: dict) -> dict:
    """Tóm tắt trạng thái workflow: completed, ready, running, pending, failed."""
    tasks = state.get("tasks", {})
    counts = {"complete": 0, "ready": 0, "running": 0, "pending": 0, "failed": 0}
    by_status: dict[str, list[str]] = {k: [] for k in counts}
    for tid, info in tasks.items():
        st = info.get("status", "pending")
        counts[st] = counts.get(st, 0) + 1
        by_status.setdefault(st, []).append(tid)
    total = len(tasks)
    all_complete = total > 0 and counts["complete"] == total
    any_failed = counts.get("failed", 0) > 0
    return {
        "workflow_id": state.get("workflow_id"),
        "total_tasks": total,
        "counts": counts,
        "by_status": by_status,
        "all_complete": all_complete,
        "any_failed": any_failed,
    }


# ---------------------------------------------------------------------------
# Các thao tác chính
# ---------------------------------------------------------------------------

def execute(workflow: dict, batch_size: int) -> dict:
    """Thực thi: lấy lô task sẵn sàng, đánh dấu "running", trả về lô.

    Bước 1: Tải hoặc khởi tạo trạng thái.
    Bước 2: Đánh dấu task sẵn sàng.
    Bước 3: Lấy lô batch_size task.
    Bước 4: Đánh dấu lô là "running".
    Bước 5: Lưu trạng thái.
    Bước 6: Trả về lô + tóm tắt.
    """
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        state = _init_state(workflow)
        if not state or not state.get("tasks"):
            return {"executed": False, "reason": "Không thể khởi tạo trạng thái (có thể do chu trình)"}
    # Đánh dấu ready + lấy lô.
    _mark_ready(state)
    batch = _get_ready_tasks(state, batch_size)
    for tid in batch:
        state["tasks"][tid]["status"] = "running"
    _save_state(state)
    summary = _get_status_summary(state)
    batch_details = [
        {
            "id": tid,
            "goal": state["tasks"][tid].get("goal", ""),
            "agent": state["tasks"][tid].get("agent", ""),
            "dependencies": state["tasks"][tid].get("dependencies", []),
        }
        for tid in batch
    ]
    return {
        "executed": True,
        "workflow_id": wf_id,
        "batch": batch_details,
        "batch_size": len(batch),
        "status": summary,
    }


def get_next(workflow: dict, batch_size: int) -> dict:
    """Lấy lô task sẵn sàng tiếp theo (không đánh dấu running)."""
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        state = _init_state(workflow)
        if not state:
            return {"next": [], "reason": "Không thể khởi tạo trạng thái"}
    _mark_ready(state)
    batch = _get_ready_tasks(state, batch_size)
    batch_details = [
        {
            "id": tid,
            "goal": state["tasks"][tid].get("goal", ""),
            "agent": state["tasks"][tid].get("agent", ""),
            "dependencies": state["tasks"][tid].get("dependencies", []),
        }
        for tid in batch
    ]
    return {
        "workflow_id": wf_id,
        "next": batch_details,
        "batch_size": len(batch),
        "status": _get_status_summary(state),
    }


def get_status(workflow: dict) -> dict:
    """Lấy trạng thái hiện tại của workflow."""
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        state = _init_state(workflow)
        if not state:
            return {"status": {"error": "Không thể khởi tạo trạng thái"}}
        _save_state(state)
    _mark_ready(state)
    _save_state(state)
    return _get_status_summary(state)


def complete_task(workflow: dict, task_id: str, result: Any) -> dict:
    """Đánh dấu một task hoàn thành + tìm task mới sẵn sàng.

    Bước 1: Tải trạng thái. Bước 2: Đánh dấu task complete + lưu result.
    Bước 3: Đánh dấu task mới ready. Bước 4: Lưu + trả về.
    """
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        return {"completed": False, "reason": "Chưa có trạng thái thực thi"}
    if task_id not in state.get("tasks", {}):
        return {"completed": False, "reason": f"Task '{task_id}' không tồn tại"}
    state["tasks"][task_id]["status"] = "complete"
    state["tasks"][task_id]["result"] = result
    state["tasks"][task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _mark_ready(state)
    _save_state(state)
    summary = _get_status_summary(state)
    newly_ready = [
        tid for tid, info in state["tasks"].items()
        if info.get("status") == "ready" and tid != task_id
    ]
    return {
        "completed": True,
        "task_id": task_id,
        "newly_ready": newly_ready,
        "status": summary,
    }


def fail_task(workflow: dict, task_id: str, reason: str) -> dict:
    """Đánh dấu một task thất bại."""
    wf_id = workflow["workflow_id"]
    state = _load_state(wf_id)
    if state is None:
        return {"failed": False, "reason": "Chưa có trạng thái thực thi"}
    if task_id not in state.get("tasks", {}):
        return {"failed": False, "reason": f"Task '{task_id}' không tồn tại"}
    state["tasks"][task_id]["status"] = "failed"
    state["tasks"][task_id]["result"] = {"error": reason}
    state["tasks"][task_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _save_state(state)
    return {
        "failed": True,
        "task_id": task_id,
        "reason": reason,
        "status": _get_status_summary(state),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_result_file(path: str) -> Any:
    """Đọc file JSON kết quả cho --complete."""
    try:
        text = Path(path).read_text(encoding="utf-8")
        return json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor] Không đọc được file kết quả {path}: {exc}",
              file=sys.stderr)
        return None


def _exit_code_from_summary(summary: dict) -> int:
    """Xác định mã thoát từ tóm tắt trạng thái."""
    if summary.get("any_failed"):
        return 1
    if summary.get("all_complete"):
        return 0
    return 2


def _build_arg_parser() -> argparse.ArgumentParser:
    """Xây dựng trình phân tích tham số dòng lệnh."""
    ap = argparse.ArgumentParser(
        description="Phase D: Bộ thực thi song song dựa trên DAG"
    )
    ap.add_argument("workflow", help="Đường dẫn file workflow đã biên dịch")
    ap.add_argument("--execute", action="store_true",
                    help="Thực thi lô task sẵn sàng (đánh dấu running)")
    ap.add_argument("--status", action="store_true",
                    help="Hiển thị trạng thái workflow")
    ap.add_argument("--next", action="store_true",
                    help="Lấy lô task sẵn sàng tiếp theo")
    ap.add_argument("--complete", nargs=2, metavar=("task_id", "result.json"),
                    help="Đánh dấu task hoàn thành với kết quả")
    ap.add_argument("--fail", nargs=2, metavar=("task_id", "reason"),
                    help="Đánh dấu task thất bại với lý do")
    ap.add_argument("--batch-size", type=int, default=DEFAULT_BATCH_SIZE,
                    help=f"Kích thước lô tối đa (mặc định {DEFAULT_BATCH_SIZE})")
    return ap


def main(argv: list[str] | None = None) -> int:
    """Hàm chính: phân tích tham số, thực thi, in kết quả JSON."""
    ap = _build_arg_parser()
    args = ap.parse_args(argv)

    workflow = _load_workflow(args.workflow)
    if workflow is None:
        return 1

    if args.complete:
        task_id, result_path = args.complete
        result = _read_result_file(result_path)
        out = complete_task(workflow, task_id, result)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("completed"):
            return _exit_code_from_summary(out.get("status", {}))
        return 1

    if args.fail:
        task_id, reason = args.fail
        out = fail_task(workflow, task_id, reason)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if out.get("failed"):
            return 1
        return 1

    if args.execute:
        out = execute(workflow, args.batch_size)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        if not out.get("executed"):
            return 1
        return _exit_code_from_summary(out.get("status", {}))

    if args.next:
        out = get_next(workflow, args.batch_size)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        # Nếu có lỗi (chu trình, không khởi tạo được) → không có "status" → exit 1.
        if "status" not in out:
            return 1
        return _exit_code_from_summary(out.get("status", {}))

    if args.status:
        out = get_status(workflow)
        print(json.dumps(out, ensure_ascii=False, indent=2))
        # Nếu có lỗi (chu trình, không khởi tạo được) → exit 1.
        if isinstance(out, dict) and isinstance(out.get("status"), dict) and "error" in out["status"]:
            return 1
        return _exit_code_from_summary(out)

    ap.print_help(sys.stderr)
    return 1


if __name__ == "__main__":
    sys.exit(main())
