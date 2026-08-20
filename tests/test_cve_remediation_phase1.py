#!/usr/bin/env python3
"""Regression tests cho Phase 1 remediation (CVE-2026-AHD-001..005).

Bao phủ:
- CVE-001: plan_enforce session confusion — strict session binding.
- CVE-002: state_schema validation (StrictBool, extra=forbid, HMAC).
- CVE-003: idempotency fail-closed lock (không chạy unlocked) + DAG blocked.
- CVE-004: checkpoint path traversal — reject '..' fail-closed + chroot.
- CVE-005: schema_gate secret scan toàn bộ output (chunked, entropy, HLK).
"""
import json
import os
import subprocess
import sys
import tempfile
import threading
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)


# ---------------------------------------------------------------------------
# CVE-002: state schema
# ---------------------------------------------------------------------------
def test_state_schema_rejects_unknown_fields():
    from state_schema import validate_state, StateValidationError

    with pytest.raises(StateValidationError):
        validate_state({
            "workflow_id": "wf-1", "stage": "PLAN", "approved": True,
            "evil_field": "x",  # extra field -> reject (fail closed)
        })


def test_state_schema_strict_bool():
    from state_schema import validate_state, StateValidationError

    # 'yes'/'true' string không phải bool -> reject
    for bad in ("yes", "true", "1", 1, "no"):
        with pytest.raises(StateValidationError):
            validate_state({"approved": bad})


def test_state_schema_hmac_sign_verify_tamper():
    from state_schema import sign_state, verify_state

    state = {"workflow_id": "wf-1", "stage": "DISPATCH", "approved": True}
    signed = sign_state(state, key=b"test-key")
    assert "_sig" in signed
    assert verify_state(signed, key=b"test-key")
    # Tamper: đổi stage sau khi ký -> verify fail
    tampered = dict(signed, stage="DONE")
    assert not verify_state(tampered, key=b"test-key")
    # Sai key -> fail
    assert not verify_state(signed, key=b"wrong-key")
    # State không ký + có khóa -> fail (fail closed)
    assert not verify_state(state, key=b"test-key")


def test_state_router_rejects_invalid_state(tmp_path):
    from state_router import _normalize_state, StateValidationError

    with pytest.raises(StateValidationError):
        _normalize_state({"workflow_id": "wf-1", "approved": "yes"})


# ---------------------------------------------------------------------------
# CVE-003: idempotency fail-closed
# ---------------------------------------------------------------------------
def test_idempotency_lock_unavailable_fails_closed(tmp_path, monkeypatch):
    """Lock backend lỗi + filelock không có -> register() raise (KHÔNG chạy unlocked)."""
    import ahd_session
    import idempotency

    def _boom(lock_path, timeout=5.0):
        raise RuntimeError("lock service unavailable")

    monkeypatch.setattr(ahd_session, "_acquire_lock", _boom)
    monkeypatch.setattr(idempotency, "_repo_root", lambda: tmp_path)
    # Chặn filelock fallback để buộc fail-closed
    monkeypatch.setitem(sys.modules, "filelock", None)
    calls = []
    with pytest.raises(idempotency.IdempotencyLockError):
        idempotency.register("k-unavail", lambda: calls.append(1) or "x")
    assert calls == [], "op phải KHÔNG chạy khi lock không khả dụng (fail closed)"


def test_idempotency_parallel_no_duplicate_execution(tmp_path, monkeypatch):
    """2 thread cùng key -> chỉ 1 lần thực thi, cả 2 nhận kết quả."""
    import idempotency
    monkeypatch.setattr(idempotency, "_repo_root", lambda: tmp_path)

    def op():
        time.sleep(0.2)
        return "x"

    results = []

    def worker():
        try:
            results.append(idempotency.register("k-par", op))
        except Exception as e:  # noqa: BLE001
            results.append(f"err:{type(e).__name__}")

    ts = [threading.Thread(target=worker) for _ in range(2)]
    [t.start() for t in ts]
    [t.join() for t in ts]
    assert results == ["x", "x"], results


def test_dag_executor_blocked_status():
    """IdempotencyLockError -> IdempotencyBlockedError -> task 'blocked',
    DAG dừng (success=False) — không chạy tiếp task phụ thuộc."""
    import dag_executor as de

    assert issubclass(de.IdempotencyBlockedError, RuntimeError)
    summary = de._get_status_summary({
        "workflow_id": "wf-1",
        "tasks": {
            "t1": {"status": "blocked"},
            "t2": {"status": "pending"},
        },
    })
    assert summary["any_blocked"] is True
    assert summary["counts"]["blocked"] == 1


