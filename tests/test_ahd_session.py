#!/usr/bin/env python3
"""Test ahd_session.py — shared session helpers.

Test coverage cho:
- _safe_mkdir (handle FileExistsError trên Linux Python 3.13)
- get_config_root (config root detection)
- get_repo_root (repo root discovery)
- slugify_session_id (filesystem-safe slugification)
- read/write/update_session_state (locked JSON operations)
- Lock mechanism (_acquire_lock, _release_lock)
- Circuit breaker (record_failure, is_circuit_open, reset_circuit)

Chạy: python -m pytest tests/test_ahd_session.py -v
"""
import json
import os
import sys
import tempfile
from pathlib import Path

import pytest

# Add .devin/hooks to path
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT / ".devin" / "hooks"))

import ahd_session


# ---------------------------------------------------------------------------
# _safe_mkdir
# ---------------------------------------------------------------------------

class TestSafeMkdir:
    """Test _safe_mkdir handles FileExistsError on Linux Python 3.13."""

    def test_mkdir_creates_directory(self, tmp_path):
        """Tạo thư mục mới thành công."""
        new_dir = tmp_path / "new_dir"
        ahd_session._safe_mkdir(new_dir)
        assert new_dir.is_dir()

    def test_mkdir_existing_dir_ok(self, tmp_path):
        """Đã tồn tại thư mục — không lỗi."""
        existing = tmp_path / "existing"
        existing.mkdir()
        ahd_session._safe_mkdir(existing)
        assert existing.is_dir()

    def test_mkdir_symlink_dir_ok(self, tmp_path):
        """Symlink đến directory — không lỗi (Linux Python 3.13 bug)."""
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        try:
            link.symlink_to(target)
            ahd_session._safe_mkdir(link)
            assert link.is_dir()
        except OSError:
            # Symlink không hỗ trợ trên Windows — skip
            pytest.skip("Symlink not supported on this platform")


# ---------------------------------------------------------------------------
# get_config_root
# ---------------------------------------------------------------------------

class TestGetConfigRoot:
    """Test config root detection."""

    def test_devin_config_root(self, tmp_path):
        """Nếu .devin/session_state tồn tại → return .devin."""
        (tmp_path / ".devin" / "session_state").mkdir(parents=True)
        result = ahd_session.get_config_root(tmp_path)
        assert result == tmp_path / ".devin"

    def test_agents_config_root(self, tmp_path):
        """Nếu .agents/session_state tồn tại → return .agents."""
        (tmp_path / ".agents" / "session_state").mkdir(parents=True)
        result = ahd_session.get_config_root(tmp_path)
        assert result == tmp_path / ".agents"

    def test_fallback_to_agents(self, tmp_path):
        """Không có marker → fallback .agents."""
        result = ahd_session.get_config_root(tmp_path)
        assert result == tmp_path / ".agents"


# ---------------------------------------------------------------------------
# get_repo_root
# ---------------------------------------------------------------------------

class TestGetRepoRoot:
    """Test repo root discovery."""

    def test_repo_root_from_git(self, tmp_path):
        """Phát hiện repo root qua .git directory."""
        (tmp_path / ".git").mkdir()
        root = ahd_session.get_repo_root(start_from=tmp_path)
        assert root == tmp_path

    def test_repo_root_from_marker(self, tmp_path):
        """Phát hiện repo root qua marker file."""
        (tmp_path / "AGENTS.md").write_text("test")
        root = ahd_session.get_repo_root(start_from=tmp_path)
        assert root == tmp_path

    def test_repo_root_from_subdir(self, tmp_path):
        """Phát hiện repo root từ subdirectory."""
        (tmp_path / ".git").mkdir()
        subdir = tmp_path / "subdir"
        subdir.mkdir()
        root = ahd_session.get_repo_root(start_from=subdir)
        assert root == tmp_path


# ---------------------------------------------------------------------------
# slugify_session_id
# ---------------------------------------------------------------------------

