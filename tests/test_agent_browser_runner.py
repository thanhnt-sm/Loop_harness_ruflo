"""Tests cho agent_browser_runner.py — wrap agent-browser skill cho UI scenarios."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import agent_browser_runner  # noqa: E402
from agent_browser_runner import (  # noqa: E402
    BrowserStepResult,
    _is_cc_available,
    run_browser_step,
)


def test_is_cc_available_returns_bool():
    """Returns True hoặc False, không raise."""
    r = _is_cc_available()
    assert isinstance(r, bool)


def test_run_browser_step_uses_cc_client():
    """Khi CC client available và trả JSON → parse success."""
    with mock.patch.object(agent_browser_runner, "_is_cc_available", return_value=True), \
         mock.patch("command_code_client.chat") as mock_chat:
        mock_chat.return_value = type("R", (), {
            "content": json.dumps({"success": True, "screenshot_path": "/tmp/s.png"}),
            "fallback_used": False,
        })()
        r = run_browser_step("Click button", "ui", "SC-001", Path("/tmp/evidence"))
        assert r.success is True
        assert r.evidence_path == Path("/tmp/s.png")


def test_run_browser_step_fallback_when_cc_fail():
    """Khi CC fail → fallback_used=True, success=False."""
    with mock.patch("command_code_client.chat") as mock_chat:
        mock_chat.return_value = type("R", (), {
            "content": "fallback", "fallback_used": True,
        })()
        r = run_browser_step("Click", "ui", "SC-001", Path("/tmp"))
        assert r.fallback_used is True
        assert r.success is False


def test_run_browser_step_parse_non_json_response():
    """Khi response không phải JSON → heuristic: success nếu không có 'fail'."""
    with mock.patch("command_code_client.chat") as mock_chat:
        mock_chat.return_value = type("R", (), {
            "content": "Successfully clicked button", "fallback_used": False,
        })()
        r = run_browser_step("Click", "ui", "SC-001", Path("/tmp"))
        assert r.success is True
        assert r.error == ""


def test_run_browser_step_detect_fail_in_text():
    """Khi response có 'fail' → success=False."""
    with mock.patch("command_code_client.chat") as mock_chat:
        mock_chat.return_value = type("R", (), {
            "content": "Failed to click", "fallback_used": False,
        })()
        r = run_browser_step("Click", "ui", "SC-001", Path("/tmp"))
        assert r.success is False
        assert "fail" in r.error.lower() or r.error == ""


def test_run_browser_step_simulator_type():
    """action_type='simulator' works same as 'ui'."""
    with mock.patch("command_code_client.chat") as mock_chat:
        mock_chat.return_value = type("R", (), {
            "content": json.dumps({"success": True}), "fallback_used": False,
        })()
        r = run_browser_step("open simulator", "simulator", "SC-002", Path("/tmp"))
        assert r.success is True


def test_run_browser_step_creates_evidence_dir(tmp_path):
    """evidence_dir được tạo nếu chưa tồn tại."""
    target = tmp_path / "nested" / "evidence"
    with mock.patch("command_code_client.chat") as mock_chat:
        mock_chat.return_value = type("R", (), {
            "content": json.dumps({"success": True}), "fallback_used": False,
        })()
        r = run_browser_step("x", "ui", "SC-003", target)
        assert target.exists()


def test_run_browser_step_import_error_falls_back():
    """Khi command_code_client import fail → fallback path."""
    # Simulate import error bằng cách patch sys.modules
    import builtins
    real_import = builtins.__import__
    def fake_import(name, *args, **kwargs):
        if name == "command_code_client":
            raise ImportError("simulated")
        return real_import(name, *args, **kwargs)
    with mock.patch("builtins.__import__", side_effect=fake_import), \
         mock.patch.object(agent_browser_runner, "_is_cc_available", return_value=False):
        r = run_browser_step("x", "ui", "SC-004", Path("/tmp"))
        assert r.fallback_used is True
