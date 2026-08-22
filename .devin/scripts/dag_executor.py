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
import copy
import json
import os
import sys
from concurrent.futures import ThreadPoolExecutor, as_completed
from dataclasses import dataclass
from datetime import datetime, timezone
from pathlib import Path
from typing import Any, Callable

import checkpoint as checkpoint_module
import idempotency as idempotency_module
from data_models import CheckpointState, Turn

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
    # Task 3.9: namespace isolation — loop_id prefix nếu cấu hình AHD_LOOP_ID
    loop_id = os.environ.get("AHD_LOOP_ID", "")
    if loop_id:
        safe_id = f"{loop_id.replace('/', '_')}__{safe_id}"
    return _state_dir() / f"{safe_id}_execution.json"


# Task 3.9: hard max iterations (configurable, default 50)
def _max_loop_iterations() -> int:
    """Đọc giới hạn loop từ env mỗi lần gọi (cho phép đổi lúc runtime)."""
    try:
        return int(os.environ.get("AHD_MAX_LOOP_ITERATIONS", "50"))
    except (TypeError, ValueError):
        return 50


# Kích thước lô mặc định (số task tối đa trả về mỗi lần).
DEFAULT_BATCH_SIZE = 5


# ---------------------------------------------------------------------------
# Đọc/ghi trạng thái
# ---------------------------------------------------------------------------

def _load_workflow(path: str) -> dict | None:
    """Đọc file workflow đã biên dịch — hỗ trợ schema mới (tasks) và cũ (nodes).

    Bước 1: Đọc file JSON.
    Bước 2: Validate + migrate schema (dag_schema.normalize_workflow).
    Bước 3: Strict validation — reject nếu có cả tasks và nodes.
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[dag_executor] Không đọc được workflow {path}: {exc}",
              file=sys.stderr)
        return None
    if not isinstance(data, dict) or "workflow_id" not in data:
        print(f"[dag_executor] Workflow sai định dạng: thiếu workflow_id",
              file=sys.stderr)
        return None
    # T1 fix: dùng dag_schema để validate + migrate
    try:
        from dag_schema import normalize_workflow
        normalized, error = normalize_workflow(data)
        if normalized is None:
            print(f"[dag_executor] Workflow không hợp lệ: {error}",
                  file=sys.stderr)
            return None
        return normalized
    except (ImportError, ModuleNotFoundError):
        # Fallback: chấp nhận schema cũ (tasks hoặc nodes)
        has_tasks = "tasks" in data and data["tasks"] is not None
        has_nodes = "nodes" in data and data["nodes"] is not None
        if has_tasks and has_nodes:
            print(f"[dag_executor] Schema confusion: có cả tasks và nodes",
                  file=sys.stderr)
            return None
        if not has_tasks and not has_nodes:
            print(f"[dag_executor] Workflow sai định dạng: thiếu tasks hoặc nodes",
                  file=sys.stderr)
            return None
        # Migrate old schema (nodes → tasks) inline
        if has_nodes:
            tasks = []
            for node in data["nodes"]:
                tasks.append({
                    "id": node.get("task_id", ""),
                    "goal": node.get("description", ""),
                    "dependencies": node.get("deps", []),
                    "agent": node.get("agent", ""),
                })
            data = {
                "workflow_id": data.get("workflow_id", ""),
                "schema_version": 1,
                "tasks": tasks,
                "edges": data.get("edges", []),
            }
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
        # Task 3.9: immutable state log (append-only Merkle chain) —
        # best-effort, không chặn execution khi telemetry lỗi.
        try:
            from loop_memory_sync import append_state_log
            append_state_log(
                _repo_root(), str(wf_id), "dag_state_saved",
                {"step": state.get("last_executed_step", ""),
                 "status": state.get("status", "")},
            )
        except (ImportError, ModuleNotFoundError):
            pass
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
    """Tóm tắt trạng thái workflow: completed, ready, running, pending, failed, blocked."""
    tasks = state.get("tasks", {})
    counts = {"complete": 0, "ready": 0, "running": 0, "pending": 0, "failed": 0, "blocked": 0}
    by_status: dict[str, list[str]] = {k: [] for k in counts}
    for tid, info in tasks.items():
        st = info.get("status", "pending")
        counts[st] = counts.get(st, 0) + 1
        by_status.setdefault(st, []).append(tid)
    total = len(tasks)
    all_complete = total > 0 and counts["complete"] == total
    any_failed = counts.get("failed", 0) > 0
    any_blocked = counts.get("blocked", 0) > 0
    return {
        "workflow_id": state.get("workflow_id"),
        "total_tasks": total,
        "counts": counts,
        "by_status": by_status,
        "all_complete": all_complete,
        "any_failed": any_failed,
        "any_blocked": any_blocked,
    }


# ---------------------------------------------------------------------------
# Các thao tác chính
# ---------------------------------------------------------------------------

def get_batch(workflow: dict, batch_size: int) -> dict:
    """Lấy lô task sẵn sàng, đánh dấu "running", trả về lô.

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


