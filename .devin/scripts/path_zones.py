#!/usr/bin/env python3
"""path_zones.py — Shared source of truth cho blocked/safe zones (T4.13, REQ-022/024).

Mục đích: định nghĩa MỘT LẦN danh sách blocked zone và safe zone dùng chung
cho schema_gate.py, coverage_enforce.py, và tools/deploy-template.ps1.
Tránh trùng lặp regex/hằng số giữa các hook và script packaging.

Hàm chính:
  - is_blocked(path: str) -> bool   : kiểm tra đường dẫn có nằm trong blocked zone.
  - is_safe(path: str) -> bool      : kiểm tra đường dẫn có nằm trong safe zone.
  - normalize_path(p: str) -> str   : chuẩn hóa đường dẫn để so khớp.
  - get_blocked_zones() -> tuple    : trả danh sách blocked zone.
  - get_safe_zones() -> tuple       : trả danh sách safe zone.

Tuân thủ safe zone (.devin/scripts/), không đụng HLK/.env/security policies.
File < 500 dòng, typed interface.
"""
from __future__ import annotations

import fnmatch
import os
import sys
from pathlib import Path


# --- Dangerous system roots: không cho deploy đến (C3 red-team finding) ---
# Đường dẫn tuyệt đối resolve xong vẫn nằm trong các root này → block.
DANGEROUS_ROOTS: tuple[str, ...] = (
    "c:/windows",
    "c:/program files",
    "c:/program files (x86)",
    "c:/programdata",
    "c:/$recycle.bin",
    "/system",
    "/usr/bin",
    "/usr/sbin",
    "/bin",
    "/sbin",
    "/etc",
    "/lib",
    "/lib64",
    "/opt",
    "/var",
)


# --- Blocked zone: KHÔNG bao giờ cho phép ghi vào ---
# C-02 fix: Block agent từ việc sửa hooks, canon, config, AGENTS.md —
# nếu agent sửa được hooks thì toàn bộ enforcement bị vô hiệu hóa.
BLOCKED_ZONES: tuple[str, ...] = (
    "HLK/",
    ".env",
    ".git/",
    "credentials/",
    "secrets/",
    # C-02: Agent KHÔNG được sửa hooks (sẽ vô hiệu hóa enforcement)
    ".devin/hooks/",
    # C-02: Agent KHÔNG được sửa canon (will change red lines)
    ".devin/canon/",
    # C-02: Agent KHÔNG được sửa config (will change permissions/deny list)
    ".devin/config.json",
    ".devin/config.local.json",
    ".devin/config.minimal.json",
    ".devin/tool_registry.json",
    ".devin/risk_contract.json",
    ".devin/hook_hashes.json",
    ".devin/memory_config.json",
    ".devin/mcp_config.json",
    # C-02: Agent KHÔNG được sửa AGENTS.md (will change own rules)
    "AGENTS.md",
    ".devin/AGENTS.md",
    "CLAUDE.md",
)

# --- Safe zone: agent được phép ghi file vào các thư mục này ---
SAFE_ZONES: tuple[str, ...] = (
    "src/",
    "tests/",
    ".devin/skills/",
    ".devin/agents/personas/",
    ".devin/reports/",
    "scripts/",
    "docs/plans/",
    "docs/templates/",
    "docs/research/",
    "docs/reports/",
    "tmp/",
    # Worktrees: worker cần ghi trong worktree của mình (schema_gate nên scope theo worker).
    ".worktrees/",
)

# --- Root allowlist: file được phép nằm trực tiếp ở root ---
# Cập nhật kèm WORKSPACE_GOVERNANCE.md nếu thêm entry file/config/launcher mới.
ALLOWED_ROOT_FILES: tuple[str, ...] = (
    "AGENTS.md",
    "CLAUDE.md",
    "SECURITY.md",
    "REPOS.md",
    "LICENSE",
    ".gitignore",
    ".gitattributes",
    ".ignore",
    "opencode.json",
    "pyproject.toml",
    "pytest.ini",
    "package.json",
    "package-lock.json",
    "requirements-lock.txt",
    "renovate.json",
    "loop",
    "session",
)

