#!/usr/bin/env python3
"""Storage helpers: tìm repo root, slugify, đọc/ghi state và plan files."""
from __future__ import annotations

import hashlib
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


def fingerprint(task_description: str) -> str:
    """Tạo SHA-256 fingerprint từ task description — không truncate, không strip
    ký tự (V5-02): slug bị mất thông tin (truncate 60 + strip non-word) nên 2 task
    khác nhau có thể trùng slug. Fingerprint đầy đủ thông tin → phát hiện collision
    tại plan_enforce. Chỉ chuẩn hóa khoảng trắng."""
    if not task_description:
        return ""
    norm = re.sub(r"\s+", " ", task_description.strip())
    return hashlib.sha256(norm.encode("utf-8")).hexdigest()


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


def locked_save_state(state_path: Path, state: dict) -> None:
    """T7 fix: Atomic save state — dùng write-to-temp + rename để chống race.

    Hai process ghi cùng lúc → không corrupt (rename là atomic trên cùng filesystem).

    Pentest V7 fix: Windows os.replace có thể fail với WinError 5 (access denied)
    khi nhiều threads cùng rename — thêm retry với backoff.
    """
    import os
    import tempfile
    import time
    # Ghi vào temp file cùng thư mục (đảm bảo cùng filesystem cho atomic rename)
    tmp_fd, tmp_path = tempfile.mkstemp(
        dir=str(state_path.parent), suffix=".tmp", prefix=state_path.stem + "_"
    )
    try:
        with os.fdopen(tmp_fd, "w", encoding="utf-8") as f:
            json.dump(state, f, ensure_ascii=False, indent=2)
        # Atomic rename (Windows: os.replace, Unix: os.rename)
        # Pentest V7 fix: retry 3 lần với backoff cho Windows race
        max_retries = 3
        for attempt in range(max_retries):
            try:
                os.replace(tmp_path, state_path)
                return  # Thành công
            except PermissionError:
                if attempt < max_retries - 1:
                    time.sleep(0.01 * (attempt + 1))  # 10ms, 20ms backoff
                else:
                    raise  # Hết retry → raise
    except Exception:
        # Cleanup temp file nếu lỗi
        try:
            os.unlink(tmp_path)
        except OSError:
            pass
        raise


def collision_safe_state_path(root: Path, task_slug: str, task_description: str) -> Path:
    """T8 fix: Trả state path với fingerprint suffix nếu có collision.

    Nếu state file cho slug đã tồn tại nhưng fingerprint khác → thêm _fp8 suffix.
    Format: {slug}_fp8_orchestrator.json (fp8 = 8 chars đầu của fingerprint)
    """
    base_path = state_path(root, task_slug)
    if not base_path.exists():
        return base_path  # Chưa có → dùng base

    # Đọc existing state để check fingerprint
    existing = load_state(base_path)
    existing_fp = existing.get("task_fingerprint", "")
    new_fp = fingerprint(task_description)

    if not existing_fp or existing_fp == new_fp:
        return base_path  # Cùng fingerprint → dùng base

    # Collision! Thêm fp8 suffix
    fp8 = new_fp[:8] if new_fp else "00000000"
    return state_dir(root) / f"{task_slug}_{fp8}_orchestrator.json"


def create_initial_state(task_description: str, root: Path) -> dict:
    """Tạo state ban đầu cho orchestrator."""
    task_slug = slugify(task_description)
    return {
        "task_description": task_description,
        "task_slug": task_slug,
        "task_fingerprint": fingerprint(task_description),
        "state": "INIT",
        "tier": None,
        "round": 0,
        "revision_round": 0,
        "qc_round": 0,
        "enhance_round": 0,
        "scout_results": [],
        "sdd_path": None,
        "sdd_approved": False,
        "review_findings": [],
        "plan_path": None,
        "quality_report_path": None,
        "plan_approved": False,
        "approval_status": None,
        # CHG-007: Task-scoped permissions — task declares required tools
        "required_tools": [],
        "approved_tools": [],
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
