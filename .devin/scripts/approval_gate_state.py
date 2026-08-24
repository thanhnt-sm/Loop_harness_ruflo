#!/usr/bin/env python3
"""approval_gate_state.py — State management cho approval gate."""

from __future__ import annotations

import json
from pathlib import Path

from approval_gate_constants import (
    STATE_DIR_NAME,
    STATUS_PENDING,
    VALID_STATUSES,
    ARTIFACT_PLAN,
)


def _repo_root(plan_path: Path) -> Path:
    """Xác định repo root cho plan_path.

    Ưu tiên git rev-parse; nếu không có git, dò các marker chuẩn (.git,
    pyproject.toml, README.md, AGENTS.md) từ thư mục chứa plan. Không dùng
    .devin/.agents làm marker vì chúng có thể tồn tại ở thư mục home của user,
    gây nhầm lẫn khi chạy test trong tmp_path.
    """
    import subprocess
    start = plan_path.parent
    try:
        r = subprocess.run(
            ["git", "rev-parse", "--show-toplevel"],
            capture_output=True, text=True, cwd=str(start)
        )
        if r.returncode == 0 and r.stdout.strip():
            return Path(r.stdout.strip())
    except (OSError, ValueError, subprocess.SubprocessError):
        pass
    for parent in [start, *start.parents]:
        if parent.parent == parent:
            break
        for marker in (".git", "pyproject.toml", "README.md", "AGENTS.md"):
            if (parent / marker).exists():
                return parent
    return start


def _state_dir(repo_root: Path) -> Path:
    """Trả về thư mục state. Tạo nếu chưa tồn tại."""
    sd = repo_root / STATE_DIR_NAME
    sd.mkdir(parents=True, exist_ok=True)
    return sd


def _plan_state_name(plan_path: Path, artifact: str = ARTIFACT_PLAN) -> str:
    """
    Tạo tên state file duy nhất cho artifact.

    Nếu plan/SDD nằm trong docs/plans/<task_slug>/ → dùng <task_slug>[_<artifact>]_approved.json.
    - artifact='plan' → <task_slug>_approved.json (backward compatible)
    - artifact='sd'   → <task_slug>_sd_approved.json
    Fallback: dùng plan_path.stem.
    """
    suffix = f"_{artifact}" if artifact and artifact != ARTIFACT_PLAN else ""
    parts = plan_path.parts
    if "docs" in parts and "plans" in parts:
        try:
            idx = parts.index("plans")
            if idx + 1 < len(parts):
                task_slug = parts[idx + 1]
                return f"{task_slug}{suffix}_approved"
        except ValueError:
            pass
    return f"{plan_path.stem}{suffix}"


def _state_path(repo_root: Path, plan_path: Path, artifact: str = ARTIFACT_PLAN) -> Path:
    """Trả về đường dẫn state file cho artifact."""
    return _state_dir(repo_root) / f"{_plan_state_name(plan_path, artifact)}.json"


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


def _init_state_if_needed(repo_root: Path, plan_path: Path, artifact: str) -> dict:
    """Khởi tạo state pending nếu chưa có, gắn plan_file/artifact. Trả state hiện tại."""
    sp = _state_path(repo_root, plan_path, artifact)
    state = _load_state(sp)
    if not state.get("plan_file"):
        state["plan_file"] = str(plan_path.relative_to(repo_root)) if plan_path.exists() else str(plan_path)
        state["artifact"] = artifact
        _save_state(sp, state)
    return state