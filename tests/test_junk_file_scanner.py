#!/usr/bin/env python3
"""test_junk_file_scanner.py — Test cho tools/junk_file_scanner.py.

Cross-platform (Windows + macOS + Linux). Dùng unittest stdlib.
Test:
  - is_junk_name: phát hiện junk filename patterns
  - is_provider_runtime: phát hiện provider runtime dirs
  - is_filler_content: phát hiện filler content (repeated chars)
  - scan: scan tracked + untracked + staged
  - CLI: exit code đúng
"""
from __future__ import annotations

import os
import sys
import tempfile
import unittest
from pathlib import Path

# Thêm tools/ vào path
TOOLS_DIR = Path(__file__).resolve().parent.parent / "tools"
sys.path.insert(0, str(TOOLS_DIR))

from junk_file_scanner import (
    is_junk_name,
    is_provider_runtime,
    is_filler_content,
    is_binary_junk,
    JUNK_EXTENSIONS,
    JUNK_FILENAMES,
    PROVIDER_RUNTIME_DIRS,
)


class TestJunkNameDetection(unittest.TestCase):
    """Test is_junk_name — phát hiện junk filename patterns."""

    def test_os_junk_filenames(self):
        """OS junk files phải bị phát hiện."""
        for name in JUNK_FILENAMES:
            with self.subTest(name=name):
                self.assertTrue(is_junk_name(name), f"{name} should be junk")

    def test_junk_extensions(self):
        """File với junk extension phải bị phát hiện."""
        for ext in JUNK_EXTENSIONS:
            with self.subTest(ext=ext):
                self.assertTrue(is_junk_name(f"file{ext}"), f"file{ext} should be junk")

    def test_junk_prefixes(self):
        """File với junk prefix phải bị phát hiện."""
        self.assertTrue(is_junk_name("untitled.py"))
        self.assertTrue(is_junk_name("scratch_test.py"))
        self.assertTrue(is_junk_name("copy_of_file.py"))

    def test_clean_filenames(self):
        """File bình thường không bị flag."""
        self.assertFalse(is_junk_name("check_governance.py"))
        self.assertFalse(is_junk_name("WORKSPACE_GOVERNANCE.md"))
        self.assertFalse(is_junk_name("REPOS_TRACKER.json"))
        self.assertFalse(is_junk_name("path_zones.py"))

    def test_case_insensitive(self):
        """Junk detection phải case-insensitive."""
        self.assertTrue(is_junk_name(".ds_store"))
        self.assertTrue(is_junk_name(".DS_Store"))
        self.assertTrue(is_junk_name("THUMBS.DB"))


class TestProviderRuntimeDetection(unittest.TestCase):
    """Test is_provider_runtime — phát hiện provider runtime dirs."""

    def test_provider_runtime_dirs(self):
        """Provider runtime dirs phải bị phát hiện."""
        for pdir in PROVIDER_RUNTIME_DIRS:
            with self.subTest(pdir=pdir):
                # File nằm trong provider dir
                filepath = f"{pdir}state.json"
                self.assertTrue(is_provider_runtime(filepath),
                                f"{filepath} should be provider runtime")

    def test_nested_provider_runtime(self):
        """File nằm sâu trong provider dir cũng phải bị phát hiện."""
        self.assertTrue(is_provider_runtime(".khuym/state.json"))
        self.assertTrue(is_provider_runtime(".aide/config.json"))
        self.assertTrue(is_provider_runtime(".opencode/session_state/tool_outputs/output.txt"))

    def test_non_provider_paths(self):
        """Path không phải provider runtime không bị flag."""
        self.assertFalse(is_provider_runtime(".devin/scripts/check_updates.py"))
        self.assertFalse(is_provider_runtime("tools/junk_file_scanner.py"))
        self.assertFalse(is_provider_runtime("tests/test_junk_file_scanner.py"))

    def test_windows_backslash(self):
        """Windows backslash path cũng phải bị phát hiện."""
        self.assertTrue(is_provider_runtime(".khuym\\state.json"))
        self.assertTrue(is_provider_runtime(".aide\\config.json"))


