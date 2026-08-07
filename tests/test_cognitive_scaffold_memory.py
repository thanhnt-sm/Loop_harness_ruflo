#!/usr/bin/env python3
"""Kiểm thử cognitive_scaffold_memory.py — T4.10 (REQ-010).

Các ca kiểm thử:
1. record ghi file transcript, trả đường dẫn tồn tại.
2. recall đọc lại transcript theo run_id.
3. Mỗi role có thư mục riêng (cô lập, không role bleed).
4. Redact secret trước khi ghi (HLK patterns).
5. Retention 7 ngày: file cũ bị xóa.
6. Đầu vào không hợp lệ raise lỗi.
7. run_id mặc định từ env.
"""
import os
import sys
import time
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    """Patch repo root + config root về tmp_path/.devin."""
    devin_dir = tmp_path / ".devin"
    devin_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    return tmp_path


def test_record_returns_existing_path(patched_root):
    """record trả đường dẫn file tồn tại trên disk."""
    from cognitive_scaffold_memory import record
    path = record("summarizer", "Tóm tắt bài toán X.", run_id="run-1", root=patched_root)
    assert path.exists()
    assert path.suffix == ".json"


def test_recall_returns_entries(patched_root):
    """recall đọc lại transcript theo run_id."""
    from cognitive_scaffold_memory import record, recall
    record("summarizer", "Tóm tắt 1.", run_id="run-2", root=patched_root)
    record("main", "Trả lời 1.", run_id="run-2", root=patched_root)
    entries = recall("run-2", root=patched_root)
    assert len(entries) == 2
    roles = {e["role"] for e in entries}
    assert roles == {"summarizer", "main"}


def test_roles_isolated_no_bleed(patched_root):
    """Mỗi role có thư mục riêng — kiểm tra cấu trúc thư mục."""
    from cognitive_scaffold_memory import record, _role_dir, _scaffold_root
    record("summarizer", "s1", run_id="run-3", root=patched_root)
    record("main", "m1", run_id="run-3", root=patched_root)
    record("corrector", "c1", run_id="run-3", root=patched_root)
    scaffold = _scaffold_root(patched_root)
    # Mỗi role có thư mục riêng
    assert (scaffold / "summarizer").is_dir()
    assert (scaffold / "main").is_dir()
    assert (scaffold / "corrector").is_dir()
    # File của summarizer không nằm trong main/
    sum_files = list((scaffold / "summarizer").glob("*.json"))
    main_files = list((scaffold / "main").glob("*.json"))
    assert len(sum_files) == 1
    assert len(main_files) == 1
    # File không trùng tên giữa các role
    assert sum_files[0].parent != main_files[0].parent


def test_redact_secret_before_write(patched_root):
    """Secret (HLK patterns) bị redact trước khi ghi."""
    from cognitive_scaffold_memory import record
    secret_text = "api_key=sk-abcdefghijklmnopqrstuvwxyz0123456789 ghp_abcdefghijklmnopqrstuvwxyz0123456789"
    path = record("main", secret_text, run_id="run-redact", root=patched_root)
    content = path.read_text(encoding="utf-8")
    # Secret đã bị thay bằng [REDACTED]
    assert "sk-abcdefghijklmnopqrstuvwxyz0123456789" not in content
    assert "ghp_abcdefghijklmnopqrstuvwxyz0123456789" not in content
    assert "[REDACTED]" in content


def test_redact_bearer_token(patched_root):
    """Bearer token bị redact."""
    from cognitive_scaffold_memory import record
    text = "Authorization: Bearer abcdefghijklmnopqrstuvwxyz1234567890"
    path = record("main", text, run_id="run-bearer", root=patched_root)
    content = path.read_text(encoding="utf-8")
    assert "Bearer abcdef" not in content
    assert "[REDACTED]" in content


def test_retention_deletes_old_files(patched_root):
    """File cũ hơn 7 ngày bị xóa khi record/recall chạy."""
    from cognitive_scaffold_memory import record, recall, _role_dir
    # Ghi một file
    path = record("summarizer", "cũ", run_id="run-old", root=patched_root)
    assert path.exists()
    # Backdate timestamp của file về 8 ngày trước
    old_time = time.time() - (8 * 86400)
    os.utime(path, (old_time, old_time))
    # Ghi file mới -> trigger retention -> file cũ bị xóa
    record("summarizer", "mới", run_id="run-new", root=patched_root)
    assert not path.exists()


def test_retention_keeps_recent_files(patched_root):
    """File trong 7 ngày vẫn còn."""
    from cognitive_scaffold_memory import record, recall
    path = record("summarizer", "gần đây", run_id="run-recent", root=patched_root)
    # recall trigger retention nhưng file gần đây vẫn còn
    entries = recall("run-recent", root=patched_root)
    assert len(entries) == 1
    assert path.exists()


def test_invalid_role_raises(patched_root):
    """Role không hợp lệ raise ValueError."""
    from cognitive_scaffold_memory import record
    with pytest.raises(ValueError):
        record("invalid_role", "text", run_id="r", root=patched_root)


def test_empty_transcript_raises(patched_root):
    """Transcript rỗng raise ValueError."""
    from cognitive_scaffold_memory import record
    with pytest.raises(ValueError):
        record("main", "", run_id="r", root=patched_root)


def test_recall_empty_run_id_raises(patched_root):
    """recall với run_id rỗng raise ValueError."""
    from cognitive_scaffold_memory import recall
    with pytest.raises(ValueError):
        recall("", root=patched_root)


def test_recall_missing_run_returns_empty(patched_root):
    """recall run_id không tồn tại trả list rỗng."""
    from cognitive_scaffold_memory import recall
    entries = recall("nonexistent-run", root=patched_root)
    assert entries == []


def test_run_id_from_env(patched_root, monkeypatch):
    """run_id mặc định lấy từ env AHD_RUN_ID."""
    from cognitive_scaffold_memory import record, recall
    monkeypatch.setenv("AHD_RUN_ID", "env-run-123")
    path = record("main", "from env", root=patched_root)
    entries = recall("env-run-123", root=patched_root)
    assert len(entries) == 1
    assert entries[0]["run_id"] == "env-run-123"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
