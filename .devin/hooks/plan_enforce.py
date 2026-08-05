#!/usr/bin/env python3
"""
Hook: plan_enforce.py — Plan Phase Enforcement (PreToolUse)

Kiểm tra: agent có đang cố write/edit file mà chưa có approved plan cho task hiện tại không?
Nếu task M-tier+ và chưa có approved plan cho task hiện tại → BLOCK.

Logic:
1. Đọc session_state để xác định current task (goal hoặc task field)
2. Từ task description, tính task_slug
3. Kiểm tra orchestrator state cho task_slug: nếu state=DONE và approval_status=approved → có approved plan
4. Phân loại tier: nếu S-tier → allow
5. Nếu M-tier+ và file không thuộc docs/plans/ → BLOCK nếu chưa có approved plan cho task hiện tại
6. Nếu file thuộc docs/plans/ hoặc docs/templates/ → allow (cho phép viết plan)

Fail-closed: nếu không xác định được tier → default M → require plan.
Fail-closed: nếu hook input parse error → BLOCK (không fail-open).
"""

from __future__ import annotations
import json
import os
import sys
import re
from pathlib import Path
from datetime import datetime


def _repo_root() -> Path:
    """Tìm repo root — đi lên cho đến khi thấy .devin/"""
    p = Path.cwd()
    for parent in [p] + list(p.parents):
        if (parent / ".devin").is_dir():
            return parent
    return p


def _get_session_state(root: Path) -> dict:
    """Đọc session state mới nhất"""
    state_dir = root / ".devin" / "session_state"
    if not state_dir.exists():
        return {}
    states = sorted(state_dir.glob("*.json"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not states:
        return {}
    try:
        return json.loads(states[0].read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _slugify(text: str) -> str:
    """Tạo task slug — giống logic trong plan_orchestrator.py"""
    if not text:
        return ""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] if slug else ""


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


def _get_plan_state_for_task(root: Path, task_slug: str) -> dict:
    """
    Đọc plan state cho task cụ thể thông qua orchestrator state.

    1. Load orchestrator state: .devin/plan_state/<task_slug>_orchestrator.json
    2. Nếu state=DONE và approval_status=approved → lấy plan_path
    3. Load approval state cho plan_path (dùng task_slug_approved.json nếu trong docs/plans/<task_slug>)
    4. Trả về approved state nếu tồn tại

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
    # S-tier indicators: rất ngắn, 1 file, no verification
    s_indicators = [
        len(desc_lower) < 50,  # Very short description
        any(kw in desc_lower for kw in ["typo", "rename", "update date", "fix spelling"]),
        any(kw in desc_lower for kw in ["s-tier", "trivial", "one line", "1 line"]),
    ]
    # Nếu session state có complexity field
    complexity = session_state.get("complexity", "")
    if complexity in ("S", "s"):
        return "S"
    if complexity in ("M", "L", "XL"):
        return complexity
    # Nếu có S indicators rõ ràng
    if sum(s_indicators) >= 2:
        return "S"
    # Default: M (fail-closed)
    return "M"


def _is_plan_file(file_path: str) -> bool:
    """Kiểm tra: file có thuộc docs/plans/ không? (cho phép viết plan)"""
    if not file_path:
        return False
    p = Path(file_path)
    return "docs" in p.parts and "plans" in p.parts


def _is_template_file(file_path: str) -> bool:
    """Kiểm tra: file có thuộc docs/templates/ không?"""
    if not file_path:
        return False
    p = Path(file_path)
    return "docs" in p.parts and "templates" in p.parts


def _extract_file_path(tool_input: dict) -> str | None:
    """Trích file path từ tool input — kiểm tra nhiều key phổ biến."""
    if not tool_input:
        return None
    # Các key phổ biến cho write/edit tools
    for key in ("file_path", "path", "filename", "file", "target", "destination"):
        if key in tool_input:
            val = tool_input[key]
            if isinstance(val, (str, os.PathLike)):
                return str(val)
    # Fallback: tìm string chứa dấu / hoặc \ trong nested dict
    def _find_path(obj):
        if isinstance(obj, str) and ("/" in obj or "\\" in obj):
            # Ưu tiên các đường dẫn source / docs / tests
            if any(obj.startswith(p) for p in ("src/", "tests/", ".devin/", "docs/", "HLK/")):
                return obj
            # Nếu kết thúc bằng extension phổ biến → cũng coi là file path
            if any(obj.endswith(ext) for ext in (".py", ".js", ".ts", ".md", ".json", ".yml", ".yaml", ".toml")):
                return obj
        if isinstance(obj, dict):
            for v in obj.values():
                found = _find_path(v)
                if found:
                    return found
        return None
    return _find_path(tool_input)


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

    # Chỉ enforce cho Write/Edit — không enforce cho read/grep/glob/exec
    if tool_name not in ("write", "edit", "notebook_edit"):
        print(json.dumps({"allow": True, "reason": "not a write tool"}))
        sys.exit(0)

    root = _repo_root()
    session_state = _get_session_state(root)
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
        if _is_plan_file(file_path) or _is_template_file(file_path):
            print(json.dumps({"allow": True, "reason": "writing plan/template file"}))
            sys.exit(0)

    # Kiểm tra: task hiện tại có approved plan không?
    plan_state = _get_plan_state_for_task(root, task_slug)
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
