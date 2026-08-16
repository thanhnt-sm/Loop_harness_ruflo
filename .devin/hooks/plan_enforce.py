#!/usr/bin/env python3
"""
Hook: plan_enforce.py — Plan Phase Enforcement (PreToolUse)

Kiểm tra: agent có đang cố write/edit file mà chưa có approved plan cho task hiện tại không?
Nếu task M-tier+ và chưa có approved plan cho task hiện tại → BLOCK.

Logic:
1. Đọc session_state để xác định current task (goal hoặc task field)
2. Từ task description, tính task_slug
3. Kiểm tra orchestrator state cho task_slug: nếu state=DONE và approval_status=approved → có approved plan
   (V5-02: state phải thuộc đúng task — khớp task_description HOẶC task_fingerprint; slug-collision → block)
4. Phân loại tier: nếu S-tier → allow
5. Nếu M-tier+ và file không thuộc docs/plans/ → BLOCK nếu chưa có approved plan cho task hiện tại
6. Nếu file thuộc docs/plans/ hoặc docs/templates/ → allow (cho phép viết plan)

Fail-closed: nếu không xác định được tier → default M → require plan.
Fail-closed: nếu hook input parse error → BLOCK (không fail-open).
"""

from __future__ import annotations
import hashlib
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime

# Import ahd_session để lấy đường dẫn session_state cụ thể theo session_id.
sys.path.insert(0, str(Path(__file__).resolve().parent))
import ahd_session  # noqa: E402


def _repo_root() -> Path:
    """Tìm repo root — đi lên cho đến khi thấy .devin/"""
    p = Path.cwd()
    for parent in [p] + list(p.parents):
        if (parent / ".devin").is_dir():
            return parent
    return p


def _get_session_state(root: Path, session_id: str = "") -> dict:
    """Đọc session state cụ thể theo session_id — STRICT binding (CVE-2026-AHD-001).

    Security contract (fail closed):
    1. Nếu session_id rỗng/không xác định → trả {} (KHÔNG fallback "newest file").
       Fallback newest-file gây session confusion khi chạy nhiều session song song:
       session B có thể thừa hưởng approved plan của session A.
    2. Nếu session_id có nhưng state file không tồn tại → trả {} (không thừa hưởng).
    3. Nếu state file lỗi (JSON hỏng) → trả {} (fail closed, không fallback).
    4. Ownership check: session_id trong state phải khớp session_id yêu cầu;
       nếu state có session_nonce nhưng thiếu/sai → trả {} (state bị tráo/copy).
    """
    if not session_id:
        return {}
    state_path = ahd_session.get_session_state_path(session_id, root)
    if not state_path.exists():
        return {}
    try:
        state = json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}
    if not isinstance(state, dict):
        return {}
    # Ownership verification: session_id trong state phải khớp chính xác.
    state_sid = state.get("session_id", "")
    if state_sid and state_sid != ahd_session.slugify_session_id(session_id):
        return {}
    # Cryptographic nonce binding: nếu state đã có nonce, bắt buộc khớp env nonce.
    stored_nonce = state.get("session_nonce", "")
    env_nonce = os.environ.get("AHD_SESSION_NONCE", "")
    if stored_nonce and env_nonce and stored_nonce != env_nonce:
        return {}
    return state


def _slugify(text: str) -> str:
    """Tạo task slug — giống logic trong plan_orchestrator.py"""
    if not text:
        return ""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] if slug else ""


def _fingerprint(task_description: str) -> str:
    """SHA-256 fingerprint của task description — khớp logic trong storage.fingerprint.

    V5-02: slug mất thông tin (truncate 60 + strip non-word) → 2 task khác nhau có
    thể trùng slug. Fingerprint giữ toàn bộ thông tin (chỉ chuẩn hóa khoảng trắng)
    → phát hiện slug-collision tại enforcement.
    """
    if not task_description:
        return ""
    norm = re.sub(r"\s+", " ", task_description.strip())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


def _plan_state_name_from_path(plan_path: str) -> str:
    """
    Tạo tên state file duy nhất cho plan — phải khớp với logic trong approval_gate.py.
    Nếu plan nằm trong docs/plans/<task_slug>/ → dùng <task_slug>_approved.json.
    Fallback: dùng stem.
    """
    if not plan_path:
        return ""
    p = Path(plan_path)
    parts = p.parts
    if "docs" in parts and "plans" in parts:
        try:
            idx = parts.index("plans")
            if idx + 1 < len(parts):
                return f"{parts[idx + 1]}_approved"
        except ValueError:
            pass
    return p.stem