# Pattern cho root file (không dùng cho safe zone).
ALLOWED_ROOT_PATTERNS: tuple[str, ...] = (
    "activate.*",
    "devin-run.*",
    "devin-swe.*",
)

# --- Junk file patterns: cấm sinh ra trong workspace ---
JUNK_EXTENSIONS: tuple[str, ...] = (
    ".bak", ".tmp", ".orig", ".swp", ".swo", ".temp", "~"
)

JUNK_FILENAMES: tuple[str, ...] = (
    ".DS_Store",
    "Thumbs.db",
    ".fuse_hidden*",
)


def is_junk_path(file_path: str) -> bool:
    """Kiểm tra đường dẫn có phải file rác (bak/tmp/...) không."""
    if not file_path:
        return False
    norm = normalize_path(file_path).lower()
    name = Path(norm).name
    if any(name.endswith(ext) for ext in JUNK_EXTENSIONS):
        return True
    if any(fnmatch.fnmatch(name, pat.lower()) for pat in JUNK_FILENAMES):
        return True
    # `untitled*` / `scratch*` vô danh
    if name.startswith("untitled") or name.startswith("scratch"):
        return True
    return False


def is_allowed_root_file(file_path: str) -> bool:
    """Kiểm tra file nằm trực tiếp ở root có được phép không.

    Chỉ áp dụng cho file ở depth=1 (không có thư mục con).
    """
    if not file_path:
        return False
    norm = normalize_path(file_path)
    # Bỏ prefix ./
    if norm.startswith("./"):
        norm = norm[2:]
    # Chỉ xét path tương đối 1 cấp hoặc absolute nằm dưới repo root.
    parts = norm.split("/")
    # Nếu có nhiều hơn 1 phần → không phải root file.
    if len(parts) != 1:
        return False
    name = parts[0]
    if name in ALLOWED_ROOT_FILES:
        return True
    if any(fnmatch.fnmatch(name, pat) for pat in ALLOWED_ROOT_PATTERNS):
        return True
    return False


def _repo_root() -> Path:
    """Repo root: parent của .devin/scripts/path_zones.py."""
    return Path(__file__).resolve().parent.parent.parent


def _relative_to_repo(file_path: str) -> str:
    """Chuyển absolute path nằm trong repo thành relative; ngoài repo giữ nguyên."""
    p = Path(file_path)
    if p.is_absolute():
        try:
            rel = p.resolve().relative_to(_repo_root().resolve())
            return normalize_path(str(rel))
        except ValueError:
            return normalize_path(file_path)
    return normalize_path(file_path)


def validate_workspace_path(file_path: str) -> tuple[bool, str]:
    """Kiểm tra đường dẫn ghi file mới có tuân workspace governance không.

    Quy tắc:
      - Không cho path traversal.
      - Không cho junk file.
      - Blocked zone → block.
      - Safe zone / tmp/ → allow.
      - Root file phải nằm trong ALLOWED_ROOT_FILES/PATTERNS.
      - Các path còn lại (vd. markdown ngẫu nhiên ở root) → block + gợi ý đúng chỗ.
    """
    if not file_path:
        return (False, "đường dẫn rỗng")

    rel = _relative_to_repo(file_path)
    norm = normalize_path(rel)
    if ".." in norm.split("/"):
        return (False, f"Path traversal blocked: '..' detected in '{file_path}'")

    # Junk file
    if is_junk_path(norm):
        return (False, f"Junk file blocked: '{file_path}' — use tmp/ for scratch")

    # Root file allowlist (phải kiểm tra trước blocked zone vì AGENTS.md/CLAUDE.md
    # nằm trong allowlist nhưng cũng bị đánh dấu blocked để hạn chế sửa đổi tùy tiện).
    if is_allowed_root_file(norm):
        return (True, "")

    # Blocked zone
    if is_blocked(norm):
        return (False, f"Blocked zone: writing to '{file_path}' is not allowed")

    # Safe zone
    if is_safe(norm):
        return (True, "")

    # Nếu là file ở root, gợi ý đúng chỗ
    if "/" not in norm:
        return (
            False,
            f"Root file '{file_path}' is not allowed. "
            "Place plans in docs/plans/<slug>/, reports in docs/reports/<SUBJECT>_<YYYY-MM-DD>.md, "
            "research in docs/research/<topic>.md, templates in docs/templates/."
        )

    # Các đường dẫn khác ngoài safe/blocked
    return (
        False,
        f"Path '{file_path}' is outside allowed workspace zones. "
        f"Safe zones: {', '.join(SAFE_ZONES)}; root allowlist: {', '.join(ALLOWED_ROOT_FILES + ALLOWED_ROOT_PATTERNS)}"
    )


