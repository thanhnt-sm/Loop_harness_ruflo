#!/usr/bin/env python3
"""Kiểm thử blackboard.py — T2.1/T2.2 (REB-010/REB-001).

Các ca kiểm thử chính:
1. Đọc key chưa tồn tại → exists=False.
2. Ghi và đọc lại giá trị.
3. Các quy tắc region (append-only, single-writer, v.v.).
4. Đồng thời 5 thread ghi 50 key → JSON không bị corrupt.
5. Timeout khi không lấy được khóa.
6. Read-modify-write nguyên tử.
7. Không ghi nếu khóa thất bại (rollback).
8. Liệt kê key trong region.
"""
import json
import sys
import threading
import time
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest
from filelock import FileLock

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import blackboard  # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Dùng thư mục tạm cho blackboard, không động đến repo thật."""
    monkeypatch.setattr(blackboard, "_repo_root", lambda: tmp_path)
    yield tmp_path


# ---------------------------------------------------------------------------
# 1. Đọc key chưa tồn tại
# ---------------------------------------------------------------------------
def test_read_empty(root):
    result = blackboard.read_value("metrics", "missing")
    assert result["exists"] is False
    assert result["value"] is None


# ---------------------------------------------------------------------------
# 2. Ghi và đọc lại giá trị
# ---------------------------------------------------------------------------
def test_write_and_read(root):
    res = blackboard.write_value("metrics", "foo", 42, agent="test")
    assert res["written"] is True
    read = blackboard.read_value("metrics", "foo")
    assert read["exists"] is True
    assert read["value"] == 42


# ---------------------------------------------------------------------------
# 3. Các quy tắc region
# ---------------------------------------------------------------------------
def test_append_only_region_rejects_overwrite(root):
    blackboard.write_value("hypotheses", "h1", "first", agent="a1")
    res = blackboard.write_value("hypotheses", "h1", "second", agent="a2")
    assert res["written"] is False
    assert "append-only" in res["reason"]


def test_single_writer_region_allows_owner_update(root):
    blackboard.write_value("evidence", "e1", "v1", agent="a1")
    res = blackboard.write_value("evidence", "e1", "v2", agent="a1")
    assert res["written"] is True
    assert blackboard.read_value("evidence", "e1")["value"] == "v2"


def test_single_writer_region_rejects_other_writer(root):
    blackboard.write_value("evidence", "e1", "v1", agent="a1")
    res = blackboard.write_value("evidence", "e1", "v2", agent="a2")
    assert res["written"] is False


# ---------------------------------------------------------------------------
# 4. Đồng thời 5 thread ghi 50 key — JSON không bị corrupt
# ---------------------------------------------------------------------------
def test_concurrent_writes_no_corrupt(root):
    def worker(args):
        i, k = args
        return blackboard.write_value("metrics", f"key_{i}_{k}", f"val_{i}_{k}", agent=f"agent_{i}")

    items = [(i, k) for i in range(5) for k in range(10)]
    with ThreadPoolExecutor(max_workers=5) as ex:
        list(ex.map(worker, items))

    region_file = root / ".devin" / "blackboard" / "metrics.json"
    assert region_file.exists()
    data = json.loads(region_file.read_text(encoding="utf-8"))
    assert len(data) == 50


# ---------------------------------------------------------------------------
# 5. Timeout khi không lấy được khóa
# ---------------------------------------------------------------------------
def test_lock_timeout(root):
    """Giữ khóa bằng thread cùng process, kiểm tra _acquire_lock raise đúng hạn."""
    lock_path = blackboard._region_lock_path("metrics")
    lock_path.parent.mkdir(parents=True, exist_ok=True)

    fl = FileLock(str(lock_path))
    held = threading.Event()

    def hold():
        fl.acquire()
        held.set()
        time.sleep(0.2)
        fl.release()

    t = threading.Thread(target=hold)
    t.start()
    held.wait(timeout=2)
    time.sleep(0.01)

    # _acquire_lock với timeout rất ngắn phải ném LockAcquireError.
    with pytest.raises(blackboard.LockAcquireError):
        blackboard._acquire_lock(lock_path, timeout=0.05)

    t.join(timeout=5)


# ---------------------------------------------------------------------------
# 6. Read-modify-write nguyên tử
# ---------------------------------------------------------------------------
def test_atomic_read_modify_write(root):
    """Nhiều thread ghi đè cùng key; file JSON phải luôn hợp lệ
    và cuối cùng chứa đúng 1 giá trị."""
    def worker(i):
        return blackboard.write_value("metrics", "shared", f"value_{i}", agent=f"a{i}")

    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(worker, range(20)))

    # Tất cả đều ghi thành công vì metrics là last_write_wins.
    assert all(r["written"] for r in results)
    region_file = root / ".devin" / "blackboard" / "metrics.json"
    data = json.loads(region_file.read_text(encoding="utf-8"))
    assert "shared" in data
    assert data["shared"].startswith("value_")


# ---------------------------------------------------------------------------
# 7. Không ghi nếu khóa thất bại (rollback)
# ---------------------------------------------------------------------------
def test_rollback_on_lock_fail(root):
    """Nếu khóa không lấy được, file region không được thay đổi."""
    blackboard.write_value("metrics", "before", "ok", agent="test")
    region_file = root / ".devin" / "blackboard" / "metrics.json"
    before_text = region_file.read_text(encoding="utf-8")

    # Giữ khóa bằng filelock để write tiếp theo thất bại.
    lock_path = blackboard._region_lock_path("metrics")
    fl = FileLock(str(lock_path))
    try:
        fl.acquire()
        res = blackboard.write_value("metrics", "after", "nok", agent="test")
        assert res["written"] is False
        after_text = region_file.read_text(encoding="utf-8")
        assert after_text == before_text
    finally:
        fl.release()
        # Dọn file khóa tạm.
        try:
            lock_path.unlink()
        except Exception:
            pass


# ---------------------------------------------------------------------------
# 8. Liệt kê key trong region
# ---------------------------------------------------------------------------
def test_list_keys(root):
    blackboard.write_value("metrics", "k1", 1, agent="test")
    blackboard.write_value("metrics", "k2", 2, agent="test")
    res = blackboard.list_keys("metrics")
    assert res["count"] == 2
    assert set(res["keys"]) == {"k1", "k2"}