def _get_plan_state_for_task(root: Path, task_slug: str, task_fp: str = "", task_desc: str = "") -> dict:
    """
    Đọc plan state cho task cụ thể thông qua orchestrator state.

    1. Load orchestrator state: .devin/plan_state/<task_slug>_orchestrator.json
    2. BINDING CHECK (V5-02): state phải thuộc task hiện tại —
       - task_description trong state khớp chính xác task_desc → OK (mạnh nhất)
       - HOẶC task_fingerprint trong state == fingerprint(task_desc) → OK (dung sai khoảng trắng)
       - Ngược lại → trả {} (slug-collision: state của task khác, KHÔNG được dùng)
    3. Nếu state=DONE và approval_status=approved → lấy plan_path
    4. Load approval state cho plan_path (dùng task_slug_approved.json nếu trong docs/plans/<task_slug>)
    5. Trả về approved state nếu tồn tại

    KHÔNG tìm bất kỳ approved plan nào — chỉ dùng plan của task hiện tại.
    """
    if not task_slug:
        return {}
    orchestrator_path = root / ".devin" / "plan_state" / f"{task_slug}_orchestrator.json"
    if not orchestrator_path.exists():
        return {}
    try:
        orch_state = json.loads(orchestrator_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}

    # V5-02 binding check: state phải thuộc đúng task này (chống slug-collision).
    stored_desc = orch_state.get("task_description", "")
    stored_fp = orch_state.get("task_fingerprint", "")
    if stored_desc:
        # State mang task_description: khớp chính xác HOẶC fingerprint (dung sai khoảng trắng).
        if stored_desc != task_desc and (
            not stored_fp or _fingerprint(task_desc) != stored_fp
        ):
            return {}
    elif stored_fp:
        if _fingerprint(task_desc) != stored_fp:
            return {}
    else:
        # Legacy state (pre-V5-02, không metadata): bind bằng slug — hành vi cũ.
        print(
            "[plan_enforce] WARNING: orchestrator state không có task_description/"
            "task_fingerprint (legacy) — bind bằng task_slug.",
            file=sys.stderr,
        )

    # Chỉ cho phép nếu orchestrator state = DONE và approval_status=approved
    if orch_state.get("state") != "DONE":
        return {}
    if orch_state.get("approval_status") != "approved":
        return {}

    plan_path = orch_state.get("plan_path", "")
    if not plan_path:
        return {}

    # Load approval state tương ứng (dùng task_slug_approved.json nếu trong docs/plans/<task_slug>)
    state_name = _plan_state_name_from_path(plan_path)
    state_file = root / ".devin" / "plan_state" / f"{state_name}.json"
    if not state_file.exists():
        return {}
    try:
        return json.loads(state_file.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _classify_tier(task_description: str, session_state: dict) -> str:
    """
    Phân loại task tier dựa trên description và session state.
    Default: M (require plan). Chỉ S nếu rõ ràng trivial.
    """
    if not task_description:
        return "M"  # Fail-closed: default M
    desc_lower = task_description.lower().strip()
    # S-tier indicators: chỉ dựa trên từ khóa rõ ràng, KHÔNG dùng độ dài.
    # Pentest fix: mô tả ngắn kết hợp keyword có thể bypass plan cho task nhạy cảm.
    s_keywords = ("typo", "rename", "update date", "fix spelling",
                  "s-tier", "trivial", "one line", "1 line")
    # destructive keyword -> bắt buộc tối thiểu M (không cho phép tự động S)
    destructive_keywords = ("rm -rf", "drop", "delete", "force_push", "force-push")
    if any(kw in desc_lower for kw in destructive_keywords):
        return "M"
    s_indicators = [
        any(kw in desc_lower for kw in s_keywords),
    ]
    # Nếu session state có complexity field (single source of truth)
    complexity = session_state.get("complexity", "")
    if complexity in ("S", "s"):
        return "S"
    if complexity in ("M", "L", "XL"):
        return complexity
    # Nếu có S keyword rõ ràng -> S
    if sum(s_indicators) >= 1:
        return "S"
    # Default: M (fail-closed)
    return "M"


def _is_plan_file(file_path: str, root: Path) -> bool:
    """Kiểm tra: file có thuộc docs/plans/ không? (cho phép viết plan)"""
    if not file_path:
        return False
    p = (root / file_path).resolve()
    try:
        rel = p.relative_to(root.resolve())
    except ValueError:
        return False
    norm = str(rel).replace("\\", "/")
    return norm.startswith("docs/plans/")


def _is_template_file(file_path: str, root: Path) -> bool:
    """Kiểm tra: file có thuộc docs/templates/ không?"""
    if not file_path:
        return False
    p = (root / file_path).resolve()
    try:
        rel = p.relative_to(root.resolve())
    except ValueError:
        return False
    norm = str(rel).replace("\\", "/")
    return norm.startswith("docs/templates/")


def _extract_file_path(tool_input: dict) -> str | None:
    """Trích file path từ tool input — chỉ kiểm tra key chuẩn."""
    if not tool_input:
        return None
    # Các key chuẩn cho write/edit/notebook_edit tools
    for key in ("file_path", "path", "notebook_path", "filename", "file", "target", "destination"):
        if key in tool_input:
            val = tool_input[key]
            if isinstance(val, (str, os.PathLike)):
                return str(val)
    return None


def main():
    """Entry point — đọc hook input từ stdin, output JSON"""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError) as e:
        # Không parse được → BLOCK (fail-closed)
        print(json.dumps({"allow": False, "reason": f"PLAN ENFORCEMENT: hook input parse error, fail-closed: {e}", "enforcement": "hook_error"}))
        sys.exit(1)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})
    session_id = hook_input.get("session_id", "")

    # Chỉ enforce cho Write/Edit — hỗ trợ cả chữ hoa/thường và các biến thể.
    # Pentest fix: Claude/Devin gửi tool_name dạng "Write"/"Edit"; so sánh lower-case.
    write_tools = {"write", "edit", "notebook_edit", "write_file", "edit_file"}
    if tool_name.lower() not in write_tools:
        print(json.dumps({"allow": True, "reason": "not a write tool"}))
        sys.exit(0)

    root = _repo_root()
    # CVE-2026-AHD-001: session_id BẮT BUỘC cho write tools (fail closed).
    # Thiếu session_id → không thể xác định ownership → không allow write.
    if not session_id:
        block_reason = (
            "PLAN ENFORCEMENT: session_id missing. Strict session binding "
            "requires a valid session_id (CVE-2026-AHD-001). Rejecting to "
            "prevent session confusion."
        )
        print(json.dumps({"allow": False, "reason": block_reason, "enforcement": "session_id_required"}))
        sys.exit(1)

    session_state = _get_session_state(root, session_id)
    task_desc = session_state.get("goal", "") or hook_input.get("task", "")
    task_slug = _slugify(task_desc)
    tier = _classify_tier(task_desc, session_state)

    # S-tier → allow (no plan needed)
    if tier == "S":
        print(json.dumps({"allow": True, "reason": "S-tier task, plan not required"}))
        sys.exit(0)

    # M-tier+ → require approved plan cho task hiện tại
    file_path = _extract_file_path(tool_input)
    if file_path:
        # Cho phép viết plan files + templates
        if _is_plan_file(file_path, root) or _is_template_file(file_path, root):
            print(json.dumps({"allow": True, "reason": "writing plan/template file"}))
            sys.exit(0)

    # Kiểm tra: task hiện tại có approved plan không?
    plan_state = _get_plan_state_for_task(root, task_slug, _fingerprint(task_desc), task_desc)
    if plan_state.get("status") == "approved":
        print(json.dumps({"allow": True, "reason": f"plan approved: {plan_state.get('plan_file', 'unknown')}"}))
        sys.exit(0)

    # KHÔNG có approved plan + M-tier+ + đang cố write code → BLOCK
    block_reason = (
        f"PLAN ENFORCEMENT: Task tier={tier} requires approved plan before execution. "
        f"No approved plan found for task '{task_desc}'. Run /plan or /full-power first. "
        f"Plan phase is MANDATORY for M-tier+ tasks. "
        f"To override: classify as S-tier or get plan approved via approval_gate.py."
    )
    print(json.dumps({"allow": False, "reason": block_reason, "enforcement": "plan_required"}))
    sys.exit(1)


if __name__ == "__main__":
    main()