def normalize_path(file_path: str) -> str:
    """Chuẩn hóa đường dẫn: chuyển \\ thành /, bỏ ./ đầu, để so sánh đồng nhất."""
    norm = file_path.replace("\\", "/")
    # Bỏ prefix ./ (thư mục hiện tại)
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def get_blocked_zones() -> tuple[str, ...]:
    """Trả danh sách blocked zone (source of truth)."""
    return BLOCKED_ZONES


def get_safe_zones() -> tuple[str, ...]:
    """Trả danh sách safe zone (source of truth)."""
    return SAFE_ZONES


def is_blocked(file_path: str) -> bool:
    """Kiểm tra đường dẫn có nằm trong blocked zone không.

    Nhận vào:
        file_path — đường dẫn cần kiểm tra (relative hoặc absolute).

    Trả về True nếu đường dẫn bắt đầu bằng một blocked zone.
    So sánh không phân biệt hoa thường để chống bypass trên FS case-sensitive.
    """
    if not file_path:
        return False
    norm = normalize_path(file_path).lower()
    for zone in BLOCKED_ZONES:
        zone_norm = zone.replace("\\", "/").lower()
        if norm.startswith(zone_norm) or norm == zone_norm.rstrip("/"):
            return True
    return False


def is_safe(file_path: str) -> bool:
    """Kiểm tra đường dẫn có nằm trong safe zone không.

    Nhận vào:
        file_path — đường dẫn cần kiểm tra (relative hoặc absolute).

    Trả về True nếu đường dẫn bắt đầu bằng ít nhất một safe zone.
    """
    if not file_path:
        return False
    norm = normalize_path(file_path).lower()
    return any(norm.startswith(sz.lower()) for sz in SAFE_ZONES)


def validate_path(file_path: str) -> tuple[bool, str]:
    """Kiểm tra đường dẫn hợp lệ để ghi (không blocked, nằm trong safe zone).

    Nhận vào:
        file_path — đường dẫn cần kiểm tra.

    Trả về (ok, reason):
      - (True, "") nếu hợp lệ.
      - (False, reason) nếu blocked hoặc ngoài safe zone.
    """
    if not file_path:
        return (False, "đường dẫn rỗng")
    norm = normalize_path(file_path).lower()
    # Kiểm tra path traversal
    if ".." in norm.split("/"):
        return (False, f"Path traversal blocked: '..' detected in path")
    # Kiểm tra blocked zone
    for zone in BLOCKED_ZONES:
        zone_norm = zone.replace("\\", "/").lower()
        if norm.startswith(zone_norm) or norm == zone_norm.rstrip("/"):
            return (False, f"Blocked zone: writing to '{zone}' is not allowed")
    # Kiểm tra safe zone
    if not is_safe(file_path):
        return (False, f"File outside safe zone. Safe zones: {', '.join(SAFE_ZONES)}")
    return (True, "")


