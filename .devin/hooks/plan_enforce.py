#!/usr/bin/env python3
"""
Hook: plan_enforce.py — Plan Phase Enforcement (PreToolUse)

Kiểm tra: agent có đang cố execute (Write/Edit) mà chưa có approved plan không?
Nếu task M-tier+ và chưa có approved plan → BLOCK.

Logic:
1. Đọc session_state để xác định current task tier
2. Nếu M-tier+ → kiểm tra plan_state có approved plan không
3. Nếu chưa approved → BLOCK Write/Edit (trừ docs/plans/ — cho phép viết plan)
4. Nếu S-tier hoặc đã approved → allow

Fail-closed: nếu không xác định được tier → default M → require plan.
"""

from __future__ import annotations
import json
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


def _get_plan_state(root: Path, plan_name: str | None = None) -> dict:
    """Đọc plan state — kiểm tra approval status"""
    plan_dir = root / ".devin" / "plan_state"
    if not plan_dir.exists():
        return {}
    if plan_name:
        state_file = plan_dir / f"{plan_name}.json"
        if state_file.exists():
            try:
                return json.loads(state_file.read_text(encoding="utf-8"))
            except (json.JSONDecodeError, OSError):
                return {}
    # Tìm plan approved mới nhất
    approved_plans = []
    for f in plan_dir.glob("*.json"):
        if f.name.endswith("_coverage.json") or f.name.endswith("_workflow.json"):
            continue
        try:
            state = json.loads(f.read_text(encoding="utf-8"))
            if state.get("status") == "approved":
                approved_plans.append((f, state))
        except (json.JSONDecodeError, OSError):
            continue
    if approved_plans:
        approved_plans.sort(key=lambda x: x[1].get("date", ""), reverse=True)
        return approved_plans[0][1]
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
    """Trích file path từ tool input"""
    if not tool_input:
        return None
    for key in ("file_path", "path", "filename", "file"):
        if key in tool_input:
            return str(tool_input[key])
    return None


def main():
    """Entry point — đọc hook input từ stdin, output JSON"""
    try:
        hook_input = json.load(sys.stdin)
    except (json.JSONDecodeError, OSError):
        # Không parse được → allow (don't block on hook errors)
        print(json.dumps({"allow": True, "reason": "hook input parse error, fail-open"}))
        sys.exit(0)

    tool_name = hook_input.get("tool_name", "")
    tool_input = hook_input.get("tool_input", {})

    # Chỉ enforce cho Write/Edit — không enforce cho read/grep/glob/exec
    if tool_name not in ("write", "edit", "notebook_edit"):
        print(json.dumps({"allow": True, "reason": "not a write tool"}))
        sys.exit(0)

    root = _repo_root()
    session_state = _get_session_state(root)
    task_desc = session_state.get("goal", "") or hook_input.get("task", "")
    tier = _classify_tier(task_desc, session_state)

    # S-tier → allow (no plan needed)
    if tier == "S":
        print(json.dumps({"allow": True, "reason": "S-tier task, plan not required"}))
        sys.exit(0)

    # M-tier+ → require approved plan
    file_path = _extract_file_path(tool_input)
    if file_path:
        # Cho phép viết plan files + templates
        if _is_plan_file(file_path) or _is_template_file(file_path):
            print(json.dumps({"allow": True, "reason": "writing plan/template file"}))
            sys.exit(0)

    # Kiểm tra: có approved plan không?
    plan_state = _get_plan_state(root)
    if plan_state.get("status") == "approved":
        print(json.dumps({"allow": True, "reason": f"plan approved: {plan_state.get('plan_file', 'unknown')}"}))
        sys.exit(0)

    # KHÔNG có approved plan + M-tier+ + đang cố write code → BLOCK
    block_reason = (
        f"PLAN ENFORCEMENT: Task tier={tier} requires approved plan before execution. "
        f"No approved plan found. Run /plan or /full-power first. "
        f"Plan phase is MANDATORY for M-tier+ tasks. "
        f"To override: classify as S-tier or get plan approved via approval_gate.py."
    )
    print(json.dumps({"allow": False, "reason": block_reason, "enforcement": "plan_required"}))
    sys.exit(1)


if __name__ == "__main__":
    main()