class TestFillerContentDetection(unittest.TestCase):
    """Test is_filler_content — phát hiện filler content."""

    def setUp(self):
        """Tạo temp dir trong repo (tmp/ đã gitignored) để avoid cross-drive issue."""
        from junk_file_scanner import ROOT
        self.tmpdir = ROOT / "tmp" / "junk_test"
        self.tmpdir.mkdir(parents=True, exist_ok=True)

    def tearDown(self):
        """Dọn temp files."""
        import shutil
        if self.tmpdir.exists():
            shutil.rmtree(self.tmpdir, ignore_errors=True)

    def _create_filler_file(self, name: str, char: str, count: int) -> str:
        """Tạo file filler trong tmp/junk_test/. Trả về relative path."""
        path = self.tmpdir / name
        with open(path, "w", encoding="utf-8") as f:
            f.write(char * count)
        rel = str(path.relative_to(Path(__file__).resolve().parent.parent)).replace("\\", "/")
        return rel

    def test_x_filler_detected(self):
        """File chỉ chứa 'xxxx...' phải bị phát hiện."""
        rel = self._create_filler_file("filler_x.txt", "x", 500)
        self.assertTrue(is_filler_content(rel),
                        "File with 500 'x' chars should be filler")

    def test_short_file_not_filler(self):
        """File ngắn không bị flag."""
        rel = self._create_filler_file("short.txt", "x", 10)
        self.assertFalse(is_filler_content(rel),
                         "Short file should not be filler")

    def test_normal_content_not_filler(self):
        """File content bình thường không bị flag."""
        path = self.tmpdir / "normal.py"
        with open(path, "w", encoding="utf-8") as f:
            f.write("def hello():\n    print('Hello World')\n")
        rel = str(path.relative_to(Path(__file__).resolve().parent.parent)).replace("\\", "/")
        self.assertFalse(is_filler_content(rel),
                         "Normal code file should not be filler")


class TestBinaryJunkDetection(unittest.TestCase):
    """Test is_binary_junk — phát hiện binary junk."""

    def test_ds_store(self):
        self.assertTrue(is_binary_junk(".DS_Store"))

    def test_thumbs_db(self):
        self.assertTrue(is_binary_junk("Thumbs.db"))

    def test_desktop_ini(self):
        self.assertTrue(is_binary_junk("desktop.ini"))

    def test_normal_binary(self):
        self.assertFalse(is_binary_junk("image.png"))
        self.assertFalse(is_binary_junk("data.bin"))


class TestCLIBehavior(unittest.TestCase):
    """Test CLI exit codes."""

    def test_clean_scan_exit_zero(self):
        """Scanner chạy trên repo sạch phải exit 0."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "junk_file_scanner.py"), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        # Exit 0 = sạch (sau khi đã untrack junk)
        self.assertEqual(result.returncode, 0,
                         f"Clean scan should exit 0, got {result.returncode}: {result.stderr}")

    def test_json_output_valid(self):
        """JSON output phải parse được."""
        import subprocess
        import json
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "junk_file_scanner.py"), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        self.assertIn("junk_count", data)
        self.assertIn("findings", data)
        self.assertIsInstance(data["findings"], list)


class TestGitignoreAudit(unittest.TestCase):
    """Test tools/gitignore_audit.py."""

    def test_audit_exit_zero_when_clean(self):
        """Audit chạy khi .gitignore đầy đủ phải exit 0."""
        import subprocess
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "gitignore_audit.py"), "--strict"],
            capture_output=True, text=True, timeout=30,
        )
        self.assertEqual(result.returncode, 0,
                         f"Audit should exit 0 when clean, got {result.returncode}: {result.stderr}")

    def test_audit_json_output(self):
        """Audit JSON output phải parse được."""
        import subprocess
        import json
        result = subprocess.run(
            [sys.executable, str(TOOLS_DIR / "gitignore_audit.py"), "--json"],
            capture_output=True, text=True, timeout=30,
        )
        data = json.loads(result.stdout)
        self.assertIn("required_rules", data)
        self.assertIn("missing_rules", data)
        self.assertIn("findings", data)


if __name__ == "__main__":
    unittest.main()
