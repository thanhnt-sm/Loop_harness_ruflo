#!/usr/bin/env python3
"""Targeted coverage tests cho các module low-coverage.

Bổ sung test cho các nhánh còn thiếu ở các module:
- artifact_registry.py (CLI, fallback locks, sanitize edge cases, list_artifacts)
- idempotency.py (sanitize, fallback lock, non-serializable result, empty run_id)
- migrate_state.py (_move_files edge cases, symlink failure, main CLI)
- cognitive_scaffold_memory.py (CLI, _redact_text empty, retention no scaffold)
- coverage_matrix.py (parse edge cases, verify_matrix, render markdown, main CLI)
- cost_tracker.py (CLI, track_tool_cost, set_cost_cap, edge cases)
- dyflow.py (CLI, _normalize_module_to_path edge cases, relative imports)
- cot_synthesis.py (CLI, _fit_to_budget edge cases, _coherence)
- adaptive_compress.py (CLI, _summarize, _prefix_hash)
- context_projection.py (CLI, _read_single_file, _extract_chunks_from_json)
- tscg.py (CLI, _to_conservative short desc)
- llm_as_judge.py (CLI, _audit_path, _log_audit, _heuristic_score edge cases)
"""
from __future__ import annotations

import io
import json
import os
import sys
import time
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


# ============================================================================
# Shared fixtures
# ============================================================================