def _resolved_norm(file_path: str) -> str:
    """Trả về đường dẫn chuẩn hóa đã resolve `..` và symlinks, dạng `/` lowercase.

    Dùng Path.resolve(strict=False) để bắt path traversal kể cả khi đích chưa tồn tại.
    """
    try:
        resolved = Path(file_path).resolve(strict=False)
    except (OSError, ValueError) as exc:
        # Nếu resolve thất bại (path quá dài, ký tự không hợp lệ), fallback norm
        return normalize_path(file_path).lower()
    return normalize_path(str(resolved)).lower()


def validate_absolute_path(file_path: str) -> tuple[bool, str]:
    """Kiểm tra đường dẫn tuyệt đối cho deploy target (không block, không path traversal, không system dir).

    Khác validate_path ở chỗ: không yêu cầu safe zone, vì target có thể nằm ngoài workspace.
    Vẫn chặn blocked zones, path traversal, và dangerous system roots.
    """
    if not file_path:
        return (False, "đường dẫn rỗng")
    norm = _resolved_norm(file_path)
    # Bảo mật: kiểm tra CẢ dạng raw (chưa resolve) để chặn system dir dạng
    # Windows path (C:\Windows\...) trên nền Linux — Path.resolve() coi backslash
    # là ký tự thường nên sẽ prefix cwd, làm bypass toàn bộ dangerous-root check.
    raw_norm = normalize_path(file_path).lower()
    # Kiểm tra path traversal: `..` ở cả raw lẫn resolved đều chặn
    if ".." in norm.split("/") or ".." in raw_norm.split("/"):
        return (False, f"Path traversal blocked: '..' detected in resolved path")
    # Kiểm tra dangerous system roots (raw trước — bắt cả dạng drive-letter)
    for root in DANGEROUS_ROOTS:
        if raw_norm.startswith(root) or norm.startswith(root):
            return (False, f"System directory blocked: writing to '{root}' is not allowed")
    # Kiểm tra blocked zone
    for zone in BLOCKED_ZONES:
        zone_norm = zone.replace("\\", "/").lower()
        if norm.startswith(zone_norm) or norm == zone_norm.rstrip("/"):
            return (False, f"Blocked zone: writing to '{zone}' is not allowed")
    return (True, "")


def _cli() -> int:
    """CLI stub:
    - check <path>       : kiểm tra đường dẫn hợp lệ không.
    - check-absolute <path> : kiểm tra đường dẫn tuyệt đối (chỉ block/traversal, không kiểm safe zone).
    - list blocked       : liệt kê blocked zones.
    - list safe          : liệt kê safe zones.
    """
    if len(sys.argv) < 2:
        print("Usage: path_zones.py [check <path> | check-absolute <path> | list blocked | list safe]", file=sys.stderr)
        return 1
    cmd = sys.argv[1]
    if cmd == "check":
        if len(sys.argv) < 3:
            print("Usage: check <path>", file=sys.stderr)
            return 1
        ok, reason = validate_path(sys.argv[2])
        if ok:
            print("OK")
            return 0
        print(f"BLOCKED: {reason}", file=sys.stderr)
        return 2
    if cmd == "check-absolute":
        if len(sys.argv) < 3:
            print("Usage: check-absolute <path>", file=sys.stderr)
            return 1
        ok, reason = validate_absolute_path(sys.argv[2])
        if ok:
            print("OK")
            return 0
        print(f"BLOCKED: {reason}", file=sys.stderr)
        return 2
    if cmd == "list":
        what = sys.argv[2] if len(sys.argv) > 2 else "all"
        if what in ("blocked", "all"):
            print("Blocked zones:")
            for z in BLOCKED_ZONES:
                print(f"  {z}")
        if what in ("safe", "all"):
            print("Safe zones:")
            for z in SAFE_ZONES:
                print(f"  {z}")
        return 0
    print(f"Unknown command: {cmd}", file=sys.stderr)
    return 1


if __name__ == "__main__":
    raise SystemExit(_cli())
