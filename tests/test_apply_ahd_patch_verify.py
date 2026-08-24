#!/usr/bin/env python3
"""Kiểm thử verify pipeline (T3.8 / REQ-006)."""
import sys
from pathlib import Path
from unittest.mock import patch

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import apply_ahd_patch  # noqa: E402
import update_common  # noqa: E402


def test_verify_fails_when_smoke_test_fails(tmp_path: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_path
    apply_ahd_patch.REPO_ROOT = tmp_path
    try:
        with patch.object(apply_ahd_patch, "run_cmd", return_value=(1, "", "smoke failed")):
            ok = apply_ahd_patch.verify([".devin/scripts/test.py"])
            assert ok is False
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old


def test_verify_passes_with_mocked_commands(tmp_path: Path):
    old = update_common.REPO_ROOT
    update_common.REPO_ROOT = tmp_path
    apply_ahd_patch.REPO_ROOT = tmp_path
    try:
        # Tạo file test để py_compile pass
        test_file = tmp_path / ".devin" / "scripts" / "test.py"
        test_file.parent.mkdir(parents=True, exist_ok=True)
        test_file.write_text("# test\nprint('hello')\n", encoding="utf-8")

        import json as _json
        import apply_ahd_verify

        def _fake_run(cmd, cwd=None, timeout=120, input_text=""):
            if any("qa_doc_audit.py" in c for c in cmd):
                return 0, _json.dumps({"stale_refs": [], "missing_paths": []}), ""
            if any("import_smoke_test.py" in c for c in cmd):
                return 0, "SMOKE TEST: 0 passed, 0 failed", ""
            return 0, "", ""

        with patch.object(apply_ahd_verify, "run_cmd", _fake_run):
            ok = apply_ahd_patch.verify([".devin/scripts/test.py"])
            assert ok is True
    finally:
        update_common.REPO_ROOT = old
        apply_ahd_patch.REPO_ROOT = old
