#!/usr/bin/env python3
"""approval_gate.py — quản lý human approval gate cho implementation plan.

Script này theo dõi trạng thái phê duyệt của một plan qua state file JSON.
Có 4 thao tác:
  --status           : Kiểm tra trạng thái phê duyệt hiện tại
  --approve          : Đánh dấu plan đã được phê duyệt
  --reject           : Đánh dấu plan bị từ chối (kèm lý do)
  --request-changes  : Đánh dấu plan cần sửa đổi (kèm feedback)

State file: .devin/plan_state/<plan_name>.json
Cấu trúc state:
  {plan_file, status: pending|approved|rejected|changes_requested,
   reviewer, date, comments}

Usage:
    python .devin/scripts/approval_gate.py <plan_file.md> --status
    python .devin/scripts/approval_gate.py <plan_file.md> --approve --reviewer "Nguyen Van A"
    python .devin/scripts/approval_gate.py <plan_file.md> --reject --reason "Thiếu test"
    python .devin/scripts/approval_gate.py <plan_file.md> --request-changes --reason "Cần thêm D9"

Exit codes:
    0 = plan đã approved
    1 = pending / rejected / changes_requested
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

# Bước 0: Ép stdout/stderr dùng UTF-8 (tránh lỗi cp1258 trên Windows console với tiếng Việt)
for _stream in (sys.stdout, sys.stderr):
    try:
        _stream.reconfigure(encoding="utf-8")
    except Exception:
        pass

# Các trạng thái hợp lệ
STATUS_PENDING = "pending"
STATUS_APPROVED = "approved"
STATUS_REJECTED = "rejected"
STATUS_CHANGES_REQUESTED = "changes_requested"

VALID_STATUSES = (STATUS_PENDING, STATUS_APPROVED, STATUS_REJECTED, STATUS_CHANGES_REQUESTED)


def _repo_root(plan_path: Path) -> Path:
    """Xác định repo root (thư mục chứa .devin hoặc .git)."""
    for parent in [plan_path.parent, *plan_path.parents]:
        if (parent / ".devin").exists() or (parent / ".git").exists():
            return parent
    return plan_path.parent


def _state_dir(repo_root: Path) -> Path:
    """Trả về thư mục state. Tạo nếu chưa tồn tại."""
    sd = repo_root / ".devin" / "plan_state"
    sd.mkdir(parents=True, exist_ok=True)
    return sd


def _state_path(repo_root: Path, plan_path: Path) -> Path:
    """Trả về đường dẫn state file cho plan."""
    return _state_dir(repo_root) / f"{plan_path.stem}.json"


def _load_state(state_path: Path) -> dict:
    """Đọc state file. Trả state pending mặc định nếu chưa có hoặc JSON lỗi.

    Edge case: file không tồn tại -> pending; JSON hỏng -> pending + cảnh báo.
    """
    if not state_path.exists():
        return {
            "plan_file": "",
            "status": STATUS_PENDING,
            "reviewer": "",
            "date": "",
            "comments": "",
        }
    try:
        data = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError) as e:
        # Edge case: state file hỏng -> trả pending + ghi chú lỗi
        return {
            "plan_file": "",
            "status": STATUS_PENDING,
            "reviewer": "",
            "date": "",
            "comments": f"State file hỏng: {e}",
        }
    # Validate status hợp lệ
    if data.get("status") not in VALID_STATUSES:
        data["status"] = STATUS_PENDING
    return data


def _save_state(state_path: Path, state: dict) -> None:
    """Ghi state file JSON."""
    state_path.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")


def _init_state_if_needed(repo_root: Path, plan_path: Path) -> dict:
    """Khởi tạo state pending nếu chưa có, gắn plan_file. Trả state hiện tại."""
    sp = _state_path(repo_root, plan_path)
    state = _load_state(sp)
    if not state.get("plan_file"):
        state["plan_file"] = str(plan_path.relative_to(repo_root)) if plan_path.exists() else str(plan_path)
        _save_state(sp, state)
    return state


def cmd_status(plan_path: Path) -> dict:
    """--status: Trả trạng thái phê duyệt hiện tại."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy plan file: {plan_path}", "status": STATUS_PENDING}
    root = _repo_root(plan_path)
    state = _init_state_if_needed(root, plan_path)
    return state


