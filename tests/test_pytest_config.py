#!/usr/bin/env python3
"""Kiểm tra pytest/coverage config theo T1.2."""
import subprocess
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def test_pytest_ini_exists_and_has_coverage_gate():
    ini = REPO_ROOT / "pytest.ini"
    assert ini.exists()
    text = ini.read_text(encoding="utf-8")
    assert "--cov" in text
    assert "--cov-fail-under=80" in text


def test_coveragerc_exists_and_has_fail_under():
    rc = REPO_ROOT / ".coveragerc"
    assert rc.exists()
    text = rc.read_text(encoding="utf-8")
    assert "fail_under = 80" in text


def test_pyproject_toml_has_coverage_config():
    toml = REPO_ROOT / "pyproject.toml"
    assert toml.exists()
    text = toml.read_text(encoding="utf-8")
    assert "[tool.coverage.run]" in text
    assert "[tool.coverage.report]" in text


def test_pytest_collect_only_passes():
    result = subprocess.run(
        ["python", "-m", "pytest", "--collect-only", "-q"],
        cwd=REPO_ROOT,
        capture_output=True,
        text=True,
    )
    assert result.returncode == 0, result.stdout + result.stderr
