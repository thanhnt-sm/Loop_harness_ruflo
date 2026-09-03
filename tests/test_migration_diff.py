"""Tests cho diff_compare.py + verify HLK config + sync mechanism."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
DIFF_SCRIPT = ROOT / "HLK" / "scripts" / "diff_compare.py"


def test_diff_script_runs():
    """diff_compare.py chạy thành công, output có sections."""
    r = subprocess.run(
        ["py", str(DIFF_SCRIPT)],
        capture_output=True, cwd=str(ROOT), timeout=30,
    )
    assert r.returncode == 0
    # Decode với UTF-8 thay vì charmap
    stdout = r.stdout.decode("utf-8", errors="replace")
    assert "Section 1" in stdout
    assert "Section 2" in stdout
    assert "CẦN CLONE" in stdout or "clone" in stdout.lower()


def test_diff_script_output_to_file(tmp_path):
    """diff_compare.py --output ghi file thành công."""
    out = tmp_path / "diff.md"
    r = subprocess.run(
        ["py", str(DIFF_SCRIPT), "--output", str(out)],
        capture_output=True, cwd=str(ROOT), timeout=30,
    )
    assert r.returncode == 0
    assert out.exists()
    content = out.read_text(encoding="utf-8")
    assert "# Migration Diff" in content
    assert "Section 2" in content


def test_hlk_chain_has_17_modules():
    """HLK/chain/ có ≥17 modules (sau khi clone)."""
    hlk_chain = ROOT / "HLK" / "chain"
    modules = [p.name for p in hlk_chain.glob("*.py") if p.is_file()]
    modules.remove("__init__.py")
    assert len(modules) >= 17, f"chỉ có {len(modules)} modules: {modules}"
    expected = [
        "brd_schema.py", "brd_validator.py", "scenario_runner.py",
        "verify_env_setup.py", "rubric_generator.py", "test_generator.py",
        "secret_scanner.py", "prompt_sanitizer.py", "judge_config.py",
        "redteam_spawner.py", "skill_promoter.py", "skill_bench.py",
        "auto_pr_runner.py", "auto_pr_gh.py", "command_code_client.py",
        "agent_browser_runner.py", "_platform_utils.py",
    ]
    for name in expected:
        assert name in modules, f"thiếu {name} trong HLK/chain/"


def test_hlk_chain_init_imports():
    """HLK/chain/__init__.py re-export đủ API."""
    hlk_dir = str(ROOT / "HLK")
    if hlk_dir not in sys.path:
        sys.path.insert(0, hlk_dir)
    import importlib
    chain = importlib.import_module("chain")
    # Spot-check 1 số API
    assert hasattr(chain, "BRD")
    assert hasattr(chain, "parse_brd_file")
    assert hasattr(chain, "Scenario")
    assert hasattr(chain, "should_auto_merge")
    assert hasattr(chain, "chat")
    assert hasattr(chain, "run_scenario")
    assert hasattr(chain, "is_safe")
    assert hasattr(chain, "scan")
    assert hasattr(chain, "sanitize")
    assert hasattr(chain, "redact")
