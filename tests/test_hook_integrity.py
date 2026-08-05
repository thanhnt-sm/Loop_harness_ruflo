#!/usr/bin/env python3
"""Kiểm thử cho hook_integrity.py và hook_hashes.json."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent


def _run(args):
    # Chạy hook_integrity.py
    cmd = [sys.executable, str(REPO_ROOT / ".devin" / "scripts" / "hook_integrity.py"), *args]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    result = subprocess.run(cmd, capture_output=True, text=True, cwd=REPO_ROOT, env=env)
    return result


def test_baseline_exists():
    # hook_hashes.json phải tồn tại và có đủ số hook
    baseline_path = REPO_ROOT / ".devin" / "hook_hashes.json"
    assert baseline_path.exists()
    data = json.loads(baseline_path.read_text(encoding="utf-8"))
    hook_dir = REPO_ROOT / ".devin" / "hooks"
    actual_hooks = sorted(p.name for p in hook_dir.glob("*.py"))
    baseline_hooks = sorted(Path(k).name for k in data["hooks"].keys())
    assert baseline_hooks == actual_hooks, f"Baseline thiếu hoặc thừa hook: {baseline_hooks} vs {actual_hooks}"


def test_verify_passes():
    # Sau khi generate, verify phải pass
    res = _run(["--verify"])
    assert res.returncode == 0, res.stderr
    assert "OK" in res.stdout or "verified" in res.stdout.lower()


def test_tamper_detected():
    # Nếu sửa một hook, verify phải phát hiện
    hook_path = REPO_ROOT / ".devin" / "hooks" / "session_start.py"
    original = hook_path.read_bytes()
    try:
        hook_path.write_bytes(original + b"\n# tamper test")
        res = _run(["--verify"])
        assert res.returncode != 0
        assert "TAMPERED" in res.stdout
    finally:
        hook_path.write_bytes(original)


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
