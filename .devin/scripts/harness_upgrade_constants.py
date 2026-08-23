#!/usr/bin/env python3
"""harness_upgrade_constants.py — Constants cho harness upgrade loop.

Chứa các PRIORITY_RULES, SKIP_PATTERNS, RESTRICTED_PATTERNS, AUDIT_SKIP_PATTERNS
và các DEFAULT_* constants.
"""

from __future__ import annotations
import sys
from pathlib import Path

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOOP_STATE_DIR = REPO_ROOT / ".devin" / "state"
LOOP_STATE_FILE = LOOP_STATE_DIR / "harness_upgrade_loop.json"
LOOP_LOG_FILE = LOOP_STATE_DIR / "harness_upgrade_loop.md"
LOG_FILE = REPO_ROOT / "docs" / "reports" / "harness-upgrade-log.md"

# Priority thấp = quan trọng hơn.
PRIORITY_RULES = [
    (0, r"test_destructive_block|plan_enforce"),
    (1, r"test_cve_remediation_phase3"),
    (2, r"test_cve_remediation_phase2"),
    (3, r"test_cve_remediation_phase1"),
    (4, r"test_pytest_config"),
    (5, r"test_coverage"),
    (6, r"test_opencode_harness"),
    (7, r"test_phase3_extra_cov|sbom|cosign"),
]

# Không còn bỏ qua HLK tests vì đã fix cross-platform (ESM import + file:// URL).
# Nếu cần loại trừ một target ngoài phạm vi, thêm vào đây với lý do rõ ràng.
SKIP_PATTERNS = []

# Các file/path KHÔNG được phép sửa bởi devin -p trong auto-execute;
# khớp với lời nhắc của _build_execute_task. Dùng để revert nếu devin -p vượt quyền.
RESTRICTED_PATTERNS = [
    r"^sbom/",
    r"\.env$",
    r"hook_hashes\.json$",
    r"^HLK/",
    r"^\.devin/scripts/[^/]+\.py$",
    r"^\.devin/hooks/[^/]+\.py$",
    r"^pytest\.ini$",
]

# Audit findings liên quan HLK/secrets sẽ bị bỏ qua để không vi phạm REDLINES.
AUDIT_SKIP_PATTERNS = [
    r"[Hh][Ll][Kk]",
    r"\.env",
    r"[Ss]ecrets?[/\\]",
    r"[Cc]redentials?[/\\]",
    r"\.pem",
    r"\.key",
]

DEFAULT_MAX_ITERATIONS = 10
DEFAULT_MAX_TIME_MIN = 120
DEFAULT_CONVERGENCE = 3
DEFAULT_PROACTIVE_COVERAGE_THRESHOLD = 80.0