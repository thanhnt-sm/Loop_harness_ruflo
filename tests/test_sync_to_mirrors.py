"""Tests cho HLK/scripts/sync_to_mirrors.py."""
from __future__ import annotations

import subprocess
import sys
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
SYNC_SCRIPT = ROOT / "HLK" / "scripts" / "sync_to_mirrors.py"


def test_sync_script_runs():
    """sync_to_mirrors.py --dry-run chạy thành công."""
    r = subprocess.run(
        ["py", str(SYNC_SCRIPT), "--dry-run", "--target", "all"],
        capture_output=True, cwd=str(ROOT), timeout=30,
    )
    assert r.returncode == 0
    stdout = r.stdout.decode("utf-8", errors="replace")
    assert "HLK/chain/" in stdout
    assert ".devin/scripts/" in stdout


def test_sync_to_devin_creates_shim(tmp_path, monkeypatch):
    """sync_to_devin tạo shim file với re-export content."""
    from HLK.scripts import sync_to_mirrors
    # Create test file in temp HLK/chain
    test_hlk = tmp_path / "HLK" / "chain"
    test_hlk.mkdir(parents=True)
    test_hlk.joinpath("test_module.py").write_text("# test content\n", encoding="utf-8")
    test_devin = tmp_path / ".devin" / "scripts"
    actions = sync_to_mirrors.sync_to_devin(tmp_path, dry_run=False)
    shim = test_devin / "test_module.py"
    assert shim.exists()
    content = shim.read_text(encoding="utf-8")
    assert "from HLK.chain.test_module import" in content
    assert any("created/updated" in a[0] for a in actions)


def test_sync_to_devin_idempotent(tmp_path):
    """Chạy 2 lần liên tiếp → lần 2 phải skip (unchanged)."""
    from HLK.scripts import sync_to_mirrors
    test_hlk = tmp_path / "HLK" / "chain"
    test_hlk.mkdir(parents=True)
    test_hlk.joinpath("test_module.py").write_text("# content\n", encoding="utf-8")
    test_devin = tmp_path / ".devin" / "scripts"
    # Lần 1: tạo
    sync_to_mirrors.sync_to_devin(tmp_path, dry_run=False)
    # Lần 2: skip
    actions2 = sync_to_mirrors.sync_to_devin(tmp_path, dry_run=False)
    assert any("skip (unchanged)" in a[0] for a in actions2)


def test_sync_to_devin_does_not_delete(tmp_path):
    """Sync KHÔNG xóa file ở mirror (theo user directive)."""
    from HLK.scripts import sync_to_mirrors
    test_hlk = tmp_path / "HLK" / "chain"
    test_hlk.mkdir(parents=True)
    test_hlk.joinpath("test_module.py").write_text("# HLK\n", encoding="utf-8")
    test_devin = tmp_path / ".devin" / "scripts"
    test_devin.mkdir(parents=True)
    # Tạo file ở mirror KHÔNG có ở HLK
    extra = test_devin / "extra_file.py"
    extra.write_text("# extra\n", encoding="utf-8")
    # Run sync
    sync_to_mirrors.sync_to_devin(tmp_path, dry_run=False)
    # Verify file extra vẫn còn
    assert extra.exists()


def test_sync_to_cmdc_creates_pointer(tmp_path):
    """sync_to_cmdc tạo pointer file ở .commandcode/."""
    from HLK.scripts import sync_to_mirrors
    # Need HLK/skills/verify-first/SKILL.md
    test_hlk_skill = tmp_path / "HLK" / "skills" / "verify-first" / "SKILL.md"
    test_hlk_skill.parent.mkdir(parents=True)
    test_hlk_skill.write_text("# canonical SKILL\n", encoding="utf-8")
    actions = sync_to_mirrors.sync_to_cmdc(tmp_path, dry_run=False)
    cmdc = tmp_path / ".commandcode" / "skills" / "verify-first" / "SKILL.md"
    assert cmdc.exists()
    content = cmdc.read_text(encoding="utf-8")
    assert "POINTER" in content or "Canonical source" in content
    assert any("created/updated" in a[0] for a in actions)


def test_sync_to_opencode_creates_pointer(tmp_path):
    """sync_to_opencode tạo pointer file ở .opencode/."""
    from HLK.scripts import sync_to_mirrors
    test_hlk_skill = tmp_path / "HLK" / "skills" / "verify-first" / "SKILL.md"
    test_hlk_skill.parent.mkdir(parents=True)
    test_hlk_skill.write_text("# canonical SKILL\n", encoding="utf-8")
    actions = sync_to_mirrors.sync_to_opencode(tmp_path, dry_run=False)
    oc = tmp_path / ".opencode" / "command" / "verify-first.md"
    assert oc.exists()
    assert any("created/updated" in a[0] for a in actions)
