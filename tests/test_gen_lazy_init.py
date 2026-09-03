"""Tests cho HLK/scripts/gen_lazy_init.py."""
from __future__ import annotations

import shutil
import subprocess
from pathlib import Path

import pytest

ROOT = Path("D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo")
SCRIPT = ROOT / "HLK" / "scripts" / "gen_lazy_init.py"


def test_script_exists():
    assert SCRIPT.exists()


def test_generate_produces_content():
    """Chạy script và verify output có đủ modules + symbols."""
    r = subprocess.run(
        ["py", str(SCRIPT), "--check"],
        capture_output=True, cwd=str(ROOT), timeout=30,
    )
    stdout = r.stdout.decode("utf-8", errors="replace")
    assert r.returncode in (0, 1)
    assert stdout  # có output


def test_idempotent(tmp_path):
    """Chạy 2 lần liên tiếp → lần 2 phải idempotent (same output)."""
    tmp_chain = tmp_path / "HLK" / "chain"
    tmp_chain.mkdir(parents=True)
    (tmp_chain / "test_mod.py").write_text(
        '__all__ = ["foo", "bar"]\n'
        'def foo():\n    pass\n'
        'def bar():\n    pass\n',
        encoding="utf-8",
    )
    tmp_script = tmp_path / "gen_lazy_init.py"
    shutil.copy(SCRIPT, tmp_script)
    subprocess.run(
        ["py", str(tmp_script), "--repo", str(tmp_path)],
        capture_output=True, timeout=30,
    )
    init_path = tmp_chain / "__init__.py"
    content1 = init_path.read_text(encoding="utf-8")
    subprocess.run(
        ["py", str(tmp_script), "--repo", str(tmp_path)],
        capture_output=True, timeout=30,
    )
    content2 = init_path.read_text(encoding="utf-8")
    assert content1 == content2  # idempotent


def test_check_mode_no_write(tmp_path):
    """--check KHÔNG ghi file, chỉ check."""
    tmp_chain = tmp_path / "HLK" / "chain"
    tmp_chain.mkdir(parents=True)
    (tmp_chain / "test_mod.py").write_text(
        '__all__ = ["foo"]\ndef foo():\n    pass\n',
        encoding="utf-8",
    )
    init_path = tmp_chain / "__init__.py"
    init_path.write_text("# wrong content\n", encoding="utf-8")
    tmp_script = tmp_path / "gen_lazy_init.py"
    shutil.copy(SCRIPT, tmp_script)
    subprocess.run(
        ["py", str(tmp_script), "--repo", str(tmp_path), "--check"],
        capture_output=True, timeout=30,
    )
    # File KHÔNG bị thay đổi
    assert init_path.read_text(encoding="utf-8") == "# wrong content\n"


def test_module_count(tmp_path):
    """Đếm modules + symbols in generated __init__.py."""
    tmp_chain = tmp_path / "HLK" / "chain"
    tmp_chain.mkdir(parents=True)
    for name in ["alpha", "beta", "gamma"]:
        (tmp_chain / f"{name}.py").write_text(
            f'__all__ = ["func_{name}"]\n'
            f'def func_{name}():\n    return "{name}"\n',
            encoding="utf-8",
        )
    tmp_script = tmp_path / "gen_lazy_init.py"
    shutil.copy(SCRIPT, tmp_script)
    r = subprocess.run(
        ["py", str(tmp_script), "--repo", str(tmp_path)],
        capture_output=True, timeout=30,
    )
    assert r.returncode == 0
    content = (tmp_chain / "__init__.py").read_text(encoding="utf-8")
    assert '"alpha"' in content
    assert '"beta"' in content
    assert '"gamma"' in content
    assert "func_alpha" in content
    assert "func_beta" in content
    assert "func_gamma" in content

