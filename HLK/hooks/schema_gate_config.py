#!/usr/bin/env python3
"""schema_gate_config — constants + config helpers cho schema_gate.

Tách từ schema_gate.py (monolith 824 lines) để dễ maintain/test.
Giữ NGUYÊN tất cả constants, patterns và helpers path resolution.
"""
from __future__ import annotations

import json
import math
import re
import sys
from pathlib import Path

# T4.13: Import shared path_zones (single source of truth cho blocked/safe zones).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from path_zones import (
        BLOCKED_ZONES as _PATHZONES_BLOCKED,
        SAFE_ZONES as _PATHZONES_SAFE,
        normalize_path as _pathzones_normalize,
    )
except Exception as e:  # noqa: BLE001
    print(f"[schema_gate] unexpected exception: {e}", file=sys.stderr)
    _PATHZONES_BLOCKED = None
    _PATHZONES_SAFE = None
    _pathzones_normalize = None

# U15: Timeout nội bộ — schema_gate phải nhanh (deterministic). Config timeout 3s.
HOOK_TIMEOUT_SECONDS = 2.5

# --- Cấu hình safe zone / blocked zone ---
# T4.13: Dùng shared path_zones làm source of truth; fallback về local nếu import fail.
# Safe zone: agent được phép ghi file vào các thư mục này
SAFE_ZONES = (
    _PATHZONES_SAFE if _PATHZONES_SAFE is not None else
    (
        "src/",
        "tests/",
        ".devin/skills/",
        ".devin/agents/personas/",
        "scripts/",
        "docs/plans/",
        "docs/templates/",
        "docs/research/",
    )
)

