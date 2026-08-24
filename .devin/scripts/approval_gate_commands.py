#!/usr/bin/env python3
"""approval_gate_commands.py — Command implementations: approve, reject, request_changes, status."""

from __future__ import annotations

from pathlib import Path

from approval_gate_constants import (
    STATUS_PENDING,
    STATUS_APPROVED,
    STATUS_REJECTED,
    STATUS_CHANGES_REQUESTED,
    ARTIFACT_PLAN,
)
from approval_gate_crypto import (
    plan_hash,
    load_reviewer_keys,
    signature_required,
    verify_signature,
    _sig_message,
)
from approval_gate_archive import _plan_file_hashes, _archive_approved_plan
from approval_gate_audit import _append_approval_audit
from approval_gate_state import (
    _repo_root,
    _state_path,
    _load_state,
    _save_state,
    _init_state_if_needed,
    _plan_state_name,
)
from datetime import datetime, timezone


def cmd_status(plan_path: Path, artifact: str = ARTIFACT_PLAN) -> dict:
    """--status: Trả trạng thái phê duyệt hiện tại."""
    if not plan_path.exists():
        return {"error": f"Không tìm thấy plan file: {plan_path}", "status": STATUS_PENDING}
    root = _repo_root(plan_path)
    state = _init_state_if_needed(root, plan_path, artifact)
    state["artifact"] = artifact
    return state


def _write_approval_state(
    plan_path: Path,
    artifact: str,
    status: str,
    reviewer: str,
    comments: str,
    signature: str = "",
    signed_ts: str = "",
) -> dict:
    """Helper ghi approval state cho plan hoặc SDD.

    CVE-2026-AHD-006: nếu reviewer_keys được cấu hình (hoặc HLK config bật
    approval_signature_required), status=approved BẮT BUỘC có Ed25519
    signature hợp lệ (base64, ký trên plan_hash|reviewer|timestamp).
    `signed_ts` (nếu có) là timestamp ĐÃ ký — được ghi verbatim vào state/audit
    để replay verify; mặc định = now.
    Mọi thao tác đều được ghi vào telemetry append-only.
    """
    if not plan_path.exists():
        return {"error": f"Không tìm thấy file: {plan_path}"}
    root = _repo_root(plan_path)
    sp = _state_path(root, plan_path, artifact)

    phash = plan_hash(plan_path)
    ts = signed_ts or datetime.now(timezone.utc).isoformat()

    # CVE-2026-AHD-006: verify signature cho approval
    if status == STATUS_APPROVED:
        keys = load_reviewer_keys(root)
        if signature_required(root):
            if not signature:
                _append_approval_audit(root, {
                    "event": "approval_rejected", "plan_hash": phash,
                    "artifact": artifact, "reviewer": reviewer,
                    "reason": "missing_signature", "date": ts,
                })
                return {
                    "error": "Signature bắt buộc (CVE-2026-AHD-006): approve cần "
                             "--signature <base64 Ed25519> từ reviewer được ủy quyền",
                    "status": STATUS_PENDING,
                }
            if not verify_signature(_sig_message(phash, reviewer, ts), signature, keys):
                _append_approval_audit(root, {
                    "event": "approval_rejected", "plan_hash": phash,
                    "artifact": artifact, "reviewer": reviewer,
                    "reason": "invalid_signature", "date": ts,
                })
                return {
                    "error": "Chữ ký không hợp lệ hoặc reviewer không được ủy quyền "
                             "(CVE-2026-AHD-006)",
                    "status": STATUS_PENDING,
                }

    state = {
        "plan_file": str(plan_path.relative_to(root)),
        "artifact": artifact,
        "status": status,
        "reviewer": reviewer,
        "date": ts,
        "comments": comments,
        "plan_hash": phash,
    }
    if signature:
        state["signature"] = signature
    # CVE-2026-AHD-010: ghi SHA-256 từng file tham chiếu + archive bất biến
    if status == STATUS_APPROVED and artifact == ARTIFACT_PLAN:
        state["file_hashes"] = _plan_file_hashes(plan_path, root)
        archived = _archive_approved_plan(root, plan_path, phash)
        if archived:
            state["artifact_path"] = archived
    _save_state(sp, state)

    # Audit log append-only (mọi event: approve/reject/changes_requested)
    _append_approval_audit(root, {
        "event": f"approval_{status}", "plan_hash": phash,
        "artifact": artifact, "reviewer": reviewer,
        "plan_file": state["plan_file"], "date": ts,
        "has_signature": bool(signature),
    })
    return state


def cmd_approve(plan_path: Path, reviewer: str, comments: str, artifact: str = ARTIFACT_PLAN, signature: str = "", signed_ts: str = "") -> dict:
    """--approve: Đánh dấu plan/SDD approved (cần Ed25519 signature nếu cấu hình)."""
    return _write_approval_state(plan_path, artifact, STATUS_APPROVED, reviewer, comments, signature=signature, signed_ts=signed_ts)


def cmd_reject(plan_path: Path, reviewer: str, reason: str, artifact: str = ARTIFACT_PLAN) -> dict:
    """--reject: Đánh dấu plan/SDD rejected (kèm lý do)."""
    return _write_approval_state(plan_path, artifact, STATUS_REJECTED, reviewer, reason)


def cmd_request_changes(plan_path: Path, reviewer: str, feedback: str, artifact: str = ARTIFACT_PLAN) -> dict:
    """--request-changes: Đánh dấu plan/SDD cần sửa đổi (kèm feedback)."""
    return _write_approval_state(plan_path, artifact, STATUS_CHANGES_REQUESTED, reviewer, feedback)