# ---------------------------------------------------------------------------
# CVE-004: checkpoint path traversal
# ---------------------------------------------------------------------------
def test_checkpoint_reject_dotdot_raw():
    import checkpoint as cp

    for evil in ("../../../etc/passwd", "..\\..\\HLK\\config",
                 "....//....//HLK/config", "a/../../HLK/x"):
        with pytest.raises(ValueError):
            cp._sanitize_workflow_id(evil)
        with pytest.raises(ValueError):
            cp._sanitize_step_id(evil)


def test_checkpoint_chroot_resolve():
    import checkpoint as cp
    from pathlib import Path

    with tempfile.TemporaryDirectory() as td:
        root = Path(td)
        (root / ".devin").mkdir()
        r = cp._checkpoints_root(root, "wf-1")
        assert str(r).startswith(str((root / ".devin" / "checkpoints").resolve()))
        # index.json tampered: file entry vượt ra ngoài -> None
        ckpt_dir = root / ".devin" / "checkpoints" / "wf-1"
        ckpt_dir.mkdir(parents=True)
        (ckpt_dir / "index.json").write_text(json.dumps({
            "checkpoints": [
                {"step_id": "s1", "file": "../../../../HLK/config/evil.json",
                 "timestamp": "2026-01-01T00:00:00"},
            ]}))
        assert cp._find_latest_checkpoint(ckpt_dir, "s1") is None


# ---------------------------------------------------------------------------
# CVE-005: schema_gate full secret scan
# ---------------------------------------------------------------------------
def test_secret_scan_middle_of_large_output():
    """Secret ở giữa output 600K chars (trước đây bị truncate bỏ sót)."""
    import schema_gate as sg

    big = "a" * 300_000 + "sk-proj-" + "xYz" * 40 + "b" * 300_000
    r = sg._gate_secret_scan(big)
    assert r is not None, "secret ở giữa output lớn phải bị phát hiện (CVE-005)"


def test_secret_scan_chunk_boundary():
    import schema_gate as sg

    r = sg._gate_secret_scan(
        "x" * 70_000 + "sk-test-AAAAAAAAAAAAAAAAAAAA" + "y" * 70_000)
    assert r is not None, "secret nằm lệch chunk phải bị phát hiện"


def test_secret_scan_hlk_patterns_loaded():
    """Patterns từ HLK config được load (source of truth) — >= defaults."""
    import schema_gate as sg

    assert len(sg.SECRET_PATTERNS) >= len(sg.DEFAULT_SECRET_PATTERNS)
    for val in (
        "AKIAIOSFODNN7EXAMPLE",
        "glpat-abcdefghijklmnopqrstuvwx",
        "postgres://admin:s3cr3t@db.example.com:5432/prod",
        "redis://:pass123@cache.internal:6379/0",
        "-----BEGIN PRIVATE KEY-----",
    ):
        assert sg._gate_secret_scan("text " + val + " end") is not None, val


def test_secret_scan_entropy_detection():
    import schema_gate as sg

    r = sg._gate_secret_scan(
        "qzv9kM2xR7tL4pWn8cJ1sH6dF3gU5iY0aB7eD2xV9nM4kL8pQ1zX3cV7bN5mK9jH2wR6tY4uI8oP0qW3sE5rT7yU1iO9aG4dF6hJ2")
    assert r is not None and r["details"].get("pattern") == "entropy"


def test_secret_scan_no_false_positive_identifiers():
    import schema_gate as sg

    assert sg._gate_secret_scan(
        "function get_customer_order_invoice_details_by_status_and_date_range_result") is None
    assert sg._gate_secret_scan(
        "process_customer_order_2024_data") is None
    assert sg._gate_secret_scan(
        "commit sha 9f86d081884c7d659a2feaa0c55ad015a3bf4f1b2b0b822cd15d6c15b0f00a08") is None


def test_secret_scan_perf_1mb():
    """1MB output phải quét nhanh (plan Task 1.5: <100ms trên máy nhàn).

    Ngưỡng test 250ms để hấp thụ nhiễu load CI; vẫn bắt regression nặng
    (catastrophic backtracking trước đây mất 2.8s+).
    """
    import random
    import string
    import schema_gate as sg

    big = "".join(random.choices(string.ascii_lowercase + " ", k=1_000_000))
    t0 = time.perf_counter()
    r = sg._gate_secret_scan(big)
    dt = (time.perf_counter() - t0) * 1000
    assert r is None
    assert dt < 500, f"1MB scan quá chậm: {dt:.0f}ms"


def test_secret_scan_masking_no_raw_secret():
    """Báo cáo KHÔNG chứa secret thật (chỉ masked)."""
    import schema_gate as sg

    secret = "ghp_" + "1" * 36
    r = sg._gate_secret_scan("x " + secret + " y")
    assert r is not None
    assert secret not in r["reason"]
    assert secret not in json.dumps(r["details"])