# ---------------------------------------------------------------------------
# T2.7: Durable execution API
# ---------------------------------------------------------------------------

@dataclass
class ExecResult:
    """Kết quả thực thi DAG hoàn chỉnh."""
    success: bool
    status: dict
    results: dict[str, Any]
    error: str | None = None


def _transient_exception(exc: Exception) -> bool:
    """Coi hầu hết exception trong runner là transient (có thể retry).

    Có thể mở rộng sau này để phân biệt fatal vs transient.
    """
    return True


def _default_runner(task_id: str, goal: str) -> Any:
    """Runner mặc định — trả về ok nếu không có runner tùy chỉnh."""
    return {"ok": True, "task_id": task_id, "goal": goal}


def _current_run_id() -> str:
    """Lấy run_id từ env hoặc module."""
    return os.environ.get("AHD_RUN_ID", "")


def _state_to_workflow(state: dict) -> dict:
    """Tái tạo workflow dict từ trạng thái đã lưu để resume."""
    tasks = []
    for tid, info in state.get("tasks", {}).items():
        tasks.append({
            "id": tid,
            "dependencies": info.get("dependencies", []),
            "goal": info.get("goal", ""),
            "agent": info.get("agent", ""),
        })
    return {"workflow_id": state.get("workflow_id", "default"), "tasks": tasks}


def _save_checkpoint_for_state(state: dict) -> None:
    """T2.7: Lưu checkpoint sau mỗi batch bằng checkpoint.save."""
    try:
        wf_id = state.get("workflow_id", "default")
        step_id = state.get("last_executed_step", "batch") or "batch"
        ts = datetime.now(timezone.utc)
        ckpt = CheckpointState(
            version=2,
            run_id=wf_id,
            conversation=[],
            side_effects_ledger=[],
            run_metadata={"dag_state": copy.deepcopy(state)},
            external_handles=[],
            timestamp=ts,
            step_id=step_id,
        )
        checkpoint_module.save(ckpt, workflow_id=wf_id, root=_repo_root())
    except (ValueError, TypeError, KeyError, AttributeError):
        pass


    except Exception as e:
        print(f"[dag_executor] unexpected exception: {e}", file=sys.stderr)
        pass


