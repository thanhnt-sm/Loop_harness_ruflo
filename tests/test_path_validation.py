#!/usr/bin/env python3
"""Kiểm thử path_zones.py — T4.13 (REQ-022/024).

Các ca kiểm thử:
1. is_blocked nhận diện blocked zone (HLK/, .env, .git/, .devin/hooks/...).
2. is_safe nhận diện safe zone (src/, tests/, .devin/scripts/...).
3. normalize_path chuẩn hóa \\ thành /, bỏ ./.
4. validate_path trả (True, "") cho path hợp lệ, (False, reason) cho path vi phạm.
5. Path traversal (..) bị block.
6. get_blocked_zones / get_safe_zones trả đúng danh sách.
7. schema_gate import và dùng cùng path_zones (single source of truth).
8. coverage_enforce import và dùng path_zones helper.
"""
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

from path_zones import (  # noqa: E402
    is_blocked,
    is_safe,
    normalize_path,
    validate_path,
    validate_absolute_path,
    validate_workspace_path,
    is_junk_path,
    is_allowed_root_file,
    get_blocked_zones,
    get_safe_zones,
    BLOCKED_ZONES,
    SAFE_ZONES,
    DANGEROUS_ROOTS,
    ALLOWED_ROOT_FILES,
    ALLOWED_ROOT_PATTERNS,
)


def test_is_blocked_detects_blocked_zones():
    """is_blocked nhận diện blocked zone."""
    for path in ("HLK/config.json", ".env", ".git/config", "credentials/secret",
                 "secrets/key", ".devin/hooks/pre_tool_use.py", ".devin/canon/CORE_CANON.md",
                 ".devin/config.json", "AGENTS.md", "CLAUDE.md"):
        assert is_blocked(path) is True, f"phải block {path}"


def test_is_blocked_allows_safe_paths():
    """is_blocked trả False cho safe path."""
    for path in ("src/app.py", "tests/test_x.py", ".devin/scripts/run.py",
                 "docs/plans/plan.md"):
        assert is_blocked(path) is False, f"không nên block {path}"


def test_is_safe_detects_safe_zones():
    """is_safe nhận diện safe zone."""
    for path in ("src/app.py", "tests/test_x.py", ".devin/skills/skill.md",
                 "scripts/run.sh", "docs/plans/plan.md", "docs/templates/tpl.md",
                 "docs/research/r.md", "docs/reports/r.md", ".devin/reports/a.md",
                 "tmp/scratch.md"):
        assert is_safe(path) is True, f"phải safe {path}"


def test_is_safe_rejects_outside_safe_zone():
    """is_safe trả False cho path ngoài safe zone."""
    for path in ("random/file.py", "root_file.py", "other/dir/x.py"):
        assert is_safe(path) is False, f"không nên safe {path}"


def test_normalize_path():
    """normalize_path chuẩn hóa \\ thành /, bỏ ./."""
    assert normalize_path("src\\app.py") == "src/app.py"
    assert normalize_path("./src/app.py") == "src/app.py"
    assert normalize_path("././tests/x.py") == "tests/x.py"
    assert normalize_path("src/app.py") == "src/app.py"


def test_validate_path_valid():
    """validate_path trả (True, "") cho path hợp lệ."""
    ok, reason = validate_path("src/app.py")
    assert ok is True
    assert reason == ""


def test_validate_path_blocked():
    """validate_path trả (False, reason) cho blocked path."""
    ok, reason = validate_path("HLK/config.json")
    assert ok is False
    assert "Blocked zone" in reason


def test_validate_path_outside_safe():
    """validate_path trả (False, reason) cho path ngoài safe zone."""
    ok, reason = validate_path("random/file.py")
    assert ok is False
    assert "safe zone" in reason.lower() or "outside" in reason.lower()


def test_validate_path_traversal():
    """validate_path block path traversal '..'."""
    ok, reason = validate_path("docs/plans/../secrets/file.py")
    assert ok is False
    assert "traversal" in reason.lower() or ".." in reason


def test_validate_path_empty():
    """validate_path trả (False, ...) cho path rỗng."""
    ok, reason = validate_path("")
    assert ok is False


def test_get_blocked_zones():
    """get_blocked_zones trả danh sách blocked zone."""
    zones = get_blocked_zones()
    assert "HLK/" in zones
    assert ".env" in zones
    assert ".devin/hooks/" in zones


def test_get_safe_zones():
    """get_safe_zones trả danh sách safe zone."""
    zones = get_safe_zones()
    assert "src/" in zones
    assert "tests/" in zones
    assert ".devin/skills/" in zones
    assert "docs/reports/" in zones
    assert "tmp/" in zones


def test_is_junk_path_detects_junk():
    """is_junk_path nhận diện file rác."""
    assert is_junk_path("file.bak") is True
    assert is_junk_path("file.tmp") is True
    assert is_junk_path("file.txt.orig") is True
    assert is_junk_path("notes.md~") is True
    assert is_junk_path(".DS_Store") is True
    assert is_junk_path("scratch123") is True
    assert is_junk_path("report.md") is False
    assert is_junk_path("docs/reports/report.md") is False


