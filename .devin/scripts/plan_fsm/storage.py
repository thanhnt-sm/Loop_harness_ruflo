#!/usr/bin/env python3
"""Storage helpers: tìm repo root, slugify, đọc/ghi state và plan files."""
from __future__ import annotations

import json
import re
from datetime import datetime, timezone
from pathlib import Path


def repo_root() -> Path:
    """Tìm repo root — đi lên cho đến khi thấy thư mục .devin/."""
    p = Path.cwd()
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def slugify(text: str) -> str:
    """Tạo slug từ task description — lowercase, hyphen-separated."""
    slug = re.sub(r"[^\w\s-]", "", text.lower().strip())
    slug = re.sub(r"[\s_]+", "-", slug)
    slug = re.sub(r"-+", "-", slug).strip("-")
    return slug[:60] if slug else "task"


def state_dir(root: Path) -> Path:
    """Trả về thư mục .devin/plan_state. Tạo nếu chưa tồn tại."""
    sd = root / ".devin" / "plan_state"
    sd.mkdir(parents=True, exist_ok=True)
    return sd


def plans_dir(root: Path, task_slug: str) -> Path:
    """Trả về thư mục docs/plans/<task_slug>/. Tạo nếu chưa tồn tại."""
    pd = root / "docs" / "plans" / task_slug
    pd.mkdir(parents=True, exist_ok=True)
    return pd


def state_path(root: Path, task_slug: str) -> Path:
    """Trả về đường dẫn state file cho orchestrator."""
    return state_dir(root) / f"{task_slug}_orchestrator.json"


def load_state(state_path: Path) -> dict:
    """Đọc state file. Trả state rỗng nếu chưa có hoặc JSON lỗi."""
    if not state_path.exists():
        return {}
    try:
        return json.loads(state_path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def save_state(state_path: Path, state: dict) -> None:
    """Ghi state file JSON."""
    state_path.write_text(
        json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8"
    )


def create_initial_state(task_description: str, root: Path) -> dict:
    """Tạo state ban đầu cho orchestrator."""
    task_slug = slugify(task_description)
    return {
        "task_description": task_description,
        "task_slug": task_slug,
        "state": "INIT",
        "tier": None,
        "round": 0,
        "revision_round": 0,
        "qc_round": 0,
        "scout_results": [],
        "sdd_path": None,
        "sdd_approved": False,
        "review_findings": [],
        "plan_path": None,
        "quality_report_path": None,
        "plan_approved": False,
        "approval_status": None,
        "created_at": datetime.now(timezone.utc).isoformat(),
        "updated_at": datetime.now(timezone.utc).isoformat(),
        "history": [],
    }


def append_history(state: dict, action: str, detail: str) -> None:
    """Ghi lịch sử action vào state và cập nhật timestamp."""
    state["history"].append(
        {
            "timestamp": datetime.now(timezone.utc).isoformat(),
            "state": state["state"],
            "action": action,
            "detail": detail,
        }
    )
    state["updated_at"] = datetime.now(timezone.utc).isoformat()