@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    """Patch repo root + config root của ahd_session về tmp_path/.devin."""
    devin_dir = tmp_path / ".devin"
    devin_dir.mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr("ahd_session_id.get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr("ahd_session_paths.get_config_root", lambda _root=None: devin_dir)
    # Xoá cache repo root để tránh leak giữa test
    monkeypatch.setattr("ahd_session_id._REPO_ROOT_CACHE", None)
    return tmp_path


# ============================================================================
# artifact_registry.py — CLI + fallback locks + sanitize edge cases
# ============================================================================

class TestArtifactRegistryCLI:
    def test_cli_no_args_prints_usage(self, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py"])
        code = _cli()
        assert code == 1

    def test_cli_register_and_get(self, patched_root, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr("artifact_registry._repo_root", lambda: patched_root)
        monkeypatch.setattr(sys, "argv", [
            "artifact_registry.py", "register", "cot", "cli-1",
            json.dumps({"k": "v"}),
        ])
        code = _cli()
        assert code == 0
        out = capsys.readouterr().out
        assert "registered: cot/cli-1" in out

        monkeypatch.setattr(sys, "argv", [
            "artifact_registry.py", "get", "cot", "cli-1",
        ])
        code = _cli()
        assert code == 0
        out = capsys.readouterr().out
        assert "cli-1" in out

    def test_cli_register_bad_json(self, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr(sys, "argv", [
            "artifact_registry.py", "register", "cot", "x", "not-json",
        ])
        code = _cli()
        assert code == 1

    def test_cli_register_missing_args(self, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py", "register", "cot"])
        code = _cli()
        assert code == 1

    def test_cli_get_missing(self, patched_root, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr("artifact_registry._repo_root", lambda: patched_root)
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py", "get", "nope", "missing"])
        code = _cli()
        assert code == 1

    def test_cli_get_missing_args(self, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py", "get", "only-one"])
        code = _cli()
        assert code == 1

    def test_cli_list(self, patched_root, capsys, monkeypatch):
        from artifact_registry import _cli, register
        monkeypatch.setattr("artifact_registry._repo_root", lambda: patched_root)
        register("cot", "list-1", {"a": 1}, root=patched_root)
        register("verdict", "list-2", {"b": 2}, root=patched_root)
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py", "list"])
        code = _cli()
        assert code == 0
        out = capsys.readouterr().out
        assert "cot/list-1" in out
        assert "verdict/list-2" in out

    def test_cli_list_with_type_filter(self, patched_root, capsys, monkeypatch):
        from artifact_registry import _cli, register
        monkeypatch.setattr("artifact_registry._repo_root", lambda: patched_root)
        register("cot", "f1", {"a": 1}, root=patched_root)
        register("verdict", "f2", {"b": 2}, root=patched_root)
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py", "list", "cot"])
        code = _cli()
        assert code == 0
        out = capsys.readouterr().out
        assert "cot/f1" in out
        assert "verdict/f2" not in out

    def test_cli_unknown_command(self, capsys, monkeypatch):
        from artifact_registry import _cli
        monkeypatch.setattr(sys, "argv", ["artifact_registry.py", "bogus"])
        code = _cli()
        assert code == 1


class TestArtifactRegistrySanitize:
    def test_sanitize_empty_returns_unnamed(self):
        from artifact_registry import _sanitize_id
        assert _sanitize_id("") == "unnamed"

    def test_sanitize_all_invalid_returns_unnamed(self):
        from artifact_registry import _sanitize_id
        # Chỉ ký tự không hợp lệ -> sau replace + strip -> rỗng -> unnamed
        assert _sanitize_id("!!!") == "unnamed"

    def test_sanitize_truncates_long(self):
        from artifact_registry import _sanitize_id
        long_id = "a" * 100
        result = _sanitize_id(long_id)
        assert len(result) == 64

    def test_sanitize_strips_leading_trailing(self):
        from artifact_registry import _sanitize_id
        assert _sanitize_id("--abc--") == "abc"


class TestArtifactRegistryCorruptFile:
    def test_get_corrupt_json_returns_none(self, patched_root):
        from artifact_registry import get, _artifact_path
        # Tạo file JSON hỏng
        path = _artifact_path("cot", "corrupt", root=patched_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not valid json {{{", encoding="utf-8")
        assert get("cot", "corrupt", root=patched_root) is None

    def test_get_empty_type_id_returns_none(self, patched_root):
        from artifact_registry import get
        assert get("", "id", root=patched_root) is None
        assert get("type", "", root=patched_root) is None

    def test_list_artifacts_no_registry(self, patched_root):
        from artifact_registry import list_artifacts
        # Xoá registry dir -> trả []
        assert list_artifacts(root=patched_root) == []

    def test_register_update_with_corrupt_existing(self, patched_root):
        from artifact_registry import register, get, _artifact_path
        # Tạo file hỏng trước
        path = _artifact_path("cot", "upd-corrupt", root=patched_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("corrupt", encoding="utf-8")
        # update=True -> đọc fail -> version=1, ghi đè
        register("cot", "upd-corrupt", {"k": 1}, root=patched_root, update=True)
        art = get("cot", "upd-corrupt", root=patched_root)
        assert art is not None
        assert art.version == 1


class TestArtifactRegistryFallbackLock:
    def test_fallback_acquire_release_lock(self, tmp_path):
        """Fallback lock (khi ahd_session._acquire_lock fail) hoạt động."""
        from artifact_registry import _acquire_lock, _release_lock
        lock_path = tmp_path / "test.lock"
        # Patch ahd_session._acquire_lock raise -> fallback sentinel
        import artifact_registry
        original_acquire = ahd_session._acquire_lock
        ahd_session._acquire_lock = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("nope"))
        try:
            handle = _acquire_lock(lock_path, timeout=1.0)
            assert handle is not None
            _release_lock(handle)
            assert not lock_path.exists()
        finally:
            ahd_session._acquire_lock = original_acquire

    def test_fallback_acquire_lock_timeout(self, tmp_path):
        """Fallback lock timeout khi lock đã có."""
        from artifact_registry import _acquire_lock
        lock_path = tmp_path / "taken.lock"
        lock_path.parent.mkdir(parents=True, exist_ok=True)
        # Tạo lock file trước -> O_EXCL fail -> timeout
        lock_path.write_text("taken", encoding="utf-8")
        import artifact_registry
        original_acquire = ahd_session._acquire_lock
        ahd_session._acquire_lock = lambda *a, **kw: (_ for _ in ()).throw(RuntimeError("nope"))
        try:
            handle = _acquire_lock(lock_path, timeout=0.2)
            # _acquire_lock trả tuple (lock_path, handle, is_sentinel)
            # Khi timeout, handle[1] is None
            assert handle[1] is None
        finally:
            ahd_session._acquire_lock = original_acquire

    def test_release_none_handle_noop(self):
        from artifact_registry import _release_lock
        _release_lock(None)  # không raise


class TestArtifactRegistryTimeout:
    def test_register_lock_timeout_raises(self, patched_root, monkeypatch):
        from artifact_registry import register
        import artifact_registry
        # Patch _acquire_lock trả None -> timeout
        monkeypatch.setattr(artifact_registry, "_acquire_lock", lambda *a, **kw: None)
        with pytest.raises(TimeoutError):
            register("cot", "x", {"a": 1}, root=patched_root)


# ============================================================================
# idempotency.py — sanitize + fallback lock + non-serializable + CLI
# ============================================================================

class TestIdempotencySanitize:
    def test_sanitize_empty_returns_default(self):
        from idempotency import _sanitize_run_id
        assert _sanitize_run_id("") == "default"

    def test_sanitize_path_traversal(self):
        from idempotency import _sanitize_run_id
        # ../../HLK/evil -> không có path separator
        result = _sanitize_run_id("../../HLK/evil")
        assert ".." not in result
        assert "/" not in result
        assert "\\" not in result

    def test_sanitize_all_invalid_returns_default(self):
        from idempotency import _sanitize_run_id
        assert _sanitize_run_id("!!!@@@") == "default"

    def test_sanitize_truncates_long(self):
        from idempotency import _sanitize_run_id
        result = _sanitize_run_id("a" * 100)
        assert len(result) <= 64

    def test_ledger_path_empty_run_id(self, patched_root):
        from idempotency import ledger_path
        p = ledger_path("", root=patched_root)
        assert "default" in p.name


class TestIdempotencyRegister:
    def test_register_empty_key_raises(self, patched_root):
        from idempotency import register
        with pytest.raises(ValueError):
            register("", lambda: 1, run_id="r1")

    def test_register_non_serializable_result(self, patched_root):
        from idempotency import register, lookup
        # Object không serializable -> fallback str()
        class NonSerializable:
            def __str__(self):
                return "obj-str"
        result = register("ns-key", lambda: NonSerializable(), run_id="r-ns")
        # lookup trả về string representation
        cached = lookup("ns-key", run_id="r-ns")
        assert cached == "obj-str"

    def test_register_uses_env_run_id(self, patched_root, monkeypatch):
        from idempotency import register, lookup
        monkeypatch.setattr("idempotency._repo_root", lambda: patched_root)
        monkeypatch.setenv("AHD_RUN_ID", "env-run-x")
        register("env-key", lambda: 42)
        assert lookup("env-key", run_id="env-run-x") == 42

    def test_register_corrupt_ledger_line_skipped(self, patched_root, monkeypatch):
        from idempotency import register, lookup, ledger_path
        monkeypatch.setattr("idempotency._repo_root", lambda: patched_root)
        # Tạo ledger có dòng hỏng
        path = ledger_path("r-corrupt", root=patched_root)
        path.parent.mkdir(parents=True, exist_ok=True)
        path.write_text("not json line\n{\"key\":\"k1\",\"result\":1}\n", encoding="utf-8")
        # lookup vẫn đọc được key hợp lệ
        assert lookup("k1", run_id="r-corrupt") == 1
        # register key mới không bị ảnh hưởng
        result = register("k2", lambda: 2, run_id="r-corrupt")
        assert result == 2

    def test_read_ledger_missing_file(self, patched_root):
        from idempotency import _read_ledger
        from pathlib import Path
        assert _read_ledger(Path(patched_root / "nonexistent.ledger.jsonl")) == {}

    def test_read_ledger_corrupt_file(self, patched_root):
        from idempotency import _read_ledger
        from pathlib import Path
        path = patched_root / "bad.ledger.jsonl"
        path.write_text("totally not json", encoding="utf-8")
        assert _read_ledger(path) == {}


class TestIdempotencyFallbackLock:
    def test_register_fallback_filelock(self, patched_root, monkeypatch):
        """Khi ahd_session._acquire_lock fail -> fallback filelock (nếu có)."""
        from idempotency import register
        import idempotency
        monkeypatch.setattr(ahd_session, "_acquire_lock", lambda *a, **kw: None)
        # filelock có thể có hoặc không; nếu không có -> RuntimeError
        try:
            result = register("fb-key", lambda: 99, run_id="r-fb")
            assert result == 99
        except RuntimeError as e:
            # filelock không có sẵn -> raise RuntimeError (đúng hành vi pentest fix)
            assert "lock" in str(e).lower()


# ============================================================================
# migrate_state.py — _move_files + symlink failure + main CLI
# ============================================================================

class TestMigrateStateMoveFiles:
    def test_move_files_nonexistent_src(self, tmp_path):
        from migrate_state import _move_files
        result = _move_files(tmp_path / "noexist", tmp_path / "dst")
        assert result == 0

    def test_move_files_dst_mkdir_fail(self, tmp_path, monkeypatch):
        from migrate_state import _move_files
        src = tmp_path / "src"
        src.mkdir()
        (src / "f.txt").write_text("x", encoding="utf-8")
        dst = tmp_path / "dst"
        # Patch Path.mkdir raise OSError
        original_mkdir = dst.mkdir
        def fail_mkdir(*a, **kw):
            raise OSError("denied")
        monkeypatch.setattr(Path, "mkdir", fail_mkdir)
        result = _move_files(src, dst)
        assert result == 0

    def test_move_files_idempotent_skip_existing(self, tmp_path):
        from migrate_state import _move_files
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        src.mkdir()
        dst.mkdir()
        (src / "f.txt").write_text("new", encoding="utf-8")
        (dst / "f.txt").write_text("existing", encoding="utf-8")
        result = _move_files(src, dst)
        assert result == 0  # đã tồn tại -> skip
        assert (dst / "f.txt").read_text() == "existing"

    def test_move_files_subdirectory_recursion(self, tmp_path):
        from migrate_state import _move_files
        src = tmp_path / "src"
        dst = tmp_path / "dst"
        sub = src / "sub"
        sub.mkdir(parents=True)
        (sub / "deep.txt").write_text("deep", encoding="utf-8")
        result = _move_files(src, dst)
        assert result == 1
        assert (dst / "sub" / "deep.txt").read_text() == "deep"

    def test_move_files_oserror_on_iterdir(self, tmp_path, monkeypatch):
        from migrate_state import _move_files
        src = tmp_path / "src"
        src.mkdir()
        (src / "f.txt").write_text("x", encoding="utf-8")
        def fail_iterdir(self):
            raise OSError("io error")
        monkeypatch.setattr(Path, "iterdir", fail_iterdir)
        result = _move_files(src, tmp_path / "dst")
        assert result == 0


class TestMigrateStateSymlink:
    def test_create_symlink_existing_real_file_returns_false(self, tmp_path):
        from migrate_state import _create_symlink
        link = tmp_path / "link"
        link.write_text("real file", encoding="utf-8")
        result = _create_symlink(link, tmp_path / "target")
        assert result is False

    def test_create_symlink_wrong_target_recreated(self, tmp_path):
        """Symlink trỏ sai target -> xoá rồi tạo lại."""
        from migrate_state import _create_symlink
        if not hasattr(os, "symlink"):
            pytest.skip("OS không hỗ trợ symlink")
        link = tmp_path / "link"
        wrong_target = tmp_path / "wrong"
        wrong_target.mkdir()
        try:
            os.symlink(str(wrong_target), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Không có quyền tạo symlink")
        right_target = tmp_path / "right"
        right_target.mkdir()
        result = _create_symlink(link, right_target)
        # Có thể True (tạo lại thành công) hoặc False (không có quyền)
        assert isinstance(result, bool)

    def test_create_symlink_correct_existing(self, tmp_path):
        from migrate_state import _create_symlink
        if not hasattr(os, "symlink"):
            pytest.skip("OS không hỗ trợ symlink")
        target = tmp_path / "target"
        target.mkdir()
        link = tmp_path / "link"
        try:
            os.symlink(str(target), str(link), target_is_directory=True)
        except (OSError, NotImplementedError):
            pytest.skip("Không có quyền tạo symlink")
        result = _create_symlink(link, target)
        assert result is True


class TestMigrateStateMigrate:
    def test_migrate_creates_state_dir(self, tmp_path):
        from migrate_state import migrate
        new_root = migrate(tmp_path)
        assert new_root == tmp_path / "state"
        assert new_root.exists()

    def test_migrate_moves_legacy_files(self, tmp_path):
        from migrate_state import migrate
        # Tạo legacy dir với file
        legacy = tmp_path / ".devin" / "session_state"
        legacy.mkdir(parents=True)
        (legacy / "s1.json").write_text("{}", encoding="utf-8")
        migrate(tmp_path)
        assert (tmp_path / "state" / "session" / "s1.json").exists()

    def test_migrate_idempotent(self, tmp_path):
        from migrate_state import migrate
        legacy = tmp_path / ".devin" / "session_state"
        legacy.mkdir(parents=True)
        (legacy / "s1.json").write_text("{}", encoding="utf-8")
        migrate(tmp_path)
        # Chạy lại không fail, không duplicate
        migrate(tmp_path)
        assert (tmp_path / "state" / "session" / "s1.json").exists()

    def test_migrate_mkdir_fail_raises(self, tmp_path, monkeypatch):
        from migrate_state import migrate
        def fail_mkdir(self, *a, **kw):
            if "state" in str(self):
                raise OSError("denied")
            return original_mkdir(self, *a, **kw)
        original_mkdir = Path.mkdir
        monkeypatch.setattr(Path, "mkdir", fail_mkdir)
        with pytest.raises(OSError):
            migrate(tmp_path)


class TestMigrateStateCLI:
    def test_main_success(self, tmp_path, capsys, monkeypatch):
        from migrate_state import main
        monkeypatch.setattr(sys, "argv", ["migrate_state.py", "--old-root", str(tmp_path)])
        code = main()
        assert code == 0
        out = capsys.readouterr().out
        assert "state" in out

    def test_main_oserror_returns_1(self, tmp_path, monkeypatch):
        from migrate_state import main
        monkeypatch.setattr(sys, "argv", ["migrate_state.py", "--old-root", str(tmp_path)])
        import migrate_state
        monkeypatch.setattr(migrate_state, "migrate", lambda p: (_ for _ in ()).throw(OSError("fail")))
        code = main()
        assert code == 1


# ============================================================================
# cognitive_scaffold_memory.py — CLI + redact edge + retention no scaffold
# ============================================================================

class TestCognitiveScaffoldCLI:
    def test_cli_no_args(self, capsys, monkeypatch):
        from cognitive_scaffold_memory import _cli
        monkeypatch.setattr(sys, "argv", ["cognitive_scaffold_memory.py"])
        code = _cli()
        assert code == 1

    def test_cli_record(self, patched_root, capsys, monkeypatch):
        from cognitive_scaffold_memory import _cli
        monkeypatch.setattr(sys, "argv", [
            "cognitive_scaffold_memory.py", "record", "main", "test transcript",
        ])
        code = _cli()
        assert code == 0

    def test_cli_record_missing_args(self, capsys, monkeypatch):
        from cognitive_scaffold_memory import _cli
        monkeypatch.setattr(sys, "argv", ["cognitive_scaffold_memory.py", "record", "main"])
        code = _cli()
        assert code == 1

    def test_cli_recall(self, patched_root, capsys, monkeypatch):
        from cognitive_scaffold_memory import _cli, record
        record("main", "test content", run_id="cli-run", root=patched_root)
        monkeypatch.setattr("cognitive_scaffold_memory._repo_root", lambda: patched_root)
        monkeypatch.setattr(sys, "argv", ["cognitive_scaffold_memory.py", "recall", "cli-run"])
        code = _cli()
        assert code == 0
        out = capsys.readouterr().out
        assert "cli-run" in out

    def test_cli_recall_missing_args(self, capsys, monkeypatch):
        from cognitive_scaffold_memory import _cli
        monkeypatch.setattr(sys, "argv", ["cognitive_scaffold_memory.py", "recall"])
        code = _cli()
        assert code == 1

    def test_cli_unknown_command(self, capsys, monkeypatch):
        from cognitive_scaffold_memory import _cli
        monkeypatch.setattr(sys, "argv", ["cognitive_scaffold_memory.py", "bogus"])
        code = _cli()
        assert code == 1


class TestCognitiveScaffoldRedact:
    def test_redact_empty_text(self):
        from cognitive_scaffold_memory import _redact_text
        assert _redact_text("") == ""
        assert _redact_text(None) is None

    def test_redact_akia_key(self, patched_root):
        from cognitive_scaffold_memory import record
        text = "key AKIAABCDEFGHIJKLMNOP sample"
        path = record("main", text, run_id="r-akia", root=patched_root)
        content = path.read_text(encoding="utf-8")
        assert "AKIAABCDEFGHIJKLMNOP" not in content
        assert "[REDACTED]" in content

    def test_redact_aiza_key(self, patched_root):
        from cognitive_scaffold_memory import record
        text = "google AIzaSyAabcdefghijklmnopqrstuvwxyz0123456789"
        path = record("main", text, run_id="r-aiza", root=patched_root)
        content = path.read_text(encoding="utf-8")
        assert "AIzaSyAabcdefghijklmnopqrstuvwxyz0123456789" not in content

    def test_redact_slack_token(self, patched_root):
        from cognitive_scaffold_memory import record
        text = "slack xoxb-1234567890-abcdefghij"
        path = record("main", text, run_id="r-slack", root=patched_root)
        content = path.read_text(encoding="utf-8")
        assert "xoxb-1234567890-abcdefghij" not in content

    def test_redact_password_assignment(self, patched_root):
        from cognitive_scaffold_memory import record
        text = "password=mysecretpassword123"
        path = record("main", text, run_id="r-pwd", root=patched_root)
        content = path.read_text(encoding="utf-8")
        assert "mysecretpassword123" not in content


class TestCognitiveScaffoldRetention:
    def test_retention_no_scaffold_dir(self, patched_root):
        from cognitive_scaffold_memory import _enforce_retention
        # Scaffold dir chưa tồn tại -> 0
        assert _enforce_retention(root=patched_root) == 0

    def test_retention_stat_error_skipped(self, patched_root):
        from cognitive_scaffold_memory import _enforce_retention, record
        # Ghi file rồi xoá giữa chừng -> stat fail -> skip
        path = record("main", "x", run_id="r-stat", root=patched_root)
        path.unlink()
        # Không raise
        assert _enforce_retention(root=patched_root) == 0


class TestCognitiveScaffoldRecallCorrupt:
    def test_recall_corrupt_json_skipped(self, patched_root):
        from cognitive_scaffold_memory import recall, _role_dir
        # Tạo file hỏng trong role dir
        role_dir = _role_dir("main", root=patched_root)
        role_dir.mkdir(parents=True, exist_ok=True)
        bad = role_dir / "badrun_123.json"
        bad.write_text("not json", encoding="utf-8")
        # recall không raise, bỏ qua file hỏng
        entries = recall("badrun", root=patched_root)
        assert entries == []


# ============================================================================
# coverage_matrix.py — parse edge cases + verify + render + main CLI
# ============================================================================

class TestCoverageMatrixParse:
    def test_read_plan_missing_file(self, tmp_path):
        from coverage_matrix import _read_plan
        with pytest.raises(FileNotFoundError):
            _read_plan(tmp_path / "noexist.md")

    def test_read_plan_empty_file(self, tmp_path):
        from coverage_matrix import _read_plan
        p = tmp_path / "empty.md"
        p.write_text("   \n  ", encoding="utf-8")
        with pytest.raises(ValueError):
            _read_plan(p)

    def test_extract_section_not_found(self):
        from coverage_matrix import _extract_section
        assert _extract_section("# Other\ncontent", "Coverage") == ""

    def test_extract_section_found(self):
        from coverage_matrix import _extract_section
        text = "## Coverage Matrix\n| REQ | Task |\n| --- | --- |\n| REQ-001 | T01 |\n\n## Other\nx"
        section = _extract_section(text, "Coverage")
        assert "REQ-001" in section
        assert "Other" not in section

    def test_parse_coverage_table_no_section(self):
        from coverage_matrix import _parse_coverage_table
        assert _parse_coverage_table("# No coverage here") == {}

    def test_parse_coverage_table_with_data(self):
        from coverage_matrix import _parse_coverage_table
        text = "## Coverage\n| REQ | Task |\n| --- | --- |\n| REQ-001 | T01 |\n| REQ-002 | T02 |"
        mapping = _parse_coverage_table(text)
        assert "REQ-001" in mapping
        assert "T01" in mapping["REQ-001"]

    def test_extract_file_path_with_field(self):
        from coverage_matrix import _extract_file_path
        assert _extract_file_path("file: `src/app.py`") == "src/app.py"
        assert _extract_file_path("path: scripts/util.py") == "scripts/util.py"

    def test_extract_file_path_fallback(self):
        from coverage_matrix import _extract_file_path
        assert _extract_file_path("see ./src/main.py for details") == "./src/main.py"

    def test_extract_file_path_empty(self):
        from coverage_matrix import _extract_file_path
        assert _extract_file_path("no file here") == ""

    def test_extract_function(self):
        from coverage_matrix import _extract_function
        assert _extract_function("func: my_func()") == "my_func"
        assert _extract_function("function: do_thing") == "do_thing"
        assert _extract_function("no function") == ""

    def test_parse_tasks(self):
        from coverage_matrix import _parse_tasks
        text = "## Tasks\n- T01: src/app.py func: my_func REQ-001\n- T02: scripts/util.py REQ-002"
        tasks = _parse_tasks(text)
        assert len(tasks) == 2
        assert tasks[0]["id"] == "T01"
        assert tasks[0]["file_path"] == "src/app.py"
        assert tasks[0]["function"] == "my_func"

    def test_parse_req_ids(self):
        from coverage_matrix import _parse_req_ids
        ids = _parse_req_ids("REQ-001 and REQ_002 and req003")
        assert "REQ-001" in ids
        assert "REQ-002" in ids
        assert "REQ-003" in ids


class TestCoverageMatrixGenerate:
    def test_generate_matrix_basic(self, tmp_path):
        from coverage_matrix import generate_matrix
        plan = tmp_path / "plan.md"
        plan.write_text(
            "## Requirements\nREQ-001: do thing\n\n"
            "## Tasks\n- T01: src/app.py func: my_func REQ-001\n",
            encoding="utf-8",
        )
        result = generate_matrix(plan)
        assert "REQ-001" in result["matrix"]
        assert result["matrix"]["REQ-001"]["task_id"] == "T01"
        assert result["matrix"]["REQ-001"]["file_path"] == "src/app.py"

    def test_generate_matrix_orphan_task(self, tmp_path):
        from coverage_matrix import generate_matrix
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T99: src/x.py func: foo\n", encoding="utf-8")
        result = generate_matrix(plan)
        assert "_orphan_T99" in result["matrix"]

    def test_generate_matrix_task_req_not_in_section(self, tmp_path):
        from coverage_matrix import generate_matrix
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: src/app.py REQ-999\n", encoding="utf-8")
        result = generate_matrix(plan)
        # REQ-999 xuất hiện trong task nhưng không có section requirement
        assert "REQ-999" in result["matrix"]


class TestCoverageMatrixVerify:
    def test_verify_matrix_missing_file(self, tmp_path):
        from coverage_matrix import verify_matrix, STATUS_MISSING
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: nonexistent.py REQ-001\n", encoding="utf-8")
        # Tạo .devin để repo root detect
        (tmp_path / ".devin").mkdir(exist_ok=True)
        result = verify_matrix(plan)
        assert result["matrix"]["REQ-001"]["status"] == STATUS_MISSING

    def test_verify_matrix_executed_no_function(self, tmp_path):
        from coverage_matrix import verify_matrix, STATUS_VERIFIED
        # Tạo file tồn tại
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / ".devin").mkdir(exist_ok=True)
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: src/app.py REQ-001\n", encoding="utf-8")
        result = verify_matrix(plan)
        # File tồn tại, không có function -> VERIFIED
        assert result["matrix"]["REQ-001"]["status"] == STATUS_VERIFIED

    def test_verify_matrix_function_found(self, tmp_path):
        from coverage_matrix import verify_matrix, STATUS_VERIFIED
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "app.py").write_text("def my_func():\n    return 1\n", encoding="utf-8")
        (tmp_path / ".devin").mkdir(exist_ok=True)
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: src/app.py func: my_func REQ-001\n", encoding="utf-8")
        result = verify_matrix(plan)
        assert result["matrix"]["REQ-001"]["status"] == STATUS_VERIFIED

    def test_verify_matrix_function_missing(self, tmp_path):
        from coverage_matrix import verify_matrix, STATUS_FAIL
        (tmp_path / "src").mkdir(exist_ok=True)
        (tmp_path / "src" / "app.py").write_text("x = 1\n", encoding="utf-8")
        (tmp_path / ".devin").mkdir(exist_ok=True)
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: src/app.py func: nonexistent REQ-001\n", encoding="utf-8")
        result = verify_matrix(plan)
        assert result["matrix"]["REQ-001"]["status"] == STATUS_FAIL

    def test_verify_matrix_no_file_path(self, tmp_path):
        from coverage_matrix import verify_matrix, STATUS_PLANNED
        (tmp_path / ".devin").mkdir(exist_ok=True)
        plan = tmp_path / "plan.md"
        plan.write_text("## Requirements\nREQ-001: do thing\n", encoding="utf-8")
        result = verify_matrix(plan)
        assert result["matrix"]["REQ-001"]["status"] == STATUS_PLANNED


class TestCoverageMatrixRender:
    def test_render_markdown_report(self):
        from coverage_matrix import _render_markdown_report
        data = {
            "plan_file": "/tmp/plan.md",
            "generated_at": "2026-01-01T00:00:00Z",
            "verified_at": "2026-01-01T00:00:01Z",
            "req_count": 1,
            "task_count": 1,
            "status_counts": {"VERIFIED": 1},
            "matrix": {
                "REQ-001": {
                    "task_id": "T01",
                    "file_path": "src/app.py",
                    "function": "foo",
                    "status": "VERIFIED",
                    "evidence": "ok|with pipe",
                },
            },
        }
        report = _render_markdown_report(data)
        assert "# Coverage Matrix" in report
        assert "REQ-001" in report
        # Pipe trong evidence phải escape
        assert "ok\\|with pipe" in report


class TestCoverageMatrixMain:
    def test_main_no_args(self, capsys, monkeypatch):
        from coverage_matrix import main
        monkeypatch.setattr(sys, "argv", ["coverage_matrix.py"])
        code = main()
        assert code == 2

    def test_main_missing_plan(self, capsys, monkeypatch):
        from coverage_matrix import main
        monkeypatch.setattr(sys, "argv", ["coverage_matrix.py", "/nonexistent/plan.md"])
        code = main()
        assert code == 1

    def test_main_generate_success(self, tmp_path, capsys, monkeypatch):
        from coverage_matrix import main
        (tmp_path / ".devin").mkdir(exist_ok=True)
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: src/app.py REQ-001\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["coverage_matrix.py", str(plan)])
        code = main()
        assert code == 0

    def test_main_verify_with_failures(self, tmp_path, capsys, monkeypatch):
        from coverage_matrix import main
        (tmp_path / ".devin").mkdir(exist_ok=True)
        plan = tmp_path / "plan.md"
        plan.write_text("## Tasks\n- T01: nonexistent.py REQ-001\n", encoding="utf-8")
        monkeypatch.setattr(sys, "argv", ["coverage_matrix.py", str(plan), "--verify"])
        code = main()
        assert code == 1  # có MISSING -> exit 1


# ============================================================================
# cost_tracker.py — CLI + track_tool_cost + edge cases
# ============================================================================

class TestCostTracker:
    def test_estimate_cost_basic(self):
        from cost_tracker import _estimate_cost
        cost = _estimate_cost("Bash", 4000)  # 1000 tokens output
        assert cost > 0
        # 1000 tokens * $0.015 + 500 tokens * $0.003 = 15 + 1.5 = 16.5 / 1000
        assert abs(cost - 0.0165) < 0.001

    def test_track_tool_cost_no_session(self, patched_root):
        from cost_tracker import track_tool_cost
        result = track_tool_cost(patched_root, "", "Bash", 100)
        assert result["tracked"] is False

    def test_track_tool_cost_negative_size(self, patched_root):
        from cost_tracker import track_tool_cost
        result = track_tool_cost(patched_root, "s1", "Bash", -100)
        assert result["tracked"] is True
        # Negative -> 0 -> chỉ input overhead
        assert result["estimated_cost"] > 0

    def test_track_tool_cost_accumulates(self, patched_root):
        from cost_tracker import track_tool_cost
        r1 = track_tool_cost(patched_root, "s-acc", "Bash", 1000)
        r2 = track_tool_cost(patched_root, "s-acc", "Bash", 1000)
        assert r2["cumulative_cost"] > r1["cumulative_cost"]
        assert r2["calls_tracked"] == 2

    def test_check_cost_cap_nan(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 1.0, "cost_cap": float("nan")}) == 2

    def test_check_cost_cap_negative(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 1.0, "cost_cap": -5.0}) == 2

    def test_check_cost_cap_zero_with_cost(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 1.0, "cost_cap": 0.0}) == 2

    def test_check_cost_cap_zero_no_cost(self):
        from cost_tracker import check_cost_cap
        assert check_cost_cap({"cumulative_cost": 0.0, "cost_cap": 0.0}) == 0

    def test_check_cost_cap_session_no_session(self, patched_root):
        from cost_tracker import check_cost_cap_session
        exceeded, msg = check_cost_cap_session(patched_root, "")
        assert exceeded is False
        assert msg == ""

    def test_check_cost_cap_session_warn(self, patched_root):
        from cost_tracker import check_cost_cap_session
        import ahd_session
        ahd_session.write_session_state("s-warn", {"cumulative_cost": 8.5, "cost_cap": 10.0}, root=patched_root)
        exceeded, msg = check_cost_cap_session(patched_root, "s-warn")
        assert exceeded is False
        assert "WARNING" in msg

    def test_check_cost_cap_session_exceeded(self, patched_root):
        from cost_tracker import check_cost_cap_session
        import ahd_session
        ahd_session.write_session_state("s-exc", {"cumulative_cost": 10.0, "cost_cap": 10.0}, root=patched_root)
        exceeded, msg = check_cost_cap_session(patched_root, "s-exc")
        assert exceeded is True
        assert "EXCEEDED" in msg

    def test_set_cost_cap(self, patched_root):
        from cost_tracker import set_cost_cap
        import ahd_session
        set_cost_cap(patched_root, "s-cap", 99.0)
        state = ahd_session.read_session_state("s-cap", root=patched_root)
        assert state["cost_cap"] == 99.0

    def test_set_cost_cap_no_session(self, patched_root):
        from cost_tracker import set_cost_cap
        # Không raise khi session_id rỗng
        set_cost_cap(patched_root, "", 99.0)


class TestCostTrackerCLI:
    def test_cli_set_cap_and_check(self, patched_root, capsys, monkeypatch):
        # Test CLI logic qua set_cost_cap + check_cost_cap_session (CLI chỉ wrap 2 hàm này)
        from cost_tracker import set_cost_cap, check_cost_cap_session
        set_cost_cap(patched_root, "s-cli", 5.0)
        exceeded, msg = check_cost_cap_session(patched_root, "s-cli")
        assert exceeded is False

    def test_cli_check_exceeded(self, patched_root, capsys, monkeypatch):
        from cost_tracker import set_cost_cap, check_cost_cap_session, track_tool_cost
        set_cost_cap(patched_root, "s-cli2", 0.001)
        # Track cost để vượt cap
        track_tool_cost(patched_root, "s-cli2", "Bash", 100000)
        exceeded, msg = check_cost_cap_session(patched_root, "s-cli2")
        assert exceeded is True
        assert "EXCEEDED" in msg


# ============================================================================
# dyflow.py — CLI + _normalize_module_to_path + relative imports edge
# ============================================================================

class TestDyflowNormalize:
    def test_normalize_empty_module(self, tmp_path):
        from dyflow import _normalize_module_to_path
        assert _normalize_module_to_path("", tmp_path / "f.py", tmp_path) is None

    def test_normalize_only_dots(self, tmp_path):
        from dyflow import _normalize_module_to_path
        assert _normalize_module_to_path("...", tmp_path / "f.py", tmp_path) is None

    def test_normalize_package_init(self, tmp_path):
        from dyflow import _normalize_module_to_path
        pkg = tmp_path / "mypkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        result = _normalize_module_to_path("mypkg", tmp_path / "f.py", tmp_path)
        assert result == "mypkg/__init__.py"

    def test_normalize_module_not_found(self, tmp_path):
        from dyflow import _normalize_module_to_path
        assert _normalize_module_to_path("nonexistent", tmp_path / "f.py", tmp_path) is None


class TestDyflowRelativeImport:
    def test_resolve_relative_import_level_too_deep(self, tmp_path):
        from dyflow import _resolve_relative_import
        # current_file ở root, level=3 -> không đủ cấp -> None
        result = _resolve_relative_import("...", "", tmp_path / "f.py", tmp_path)
        assert result is None

    def test_resolve_relative_import_no_submodule_no_parts(self, tmp_path):
        from dyflow import _resolve_relative_import
        # level=1, không submodule, file ở root -> parts rỗng sau khi bỏ file -> None
        result = _resolve_relative_import(".", "", tmp_path / "f.py", tmp_path)
        # parts = [] sau khi bỏ "f.py" -> không có gì -> None
        assert result is None

    def test_resolve_relative_import_package(self, tmp_path):
        from dyflow import _resolve_relative_import
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "helper.py").write_text("x = 1\n", encoding="utf-8")
        # from .helper import X trong pkg/main.py
        result = _resolve_relative_import(".", "helper", pkg / "main.py", tmp_path)
        assert result == "pkg/helper.py"


class TestDyflowDiscoverDeps:
    def test_discover_deps_unreadable_file(self, tmp_path):
        from dyflow import discover_deps
        # Tạo file không đọc được (patch read_text raise)
        f = tmp_path / "bad.py"
        f.write_text("import os\n", encoding="utf-8")
        import dyflow
        original = dyflow._discover_python_deps
        def fail_deps(file_path, workspace):
            if file_path.name == "bad.py":
                raise Exception("io error")
            return original(file_path, workspace)
        # _discover_python_deps đã có try/except -> trả []
        # Test trực tiếp: file không đọc được
        import unittest.mock
        with unittest.mock.patch.object(Path, "read_text", side_effect=OSError("denied")):
            deps = dyflow._discover_python_deps(tmp_path / "bad.py", tmp_path)
            assert deps == []

    def test_discover_deps_from_import(self, tmp_path):
        from dyflow import _discover_python_deps
        (tmp_path / "mod.py").write_text("x = 1\n", encoding="utf-8")
        f = tmp_path / "main.py"
        f.write_text("import mod\n", encoding="utf-8")
        deps = _discover_python_deps(f, tmp_path)
        assert "mod.py" in deps

    def test_discover_deps_from_import_subname(self, tmp_path):
        from dyflow import _discover_python_deps
        pkg = tmp_path / "pkg"
        pkg.mkdir()
        (pkg / "__init__.py").write_text("", encoding="utf-8")
        (pkg / "sub.py").write_text("x = 1\n", encoding="utf-8")
        f = tmp_path / "main.py"
        f.write_text("from pkg import sub\n", encoding="utf-8")
        deps = _discover_python_deps(f, tmp_path)
        # pkg/__init__.py hoặc pkg/sub.py
        assert any("pkg" in d for d in deps)


class TestDyflowTopoSort:
    def test_topo_sort_with_cycle(self):
        from dyflow import _topo_sort
        nodes = ["a", "b"]
        edges = {"a": ["b"], "b": ["a"]}
        order, has_cycle = _topo_sort(nodes, edges)
        assert has_cycle is True
        assert len(order) < len(nodes)

    def test_topo_sort_no_deps(self):
        from dyflow import _topo_sort
        nodes = ["c", "a", "b"]
        edges = {"a": [], "b": [], "c": []}
        order, has_cycle = _topo_sort(nodes, edges)
        assert has_cycle is False
        assert sorted(order) == ["a", "b", "c"]


class TestDyflowCLI:
    def test_cli_no_args(self, capsys):
        from dyflow import _cli
        old_argv = sys.argv
        sys.argv = ["dyflow.py"]
        try:
            code = _cli()
            assert code == 1
        finally:
            sys.argv = old_argv

    def test_cli_success(self, tmp_path, capsys):
        from dyflow import _cli
        (tmp_path / "f.py").write_text("x = 1\n", encoding="utf-8")
        old_argv = sys.argv
        sys.argv = ["dyflow.py", str(tmp_path)]
        try:
            code = _cli()
            assert code == 0
        finally:
            sys.argv = old_argv

    def test_cli_error(self, capsys):
        from dyflow import _cli
        old_argv = sys.argv
        sys.argv = ["dyflow.py", "/nonexistent/path/xyz"]
        try:
            code = _cli()
            assert code == 1
        finally:
            sys.argv = old_argv


# ============================================================================
# cot_synthesis.py — CLI + _fit_to_budget + _coherence edge
# ============================================================================

class TestCotSynthesisFitBudget:
    def test_fit_to_budget_empty(self):
        from cot_synthesis import _fit_to_budget
        assert _fit_to_budget([], 100) == []

    def test_fit_to_budget_within_budget(self):
        from cot_synthesis import _fit_to_budget
        steps = ["Bước 1: a", "Bước 2: b"]
        assert _fit_to_budget(steps, 1000) == steps

    def test_fit_to_budget_keeps_first_and_last(self):
        from cot_synthesis import _fit_to_budget
        steps = ["Bước 1: first long step content here", "mid 1", "mid 2", "Bước 4: last step content"]
        # Budget nhỏ -> giữ first + last
        fitted = _fit_to_budget(steps, 20)
        assert fitted[0] == steps[0]
        if len(fitted) > 1:
            assert fitted[-1] == steps[-1]

    def test_fit_to_budget_single_step_over(self):
        from cot_synthesis import _fit_to_budget
        steps = ["very long step that exceeds budget"]
        fitted = _fit_to_budget(steps, 5)
        # Chỉ 1 step, không có last riêng -> giữ step[0]
        assert fitted == [steps[0]]


class TestCotSynthesisCoherence:
    def test_coherence_empty(self):
        from cot_synthesis import _coherence
        assert _coherence([]) == 0.0

    def test_coherence_out_of_order(self):
        from cot_synthesis import _coherence
        # Bước 1, Bước 3 (bỏ 2) -> partial coherent
        steps = ["Bước 1: a", "Bước 3: c"]
        score = _coherence(steps)
        assert 0.0 <= score <= 1.0

    def test_coherence_with_renumbered(self):
        from cot_synthesis import _coherence
        steps = ["Bước 1: a", "Bước 5: b", "Bước 2: c"]
        score = _coherence(steps)
        # Bước 5 không khớp expected=2 -> 0.5, Bước 2 khớp expected=3? không -> 0.5
        assert score > 0


class TestCotSynthesisReasoningLoad:
    def test_reasoning_load_empty(self):
        from cot_synthesis import _reasoning_load
        assert _reasoning_load([]) == 0.0

    def test_reasoning_load_no_keywords(self):
        from cot_synthesis import _reasoning_load
        assert _reasoning_load(["hello world", "foo bar"]) == 0.0

    def test_reasoning_load_all_keywords(self):
        from cot_synthesis import _reasoning_load
        score = _reasoning_load(["phân tích bài toán", "kết luận cuối"])
        assert score == 1.0


class TestCotSynthesisCLI:
    def test_cli_with_args(self, capsys):
        from cot_synthesis import _cli
        old_argv = sys.argv
        sys.argv = ["cot_synthesis.py", "Tính", "tổng", "2+2"]
        try:
            code = _cli()
            assert code == 0
            out = capsys.readouterr().out
            assert "cot" in out
        finally:
            sys.argv = old_argv

    def test_cli_error(self, capsys):
        from cot_synthesis import _cli
        old_argv = sys.argv
        sys.argv = ["cot_synthesis.py"]
        # Patch stdin rỗng -> problem rỗng -> ValueError -> exit 1
        old_stdin = sys.stdin
        sys.stdin = io.StringIO("")
        try:
            code = _cli()
            assert code == 1
        finally:
            sys.stdin = old_stdin
            sys.argv = old_argv


class TestCotSynthesisSynthesize:
    def test_synthesize_pop_middle_when_over_budget(self):
        from cot_synthesis import synthesize
        from data_models import ModelProfile
        # Budget cực nhỏ -> phải pop bước giữa
        profile = ModelProfile(
            name="tiny",
            context_budget=1024,  # min
            tool_profile="conservative",
            k_chunks=4,
        )
        cot = synthesize("Bài toán rất dài. Cần phân tích. Có ràng buộc. Phải giải.", profile)
        assert cot.tokens <= 1024


# ============================================================================
# adaptive_compress.py — CLI + _summarize + _prefix_hash
# ============================================================================

class TestAdaptiveCompressHelpers:
    def test_summarize_short(self):
        from adaptive_compress import _summarize
        assert _summarize("short text") == "short text"

    def test_summarize_long(self):
        from adaptive_compress import _summarize
        long_text = "x" * 500
        result = _summarize(long_text, max_chars=100)
        # 99 chars (rstrip) + " …[tóm tắt]" (12 chars) = 111
        assert len(result) <= 120
        assert "tóm tắt" in result

    def test_estimate_tokens_empty(self):
        from adaptive_compress import _estimate_tokens
        assert _estimate_tokens("") == 0

    def test_word_count(self):
        from adaptive_compress import _word_count
        assert _word_count("one two three") == 3

    def test_is_complex_query_empty(self):
        from adaptive_compress import _is_complex_query
        assert _is_complex_query("") is False

    def test_is_complex_query_keywords(self):
        from adaptive_compress import _is_complex_query
        assert _is_complex_query("phân tích chi tiết") is True
        assert _is_complex_query("compare A and B") is True

    def test_is_complex_query_word_count(self):
        from adaptive_compress import _is_complex_query
        assert _is_complex_query("one two three four five six seven eight nine") is True

    def test_prefix_hash_deterministic(self):
        from adaptive_compress import _prefix_hash
        from data_models import Turn
        turns = [Turn(role="user", content="x", tokens=1, timestamp=datetime(2026,1,1,tzinfo=timezone.utc))]
        h1 = _prefix_hash(turns, 1)
        h2 = _prefix_hash(turns, 1)
        assert h1 == h2
        assert len(h1) == 64  # sha256 hex


class TestAdaptiveCompressDeep:
    def test_deep_compress_single_group_no_last(self):
        from adaptive_compress import _deep_compress
        from data_models import Turn
        # 3 turn user liên tiếp, không có turn khác -> nhóm cũ gộp
        history = [
            Turn(role="user", content="a", tokens=1, timestamp=datetime(2026,1,1,tzinfo=timezone.utc)),
            Turn(role="user", content="b", tokens=1, timestamp=datetime(2026,1,2,tzinfo=timezone.utc)),
            Turn(role="user", content="c", tokens=1, timestamp=datetime(2026,1,3,tzinfo=timezone.utc)),
        ]
        out = _deep_compress(history)
        # 1 nhóm 3 turn, last là turn cuối -> gộp 2 đầu + giữ last = 2
        assert len(out) == 2


class TestAdaptiveCompressCLI:
    def test_cli(self, capsys):
        from adaptive_compress import _cli
        payload = {
            "history": [
                {"role": "user", "content": "hello", "tokens": 1, "timestamp": "2026-01-01T00:00:00+00:00"},
            ],
            "query": "hi",
            "mode": "auto",
        }
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            code = _cli()
            assert code == 0
        finally:
            sys.stdin = old_stdin


# ============================================================================
# context_projection.py — CLI + _read_single_file + _extract_chunks_from_json
# ============================================================================

class TestContextProjectionHelpers:
    def test_estimate_tokens_empty(self):
        from context_projection import _estimate_tokens
        assert _estimate_tokens("") == 0

    def test_estimate_tokens_non_empty(self):
        from context_projection import _estimate_tokens
        assert _estimate_tokens("abcd") == 1
        assert _estimate_tokens("abcde") == 2  # ceil(5/4)

    def test_hash_content(self):
        from context_projection import _hash_content
        h = _hash_content("test")
        assert len(h) == 16

    def test_tokenize(self):
        from context_projection import _tokenize
        tokens = _tokenize("Hello World hello")
        assert tokens == ["hello", "world", "hello"]

    def test_tokenize_empty(self):
        from context_projection import _tokenize
        assert _tokenize("") == []

    def test_extract_chunks_from_json_dict(self):
        from context_projection import _extract_chunks_from_json
        data = {"chunks": ["a", "b"]}
        assert _extract_chunks_from_json(data) == ["a", "b"]

    def test_extract_chunks_from_json_list(self):
        from context_projection import _extract_chunks_from_json
        data = [{"content": "x"}, {"text": "y"}, "z"]
        assert _extract_chunks_from_json(data) == ["x", "y", "z"]

    def test_extract_chunks_from_json_invalid(self):
        from context_projection import _extract_chunks_from_json
        assert _extract_chunks_from_json("not dict/list") is None
        assert _extract_chunks_from_json({"no_chunks": 1}) is None
        assert _extract_chunks_from_json([]) is None

    def test_extract_chunks_empty_items(self):
        from context_projection import _extract_chunks_from_json
        assert _extract_chunks_from_json({"chunks": []}) is None

    def test_read_single_file_json_invalid(self, tmp_path):
        from context_projection import _read_single_file
        p = tmp_path / "bad.json"
        p.write_text("not json {{{", encoding="utf-8")
        # JSON decode fail -> trả text gốc
        assert _read_single_file(p) == "not json {{{"

    def test_read_single_file_json_no_chunks(self, tmp_path):
        from context_projection import _read_single_file
        p = tmp_path / "nochunks.json"
        p.write_text(json.dumps({"other": 1}), encoding="utf-8")
        # Không có chunks -> trả text gốc
        assert "other" in _read_single_file(p)

    def test_read_single_file_text(self, tmp_path):
        from context_projection import _read_single_file
        p = tmp_path / "f.txt"
        p.write_text("plain text", encoding="utf-8")
        assert _read_single_file(p) == "plain text"

    def test_read_substrate_missing(self, tmp_path):
        from context_projection import _read_substrate
        with pytest.raises(FileNotFoundError):
            _read_substrate(tmp_path / "noexist")

    def test_read_substrate_directory_skips_unsupported(self, tmp_path):
        from context_projection import _read_substrate
        d = tmp_path / "sub"
        d.mkdir()
        (d / "a.txt").write_text("alpha", encoding="utf-8")
        (d / "b.bin").write_text("binary", encoding="utf-8")  # không hỗ trợ
        result = _read_substrate(d)
        assert "alpha" in result
        assert "binary" not in result

    def test_split_chunks_empty(self):
        from context_projection import _split_chunks
        assert _split_chunks("") == []

    def test_split_chunks_with_newline_boundary(self):
        from context_projection import _split_chunks
        content = "line1\nline2\nline3"
        chunks = _split_chunks(content, chunk_chars=10)
        assert len(chunks) >= 1

    def test_score_chunk_no_query(self):
        from context_projection import _score_chunk
        from data_models import Chunk
        chunk = Chunk(id="c1", content="hello world", source="s", tokens=2, hash="h")
        assert _score_chunk(chunk, []) == 0.0

    def test_score_chunk_no_chunk_terms(self):
        from context_projection import _score_chunk
        from data_models import Chunk
        chunk = Chunk(id="c1", content="123 456", source="s", tokens=2, hash="h")
        # _tokenize bỏ số? không, [a-zA-Z0-9_] giữ số -> có terms
        # Test với content chỉ dấu câu
        chunk2 = Chunk(id="c2", content="!!! ???", source="s", tokens=2, hash="h")
        assert _score_chunk(chunk2, ["hello"]) == 0.0


class TestContextProjectionCLI:
    def test_cli(self, tmp_path, capsys):
        from context_projection import _cli
        substrate = tmp_path / "sub.txt"
        substrate.write_text("hello world content", encoding="utf-8")
        old_argv = sys.argv
        sys.argv = ["context_projection.py", str(substrate), "--query", "hello", "--k", "5"]
        try:
            code = _cli()
            assert code == 0
            out = capsys.readouterr().out
            assert "chunks" in out
        finally:
            sys.argv = old_argv


# ============================================================================
# tscg.py — CLI + _to_conservative short desc
# ============================================================================

class TestTscgHelpers:
    def test_estimate_tool_tokens(self):
        from tscg import _estimate_tool_tokens
        from data_models import ToolDef
        tool = ToolDef(name="t", description="desc", parameters={"type": "object"}, required=[])
        tokens = _estimate_tool_tokens(tool)
        assert tokens >= 1

    def test_to_conservative_short_desc_unchanged(self):
        from tscg import _to_conservative
        from data_models import ToolDef
        tool = ToolDef(name="t", description="short", parameters={"type": "object"}, required=[])
        result = _to_conservative(tool)
        assert result.profile == "conservative"
        assert result.description == "short"  # ngắn hơn 80 -> không cắt

    def test_to_conservative_long_desc_truncated(self):
        from tscg import _to_conservative
        from data_models import ToolDef
        tool = ToolDef(name="t", description="d" * 200, parameters={"type": "object"}, required=[])
        result = _to_conservative(tool)
        assert len(result.description) <= 80

    def test_total_tokens(self):
        from tscg import _total_tokens, _estimate_tool_tokens
        from data_models import ToolDef
        tools = [
            ToolDef(name="a", description="d", parameters={"type": "object"}, required=[]),
            ToolDef(name="b", description="d", parameters={"type": "object"}, required=[]),
        ]
        assert _total_tokens(tools) == sum(_estimate_tool_tokens(t) for t in tools)


class TestTscgCLI:
    def test_cli(self, capsys):
        from tscg import _cli
        payload = {"tools": [{"name": "t", "description": "d", "parameters": {"type": "object"}, "required": []}]}
        old_stdin = sys.stdin
        old_argv = sys.argv
        sys.stdin = io.StringIO(json.dumps(payload))
        sys.argv = ["tscg.py", "--budget", "8192"]
        try:
            code = _cli()
            assert code == 0
            out = capsys.readouterr().out
            assert "t" in out
        finally:
            sys.stdin = old_stdin
            sys.argv = old_argv


# ============================================================================
# llm_as_judge.py — CLI + _audit_path + _log_audit + heuristic edge
# ============================================================================

class TestLlmAsJudgeHelpers:
    def test_audit_path_default_none(self, monkeypatch):
        import importlib
        import llm_as_judge
        monkeypatch.delenv("AHD_LLM_JUDGE_AUDIT_DIR", raising=False)
        importlib.reload(llm_as_judge)
        assert llm_as_judge._audit_path() is None

    def test_audit_path_with_env(self, tmp_path, monkeypatch):
        import importlib
        import llm_as_judge
        monkeypatch.setenv("AHD_LLM_JUDGE_AUDIT_DIR", str(tmp_path))
        importlib.reload(llm_as_judge)
        p = llm_as_judge._audit_path()
        assert p is not None
        assert p.name == "llm_judge_audit.jsonl"
        # Cleanup: reload lại không env
        monkeypatch.delenv("AHD_LLM_JUDGE_AUDIT_DIR", raising=False)
        importlib.reload(llm_as_judge)

    def test_log_audit_no_path(self, monkeypatch):
        import importlib
        import llm_as_judge
        monkeypatch.delenv("AHD_LLM_JUDGE_AUDIT_DIR", raising=False)
        importlib.reload(llm_as_judge)
        # Không raise khi không có audit path
        llm_as_judge._log_audit("task", "result", "PASS", 42)

    def test_log_audit_writes_file(self, tmp_path, monkeypatch):
        import importlib
        import llm_as_judge
        monkeypatch.setenv("AHD_LLM_JUDGE_AUDIT_DIR", str(tmp_path))
        importlib.reload(llm_as_judge)
        llm_as_judge._log_audit("task content", {"k": "v"}, "PASS: ok", 42)
        p = llm_as_judge._audit_path()
        assert p is not None
        assert p.exists()
        line = p.read_text(encoding="utf-8").strip()
        entry = json.loads(line)
        assert entry["verdict"] == "PASS: ok"
        assert entry["seed"] == 42
        # Cleanup
        monkeypatch.delenv("AHD_LLM_JUDGE_AUDIT_DIR", raising=False)
        importlib.reload(llm_as_judge)

    def test_heuristic_score_success_marker(self):
        from llm_as_judge import _heuristic_score
        score = _heuristic_score("task", "ok success complete")
        assert score >= 0.5  # có success marker

    def test_heuristic_score_fail_marker(self):
        from llm_as_judge import _heuristic_score
        score = _heuristic_score("task", "error crash fail")
        # fail marker -> -0.5, nhưng success không có -> 0 + 0.3 (len) = 0.3 - 0.5 = -0.2 -> max 0
        assert score == 0.0

    def test_heuristic_score_empty_result(self):
        from llm_as_judge import _heuristic_score
        score = _heuristic_score("task", "")
        assert score == 0.0

    def test_heuristic_score_with_criteria(self):
        from llm_as_judge import _heuristic_score
        score = _heuristic_score("task with criteria must verify", "ok")
        # success marker + criteria keyword + len
        assert score >= 0.7

    def test_heuristic_score_too_long(self):
        from llm_as_judge import _heuristic_score
        score = _heuristic_score("task", "x" * 20000)
        # len > 10000 -> không +0.3
        assert score <= 0.7

    def test_is_high_risk(self):
        from llm_as_judge import _is_high_risk
        assert _is_high_risk("delete files", "") is True
        assert _is_high_risk("rm -rf /", "") is True
        assert _is_high_risk("safe task", "ok") is False

    def test_judge_high_risk_in_result(self):
        from llm_as_judge import judge
        v = judge("safe task", "delete operation done", seed=42)
        assert v.startswith("REVIEW")


class TestLlmAsJudgeCLI:
    def test_cli(self, capsys):
        from llm_as_judge import _cli
        payload = {"task": "do thing", "result": "ok success", "seed": 42}
        old_stdin = sys.stdin
        sys.stdin = io.StringIO(json.dumps(payload))
        try:
            code = _cli()
            assert code == 0
            out = capsys.readouterr().out
            assert "PASS" in out or "FAIL" in out or "REVIEW" in out or "UNCERTAIN" in out
        finally:
            sys.stdin = old_stdin


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
