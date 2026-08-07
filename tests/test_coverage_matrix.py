#!/usr/bin/env python3
"""Kiểm thử coverage matrix integration với path_zones — T4.13 (REQ-022/024).

Kiểm tra coverage_enforce dùng shared path_zones cho path validation,
không trùng lặp regex/hằng số với schema_gate.

Các ca kiểm thử:
1. coverage_enforce import path_zones helper.
2. _is_path_in_safe_zone hoạt động đúng với safe/blocked path.
3. _is_path_blocked hoạt động đúng.
4. coverage_enforce không định nghĩa lại BLOCKED_ZONES/SAFE_ZONES.
5. Single source of truth: path_zones là module duy nhất định nghĩa zones.
6. schema_gate và coverage_enforce dùng cùng path_zones.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import path_zones  # noqa: E402
import schema_gate  # noqa: E402
import coverage_enforce  # noqa: E402


def test_coverage_enforce_imports_path_zones():
    """coverage_enforce import path_zones helper."""
    assert coverage_enforce._pathzones_is_safe is not None
    assert coverage_enforce._pathzones_is_blocked is not None


def test_coverage_enforce_safe_zone_helper():
    """_is_path_in_safe_zone hoạt động đúng."""
    assert coverage_enforce._is_path_in_safe_zone("src/app.py") is True
    assert coverage_enforce._is_path_in_safe_zone("tests/test_x.py") is True
    # Path ngoài safe zone -> False
    assert coverage_enforce._is_path_in_safe_zone("random/file.py") is False


def test_coverage_enforce_blocked_helper():
    """_is_path_blocked hoạt động đúng."""
    assert coverage_enforce._is_path_blocked("HLK/config.json") is True
    assert coverage_enforce._is_path_blocked(".env") is True
    assert coverage_enforce._is_path_blocked(".devin/hooks/x.py") is True
    # Safe path -> không blocked
    assert coverage_enforce._is_path_blocked("src/app.py") is False


def test_coverage_enforce_no_duplicate_zone_constants():
    """coverage_enforce không định nghĩa lại BLOCKED_ZONES/SAFE_ZONES."""
    # coverage_enforce không có hằng số BLOCKED_ZONES/SAFE_ZONES riêng
    assert not hasattr(coverage_enforce, "BLOCKED_ZONES")
    assert not hasattr(coverage_enforce, "SAFE_ZONES")


def test_single_source_of_truth_path_zones():
    """path_zones là module duy nhất định nghĩa zones."""
    # path_zones có BLOCKED_ZONES và SAFE_ZONES
    assert hasattr(path_zones, "BLOCKED_ZONES")
    assert hasattr(path_zones, "SAFE_ZONES")
    # schema_gate import từ path_zones (cùng giá trị)
    assert tuple(schema_gate.SAFE_ZONES) == path_zones.SAFE_ZONES
    assert tuple(schema_gate.BLOCKED_ZONES) == path_zones.BLOCKED_ZONES


def test_schema_gate_and_coverage_enforce_share_path_zones():
    """schema_gate và coverage_enforce dùng cùng path_zones."""
    # schema_gate dùng SAFE_ZONES/BLOCKED_ZONES từ path_zones
    # coverage_enforce dùng is_safe/is_blocked từ path_zones
    # Cả hai đều tham chiếu cùng source of truth
    assert schema_gate.SAFE_ZONES is path_zones.SAFE_ZONES or tuple(schema_gate.SAFE_ZONES) == path_zones.SAFE_ZONES
    # coverage_enforce helper delegate tới path_zones
    assert coverage_enforce._is_path_in_safe_zone("src/x.py") == path_zones.is_safe("src/x.py")
    assert coverage_enforce._is_path_blocked("HLK/x") == path_zones.is_blocked("HLK/x")


def test_path_zones_consistent_blocked_safe_disjoint():
    """Blocked zone và safe zone không giao nhau."""
    for blocked in path_zones.BLOCKED_ZONES:
        for safe in path_zones.SAFE_ZONES:
            # Không zone nào là prefix của zone kia (disjoint)
            assert not (blocked.startswith(safe) or safe.startswith(blocked)), \
                f"blocked '{blocked}' và safe '{safe}' giao nhau"


def test_deploy_template_uses_path_zones():
    """deploy-template.ps1 có tham chiếu path_zones.py (T4.13)."""
    deploy_script = REPO_ROOT / "tools" / "deploy-template.ps1"
    if not deploy_script.exists():
        pytest.skip("deploy-template.ps1 không tồn tại")
    content = deploy_script.read_text(encoding="utf-8")
    assert "path_zones" in content
    assert "path_zones.py" in content


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
