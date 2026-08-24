#!/usr/bin/env python3
"""checkpoint_core.py — Core checkpoint operations: save, load, state conversion.

T2.6: Checkpoint schema + sanitize + redact.
"""
from __future__ import annotations

import json
import sys
from datetime import datetime, timezone
from pathlib import Path

from data_models import CheckpointState

# Import từ các module con (absolute imports)
from checkpoint_sanitize import _sanitize_step_id, _sanitize_workflow_id
from checkpoint_redact import _redact_snapshot, migrate

# Cau hinh
CHECKPOINTS_DIR = ".devin/checkpoints"
REPAIR_MEMORY_FILE = ".devin/telemetry/repair_memory.json"


def _repo_root() -> Path:
    """Tim thu muc goc repo (co .devin)."""
    p = Path(__file__).resolve().parent
    for parent in [p, *p.parents]:
        if (parent / ".devin").is_dir():
            return parent
    return p


def _load_json(path: Path, default):
    """Doc JSON an toan (tra ve default neu loi/khong ton tai)."""
    try:
        if path.exists():
            return json.loads(path.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError):
        pass
    return default


def _save_json(path: Path, data) -> None:
    """Ghi JSON an toan."""
    try:
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text(json.dumps(data, indent=2, ensure_ascii=False, default=str), encoding="utf-8")
    except (OSError, UnicodeDecodeError, TypeError, ValueError) as e:
        print(f"[checkpoint] khong the ghi {path}: {e}", file=sys.stderr)


def _checkpoints_root(root: Path, workflow_id: str) -> Path:
    """Duong dan thu muc checkpoint cho workflow — chroot vào .devin/checkpoints/.

    CVE-2026-AHD-004 fix:
    1. REJECT '..' ngay trên input raw (trước sanitize).
    2. Sau sanitize: resolve() và verify nằm trong root/.devin/checkpoints/.
    3. Mọi file operation sau đó đều nằm dưới ckpt_root (chroot).
    """
    from checkpoint_sanitize import _reject_dotdot

    _reject_dotdot(workflow_id, "workflow_id")
    workflow_id = _sanitize_workflow_id(workflow_id)
    ckpt_root = (root / CHECKPOINTS_DIR).resolve()
    resolved = (ckpt_root / workflow_id).resolve()
    try:
        resolved.relative_to(ckpt_root)
    except ValueError:
        # Không thể xảy ra sau khi reject '..', nhưng fail-closed phòng hộ.
        raise ValueError(f"workflow_id '{workflow_id}' resolves outside checkpoints root")
    return resolved


def _to_checkpoint_state(state) -> CheckpointState:
    """Chuyển dict/Pydantic model thành CheckpointState, sanitize step_id trước."""
    if isinstance(state, CheckpointState):
        data = state.model_dump(by_alias=True, mode="json")
        data["step_id"] = _sanitize_step_id(data.get("step_id", "unknown"))
        return CheckpointState.model_validate(data)
    if isinstance(state, dict):
        data = dict(state)
        data["step_id"] = _sanitize_step_id(data.get("step_id", "unknown"))
        if data.get("version", 0) != 2:
            data = migrate(data, target_version=2)
        return CheckpointState.model_validate(data)
    raise TypeError(f"state phải là dict hoặc CheckpointState, nhận {type(state)}")


def save(state, workflow_id: str = "", root: Path | None = None) -> Path:
    """T2.6: Lưu checkpoint dưới dạng CheckpointState.

    - Sanitize step_id.
    - Redact secret trước khi lưu.
    - Trả về đường dẫn file checkpoint.
    """
    ckpt = _to_checkpoint_state(state)
    if not workflow_id:
        workflow_id = ckpt.run_id or "default"
    root = root or _repo_root()

    step_id = _sanitize_step_id(ckpt.step_id)
    ckpt = ckpt.model_copy(update={"step_id": step_id})
    ckpt = _redact_snapshot(ckpt)

    ckpt_dir = _checkpoints_root(root, workflow_id)
    ckpt_dir.mkdir(parents=True, exist_ok=True)
    ts = datetime.now(timezone.utc).strftime("%Y%m%d_%H%M%S_%f")
    ckpt_path = ckpt_dir / f"{step_id}_{ts}.json"

    _save_json(ckpt_path, ckpt.model_dump(by_alias=True, mode="json"))

    # Cập nhật index
    index_path = ckpt_dir / "index.json"
    index = _load_json(index_path, {"checkpoints": []})
    if not isinstance(index, dict):
        index = {"checkpoints": []}
    index.setdefault("checkpoints", []).append({
        "step_id": step_id,
        "file": ckpt_path.name,
        "timestamp": ckpt.timestamp.isoformat() if ckpt.timestamp else datetime.now(timezone.utc).isoformat(),
    })
    _save_json(index_path, index)

    return ckpt_path


def load(path: Path) -> CheckpointState:
    """T2.6: Đọc checkpoint và trả CheckpointState.

    Tự động migrate nếu version cũ.
    """
    data = _load_json(path, {})
    if not data:
        raise ValueError(f"Không thể đọc checkpoint: {path}")
    if data.get("version", 0) != 2:
        data = migrate(data, target_version=2)
    return CheckpointState.model_validate(data)


def _safe_ckpt_path(ckpt_dir: Path, name: str) -> Path | None:
    """CVE-2026-AHD-004: Build checkpoint file path chroot trong ckpt_dir.

    Chống index.json/checkpoint tampered: name chứa '..' hoặc resolve ra ngoài
    ckpt_dir → trả None (không đọc/ghi ngoài vùng checkpoint).
    """
    from checkpoint_sanitize import _reject_dotdot

    if not name:
        return None
    try:
        _reject_dotdot(name, "checkpoint file")
    except ValueError:
        return None
    resolved = (ckpt_dir / name).resolve()
    try:
        resolved.relative_to(ckpt_dir.resolve())
    except ValueError:
        return None
    return resolved