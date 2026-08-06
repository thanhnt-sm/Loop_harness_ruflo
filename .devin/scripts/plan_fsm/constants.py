#!/usr/bin/env python3
"""Constants cho Plan Phase FSM: trạng thái, action, giới hạn vòng lặp."""
from __future__ import annotations

# ---------------------------------------------------------------------------
# FSM states
# ---------------------------------------------------------------------------
STATE_INIT = "INIT"
STATE_CLASSIFY = "CLASSIFY"
STATE_ANALYZE = "ANALYZE"
STATE_DESIGN = "DESIGN"
STATE_REVIEW = "REVIEW"
STATE_REVISION = "REVISION"
STATE_SDD_APPROVAL = "SDD_APPROVAL"
STATE_PLAN = "PLAN"
STATE_QC = "QC"
STATE_PLAN_APPROVAL = "PLAN_APPROVAL"
STATE_WRITE_STATE = "WRITE_STATE"
STATE_DONE = "DONE"
STATE_REJECTED = "REJECTED"
STATE_ESCALATE = "ESCALATE"

# ---------------------------------------------------------------------------
# Action types
# ---------------------------------------------------------------------------
ACTION_DISPATCH_SCOUTS = "dispatch_scouts"
ACTION_WAIT_SCOUTS = "wait_scouts"
ACTION_DISPATCH_ARCHITECT = "dispatch_architect"
ACTION_DISPATCH_REVIEWERS = "dispatch_reviewers"
ACTION_DISPATCH_REVISION = "dispatch_revision"
ACTION_PRESENT_SDD_APPROVAL = "present_sdd_approval"
ACTION_DECOMPOSE_PLAN = "decompose_plan"
ACTION_RUN_QC = "run_qc"
ACTION_PRESENT_PLAN_APPROVAL = "present_plan_approval"
ACTION_WRITE_PLAN_STATE = "write_plan_state"
ACTION_DONE = "done"
ACTION_SKIP = "skip"
ACTION_ESCALATE = "escalate"

# ---------------------------------------------------------------------------
# Limits
# ---------------------------------------------------------------------------
NUM_SCOUTS = 5
NUM_REVIEWERS = 3
MAX_REVISION_ROUNDS = 3
MAX_QC_ROUNDS = 3

# ---------------------------------------------------------------------------
# Helper mapping
# ---------------------------------------------------------------------------
# State -> human-readable phase name (dùng cho log/report)
STATE_PHASE: dict[str, str] = {
    STATE_INIT: "Khởi tạo",
    STATE_CLASSIFY: "Phân loại tier",
    STATE_ANALYZE: "Phân tích",
    STATE_DESIGN: "Thiết kế giải pháp",
    STATE_REVIEW: "Review đối kháng",
    STATE_REVISION: "Sửa SDD",
    STATE_SDD_APPROVAL: "Duyệt tài liệu giải pháp",
    STATE_PLAN: "Lập kế hoạch triển khai",
    STATE_QC: "Kiểm tra chất lượng plan",
    STATE_PLAN_APPROVAL: "Duyệt kế hoạch triển khai",
    STATE_WRITE_STATE: "Ghi plan state",
    STATE_DONE: "Hoàn thành",
    STATE_REJECTED: "Bị từ chối",
    STATE_ESCALATE: "Chuyển lên human",
}