def cmd_approve(plan_path: Path, reviewer: str, comments: str) -> dict:
    """--approve: Đánh dấu plan approved."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy plan file: {plan_path}"}
    root = _repo_root(plan_path)
    sp = _state_path(root, plan_path)
    state = {
        "plan_file": str(plan_path.relative_to(root)),
        "status": STATUS_APPROVED,
        "reviewer": reviewer,
        "date": datetime.now(timezone.utc).isoformat(),
        "comments": comments,
    }
    _save_state(sp, state)
    return state


def cmd_reject(plan_path: Path, reviewer: str, reason: str) -> dict:
    """--reject: Đánh dấu plan rejected (kèm lý do)."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy plan file: {plan_path}"}
    root = _repo_root(plan_path)
    sp = _state_path(root, plan_path)
    state = {
        "plan_file": str(plan_path.relative_to(root)),
        "status": STATUS_REJECTED,
        "reviewer": reviewer,
        "date": datetime.now(timezone.utc).isoformat(),
        "comments": reason,
    }
    _save_state(sp, state)
    return state


def cmd_request_changes(plan_path: Path, reviewer: str, feedback: str) -> dict:
    """--request-changes: Đánh dấu plan cần sửa đổi (kèm feedback)."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy plan file: {plan_path}"}
    root = _repo_root(plan_path)
    sp = _state_path(root, plan_path)
    state = {
        "plan_file": str(plan_path.relative_to(root)),
        "status": STATUS_CHANGES_REQUESTED,
        "reviewer": reviewer,
        "date": datetime.now(timezone.utc).isoformat(),
        "comments": feedback,
    }
    _save_state(sp, state)
    return state


def _parse_args(argv: list[str]) -> dict:
    """Parse CLI args thủ công (không dùng argparse để giữ stdlib tối giản).

    Hỗ trợ: --status, --approve, --reject, --request-changes,
            --reviewer <name>, --reason <text>, --comments <text>
    """
    args = {
        "plan_file": "",
        "status": False,
        "approve": False,
        "reject": False,
        "request_changes": False,
        "reviewer": "",
        "reason": "",
        "comments": "",
    }
    i = 0
    # Bước 1: Tìm plan_file (đối số đầu tiên không phải flag)
    positional = []
    while i < len(argv):
        a = argv[i]
        if a in ("--status",):
            args["status"] = True
        elif a in ("--approve",):
            args["approve"] = True
        elif a in ("--reject",):
            args["reject"] = True
        elif a in ("--request-changes", "--request_changes"):
            args["request_changes"] = True
        elif a in ("--reviewer",):
            i += 1
            if i < len(argv):
                args["reviewer"] = argv[i]
        elif a in ("--reason",):
            i += 1
            if i < len(argv):
                args["reason"] = argv[i]
        elif a in ("--comments",):
            i += 1
            if i < len(argv):
                args["comments"] = argv[i]
        elif a.startswith("--"):
            # Flag không nhận dạng -> bỏ qua
            pass
        else:
            positional.append(a)
        i += 1
    if positional:
        args["plan_file"] = positional[0]
    # Bước 2: --reason và --comments dùng chung cho reject/request_changes
    if args["reason"] and not args["comments"]:
        args["comments"] = args["reason"]
    return args


def main() -> int:
    """Entry point CLI. Trả 0 nếu approved, 1 nếu pending/rejected/changes_requested."""
    args = _parse_args(sys.argv[1:])
    if not args["plan_file"]:
        print("Usage: python approval_gate.py <plan_file.md> [--approve|--reject|--request-changes|--status]",
              file=sys.stderr)
        return 2

    plan_path = Path(args["plan_file"]).resolve()

    # Bước 1: Chọn thao tác theo flag
    if args["status"]:
        result = cmd_status(plan_path)
    elif args["approve"]:
        result = cmd_approve(plan_path, args["reviewer"], args["comments"])
    elif args["reject"]:
        result = cmd_reject(plan_path, args["reviewer"], args["comments"])
    elif args["request_changes"]:
        result = cmd_request_changes(plan_path, args["reviewer"], args["comments"])
    else:
        # Mặc định: status
        result = cmd_status(plan_path)

    # Bước 2: In JSON ra stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Bước 3: Exit code dựa trên status
    status = result.get("status", STATUS_PENDING)
    if "error" in result:
        return 1
    return 0 if status == STATUS_APPROVED else 1


if __name__ == "__main__":
    sys.exit(main())