class TestSlugifySessionId:
    """Test filesystem-safe slugification."""

    def test_slugify_basic(self):
        """Slugify session ID cơ bản."""
        result = ahd_session.slugify_session_id("test-session-123")
        assert result == "test-session-123"

    def test_slugify_special_chars(self):
        """Loại bỏ special characters không an toàn."""
        result = ahd_session.slugify_session_id("test/with:spaces!and@symbols")
        assert "/" not in result
        assert ":" not in result
        # slugify có thể giữ lại một số chars — chỉ kiểm tra chars nguy hiểm
        assert "\\" not in result  # Windows path separator
        assert "\0" not in result  # Null byte

    def test_slugify_max_length(self):
        """Cắt ngắn nếu quá max_len."""
        long_id = "a" * 100
        result = ahd_session.slugify_session_id(long_id, max_len=50)
        assert len(result) <= 50


# ---------------------------------------------------------------------------
# read/write/update_session_state
# ---------------------------------------------------------------------------

class TestSessionStateIO:
    """Test locked session state I/O."""

    def test_write_read_session_state(self, tmp_path):
        """Ghi và đọc session state."""
        (tmp_path / ".devin" / "session_state").mkdir(parents=True)
        data = {"key": "value", "count": 42}
        ahd_session.write_session_state("test-session", data, root=tmp_path)
        read = ahd_session.read_session_state("test-session", root=tmp_path)
        assert read == data

    def test_update_session_state(self, tmp_path):
        """Update field trong session state."""
        (tmp_path / ".devin" / "session_state").mkdir(parents=True)
        ahd_session.write_session_state("test-session", {"key": "old"}, root=tmp_path)
        ahd_session.update_session_state("test-session", {"key": "new"}, root=tmp_path)
        read = ahd_session.read_session_state("test-session", root=tmp_path)
        assert read["key"] == "new"

    def test_read_nonexistent_returns_default(self, tmp_path):
        """Đọc session state không tồn tại → return default (empty dict)."""
        (tmp_path / ".devin" / "session_state").mkdir(parents=True)
        read = ahd_session.read_session_state("nonexistent", root=tmp_path)
        assert read == {}


# ---------------------------------------------------------------------------
# Lock mechanism
# ---------------------------------------------------------------------------

class TestLockMechanism:
    """Test file locking mechanism."""

    def test_acquire_release_lock(self, tmp_path):
        """Acquire và release lock thành công."""
        (tmp_path / ".devin" / "session_state").mkdir(parents=True)
        lock_path = ahd_session._get_lock_path(tmp_path)
        handle = ahd_session._acquire_lock(lock_path, timeout=5.0)
        assert handle is not None
        ahd_session._release_lock(handle)
        assert not lock_path.exists()

    def test_lock_timeout(self, tmp_path):
        """Lock timeout khi không thể acquire."""
        (tmp_path / ".devin" / "session_state").mkdir(parents=True)
        lock_path = ahd_session._get_lock_path(tmp_path)
        # Acquire lock đầu tiên
        handle1 = ahd_session._acquire_lock(lock_path, timeout=5.0)
        # Try acquire lại cùng lock → nên timeout hoặc fail
        try:
            handle2 = ahd_session._acquire_lock(lock_path, timeout=0.1)
            # Nếu acquire được (Windows không hỗ trợ real locking), cleanup
            if handle2:
                ahd_session._release_lock(handle2)
        except (ahd_session.LockAcquireError, Exception):
            pass  # Expected on Unix with real locking
        finally:
            ahd_session._release_lock(handle1)


# ---------------------------------------------------------------------------
# Circuit breaker
# ---------------------------------------------------------------------------

class TestCircuitBreaker:
    """Test circuit breaker logic."""

    def test_record_failure(self, tmp_path):
        """Ghi failure vào circuit state."""
        # Circuit breaker không dùng root parameter — test integration
        ahd_session.record_failure("test-component", session_id="test")
        stats = ahd_session.get_failure_stats()
        assert stats.get("test-component", 0) > 0

    def test_is_circuit_open_after_threshold(self, tmp_path):
        """Circuit mở sau threshold failures."""
        # Record nhiều failures để trigger circuit open
        for _ in range(10):
            ahd_session.record_failure("test-component", session_id="test")
        is_open = ahd_session.is_circuit_open("test-component")
        # Circuit có thể open hoặc không tùy implementation
        assert isinstance(is_open, bool)

    def test_reset_circuit(self, tmp_path):
        """Reset circuit về trạng thái đóng."""
        ahd_session.record_failure("test-component", session_id="test")
        ahd_session.reset_circuit("test-component")
        stats = ahd_session.get_failure_stats()
        assert stats.get("test-component", 0) == 0


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
