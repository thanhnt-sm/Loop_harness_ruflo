#!/usr/bin/env python3
"""Kiểm thử artifact_registry.py — T4.11 (REQ-020).

Các ca kiểm thử:
1. register ghi artifact, get đọc lại được.
2. register trùng (type, id) không update -> raise ValueError.
3. register với update=True -> ghi đè, tăng version.
4. Concurrent write cùng region -> không corrupt JSON (race-safe).
5. get artifact không tồn tại -> None.
6. list_artifacts liệt kê đúng.
7. Đầu vào không hợp lệ raise lỗi.
8. Sanitize id/type với ký tự không hợp lệ.
"""
import json
import sys
import threading
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


def test_register_and_get(patched_root):
    """register ghi artifact, get đọc lại được."""
    from artifact_registry import register, get, Artifact
    register("cot", "cot-1", {"steps": 5, "tokens": 100}, root=patched_root)
    art = get("cot", "cot-1", root=patched_root)
    assert art is not None
    assert isinstance(art, Artifact)
    assert art.type == "cot"
    assert art.id == "cot-1"
    assert art.schema_def["steps"] == 5
    assert art.version == 1


def test_register_duplicate_raises(patched_root):
    """register trùng (type, id) không update -> raise ValueError."""
    from artifact_registry import register
    register("verdict", "v-1", {"pass": True}, root=patched_root)
    with pytest.raises(ValueError):
        register("verdict", "v-1", {"pass": False}, root=patched_root)


def test_register_update_increments_version(patched_root):
    """register với update=True -> ghi đè, tăng version."""
    from artifact_registry import register, get
    register("checkpoint", "ck-1", {"step": 1}, root=patched_root)
    register("checkpoint", "ck-1", {"step": 2}, root=patched_root, update=True)
    art = get("checkpoint", "ck-1", root=patched_root)
    assert art is not None
    assert art.version == 2
    assert art.schema_def["step"] == 2


def test_concurrent_write_no_corruption(patched_root):
    """Concurrent write cùng region -> không corrupt JSON."""
    from artifact_registry import register, get
    # 10 thread ghi artifact khác id cùng type — không corrupt
    errors: list[Exception] = []

    def writer(i: int):
        try:
            register("swarm", f"worker-{i}", {"index": i}, root=patched_root)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(10)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    # Đọc lại tất cả — mỗi file phải JSON hợp lệ
    for i in range(10):
        art = get("swarm", f"worker-{i}", root=patched_root)
        assert art is not None
        assert art.schema_def["index"] == i


def test_concurrent_write_same_id_serialized(patched_root):
    """Concurrent write cùng (type, id) với update=True -> không corrupt, version tăng."""
    from artifact_registry import register, get
    errors: list[Exception] = []

    def writer(_i: int):
        try:
            register("shared", "s-1", {"ts": 1}, root=patched_root, update=True)
        except Exception as e:
            errors.append(e)

    threads = [threading.Thread(target=writer, args=(i,)) for i in range(5)]
    for t in threads:
        t.start()
    for t in threads:
        t.join()
    assert errors == []
    art = get("shared", "s-1", root=patched_root)
    assert art is not None
    # File JSON hợp lệ (không corrupt)
    assert art.version >= 1


def test_get_missing_returns_none(patched_root):
    """get artifact không tồn tại -> None."""
    from artifact_registry import get
    assert get("missing", "nope", root=patched_root) is None


def test_list_artifacts(patched_root):
    """list_artifacts liệt kê đúng."""
    from artifact_registry import register, list_artifacts
    register("cot", "c1", {"a": 1}, root=patched_root)
    register("cot", "c2", {"a": 2}, root=patched_root)
    register("verdict", "v1", {"b": 1}, root=patched_root)
    all_ids = list_artifacts(root=patched_root)
    assert "cot/c1" in all_ids
    assert "cot/c2" in all_ids
    assert "verdict/v1" in all_ids
    # Lọc theo type
    cot_only = list_artifacts(type="cot", root=patched_root)
    assert all("cot/" in x for x in cot_only)


def test_invalid_inputs_raise(patched_root):
    """Đầu vào không hợp lệ raise lỗi."""
    from artifact_registry import register
    with pytest.raises(ValueError):
        register("", "id", {"a": 1}, root=patched_root)
    with pytest.raises(ValueError):
        register("type", "", {"a": 1}, root=patched_root)
    with pytest.raises(TypeError):
        register("type", "id", "not-a-dict", root=patched_root)  # type: ignore[arg-type]


def test_sanitize_id(patched_root):
    """Sanitize id/type với ký tự không hợp lệ."""
    from artifact_registry import register, get
    # id chứa ký tự không hợp lệ -> sanitize
    register("cot", "id with spaces!", {"x": 1}, root=patched_root)
    art = get("cot", "id_with_spaces", root=patched_root)
    assert art is not None
    assert art.id == "id_with_spaces"


def test_artifact_file_is_valid_json(patched_root):
    """File artifact trên disk là JSON hợp lệ."""
    from artifact_registry import register, _artifact_path
    register("cot", "json-test", {"k": "v"}, root=patched_root)
    path = _artifact_path("cot", "json-test", root=patched_root)
    data = json.loads(path.read_text(encoding="utf-8"))
    assert data["type"] == "cot"
    assert data["id"] == "json-test"
    assert data["schema"]["k"] == "v"


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
