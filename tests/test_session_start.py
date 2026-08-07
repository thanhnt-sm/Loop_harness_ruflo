#!/usr/bin/env python3
"""Kiểm thử session_start hook — T2.8 HLK status warning.

Các ca kiểm thử:
1. HLK enabled → không cảnh báo, không ghi audit log.
2. HLK disabled → in cảnh báo stderr + ghi audit log.
3. HLK config lỗi → mặc định enabled.
"""
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


def _make_hlk_config(tmp_path: Path, enabled: bool):
    config_path = tmp_path / "HLK" / "config" / "hlk.config.json"
    config_path.parent.mkdir(parents=True, exist_ok=True)
    config_path.write_text(json.dumps({"hlk_enabled": enabled, "version": "3.0.0"}, ensure_ascii=False), encoding="utf-8")


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    devin_dir = tmp_path / ".devin"
    (devin_dir / "session_state").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    return tmp_path


def _run_session_start(data: dict):
    import session_start
    import importlib
    importlib.reload(session_start)
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(data))
        try:
            session_start.main()
        except SystemExit:
            pass
    finally:
        sys.stdin = old_stdin


def test_hlk_enabled_no_warning(patched_root, capsys):
    _make_hlk_config(patched_root, True)
    _run_session_start({"session_id": "s-hlk-ok", "prompt_id": "p1"})
    captured = capsys.readouterr()
    assert "HLK" not in captured.err


def test_hlk_disabled_warns_and_audits(patched_root, capsys):
    _make_hlk_config(patched_root, False)
    _run_session_start({"session_id": "s-hlk-off", "prompt_id": "p1"})
    captured = capsys.readouterr()
    assert "HLK" in captured.err
    assert "disabled" in captured.err.lower()
    # Kiểm tra audit log
    audit_path = patched_root / ".devin" / "audit" / "hlk_status.log"
    assert audit_path.exists()
    content = audit_path.read_text(encoding="utf-8")
    assert "disabled" in content.lower()


def test_check_hlk_status_function():
    from session_start import check_hlk_status
    assert check_hlk_status({"hlk_enabled": True}) is True
    assert check_hlk_status({"hlk_enabled": False}) is False
    assert check_hlk_status({}) is True
