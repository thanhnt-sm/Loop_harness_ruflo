#!/usr/bin/env python3
"""Kiểm thử cho hook_integrity.py (SHA256 hash + hook chain order)."""
import json
import os
import subprocess
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPT = REPO_ROOT / ".devin" / "scripts" / "hook_integrity.py"
ORDER_BASELINE = REPO_ROOT / ".devin" / "hook_order.json"


def _run(args):
    # Chạy hook_integrity.py
    cmd = [sys.executable, str(SCRIPT), *args]
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


# ---------- T1.5: hook order verification ----------

def _import_module():
    # Import module để gọi trực tiếp các hàm helper (tránh phụ thuộc subprocess).
    import importlib.util
    spec = importlib.util.spec_from_file_location("hook_integrity", SCRIPT)
    mod = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(mod)
    return mod


def test_regen_creates_order_baseline():
    # --regen phải tạo file hook_order.json
    if ORDER_BASELINE.exists():
        ORDER_BASELINE.unlink()
    try:
        res = _run(["--regen"])
        assert res.returncode == 0, res.stdout + res.stderr
        assert ORDER_BASELINE.exists()
        data = json.loads(ORDER_BASELINE.read_text(encoding="utf-8"))
        assert "hook_order" in data and isinstance(data["hook_order"], list)
        assert len(data["hook_order"]) > 0
    finally:
        # Đảm bảo baseline được tạo lại để test sau không fail do thiếu.
        if not ORDER_BASELINE.exists():
            _run(["--regen"])


def test_verify_order_passes_when_correct():
    # Khi baseline khớp config hiện tại, --verify-order exit 0
    _run(["--regen"])  # đảm bảo baseline khớp trạng thái hiện tại
    res = _run(["--verify-order"])
    assert res.returncode == 0, res.stdout + res.stderr
    assert "OK" in res.stdout


def test_verify_order_detects_mismatch():
    # Nếu baseline bị sửa thành thứ tự sai, --verify-order exit 1
    _run(["--regen"])
    original = ORDER_BASELINE.read_text(encoding="utf-8")
    data = json.loads(original)
    # Đảo ngược thứ tự để tạo mismatch
    data["hook_order"] = list(reversed(data["hook_order"]))
    try:
        ORDER_BASELINE.write_text(json.dumps(data, indent=2), encoding="utf-8")
        res = _run(["--verify-order"])
        assert res.returncode == 1, res.stdout + res.stderr
        assert "mismatch" in res.stdout.lower() or "ORDER" in res.stdout
    finally:
        ORDER_BASELINE.write_text(original, encoding="utf-8")


def test_verify_order_missing_baseline_exits_1():
    # Thiếu baseline -> exit 1, không auto-regen
    if ORDER_BASELINE.exists():
        original = ORDER_BASELINE.read_text(encoding="utf-8")
        ORDER_BASELINE.unlink()
    else:
        original = None
    try:
        res = _run(["--verify-order"])
        assert res.returncode == 1, res.stdout + res.stderr
        # Phải gợi ý chạy --regen, không tự regenerate
        assert "--regen" in res.stdout
        assert not ORDER_BASELINE.exists(), "Không được auto-regen baseline"
    finally:
        if original is not None:
            ORDER_BASELINE.write_text(original, encoding="utf-8")
        else:
            _run(["--regen"])


def test_compare_order_unit():
    # Unit test cho compare_order: đúng, sai thứ tự, thiếu hook
    mod = _import_module()
    ok, diffs = mod.compare_order(["a", "b", "c"], ["a", "b", "c"])
    assert ok and diffs == []
    ok, diffs = mod.compare_order(["a", "c", "b"], ["a", "b", "c"])
    assert not ok
    ok, diffs = mod.compare_order(["a", "b"], ["a", "b", "c"])
    assert not ok
    assert any("MISSING" in d for d in diffs)


def test_extract_hook_order_from_config():
    # extract_hook_order phải trích được ít nhất pre_tool_use và post_tool_use
    mod = _import_module()
    order = mod.extract_hook_order(REPO_ROOT)
    assert "pre_tool_use" in order
    assert "post_tool_use" in order
    # pre_tool_use phải xuất hiện trước post_tool_use (PreToolUse chạy trước PostToolUse)
    assert order.index("pre_tool_use") < order.index("post_tool_use")


if __name__ == "__main__":
    import pytest
    sys.exit(pytest.main([__file__, "-v"]))