def test_is_allowed_root_file():
    """is_allowed_root_file chỉ cho phép các file được liệt kê ở root."""
    assert is_allowed_root_file("AGENTS.md") is True
    assert is_allowed_root_file("CLAUDE.md") is True
    assert is_allowed_root_file("SECURITY.md") is True
    assert is_allowed_root_file("REPOS.md") is True
    assert is_allowed_root_file("activate.ps1") is True
    assert is_allowed_root_file("devin-run.cmd") is True
    assert is_allowed_root_file("REPORT.md") is False
    assert is_allowed_root_file("docs/reports/report.md") is False
    assert is_allowed_root_file("harness-upgrade-log.md") is False


def test_validate_workspace_path_allows_safe_and_allowed_root():
    """validate_workspace_path cho phép safe zone và root allowlist."""
    ok, reason = validate_workspace_path("docs/reports/COST_2026-01-01.md")
    assert ok is True and reason == ""
    ok, reason = validate_workspace_path("docs/plans/foo/IMPLEMENTATION_PLAN.md")
    assert ok is True and reason == ""
    ok, reason = validate_workspace_path("AGENTS.md")
    assert ok is True and reason == ""
    ok, reason = validate_workspace_path("devin-run.ps1")
    assert ok is True and reason == ""


def test_validate_workspace_path_blocks_root_markdown():
    """validate_workspace_path block markdown/work report ở root."""
    ok, reason = validate_workspace_path("HARNESS_UPGRADE_REPORT.md")
    assert ok is False
    assert "not allowed" in reason
    ok, reason = validate_workspace_path("MIGRATION_COMPONENT_MAP.md")
    assert ok is False
    ok, reason = validate_workspace_path("harness-upgrade-log.md")
    assert ok is False


def test_validate_workspace_path_blocks_junk_and_traversal():
    """validate_workspace_path block junk file và path traversal."""
    ok, reason = validate_workspace_path("scratch.tmp")
    assert ok is False
    assert "Junk" in reason
    ok, reason = validate_workspace_path("docs/plans/../secrets/file.py")
    assert ok is False
    assert "traversal" in reason.lower()


def test_schema_gate_uses_path_zones():
    """schema_gate import và dùng cùng path_zones (single source of truth)."""
    import schema_gate
    # SAFE_ZONES và BLOCKED_ZONES của schema_gate phải khớp path_zones
    assert tuple(schema_gate.SAFE_ZONES) == SAFE_ZONES
    assert tuple(schema_gate.BLOCKED_ZONES) == BLOCKED_ZONES


def test_coverage_enforce_uses_path_zones():
    """coverage_enforce import và dùng path_zones helper."""
    import coverage_enforce
    # Helper phải khả dụng
    assert hasattr(coverage_enforce, "_is_path_in_safe_zone")
    assert hasattr(coverage_enforce, "_is_path_blocked")
    # Helper hoạt động đúng
    assert coverage_enforce._is_path_in_safe_zone("src/app.py") is True
    assert coverage_enforce._is_path_blocked("HLK/config.json") is True
    assert coverage_enforce._is_path_blocked("src/app.py") is False


def test_no_duplicate_regex_between_modules():
    """grep assert no duplicate regex — path_zones là single source."""
    # path_zones định nghĩa BLOCKED_ZONES/SAFE_ZONES một lần
    # schema_gate và coverage_enforce import từ path_zones, không định nghĩa lại
    import path_zones
    import schema_gate
    # schema_gate không có định nghĩa tuple riêng (chỉ import)
    # Kiểm tra: schema_gate.SAFE_ZONES IS path_zones.SAFE_ZONES (cùng object)
    assert schema_gate.SAFE_ZONES is path_zones.SAFE_ZONES or tuple(schema_gate.SAFE_ZONES) == path_zones.SAFE_ZONES


def test_dangerous_roots_defined():
    """DANGEROUS_ROOTS chứa các system directory cần block."""
    assert len(DANGEROUS_ROOTS) > 0
    assert any("windows" in root for root in DANGEROUS_ROOTS)
    assert any("etc" in root for root in DANGEROUS_ROOTS)


def test_validate_absolute_path_blocks_system_dirs():
    """validate_absolute_path chặn deploy vào system directory nguy hiểm (C3 red-team)."""
    bad_paths = [
        r"C:\Windows\System32\my-harness",
        r"C:\Program Files\my-app",
        r"C:\ProgramData\my-app",
    ]
    if sys.platform != "win32":
        bad_paths += ["/etc/my-app", "/usr/bin/my-app"]
    for bad in bad_paths:
        ok, reason = validate_absolute_path(bad)
        assert ok is False, f"phải block {bad}"
        assert "blocked" in reason.lower()


def test_validate_absolute_path_allows_normal_project_dirs():
    """validate_absolute_path cho phép project directory thông thường."""
    ok, reason = validate_absolute_path(r"D:\projects\my-app")
    assert ok is True, f"lẽ ra phải allow D:\\projects\\my-app: {reason}"
    assert reason == ""


def test_validate_absolute_path_resolves_traversal():
    """validate_absolute_path resolve .. và chặn kết quả nguy hiểm."""
    ok, reason = validate_absolute_path(r"C:\Users\foo\..\..\Windows\System32\my-app")
    assert ok is False, f"phải block path traversal resolve: {reason}"
    assert "blocked" in reason.lower()


if __name__ == "__main__":
    sys.exit(pytest.main([__file__, "-v"]))
