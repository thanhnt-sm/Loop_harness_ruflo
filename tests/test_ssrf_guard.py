#!/usr/bin/env python3
"""Kiểm thử SSRF guard — T2.9 (REB-011).

Các ca kiểm thử chính:
1. check_ssrf trả 0 cho URL public/allowlist.
2. check_ssrf trả 2 cho loopback/private/link-local.
3. pre_tool_use exit 2 khi command chứa URL nội bộ.
4. pre_tool_use cho phép URL trong allowlist.
5. Ghi OTel-style log khi block.
"""
import importlib
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


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    devin_dir = tmp_path / ".devin"
    (devin_dir / "session_state").mkdir(parents=True, exist_ok=True)
    (devin_dir / "telemetry").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    return tmp_path


def _run_pre_tool_use(data: dict):
    import pre_tool_use
    importlib.reload(pre_tool_use)
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(data))
        try:
            pre_tool_use.main()
        except SystemExit as e:
            return e.code if e.code is not None else 0
    finally:
        sys.stdin = old_stdin
    return 0


# ---------------------------------------------------------------------------
# 1. check_ssrf với URL an toàn / allowlist
# ---------------------------------------------------------------------------
def test_check_ssrf_allow_public():
    from pre_tool_use import check_ssrf
    assert check_ssrf("https://example.com/path", {"example.com"}) == 0
    assert check_ssrf("https://api.github.com/repos/x", {"api.github.com"}) == 0


# ---------------------------------------------------------------------------
# 2. check_ssrf block loopback / private / link-local
# ---------------------------------------------------------------------------
def test_check_ssrf_blocks_private():
    from pre_tool_use import check_ssrf
    assert check_ssrf("http://127.0.0.1:8080/", set()) == 2
    assert check_ssrf("http://localhost/admin", set()) == 2
    assert check_ssrf("http://10.0.0.1/secret", set()) == 2
    assert check_ssrf("http://192.168.1.1/", set()) == 2
    assert check_ssrf("http://169.254.169.254/metadata", set()) == 2
    assert check_ssrf("http://metadata.google.internal/", set()) == 2


# ---------------------------------------------------------------------------
# 3. pre_tool_use block command curl tới private IP
# ---------------------------------------------------------------------------
def test_pre_tool_use_blocks_private_url(patched_root, capsys):
    code = _run_pre_tool_use({
        "tool_name": "Bash",
        "tool_input": {"command": "curl http://10.0.0.1/data"},
        "session_id": "s-ssrf-block",
    })
    assert code == 2
    captured = capsys.readouterr()
    assert "SSRF" in captured.err


# ---------------------------------------------------------------------------
# 4. pre_tool_use cho phép URL public trong command
# ---------------------------------------------------------------------------
def test_pre_tool_use_allows_public_url(patched_root, capsys):
    code = _run_pre_tool_use({
        "tool_name": "Bash",
        "tool_input": {"command": "curl https://example.com/index.html"},
        "session_id": "s-ssrf-ok",
    })
    assert code == 0
    captured = capsys.readouterr()
    assert "SSRF" not in captured.err


# ---------------------------------------------------------------------------
# 5. Ghi OTel-style log khi block
# ---------------------------------------------------------------------------
def test_ssrf_otel_log(patched_root, capsys):
    _run_pre_tool_use({
        "tool_name": "Bash",
        "tool_input": {"command": "curl http://169.254.169.254/metadata"},
        "session_id": "s-ssrf-otel",
    })
    log_path = patched_root / ".devin" / "telemetry" / "ssrf_blocks.jsonl"
    assert log_path.exists()
    lines = log_path.read_text(encoding="utf-8").strip().splitlines()
    assert any("169.254.169.254" in line for line in lines)
