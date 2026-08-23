#!/usr/bin/env python3
"""dag_cli.py — CLI entry point cho DAG executor.

Tách từ dag_executor.py để giảm kích thước file chính.
"""
from __future__ import annotations

import argparse
import json
import sys
from pathlib import Path
from typing import Any

from dag_state import _load_workflow
from dag_operations import get_batch, get_next
from dag_callbacks import complete_task, fail_task, get_status
from dag_config import DEFAULT_BATCH_SIZE


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