def execute(
    workflow: dict,
    checkpoint: CheckpointState | dict | None = None,
    batch_size: int = DEFAULT_BATCH_SIZE,
    runner: Callable[[str, str], Any] | None = None,
    max_retries: int = 2,
) -> ExecResult:
    """T2.7: Thực thi DAG hoàn chỉnh, checkpoint mỗi batch, retry transient.

    - Nếu checkpoint là CheckpointState/dict: resume từ đó.
    - Chạy từng batch song song (trong batch) theo dependency.
    - Gọi runner(task_id, goal) cho mỗi task; retry nếu exception transient.
    - Gọi on_node_complete sau mỗi task.
    - Trả về ExecResult khi hoàn thành hoặc thất bại.
    """
    if runner is None:
        runner = _default_runner

    # Khởi tạo hoặc resume state
    if checkpoint is not None:
        if isinstance(checkpoint, CheckpointState):
            state = checkpoint.run_metadata.get("dag_state", {})
        elif isinstance(checkpoint, dict):
            if "dag_state" in checkpoint:
                state = checkpoint["dag_state"]
            else:
                state = checkpoint
        else:
            return ExecResult(success=False, status={}, results={}, error="checkpoint invalid")
    else:
        state = _load_state(workflow["workflow_id"])

    if state is None or not state:
        state = _init_state(workflow)
        if not state:
            return ExecResult(success=False, status={}, results={}, error="cannot init state (cycle?)")

    wf_id = state.get("workflow_id", workflow["workflow_id"])
    os.environ["AHD_RUN_ID"] = wf_id

    # T2.7/T3.5: khi resume (có checkpoint/state đã lưu), reset các task đang
    # "running" về "pending" — giả định process bị kill giữa chừng. Idempotency
    # ledger sẽ đảm bảo task đã thực sự hoàn thành không bị re-run (cache hit).
    if checkpoint is not None:
        for tid, info in state.get("tasks", {}).items():
            if info.get("status") == "running":
                info["status"] = "pending"

    iteration = 0
    while True:
        _mark_ready(state)
        batch = _get_ready_tasks(state, batch_size)
        if not batch:
            summary = _get_status_summary(state)
            if summary.get("all_complete"):
                _save_state(state)
                _save_checkpoint_for_state(state)
                return ExecResult(success=True, status=summary, results={tid: state["tasks"][tid].get("result") for tid in state["tasks"]})
            if summary.get("any_failed"):
                _save_state(state)
                _save_checkpoint_for_state(state)
                failed = [tid for tid, info in state["tasks"].items() if info.get("status") == "failed"]
                return ExecResult(success=False, status=summary, results={}, error=f"failed tasks: {failed}")
            # Deadlock: có task đang running hoặc pending nhưng không ready
            _save_state(state)
            return ExecResult(success=False, status=summary, results={}, error="deadlock or waiting for running tasks")

        iteration += 1
        # Task 3.9: hard max iterations — còn batch nhưng đã vượt ngưỡng ->
        # dừng (không loop vô hạn). Chỉ áp dụng khi vẫn còn việc phải chạy.
        if iteration > _max_loop_iterations():
            _save_state(state)
            summary = _get_status_summary(state)
            return ExecResult(
                success=False, status=summary, results={},
                error=f"max loop iterations exceeded ({_max_loop_iterations()})",
            )
        # Đánh dấu running
        for tid in batch:
            state["tasks"][tid]["status"] = "running"
        _save_state(state)

        # Chạy batch song song
        results: dict[str, Any] = {}
        blocked: str | None = None
        with ThreadPoolExecutor(max_workers=min(len(batch), 8)) as pool:
            futures = {pool.submit(_run_task, tid, state["tasks"][tid], runner, max_retries, wf_id): tid for tid in batch}
            for future in as_completed(futures):
                tid = futures[future]
                try:
                    result = future.result()
                    results[tid] = result
                    state["tasks"][tid]["status"] = "complete"
                    state["tasks"][tid]["result"] = result
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()
                except IdempotencyBlockedError as exc:
                    # CVE-2026-AHD-003: lock failure -> BLOCK toàn bộ execution.
                    # Không đánh dấu "failed" (failed = có thể retry/continue),
                    # mà đánh dấu "blocked" và dừng DAG ngay.
                    blocked = str(exc)
                    state["tasks"][tid]["status"] = "blocked"
                    state["tasks"][tid]["result"] = {"error": str(exc)}
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()
                except (ValueError, TypeError, KeyError, AttributeError) as exc:
                    state["tasks"][tid]["status"] = "failed"
                    state["tasks"][tid]["result"] = {"error": str(exc)}
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()

                except Exception as exc:
                    state["tasks"][tid]["status"] = "failed"
                    state["tasks"][tid]["result"] = {"error": str(exc)}
                    state["tasks"][tid]["completed_at"] = datetime.now(timezone.utc).isoformat()

        if blocked is not None:
            # Fail-closed: dừng DAG, không chạy batch kế tiếp.
            _save_state(state)
            summary = _get_status_summary(state)
            return ExecResult(success=False, status=summary, results={}, error=blocked)

        state["last_executed_step"] = f"batch_{iteration}"
        _save_state(state)
        _save_checkpoint_for_state(state)


def _run_task(task_id: str, task_info: dict, runner: Callable[[str, str], Any], max_retries: int, run_id: str) -> Any:
    """T2.7: Chạy một task với idempotency + retry."""
    goal = task_info.get("goal", "")
    attempts = 0
    last_exc: Exception | None = None

    # Idempotency: cùng (run_id, task_id) chỉ thực sự chạy một lần
    def _op():
        return runner(task_id, goal)

    while attempts <= max_retries:
        try:
            return idempotency_module.register(
                f"{run_id}:{task_id}",
                _op,
                run_id=run_id,
            )
        except idempotency_module.IdempotencyLockError as exc:
            # CVE-2026-AHD-003: lock failure = fail CLOSED.
            # KHÔNG retry, KHÔNG đánh dấu task "failed" rồi tiếp tục —
            # phải block toàn bộ execution (caller dừng DAG ngay).
            raise IdempotencyBlockedError(task_id, str(exc)) from exc
        except Exception as exc:
            last_exc = exc
            if not _transient_exception(exc):
                break
            attempts += 1

    raise last_exc or RuntimeError(f"task {task_id} failed after {max_retries} retries")


