#!/usr/bin/env python3
"""Kiểm thử import smoke test (T2.1 / REQ-006)."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks", "tools"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import import_smoke_test  # noqa: E402


def test_smoke_test_passes_on_repo_scripts():
    result = import_smoke_test.smoke_test([".devin/scripts", ".devin/hooks"])
    assert result["failed"] == []
    assert result["passed"] > 0


def test_smoke_test_invalid_module_name_skipped(tmp_path: Path):
    # tên file không hợp lệ Python
    (tmp_path / "bad-name.py").write_text("x=1\n")
    result = import_smoke_test._modules_in_dir(tmp_path)
    assert result == []
