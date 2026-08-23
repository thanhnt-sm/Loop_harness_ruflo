#!/usr/bin/env python3
"""approval_gate.py — Human approval gate cho Solution Design và Implementation Plan.

Hỗ trợ 2 artifact:
  --artifact sd      : Duyệt SOLUTION_DESIGN.md -> state <task_slug>_sd_approved.json
  --artifact plan    : Duyệt IMPLEMENTATION_PLAN.md -> state <task_slug>_approved.json (default)

Thao tác:
  --status           : Kiểm tra trạng thái phê duyệt hiện tại
  --approve          : Đánh dấu artifact đã được phê duyệt
  --reject           : Đánh dấu artifact bị từ chối (kèm lý do)
  --request-changes  : Đánh dấu artifact cần sửa đổi (kèm feedback)
  --interactive      : Present summary + hỏi user approve/reject/modify

State file: .devin/plan_state/<task_slug>[_<artifact>]_approved.json

Usage:
    python .devin/scripts/approval_gate.py <plan_file.md> --status [--artifact sd|plan]
    python .devin/scripts/approval_gate.py <plan_file.md> --approve --artifact plan
    python .devin/scripts/approval_gate.py <sdd_file.md> --approve --artifact sd
    python .devin/scripts/approval_gate.py <plan_file.md> --approve --signature <base64_ed25519> --reviewer <name>
    python .devin/scripts/approval_gate.py <plan_file.md> --reject --reason "Thiếu test"
    python .devin/scripts/approval_gate.py <plan_file.md> --request-changes --reason "Cần thêm D9"
    python .devin/scripts/approval_gate.py <plan_file.md> --interactive --quality-report <qr.md> --artifact plan
    python .devin/scripts/approval_gate.py <sdd_file.md> --interactive --artifact sd

Exit codes:
    0 = approved
    1 = pending / rejected / changes_requested
"""
from __future__ import annotations

import json
import sys
from pathlib import Path

# Initialize UTF-8 for Windows console
from approval_gate_constants import (
    _ensure_utf8,
    EXIT_APPROVED,
    EXIT_PENDING_OR_REJECTED,
    EXIT_USAGE_ERROR,
    STATUS_APPROVED,
    STATUS_PENDING,
    STATUS_REJECTED,
    STATUS_CHANGES_REQUESTED,
    ARTIFACT_PLAN,
    ARTIFACT_SD,
    VALID_STATUSES,
)
from approval_gate_args import _parse_args
from approval_gate_commands import (
    cmd_status,
    cmd_approve,
    cmd_reject,
    cmd_request_changes,
    _write_approval_state,
)
from approval_gate_interactive import cmd_interactive
from approval_gate_summary import _parse_plan_summary, _parse_quality_report
from approval_gate_state import (
    _repo_root,
    _state_dir,
    _plan_state_name,
    _state_path,
    _load_state,
    _save_state,
    _init_state_if_needed,
)
from approval_gate_crypto import (
    plan_hash,
    load_reviewer_keys,
    signature_required,
    verify_signature,
    _sig_message,
    CRYPTO_AVAILABLE,
)
from approval_gate_archive import _sha256_chunked, _plan_file_hashes, _archive_approved_plan
from approval_gate_audit import _append_approval_audit


def main() -> int:
    """Entry point CLI. Trả 0 nếu approved, 1 nếu pending/rejected/changes_requested."""
    _ensure_utf8()
    args = _parse_args(sys.argv[1:])
    if not args["plan_file"]:
        print("Usage: python approval_gate.py <plan_file.md> [--approve|--reject|--request-changes|--status] [--artifact sd|plan]",
              file=sys.stderr)
        return EXIT_USAGE_ERROR

    plan_path = Path(args["plan_file"]).resolve()

    # Bước 1: Chọn thao tác theo flag
    artifact = args.get("artifact", "plan")
    if args["status"]:
        result = cmd_status(plan_path, artifact)
    elif args["approve"]:
        result = cmd_approve(plan_path, args["reviewer"], args["comments"], artifact, signature=args["signature"], signed_ts=args["date"])
    elif args["reject"]:
        result = cmd_reject(plan_path, args["reviewer"], args["comments"], artifact)
    elif args["request_changes"]:
        result = cmd_request_changes(plan_path, args["reviewer"], args["comments"], artifact)
    elif args["interactive"]:
        result = cmd_interactive(
            plan_path,
            args["reviewer"] or "human",
            args["quality_report"],
            artifact,
        )
    else:
        # Mặc định: status
        result = cmd_status(plan_path, artifact)

    # Bước 2: In JSON ra stdout
    print(json.dumps(result, ensure_ascii=False, indent=2))

    # Bước 3: Exit code dựa trên status
    status = result.get("status", STATUS_APPROVED)  # default to pending-like
    if "error" in result:
        return EXIT_PENDING_OR_REJECTED
    return EXIT_APPROVED if status == STATUS_APPROVED else EXIT_PENDING_OR_REJECTED


if __name__ == "__main__":
    sys.exit(main())