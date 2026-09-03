"""Tests cho verify_first_cli.py — CLI tool end-to-end."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
CLI = ROOT / "scripts" / "verify_first_cli.py"
SAMPLE_BRD = ROOT / "docs/plans/harness-upgrade-verify-first/BRD.md"


def test_cli_help():
    """CLI --help works."""
    r = subprocess.run(
        ["py", str(CLI), "--help"],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert r.returncode == 0
    assert "BRD" in r.stdout or "brd" in r.stdout.lower()
    assert "--out-dir" in r.stdout


def test_cli_missing_brd_returns_error():
    """Khi không truyền BRD → argparse error (return 2)."""
    r = subprocess.run(
        ["py", str(CLI)],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert r.returncode != 0
    assert "required" in r.stderr.lower() or "usage" in r.stderr.lower()


def test_cli_nonexistent_brd_returns_2():
    """Khi BRD file không tồn tại → return 2."""
    r = subprocess.run(
        ["py", str(CLI), "/nonexistent/path/BRD.md", "--out-dir", str(ROOT / "tmp_cli_out")],
        capture_output=True, text=True, cwd=str(ROOT),
    )
    assert r.returncode == 2


def test_cli_runs_full_chain(tmp_path):
    """End-to-end: chạy CLI với sample BRD → expect output files + exit 0."""
    out = tmp_path / "cli_output"
    r = subprocess.run(
        ["py", str(CLI), str(SAMPLE_BRD), "--out-dir", str(out), "--quiet", "--force"],
        capture_output=True, text=True, cwd=str(ROOT),
        timeout=60,
    )
    assert r.returncode == 0, f"stdout={r.stdout}\nstderr={r.stderr}"
    assert (out / "rubric.json").exists()
    assert (out / "EXECUTION_REPORT.md").exists()
    # Có ít nhất 1 test file
    test_files = list(out.glob("test_*.py"))
    assert len(test_files) >= 1


def test_cli_output_report_contains_gate_verdict(tmp_path):
    """EXECUTION_REPORT.md có chứa 'Gate verdict' line."""
    out = tmp_path / "cli_output"
    subprocess.run(
        ["py", str(CLI), str(SAMPLE_BRD), "--out-dir", str(out), "--quiet", "--force"],
        capture_output=True, text=True, cwd=str(ROOT), timeout=60,
    )
    report = (out / "EXECUTION_REPORT.md").read_text(encoding="utf-8")
    assert "Gate verdict" in report
    assert "Pytest pass" in report
    assert "Binary rubrics" in report
