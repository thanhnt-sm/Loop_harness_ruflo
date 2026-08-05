#!/usr/bin/env python3
"""approval_gate.py — quản lý human approval gate cho implementation plan.

Script này theo dõi trạng thái phê duyệt của một plan qua state file JSON.
Có 5 thao tác:
  --status           : Kiểm tra trạng thái phê duyệt hiện tại
  --approve          : Đánh dấu plan đã được phê duyệt
  --reject           : Đánh dấu plan bị từ chối (kèm lý do)
  --request-changes  : Đánh dấu plan cần sửa đổi (kèm feedback)
  --interactive      : Present plan summary + hỏi user approve/reject (interactive mode)

State file: .devin/plan_state/<plan_name>.json
Cấu trúc state:
  {plan_file, status: pending|approved|rejected|changes_requested,
   reviewer, date, comments}

Usage:
    python .devin/scripts/approval_gate.py <plan_file.md> --status
    python .devin/scripts/approval_gate.py <plan_file.md> --approve --reviewer "Nguyen Van A"
    python .devin/scripts/approval_gate.py <plan_file.md> --reject --reason "Thiếu test"
    python .devin/scripts/approval_gate.py <plan_file.md> --request-changes --reason "Cần thêm D9"
    python .devin/scripts/approval_gate.py <plan_file.md> --interactive
    python .devin/scripts/approval_gate.py <plan_file.md> --interactive --quality-report <qr.md>

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


def _plan_state_name(plan_path: Path) -> str:
    """
    Tạo tên state file duy nhất cho plan.

    Nếu plan nằm trong docs/plans/<task_slug>/ → dùng <task_slug>_approved.json
    để tránh conflict giữa các plan có cùng stem (ví dụ: IMPLEMENTATION_PLAN.md).
    Fallback: dùng plan_path.stem.
    """
    parts = plan_path.parts
    if "docs" in parts and "plans" in parts:
        # Tìm thư mục con ngay sau docs/plans/ — đó là task_slug
        try:
            idx = parts.index("plans")
            if idx + 1 < len(parts):
                task_slug = parts[idx + 1]
                return f"{task_slug}_approved"
        except ValueError:
            pass
    return plan_path.stem


def _state_path(repo_root: Path, plan_path: Path) -> Path:
    """Trả về đường dẫn state file cho plan."""
    return _state_dir(repo_root) / f"{_plan_state_name(plan_path)}.json"


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


def _parse_plan_summary(plan_path: Path) -> dict:
    """Trích tóm tắt plan từ Markdown file — dùng cho interactive mode."""
    try:
        text = plan_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    summary = {
        "feature": "",
        "complexity": "",
        "risk_tier": "",
        "files_count": 0,
        "requirements_count": 0,
        "tasks_count": 0,
    }
    # Trích Metadata table
    import re
    # Risk Tier — match cả [FILL IN: R2] và giá trị thực R2/P0/P1/P2/P3
    m = re.search(r"Risk Tier.*?\|\s*`?\*?\*?\s*(?:\[FILL IN:\s*)?([A-Za-z]\d+)\s*\]?\*?`?\s*\|", text, re.IGNORECASE)
    if m:
        summary["risk_tier"] = m.group(1).strip()
    elif "[FILL IN:" in text and "Risk Tier" in text:
        m2 = re.search(r"Risk Tier.*?\[FILL IN:\s*(.*?)\]", text, re.IGNORECASE)
        if m2:
            summary["risk_tier"] = m2.group(1).strip()
    # Đếm task IDs (T1.1, T1.2, T2.1, v.v.)
    task_ids = re.findall(r"\bT\d+\.\d+\b", text)
    summary["tasks_count"] = len(set(task_ids))
    # Đếm REQ IDs
    req_ids = re.findall(r"\bREQ-\d+\b", text)
    summary["requirements_count"] = len(set(req_ids))
    # Đếm file paths (đường dẫn có / hoặc \)
    file_paths = re.findall(r"`([^`]*[/\\][^`]*)`", text)
    summary["files_count"] = len(set(file_paths))
    # Feature = tên file (fallback)
    summary["feature"] = plan_path.stem.replace("IMPLEMENTATION_PLAN_", "").replace("_", " ")
    return summary


def _parse_quality_report(qr_path: Path) -> dict:
    """Trích tóm tắt quality report từ Markdown file."""
    if not qr_path or not qr_path.exists():
        return {}
    try:
        text = qr_path.read_text(encoding="utf-8")
    except OSError:
        return {}
    import re
    result = {"scorecard": "", "passed": 0, "failed": 0, "all_pass": False}
    # Overall PASS/FAIL
    if "**Overall**: **PASS**" in text or "**Overall**: PASS" in text:
        result["all_pass"] = True
    # Đếm PASS/FAIL trong table
    passes = len(re.findall(r"\|\s*PASS\s*\|", text))
    fails = len(re.findall(r"\|\s*FAIL\s*\|", text))
    result["passed"] = passes
    result["failed"] = fails
    result["scorecard"] = f"{passes} PASS, {fails} FAIL"
    return result


def cmd_interactive(plan_path: Path, reviewer: str, quality_report_path: str = "") -> dict:
    """--interactive: Present plan summary + hỏi user approve/reject/modify."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy plan file: {plan_path}"}

    root = _repo_root(plan_path)
    summary = _parse_plan_summary(plan_path)
    qr_summary = {}
    if quality_report_path:
        qr_path = Path(quality_report_path).resolve()
        qr_summary = _parse_quality_report(qr_path)

    # Bước 1: Present plan summary
    print("\n" + "=" * 60)
    print("  PLAN APPROVAL GATE — Human Review Required")
    print("=" * 60)
    print()
    print("## Plan Summary")
    print(f"  Feature:           {summary.get('feature', 'N/A')}")
    print(f"  Risk Tier:         {summary.get('risk_tier', 'N/A')}")
    print(f"  Tasks:             {summary.get('tasks_count', 0)}")
    print(f"  Requirements:      {summary.get('requirements_count', 0)}")
    print(f"  Files to change:   {summary.get('files_count', 0)}")
    if qr_summary:
        print(f"  Quality scorecard: {qr_summary.get('scorecard', 'N/A')}")
        print(f"  Overall:           {'PASS' if qr_summary.get('all_pass') else 'FAIL'}")
    print()
    print(f"  Plan file:         {plan_path}")
    if quality_report_path:
        print(f"  Quality report:    {quality_report_path}")
    print()
    print("-" * 60)
    print("  Options:")
    print("    [y]     Approve — proceed to execute")
    print("    [n]     Reject — stop, do not execute")
    print("    [m]     Approve with modifications — specify changes")
    print("    [i]     Request more information")
    print("-" * 60)

    # Bước 2: Hỏi user
    try:
        response = input("\n  Decision [y/n/m/i]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        print("\n  [Aborted by user]")
        return {"status": STATUS_PENDING, "reason": "User aborted"}

    # Bước 3: Xử lý response
    if response == "y":
        state = cmd_approve(plan_path, reviewer, "Approved via interactive mode")
        print(f"\n  [APPROVED] Plan state written: {plan_path.stem}.json")
        return state
    elif response == "n":
        try:
            reason = input("  Reason for rejection (optional): ").strip()
        except (EOFError, KeyboardInterrupt):
            reason = "Rejected via interactive mode"
        state = cmd_reject(plan_path, reviewer, reason or "Rejected via interactive mode")
        print(f"\n  [REJECTED] Reason: {reason}")
        return state
    elif response == "m":
        try:
            modifications = input("  Specify modifications needed: ").strip()
        except (EOFError, KeyboardInterrupt):
            modifications = "Modifications requested via interactive mode"
        state = cmd_request_changes(plan_path, reviewer, modifications)
        print(f"\n  [CHANGES REQUESTED] {modifications}")
        return state
    elif response == "i":
        try:
            question = input("  What information do you need? ").strip()
        except (EOFError, KeyboardInterrupt):
            question = "Information requested"
        print(f"\n  [INFO REQUESTED] {question}")
        return {"status": STATUS_PENDING, "reason": f"Info requested: {question}"}
    else:
        print(f"\n  [INVALID] Response '{response}' not recognized. Use y/n/m/i.")
        return {"status": STATUS_PENDING, "reason": f"Invalid response: {response}"}


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
        "interactive": False,
        "reviewer": "",
        "reason": "",
        "comments": "",
        "quality_report": "",
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
        elif a in ("--interactive",):
            args["interactive"] = True
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
        elif a in ("--quality-report", "--quality_report"):
            i += 1
            if i < len(argv):
                args["quality_report"] = argv[i]
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
    elif args["interactive"]:
        result = cmd_interactive(
            plan_path,
            args["reviewer"] or "human",
            args["quality_report"],
        )
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