# Blocked zone: KHÔNG bao giờ cho phép ghi vào các thư mục/file này
# C-02 fix: Block agent từ việc sửa hooks, canon, config, AGENTS.md —
# nếu agent sửa được hooks thì toàn bộ enforcement bị vô hiệu hóa
BLOCKED_ZONES = (
    _PATHZONES_BLOCKED if _PATHZONES_BLOCKED is not None else
    (
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
)

# --- Secret scan (CVE-2026-AHD-005) ---
# Không còn giới hạn SCAN_TRUNCATE_CHARS: quét TOÀN BỘ output theo chunk
# (64KB) để secret ở giữa output lớn (>400K chars) vẫn bị phát hiện.
# Source of truth: HLK/config/hlk.config.json security_rules.redact_patterns
# (cùng nguồn với HLK/security/sanitizer.js), union với defaults đầy đủ.
SCAN_CHUNK_SIZE = 65536
SCAN_OVERLAP = 1024  # đủ lớn hơn pattern dài nhất; chống secret nằm lệch chunk

# Default patterns (python) — khớp danh sách HLK/security/sanitizer.js + mở rộng
DEFAULT_SECRET_PATTERNS: list[str] = [
    r"ghp_[A-Za-z0-9]{36}",                       # GitHub PAT
    r"gho_[A-Za-z0-9]{36}",                       # GitHub OAuth
    r"ghs_[A-Za-z0-9]{36}",                       # GitHub SSH/session
    r"ghu_[A-Za-z0-9]{36}",                       # GitHub user token
    r"github_pat_[A-Za-z0-9_]{22,}",              # GitHub fine-grained PAT
    r"glpat-[A-Za-z0-9_-]{20}",                   # GitLab PAT
    r"sk-[A-Za-z0-9_-]{20,}",                     # OpenAI/Anthropic key
    r"AKIA[A-Z0-9]{16}",                          # AWS access key ID
    r"AIza[A-Za-z0-9_-]{35}",                     # Google API key
    r"AIzaSy[A-Za-z0-9_-]{33,}",                  # Firebase
    r"xox[baprs]-[A-Za-z0-9-]{10,}",              # Slack token
    r"(sk|pk|rk)_(live|test)_[0-9a-zA-Z]{24,}",   # Stripe
    r"AC[a-z0-9]{32}",                            # Twilio SID
    r"SG\.[a-zA-Z0-9_-]{22}\.[a-zA-Z0-9_-]{43}",  # SendGrid
    r"pub[a-f0-9]{32}",                           # Datadog
    r"npm_[A-Za-z0-9]{36}",                       # npm token
    r"(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----",  # private key
    r"(?i)Bearer\s+[A-Za-z0-9._-]{20,}",          # Bearer token
    r"(?i)aws[_-]?secret[_-]?access[_-]?key\s*=\s*['\"]?[A-Za-z0-9/+=]{40}",
    r"(?i)aws[_-]?session[_-]?token\s*=\s*['\"]?[A-Za-z0-9/+=]{40,}",
    r"\b[a-z][a-z0-9+.-]*://[^:\s]+:[^@\s]+@[^/\s]+",  # DB conn string w/ creds (anchor \b chống backtracking)
    r"\b[a-z][a-z0-9+.-]*://:[^@\s]+@[^/\s]+",  # DB conn, empty userinfo (redis://:pass@host)
    r"(?i)\b(token|password|passwd|api_key|apikey|secret|private_key|client_secret|access_token)\s*[:=]\s*['\"]?[^\s'\"&;|]{8,}",
]

# JWT (3 segments) — KHÔNG dùng regex {20,}\.{20,}\.{20,} (catastrophic
# backtracking O(n²) trên chunk dài). Dùng split-based linear check.
_JWT_MIN_SEGMENT = 20


def _find_jwt(chunk: str) -> bool:
    """Linear JWT detection: 3 segment liên tiếp, mỗi segment >= 20 chars
    base64url ([A-Za-z0-9_-]), phân cách bởi '.'. Không backtracking.
    Cho phép segment đầu/cuối bị bao bởi ký tự không phải base64url
    (vd: 'text eyJ...' hoặc '...R8U end')."""
    if "." not in chunk:
        return False
    parts = chunk.split(".")
    for i in range(len(parts) - 2):
        segs = [parts[i], parts[i + 1], parts[i + 2]]
        valid = True
        for seg in segs:
            # Strip ký tự không hợp lệ ở 2 đầu (space, quote, ...)
            start, end = 0, len(seg)
            while start < end and not (seg[start].isalnum() or seg[start] in "_-"):
                start += 1
            while end > start and not (seg[end - 1].isalnum() or seg[end - 1] in "_-"):
                end -= 1
            if end - start < _JWT_MIN_SEGMENT:
                valid = False
                break
            for ch in seg[start:end]:
                if not (ch.isalnum() or ch in "_-"):
                    valid = False
                    break
            if not valid:
                break
        if valid:
            return True
    return False


# Entropy detection (CVE-2026-AHD-005): pattern chưa biết → Shannon entropy.
# Ngưỡng: entropy > 4.5 bits/char trên chuỗi >= 20 chars = khả nghi secret.
# KHÔNG dùng lookahead (?=...\d) — O(n²) trên run dài không có chữ số.
# Regex thuần class (linear); check chữ số theo token sau khi match.
ENTROPY_MIN_LENGTH = 20
ENTROPY_THRESHOLD = 4.5
_ENTROPY_TOKEN_RE = re.compile(r"[A-Za-z0-9_\-./+]{20,}")


def _shannon_entropy(token: str) -> float:
    """Tính Shannon entropy (bits/char) của chuỗi."""
    if not token:
        return 0.0
    counts: dict[str, int] = {}
    for ch in token:
        counts[ch] = counts.get(ch, 0) + 1
    n = len(token)
    ent = 0.0
    for c in counts.values():
        p = c / n
        ent -= p * (p and math.log2(p))
    return ent


def _load_hlk_secret_patterns() -> list[str]:
    """Load patterns từ HLK config (source of truth) — union với defaults.

    HLK config lỗi/thiếu → FAIL CLOSED nếu security_rules.failClosedOnConfigError=true.
    Nếu false → dùng defaults + warning (legacy behavior).
    """
    patterns = list(DEFAULT_SECRET_PATTERNS)
    fail_closed = False
    config_patterns_loaded = 0
    try:
        root = Path(__file__).resolve().parent.parent.parent  # repo root
        hlk_cfg = root / "HLK" / "config" / "hlk.config.json"
        if hlk_cfg.exists():
            cfg = json.loads(hlk_cfg.read_text(encoding="utf-8"))
            security_rules = cfg.get("security_rules", {})
            fail_closed = bool(security_rules.get("failClosedOnConfigError", False))
            config_patterns = security_rules.get("redact_patterns", []) or []
            for p in config_patterns:
                if isinstance(p, str) and p not in patterns:
                    patterns.append(p)
                    config_patterns_loaded += 1
        else:
            raise FileNotFoundError("HLK config not found")
    except (json.JSONDecodeError, OSError, UnicodeDecodeError, FileNotFoundError) as e:
        if fail_closed:
            raise RuntimeError(
                f"[schema_gate] FAIL-CLOSED: HLK config load failed, cannot proceed without patterns: {e}"
            ) from e
        print(f"[schema_gate] WARN: HLK config load failed, using defaults only: {e}", file=sys.stderr)

    # Fail-closed: if configured to fail closed but no config patterns loaded (only defaults)
    if fail_closed and config_patterns_loaded == 0:
        raise RuntimeError(
            "[schema_gate] FAIL-CLOSED: HLK config has failClosedOnConfigError=true but no redact_patterns loaded"
        )
    return patterns


SECRET_PATTERNS: list[re.Pattern] = [re.compile(p) for p in _load_hlk_secret_patterns()]

# --- Two-stage scan (CVE-2026-AHD-005) ---
# Stage A: _FAST_PREFIX_RE — prefilter tuyến tính (không có tail nặng {n,}).
# Bỏ qua chunk sạch ngay. Stage B: scan patterns — chỉ chạy khi Stage A khớp.
# Stage B dùng các search RỜI (không gộp alternation) để fail nhanh trên chunk vô hại.
_TRIGGER_RE: re.Pattern = re.compile(
    r"://[^:\s]+:[^@\s]+@"                       # DB conn string (bắt tại ://)
    r"|://:[^@\s]+@"                             # DB conn, empty userinfo (redis://:pass@)
    r"|-----BEGIN"                               # private key
    r"|(?:ghp|gho|ghs|ghu)_[A-Za-z0-9]{30,}"     # GitHub tokens
    r"|github_pat_"                              # GitHub fine-grained PAT
    r"|glpat-[A-Za-z0-9_-]{15,}"                 # GitLab PAT
    r"|sk-[A-Za-z0-9_-]{15,}"                    # OpenAI/Anthropic
    r"|AKIA[A-Z0-9]{12,}"                        # AWS key ID
    r"|AIza[A-Za-z0-9_-]{25,}"                   # Google API key
    r"|xox[baprs]-[A-Za-z0-9-]{6,}"              # Slack token
    r"|(?:sk|pk|rk)_(?:live|test)_[0-9a-zA-Z]{20,}"  # Stripe
    r"|SG\.[A-Za-z0-9_-]{15,}"                   # SendGrid
    r"|npm_[A-Za-z0-9]{20,}"                     # npm token
    r"|AC[a-z0-9]{8,}"                           # Twilio SID
    r"|pub[a-f0-9]{8,}"                          # Datadog key
    r"|(?i:Bearer\s+[A-Za-z0-9._-]{15,})"        # Bearer
    r"|(?i:\b(?:token|password|passwd|api_key|apikey|secret|private_key|client_secret|access_token)\s*[:=])"
    r"|(?i:aws_?secret_?access_?key\s*[:=])"
    r"|(?i:aws_?session_?token\s*[:=])"
)

_ENTROPY_TRIGGER_RE: re.Pattern = re.compile(r"[A-Za-z0-9_\-./+]{20,}")

# Trigger cho chunk KHÔNG có ký tự [a-z_:.=] (toàn uppercase): chỉ còn
# AKIA (AWS) và -----BEGIN (private key) có thể khớp.
_UPPER_ONLY_RE: re.Pattern = re.compile(r"AKIA[A-Z0-9]{12,}|-----BEGIN")

# Keyword pre-check cho pattern key=value generic (chạy pattern nặng chỉ khi
# có keyword + [:=] trong chunk).
_KEYWORD_PRE: re.Pattern = re.compile(
    r"\b(?:token|password|passwd|api_key|apikey|secret|private_key|client_secret|access_token)\s*[:=]",
    re.IGNORECASE,
)


def _finalize_slow_indices() -> None:
    """Xác định chỉ mục pattern chậm theo nội dung (không phụ thuộc thứ tự).

    - _SLOW_URL_IDXS: pattern có '://' → guard bằng substring '://'.
    - _SLOW_PATTERN_IDXS: pattern có \\b + tail {n,} → guard bằng substring
      keyword (sk-/pk-/eyJ) hoặc _KEYWORD_PRE.
    """
    for i, p in enumerate(SECRET_PATTERNS):
        pat = p.pattern
        if "://" in pat:
            SLOW_URL_IDXS.add(i)
        elif "\\b(" in pat or "\\b[a-z]" in pat or "\\beyJ" in pat:
            SLOW_PATTERN_IDXS.add(i)
        elif "(token|password|passwd|api_key|apikey|secret" in pat and "\\s*[:=]" in pat:
            KEYWORD_PATTERN_IDX.append(i)


SLOW_URL_IDXS: set[int] = set()
SLOW_PATTERN_IDXS: set[int] = set()
KEYWORD_PATTERN_IDX: list[int] = []

_finalize_slow_indices()

# --- Trường bắt buộc theo loại tool (required fields) ---
# Mỗi tool có cấu trúc output kỳ vọng khác nhau; thiếu trường -> fail
REQUIRED_FIELDS_BY_TOOL: dict[str, list[str]] = {
    "Write": ["content"],
    "Edit": ["old_string", "new_string"],
    "Read": [],
    "Bash": ["command"],
    "Grep": ["pattern"],
    "Glob": ["pattern"],
    "TodoWrite": ["todos"],
}


def _extract_file_path(tool_input: dict) -> str:
    """Trích đường dẫn file từ tool_input (hỗ trợ nhiều tên trường)."""
    for key in ("file_path", "path", "notebook_path", "file"):
        if key in tool_input:
            return str(tool_input[key])
    return ""


def _normalize_path(file_path: str) -> str:
    """Chuẩn hóa đường dẫn: chuyển \\ thành /, bỏ ./ đầu, để so sánh đồng nhất."""
    norm = file_path.replace("\\", "/")
    # Bỏ prefix ./ (thư mục hiện tại)
    while norm.startswith("./"):
        norm = norm[2:]
    return norm


def _resolve_under_root(file_path: str, root: Path) -> Path | None:
    """Resolve đường dẫn dưới repo root. Trả None nếu nằm ngoài root."""
    root_resolved = root.resolve()
    p = Path(file_path).expanduser()
    if p.is_absolute():
        resolved = p.resolve()
    else:
        resolved = (root_resolved / p).resolve()
    try:
        resolved.relative_to(root_resolved)
    except ValueError:
        return None
    return resolved