class IdempotencyBlockedError(RuntimeError):
    """Execution bị BLOCK vì không giữ được idempotency lock (fail-closed).

    Khác task failed: đây là lỗi hạ tầng an toàn — DAG phải dừng, không tiếp tục.
    """

    def __init__(self, task_id: str, detail: str):
        super().__init__(f"idempotency lock failure blocked task '{task_id}': {detail}")
        self.task_id = task_id


# T12 fix: State machine retry/branch cho execute phase
MAX_RETRIES = 2


def _handle_failure(state: dict, task_id: str, error: str) -> str:
    """T12 fix: Xử lý task failure — chuyển sang retry_pending hoặc human_review.

    State transitions:
      failed → retry_pending (nếu retry_count < MAX_RETRIES)
      failed → human_review (nếu retry_count >= MAX_RETRIES)

    Returns next state name.
    """
    task = state.get("tasks", {}).get(task_id, {})
    retry_count = task.get("retry_count", 0)

    if retry_count < MAX_RETRIES:
        task["status"] = "retry_pending"
        task["retry_count"] = retry_count + 1
        task["last_error"] = error
        state["tasks"][task_id] = task
        _save_state(state)
        return "retry_pending"
    else:
        task["status"] = "human_review"
        task["last_error"] = error
        task["retry_count"] = retry_count
        state["tasks"][task_id] = task
        _save_state(state)
        return "human_review"


def _retry_task(state: dict, task_id: str) -> dict:
    """T12 fix: Retry task — chuyển từ retry_pending sang retrying.

    Returns {"retried": bool, "next_status": str}
    """
    task = state.get("tasks", {}).get(task_id, {})
    if task.get("status") != "retry_pending":
        return {"retried": False, "next_status": task.get("status", "unknown")}

    task["status"] = "retrying"
    state["tasks"][task_id] = task
    _save_state(state)
    return {"retried": True, "next_status": "retrying"}


def _branch_task(state: dict, task_id: str, branch_condition: str) -> dict:
    """T12 fix: Branch task — tạo branch task dựa trên condition.

    Pentest V12 fix: thêm counter suffix để đảm bảo branch_id unique
    ngay cả khi cùng condition (tránh collision).

    Returns {"branched": bool, "branch_task_id": str}
    """
    task = state.get("tasks", {}).get(task_id, {})
    # Pentest V12 fix: base branch_id + counter để đảm bảo unique
    base_id = f"{task_id}_branch_{branch_condition[:8]}"
    branch_id = base_id
    counter = 1
    while branch_id in state.get("tasks", {}):
        branch_id = f"{base_id}_{counter}"
        counter += 1

    state["tasks"][branch_id] = {
        "status": "pending",
        "result": None,
        "completed_at": None,
        "branch_of": task_id,
        "branch_condition": branch_condition,
    }
    _save_state(state)
    return {"branched": True, "branch_task_id": branch_id}


def on_node_complete(node_id: str, result: Any, run_id: str | None = None) -> None:
    """T2.7: Callback đánh dấu node hoàn thành và cập nhật DAG."""
    if run_id is None:
        run_id = _current_run_id()
    if not run_id:
        return
    state = _load_state(run_id)
    if state is None:
        return
    if node_id not in state.get("tasks", {}):
        return
    state["tasks"][node_id]["status"] = "complete"
    state["tasks"][node_id]["result"] = result
    state["tasks"][node_id]["completed_at"] = datetime.now(timezone.utc).isoformat()
    _mark_ready(state)
    _save_state(state)
    _save_checkpoint_for_state(state)


def resume(run_id: str, runner: Callable[[str, str], Any] | None = None, max_retries: int = 2) -> ExecResult:
    """T2.7: Resume DAG từ run_id."""
    state = _load_state(run_id)
    if state is None:
        return ExecResult(success=False, status={}, results={}, error=f"no state for run_id {run_id}")
    workflow = _state_to_workflow(state)
    return execute(workflow, checkpoint=state, runner=runner, max_retries=max_retries)


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
        out = get_batch(workflow, args.batch_size)
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
