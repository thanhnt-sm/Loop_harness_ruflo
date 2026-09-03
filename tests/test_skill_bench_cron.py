"""Tests cho skill_bench cron mode."""
from __future__ import annotations

import subprocess
import sys
from datetime import datetime
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import skill_bench  # noqa: E402

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
SCRIPT = ROOT / ".devin" / "scripts" / "skill_bench.py"


def test_cron_mode_skips_when_already_ran_today(tmp_path):
    """Khi state file có date hôm nay → skip, exit 0."""
    state_file = tmp_path / "state"
    state_file.write_text(datetime.utcnow().strftime("%Y-%m-%d"), encoding="utf-8")
    out_dir = tmp_path / "out"
    r = subprocess.run(
        ["py", str(SCRIPT), str(ROOT / ".devin/skills"), str(out_dir / "report.md"),
         "--schedule-cron", "--state-file", str(state_file)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=30,
    )
    assert r.returncode == 0
    assert "Already ran today" in r.stdout or "skip" in r.stdout.lower()
    # Output file không được tạo
    assert not (out_dir / "report.md").exists()


def test_cron_mode_runs_when_no_state(tmp_path):
    """Khi state file không tồn tại → chạy bình thường."""
    state_file = tmp_path / "state"  # không tạo
    out_dir = tmp_path / "out"
    r = subprocess.run(
        ["py", str(SCRIPT), str(ROOT / ".devin/skills"), str(out_dir / "report.md"),
         "--schedule-cron", "--state-file", str(state_file)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    # Có thể pass hoặc fail tùy skill count; quan trọng là state file được tạo
    assert state_file.exists()
    # State file chứa date hôm nay
    content = state_file.read_text(encoding="utf-8")
    assert content.strip() == datetime.utcnow().strftime("%Y-%m-%d")


def test_cron_mode_runs_when_state_yesterday(tmp_path):
    """Khi state file là date hôm qua → chạy lại."""
    from datetime import timedelta
    yesterday = (datetime.utcnow() - timedelta(days=1)).strftime("%Y-%m-%d")
    state_file = tmp_path / "state"
    state_file.write_text(yesterday, encoding="utf-8")
    out_dir = tmp_path / "out"
    r = subprocess.run(
        ["py", str(SCRIPT), str(ROOT / ".devin/skills"), str(out_dir / "report.md"),
         "--schedule-cron", "--state-file", str(state_file)],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    # State file được update thành hôm nay
    content = state_file.read_text(encoding="utf-8")
    assert content.strip() == datetime.utcnow().strftime("%Y-%m-%d")
