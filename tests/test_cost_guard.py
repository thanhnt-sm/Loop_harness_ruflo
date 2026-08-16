#!/usr/bin/env python3
"""Kiểm thử cost cap enforcement — T2.4 (REB-003).

Các ca kiểm thử chính:
1. Dưới 80% cap → pre_tool_use exit 0.
2. 80% cap → pre_tool_use exit 0 + cảnh báo stderr.
3. 100% cap → pre_tool_use exit 2 + block.
4. cost_tracker.check_cost_cap(state) trả đúng mã (0/1/2).
5. cost_cap từ config/state được tôn trọng.
"""
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
# Thêm hooks và scripts vào sys.path để import ahd_session và cost_tracker.
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


def _make_session_file(tmp_path: Path, session_id: str, cumulative: float, cost_cap: float) -> Path:
    """Tạo session_state giả lập trong tmp_path/.devin/session_state."""
    state_dir = tmp_path / ".devin" / "session_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    state_file = state_dir / f"{session_id}.json"
    state_file.write_text(
        json.dumps({
            "session_id": session_id,
            "cumulative_cost": cumulative,
            "cost_cap": cost_cap,
            "cost_tracked_calls": 10,
        }, ensure_ascii=False),
        encoding="utf-8",
    )
    return state_file


@pytest.fixture
def patched_root(tmp_path, monkeypatch):
    """Chuyển repo root và config root của ahd_session sang tmp_path."""
    devin_dir = tmp_path / ".devin"
    (devin_dir / "session_state").mkdir(parents=True, exist_ok=True)
    (devin_dir / "telemetry").mkdir(parents=True, exist_ok=True)
    monkeypatch.setattr(ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    monkeypatch.setattr(ahd_session, "get_config_root", lambda _root=None: devin_dir)
    # CVE-2026-AHD-013: cost cap gate fail-closed khi thiếu HMAC key → cấu hình key test.
    monkeypatch.setenv("AHD_COST_LEDGER_KEY", "test-key")
    return tmp_path


def _seed_ledger(root: Path, session_id: str, cumulative: float) -> None:
    """Ghi entry HMAC-signed vào ledger để gate đọc cumulative đúng (CVE-2026-AHD-013)."""
    import cost_ledger
    cost_ledger.append_entry(root, session_id, "Write", cumulative, cumulative)


def _run_pre_tool_use(data: dict, capsys):
    """Chạy pre_tool_use.main trong process, bắt SystemExit, trả (code, stderr)."""
    import pre_tool_use
    import cost_tracker
    # Buộc reload để pick up monkeypatch trên ahd_session và cost_tracker.
    importlib.reload(pre_tool_use)
    importlib.reload(cost_tracker)
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(data))
        code = 0
        try:
            pre_tool_use.main()
        except SystemExit as e:
            code = e.code if e.code is not None else 0
    finally:
        sys.stdin = old_stdin
    captured = capsys.readouterr()
    return code, captured.err


# ---------------------------------------------------------------------------
# 1. cost_tracker.check_cost_cap(state)
# ---------------------------------------------------------------------------
def test_check_cost_cap_states():
    from cost_tracker import check_cost_cap

    assert check_cost_cap({"cumulative_cost": 1.0, "cost_cap": 10.0}) == 0
    assert check_cost_cap({"cumulative_cost": 8.5, "cost_cap": 10.0}) == 1
    assert check_cost_cap({"cumulative_cost": 10.0, "cost_cap": 10.0}) == 2
    assert check_cost_cap({"cumulative_cost": 12.0, "cost_cap": 10.0}) == 2


# ---------------------------------------------------------------------------
# 2. Dưới 80% cap → exit 0
# ---------------------------------------------------------------------------
def test_below_cap_allows(patched_root, capsys):
    session_id = "s-cost-below"
    _make_session_file(patched_root, session_id, 3.0, 10.0)
    _seed_ledger(patched_root, session_id, 3.0)
    code, stderr = _run_pre_tool_use({"tool_name": "write", "tool_input": {"file_path": "x"}, "session_id": session_id}, capsys)
    assert code == 0
    assert "COST CAP" not in stderr


# ---------------------------------------------------------------------------
# 3. 80% cap → exit 0 + cảnh báo
# ---------------------------------------------------------------------------
def test_eighty_percent_warns(patched_root, capsys):
    session_id = "s-cost-warn"
    _make_session_file(patched_root, session_id, 8.1, 10.0)
    _seed_ledger(patched_root, session_id, 8.1)
    code, stderr = _run_pre_tool_use({"tool_name": "write", "tool_input": {"file_path": "x"}, "session_id": session_id}, capsys)
    assert code == 0
    assert "WARNING" in stderr


# ---------------------------------------------------------------------------
# 4. 100% cap → exit 2 + block
# ---------------------------------------------------------------------------
def test_at_cap_blocks(patched_root, capsys):
    session_id = "s-cost-block"
    _make_session_file(patched_root, session_id, 10.0, 10.0)
    _seed_ledger(patched_root, session_id, 10.0)
    code, stderr = _run_pre_tool_use({"tool_name": "write", "tool_input": {"file_path": "x"}, "session_id": session_id}, capsys)
    assert code == 2
    assert "BLOCKED" in stderr


# ---------------------------------------------------------------------------
# 5. cost_cap từ state được tôn trọng
# ---------------------------------------------------------------------------
def test_custom_cap(patched_root, capsys):
    session_id = "s-cost-custom"
    _make_session_file(patched_root, session_id, 4.5, 5.0)
    _seed_ledger(patched_root, session_id, 4.5)
    code, stderr = _run_pre_tool_use({"tool_name": "write", "tool_input": {"file_path": "x"}, "session_id": session_id}, capsys)
    assert code == 0  # 4.5/5 = 90% → warn nhưng vẫn cho phép
    assert "WARNING" in stderr
