#!/usr/bin/env python3
"""checkpoint_sanitize.py — Sanitize helpers for checkpoint IDs.

CVE-2026-AHD-004: Path traversal prevention.
Reject '..' sequences BEFORE sanitization (fail-closed).
"""
from __future__ import annotations

import re


def _reject_dotdot(value: str, label: str) -> None:
    """CVE-2026-AHD-004: REJECT bất kỳ '..' sequence nào trong input raw.

    Không chỉ thay thế: '....//HLK/config' có thể sanitize thành tên hợp lệ
    nhưng resolve ra ngoài root. Kiểm tra raw TRƯỚC khi sanitize là bắt buộc.
    """
    if not value:
        return
    # '..' với các separator khác nhau, kể cả unicode slash
    if ".." in value.replace("\\", "/"):
        raise ValueError(f"{label} chứa '..' (path traversal) — bị từ chối")


def _sanitize_workflow_id(workflow_id: str) -> str:
    """Làm sạch workflow_id theo allowlist, chống path traversal.

    Thay path separator bằng _, chỉ giữ [a-zA-Z0-9_-], giới hạn 64 ký tự.
    Gọi _reject_dotdot trước (CVE-2026-AHD-004): '..' bị REJECT, không bị
    vô hiệu hóa bằng sanitize (vì '....' cũng bypass được sanitize).
    """
    if not workflow_id:
        return "default"
    _reject_dotdot(workflow_id, "workflow_id")
    wid = workflow_id.replace("/", "_").replace("\\", "_")
    wid = re.sub(r"[^a-zA-Z0-9_-]", "_", wid)
    wid = re.sub(r"_+", "_", wid)
    wid = wid.strip("_-.")
    if not wid:
        return "default"
    wid = wid[:64]
    if not _STEP_ID_PATTERN.match(wid):
        return "default"
    return wid


# --- T2.6: Checkpoint schema + sanitize + redact ---

_STEP_ID_PATTERN = re.compile(r"^[a-zA-Z0-9_-]{1,64}$")


def _sanitize_step_id(step_id: str) -> str:
    """T2.6: Làm sạch step_id theo allowlist ^[a-zA-Z0-9_-]{1,64}$.

    Đảm bảo Path(step_id).name == step_id, không chứa path separator.
    CVE-2026-AHD-004: REJECT '..' trước khi sanitize (fail closed).
    """
    if not step_id:
        return "unnamed"
    _reject_dotdot(step_id, "step_id")
    # Thay path separator bằng _ rồi dùng allowlist
    step_id = step_id.replace("/", "_").replace("\\", "_")
    step_id = re.sub(r"[^a-zA-Z0-9_-]", "_", step_id)
    step_id = re.sub(r"_+", "_", step_id)
    step_id = step_id.strip("_-.")
    if not step_id:
        return "unnamed"
    step_id = step_id[:64]
    if not _STEP_ID_PATTERN.match(step_id):
        return "unnamed"
    return step_id