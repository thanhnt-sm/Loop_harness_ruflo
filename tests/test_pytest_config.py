#!/usr/bin/env python3
"""Kiểm thử cấu hình pytest/coverage cho AHD (Task T1.2).

Mục đích:
- Đảm bảo `pytest --collect-only` chạy xong mà không lỗi (exit code 0).
- Đảm bảo cổng coverage `--cov-fail-under=80` đang được kích hoạt trong cấu hình.

Cách kiểm tra:
1. Chạy `pytest --collect-only` qua subprocess và kiểm tra exit code.
2. Đọc file pytest.ini, tìm dòng `--cov-fail-under=80` để xác nhận cổng đã active.
   (Cách này ổn định hơn parse --help vì không phụ thuộc phiên bản pytest-cov.)
"""
import os
import subprocess
import sys
from pathlib import Path

# Thư mục gốc của repo (cha của thư mục tests).
REPO_ROOT = Path(__file__).resolve().parent.parent


def _run_pytest(args, timeout=120):
    """Chạy pytest với các tham số cho trước, trả về CompletedProcess.

    Bước 1: dựng lệnh [python, -m, pytest, *args].
    Bước 2: copy môi trường, bật PYTHONUTF8=1 để ổn định Unicode trên Windows.
    Bước 3: chạy subprocess, chặn timeout để không treo test.
    """
    cmd = [sys.executable, "-m", "pytest", *args]
    env = os.environ.copy()
    env["PYTHONUTF8"] = "1"
    try:
        result = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            cwd=REPO_ROOT,
            env=env,
            timeout=timeout,
        )
    except subprocess.TimeoutExpired as exc:
        # Nếu pytest treo quá lâu, báo lỗi rõ ràng thay để test fail mập mờ.
        raise AssertionError(
            f"pytest treo quá {timeout}s với args={args}: {exc}"
        ) from exc
    return result


def test_collect_only_exit_zero():
    """`pytest --collect-only` phải thoát với exit code 0 (không lỗi thu thập test)."""
    result = _run_pytest(["--collect-only", "-q"])
    assert result.returncode == 0, (
        f"pytest --collect-only thất bại (exit={result.returncode}).\n"
        f"STDOUT:\n{result.stdout[-2000:]}\nSTDERR:\n{result.stderr[-2000:]}"
    )


def test_cov_fail_under_gate_active():
    """Cổng coverage 80% phải đang được kích hoạt trong cấu hình pytest.

    Kiểm tra bằng cách đọc pytest.ini và tìm `--cov-fail-under=80`.
    Lý do chọn cách này: ổn định, không phụ thuộc phiên bản pytest-cov
    hay việc parse --help (có thể thay đổi giữa các bản).
    """
    pytest_ini = REPO_ROOT / "pytest.ini"
    # Bước 1: đảm bảo file cấu hình tồn tại (báo lỗi rõ nếu thiếu).
    assert pytest_ini.exists(), f"Không tìm thấy {pytest_ini}"
    # Bước 2: đọc nội dung, xử lý lỗi I/O để test không crash mập mờ.
    try:
        content = pytest_ini.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(f"Không đọc được {pytest_ini}: {exc}") from exc
    # Bước 3: xác nhận cổng 80% có mặt trong addopts.
    assert "--cov-fail-under=80" in content, (
        "Cổng --cov-fail-under=80 không xuất hiện trong pytest.ini; "
        "cổng chất lượng coverage chưa được kích hoạt."
    )


def test_coveragerc_source_and_omit():
    """File .coveragerc phải khai báo đúng source (scripts/hooks) và omit (plan_fsm/tests/.venv)."""
    coveragerc = REPO_ROOT / ".coveragerc"
    assert coveragerc.exists(), f"Không tìm thấy {coveragerc}"
    try:
        content = coveragerc.read_text(encoding="utf-8")
    except OSError as exc:
        raise AssertionError(f"Không đọc được {coveragerc}: {exc}") from exc
    # Kiểm tra các mục source bắt buộc.
    assert ".devin/scripts" in content, ".coveragerc thiếu source .devin/scripts"
    assert ".devin/hooks" in content, ".coveragerc thiếu source .devin/hooks"
    # Kiểm tra các mục omit bắt buộc.
    assert ".devin/scripts/plan_fsm/*" in content, ".coveragerc thiếu omit plan_fsm"
    assert "tests/*" in content, ".coveragerc thiếu omit tests"
    assert ".venv/*" in content, ".coveragerc thiếu omit .venv"
    # Kiểm tra branch coverage được bật.
    assert "branch = True" in content, ".coveragerc chưa bật branch = True"
