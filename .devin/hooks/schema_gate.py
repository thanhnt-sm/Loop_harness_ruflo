#!/usr/bin/env python3
"""Schema gate — cổng xác định kiểm tra deterministic cho mọi output của agent.

Hook loại PostToolUse: chạy sau mỗi tool call, đưa output qua một pipeline
các cổng kiểm tra deterministic (rẻ, nhanh, không thể bị jailbreak).

Nhận JSON trên stdin:
  {"tool_name": "Write", "tool_input": {...}, "tool_output": {...}, "session_id": "..."}

Pipeline cổng (theo thứ tự ưu tiên, rẻ nhất trước):
  1. JSON schema validation — nếu output là JSON, kiểm tra cấu trúc
  2. Required fields check — kiểm tra trường bắt buộc theo loại tool
  3. Secret scan — quét regex cho API key, token, password (không bao giờ cho phép)
  4. Symbol verification — cho Write/Edit: grep hàm kỳ vọng trong plan
  5. File path validation — không path traversal, không ghi ngoài safe zone

Luật cổng: cổng ĐẦU TIÊN FAIL -> block, trả lỗi cho agent, không chạy cổng còn lại.

Exit codes:
  0 = tất cả cổng pass (cho phép tool call)
  1 = có cổng fail (block, trả lỗi cho agent qua stderr)
"""
from __future__ import annotations

import json
import os
import re
import sys
import threading
from pathlib import Path

# T4.13: Import shared path_zones (single source of truth cho blocked/safe zones).
sys.path.insert(0, str(Path(__file__).resolve().parent.parent / "scripts"))
try:
    from path_zones import (
        BLOCKED_ZONES as _PATHZONES_BLOCKED,
        SAFE_ZONES as _PATHZONES_SAFE,
        normalize_path as _pathzones_normalize,
    )
except Exception as e:
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
        ent -= p * (p and __import__("math").log2(p))
    return ent


def _load_hlk_secret_patterns() -> list[str]:
    """Load patterns từ HLK config (source of truth) — union với defaults.

    HLK config lỗi/thiếu → chỉ dùng defaults (KHÔNG silent fail: ghi cảnh báo).
    """
    patterns = list(DEFAULT_SECRET_PATTERNS)
    try:
        root = Path(__file__).resolve().parent.parent.parent  # repo root
        hlk_cfg = root / "HLK" / "config" / "hlk.config.json"
        if hlk_cfg.exists():
            cfg = json.loads(hlk_cfg.read_text(encoding="utf-8"))
            for p in cfg.get("security_rules", {}).get("redact_patterns", []) or []:
                if isinstance(p, str) and p not in patterns:
                    patterns.append(p)
    except (json.JSONDecodeError, OSError, UnicodeDecodeError) as e:
        print(f"[schema_gate] WARN: HLK config load failed, using defaults only: {e}", file=sys.stderr)
    return patterns


SECRET_PATTERNS: list[re.Pattern] = [re.compile(p) for p in _load_hlk_secret_patterns()]

# --- Two-stage scan (CVE-2026-AHD-005) ---
# Stage A: _FAST_PREFIX_RE — prefilter tuyến tính (không có tail nặng {n,}).
# Bỏ qua chunk sạch ngay. Stage B: scan patterns — chỉ chạy khi Stage A khớp.
# Stage B dùng các search RỜI (không gộp alternation: 38 branch → 78ms/chunk
# do engine thử mọi branch tại mọi vị trí). Các pattern chậm (có tail {n,}
# hoặc (?i) alternation) được guard bằng pre-check rẻ (substring/regex nhỏ)
# để fail nhanh trên chunk vô hại.
# Stage A: chỉ giữ "phần đầu" đặc trưng của mỗi pattern, bỏ tail nặng.
# Thiết kế để thất bại nhanh: literal prefix / char class có giới hạn, không
# có {n,} dài theo sau literal gây backtracking. Linear trên mọi input.
# Tách 2 regex:
#  - _TRIGGER_RE: shape cụ thể (ghp_, AKIA, keyword:, ://, BEGIN...) → chạy
#    FULL pattern scan (chunk thật sự khả nghi).
#  - _ENTROPY_TRIGGER_RE: run 20+ chars (có thể chứa secret lạ) → chỉ chạy
#    entropy + jwt check (rẻ). Chunk chỉ khớp regex này KHÔNG chạy full scan
#    (tiết kiệm 35 pattern × mọi chunk — ví dụ văn bản có từ dài 20+ ký tự).
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
    - _SLOW_PATTERN_IDXS: pattern có \b + tail {n,} → guard bằng substring
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


def _scan_chunk_secrets(chunk: str) -> tuple[re.Match, int] | None:
    """Stage B: scan patterns trên 1 chunk. Trả (match, index) nếu tìm thấy.

    Thứ tự: patterns nhanh (literal prefix) trước; patterns chậm chỉ chạy
    khi pre-check guard khớp (fail-fast trên chunk vô hại).
    """
    for i, p in enumerate(SECRET_PATTERNS):
        if i in SLOW_PATTERN_IDXS or i in SLOW_URL_IDXS or i in KEYWORD_PATTERN_IDX:
            continue
        m = p.search(chunk)
        if m:
            return m, i
    # Patterns chậm với guard riêng
    if "://" in chunk:
        for i in SLOW_URL_IDXS:
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
    if _KEYWORD_PRE.search(chunk):
        for i in KEYWORD_PATTERN_IDX:
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
    for i in list(SLOW_PATTERN_IDXS):
        pat = SECRET_PATTERNS[i].pattern
        if ("sk-" in chunk or "pk-" in chunk) and ("sk-" in pat or "pk-" in pat):
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
        if "eyJ" in chunk and "eyJ" in pat:
            m = SECRET_PATTERNS[i].search(chunk)
            if m:
                return m, i
    return None


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


def _gate_json_schema(tool_output) -> dict | None:
    """Cổng 1: JSON schema validation.

    Nếu output là chuỗi JSON hoặc dict, thử parse và kiểm tra cấu trúc cơ bản.
    Trả về dict lỗi nếu fail, None nếu pass (hoặc không áp dụng).
    """
    # Nếu không phải JSON / dict -> bỏ qua cổng này (không áp dụng)
    if tool_output is None:
        return None
    if isinstance(tool_output, dict):
        # Đã là dict -> coi như pass cổng JSON (cấu trúc hợp lệ)
        return None
    if isinstance(tool_output, str):
        stripped = tool_output.strip()
        if not stripped:
            return None
        # Chỉ kiểm tra nếu bắt đầu bằng { hoặc [ (trông như JSON)
        if stripped[0] not in "{[":
            return None
        try:
            json.loads(stripped)
            return None  # parse thành công -> pass
        except json.JSONDecodeError as e:
            return {
                "reason": f"Invalid JSON: {e}",
                "details": {"position": getattr(e, "pos", -1)},
            }
    return None


def _gate_required_fields(tool_name: str, tool_input: dict, tool_output) -> dict | None:
    """Cổng 2: Required fields check theo loại tool.

    Kiểm tra tool_input có đủ các trường bắt buộc không.
    Trả về dict lỗi nếu thiếu, None nếu pass.
    """
    required = next(
        (v for k, v in REQUIRED_FIELDS_BY_TOOL.items() if k.lower() == tool_name.lower()),
        None,
    )
    if not required:
        return None  # tool không có yêu cầu trường -> pass
    missing = [f for f in required if f not in tool_input or tool_input[f] in (None, "")]
    if missing:
        return {
            "reason": f"Missing required fields: {', '.join(missing)}",
            "details": {"missing_fields": missing, "tool": tool_name},
        }
    return None


def _iter_chunks(text: str) -> list[str]:
    """CVE-2026-AHD-005: Chia text thành các chunk có overlap.

    Chunk 64KB + overlap 1KB ở hai đầu để pattern không bị cắt lệch chunk.
    """
    if len(text) <= SCAN_CHUNK_SIZE:
        return [text]
    chunks: list[str] = []
    start = 0
    n = len(text)
    while start < n:
        end = min(start + SCAN_CHUNK_SIZE, n)
        # Thêm overlap trước (trừ chunk đầu) và sau (trừ chunk cuối)
        chunk_start = max(0, start - SCAN_OVERLAP) if start > 0 else 0
        chunk_end = min(n, end + SCAN_OVERLAP) if end < n else n
        chunks.append(text[chunk_start:chunk_end])
        start = end
    return chunks


def _gate_secret_scan(tool_output) -> dict | None:
    """Cổng 3: Secret scan — quét TOÀN BỘ output (chunked, không truncate).

    CVE-2026-AHD-005 fix:
    - Bỏ giới hạn SCAN_TRUNCATE_CHARS (trước đây bỏ sót secret ở giữa output
      lớn > 400K chars).
    - Quét từng chunk 64KB + overlap; pattern = HLK config ∪ defaults.
    - Bổ sung entropy-based detection cho định dạng secret chưa biết.
    """
    if tool_output is None:
        return None
    # Chuyển output thành chuỗi để quét
    if isinstance(tool_output, dict):
        text = json.dumps(tool_output, ensure_ascii=False)
    elif isinstance(tool_output, str):
        text = tool_output
    else:
        text = str(tool_output)

    for chunk in _iter_chunks(text):
        # Stage A1: trigger cụ thể → full pattern scan
        # Guard [a-z_:.=] rẻ: chunk toàn uppercase không cần chạy _TRIGGER_RE
        # (chỉ AKIA/BEGIN khớp được → _UPPER_ONLY_RE).
        if re.search(r"[a-z_:.=]", chunk) is not None:
            hit = _scan_chunk_secrets(chunk) if _TRIGGER_RE.search(chunk) is not None else None
        elif _UPPER_ONLY_RE.search(chunk) is not None:
            hit = _scan_chunk_secrets(chunk)
        else:
            hit = None
        if hit is not None:
            match, pattern_idx = hit
            pattern = SECRET_PATTERNS[pattern_idx]
            # Che giá trị secret trước khi báo cáo (không log secret thật)
            masked = match.group(0)[:4] + "***" + match.group(0)[-2:]
            return {
                "reason": f"Secret detected in output (masked): {masked}",
                "details": {"pattern": pattern.pattern, "masked_value": masked},
            }
        # Stage A2: run dài 20+ (khả năng secret lạ) → entropy + jwt
        if _ENTROPY_TRIGGER_RE.search(chunk) is None:
            continue
        # 2) JWT-style token — linear split-based check
        if _find_jwt(chunk):
            return {
                "reason": "JWT token detected in output",
                "details": {"pattern": "jwt", "masked_value": "***"},
            }
        # 3) Entropy-based: định dạng secret chưa biết (finditer linear).
        #    Digit check bằng regex C-level (không dùng any() Python — chậm).
        if re.search(r"\d", chunk) is not None:
            for token_match in _ENTROPY_TOKEN_RE.finditer(chunk):
                token = token_match.group(0)
                # Regex {20,} nên len(token) >= 20 luôn; chỉ cần check digit
                if re.search(r"\d", token) is None:
                    continue
                if _shannon_entropy(token) > ENTROPY_THRESHOLD:
                    masked = token[:4] + "***" + token[-2:]
                    return {
                        "reason": f"High-entropy secret-like token detected (masked): {masked}",
                        "details": {"pattern": "entropy", "masked_value": masked,
                                    "entropy": round(_shannon_entropy(token), 2)},
                    }
    return None


def _gate_symbol_verification(tool_name: str, tool_input: dict, root: Path) -> dict | None:
    """Cổng 4: Symbol verification — cho Write/Edit, grep hàm kỳ vọng trong plan.

    Đọc IMPLEMENTATION_PLAN.md (nếu có) để tìm các symbol (hàm/class) kỳ vọng
    cho file đang được ghi. Nếu file mới không chứa symbol -> fail.
    Trả về dict lỗi nếu thiếu symbol, None nếu pass (hoặc không áp dụng).
    """
    if tool_name not in ("Write", "Edit", "write", "edit"):
        return None
    file_path = _extract_file_path(tool_input)
    if not file_path:
        return None
    # Tìm file plan (ưu tiên docs/plans/, sau đó root)
    plan_candidates = [
        root / "docs" / "plans" / "IMPLEMENTATION_PLAN.md",
        root / "IMPLEMENTATION_PLAN.md",
    ]
    plan_path = next((p for p in plan_candidates if p.exists()), None)
    if plan_path is None:
        return None  # không có plan -> bỏ qua cổng
    try:
        plan_text = plan_path.read_text(encoding="utf-8", errors="ignore")
    except Exception as e:
        print(f"[schema_gate] unexpected exception: {e}", file=sys.stderr)
        return None
    # Tìm block cho file này: dạng "## <task_id> — <file>: <symbols>"
    # Hoặc "- [ ] <task_id>: <file> (functions: foo, bar)"
    norm_file = _normalize_path(file_path)
    # Pattern 1: dòng chứa đường dẫn file + danh sách hàm trong ngoặc
    expected_symbols: list[str] = []
    for line in plan_text.splitlines():
        if norm_file in line.replace("\\", "/"):
            # Trích tên hàm sau "functions:" hoặc "symbols:"
            m = re.search(r"(?i)(?:functions?|symbols?)\s*[:=]\s*([^\)]+)", line)
            if m:
                syms = [s.strip().strip("`*") for s in m.group(1).split(",") if s.strip()]
                expected_symbols.extend(syms)
    if not expected_symbols:
        return None  # plan không liệt kê symbol cho file này -> pass
    # Đọc nội dung file mới ghi để grep symbol
    content = tool_input.get("content") or tool_input.get("new_string") or ""
    if not content:
        return None
    missing_symbols = []
    for sym in expected_symbols:
        # Tìm định nghĩa hàm/class: def sym, function sym, class sym, const sym
        pattern = re.compile(
            rf"\b(def|class|function|const|public|private|protected)\s+{re.escape(sym)}\b",
            re.IGNORECASE,
        )
        if not pattern.search(content):
            missing_symbols.append(sym)
    if missing_symbols:
        return {
            "reason": f"File missing expected symbols from plan: {', '.join(missing_symbols)}",
            "details": {
                "file": file_path,
                "expected_symbols": expected_symbols,
                "missing_symbols": missing_symbols,
                "plan": str(plan_path),
            },
        }
    return None


def detect_encoding_bypass(text: str) -> list[str]:
    """T2.10: Phát hiện các kỹ thuật encoding bypass trong text.

    Trả về danh sách các loại bypass phát hiện được (rỗng nếu sạch).
    """
    if not text:
        return []
    findings: list[str] = []

    if re.search(r'\+[A-Za-z0-9+/]+-', text):
        findings.append("utf7")

    if re.search(r'\bxn--[a-zA-Z0-9-]+\b', text):
        findings.append("punycode")

    if re.search(r'&#[xX]?[0-9a-fA-F]+;', text):
        findings.append("html_entity")

    if re.search(r'\\x[0-9a-fA-F]{2}', text):
        findings.append("hex_escape")

    if re.search(r'\\u[0-9a-fA-F]{4}', text) or re.search(r'\\U[0-9a-fA-F]{8}', text):
        findings.append("unicode_escape")

    if re.search(r'\\[0-7]{1,3}', text):
        findings.append("octal_escape")

    if re.search(r'base64.*[\|<].*(bash|sh|zsh|python|perl)', text, re.IGNORECASE) or \
       re.search(r'base64.*-d.*[\|<]', text, re.IGNORECASE):
        findings.append("base64_pipe")

    return findings


def _gate_encoding_bypass(tool_name: str, tool_input: dict, tool_output) -> dict | None:
    """T2.10: Phát hiện encoding bypass trong output hoặc content đầu vào."""
    sources: list[str] = []

    if isinstance(tool_output, str):
        sources.append(tool_output)
    elif isinstance(tool_output, dict):
        sources.append(json.dumps(tool_output, ensure_ascii=False))

    if isinstance(tool_input, dict):
        for key in ("content", "new_string", "command", "old_string"):
            value = tool_input.get(key)
            if isinstance(value, str):
                sources.append(value)

    for text in sources:
        findings = detect_encoding_bypass(text)
        if findings:
            return {
                "reason": f"Encoding bypass detected: {', '.join(findings)}",
                "details": {"findings": findings, "source": text[:200]},
            }
    return None


def _gate_file_path_validation(tool_name: str, tool_input: dict, root: Path) -> dict | None:
    """Cổng 5: File path validation — chặn path traversal và ghi ngoài safe zone.

    Áp dụng cho tool ghi file (Write/Edit/NotebookEdit).
    Trả về dict lỗi nếu vi phạm, None nếu pass (hoặc không áp dụng).
    """
    write_tools = {"Write", "write", "Edit", "edit", "notebook_edit", "NotebookEdit"}
    if tool_name not in write_tools:
        return None
    file_path = _extract_file_path(tool_input)
    if not file_path:
        return None

    # Resolve đường dẫn dưới repo root; tuyệt đối ngoài root -> block
    resolved = _resolve_under_root(file_path, root)
    if resolved is None:
        return {
            "reason": "File path outside repo root is not allowed",
            "details": {"file": file_path},
        }

    try:
        rel = resolved.relative_to(root.resolve())
    except ValueError:
        return {
            "reason": "File path outside repo root is not allowed",
            "details": {"file": file_path},
        }
    norm = _normalize_path(str(rel))

    # Chuẩn hóa lowercase để so khớp zone không phân biệt hoa thường (case-sensitive FS bypass).
    norm_lower = norm.lower()
    # Kiểm tra path traversal: .. trong đường dẫn
    if ".." in norm.split("/"):
        return {
            "reason": "Path traversal blocked: '..' detected in path",
            "details": {"file": file_path, "normalized": norm},
        }
    # Kiểm tra blocked zone: nếu đường dẫn bắt đầu bằng zone cấm -> fail
    for zone in BLOCKED_ZONES:
        zone_norm = zone.replace("\\", "/").lower()
        if norm_lower.startswith(zone_norm) or norm_lower == zone_norm.rstrip("/"):
            return {
                "reason": f"Blocked zone: writing to '{zone}' is not allowed",
                "details": {"file": file_path, "zone": zone},
            }
    # Kiểm tra safe zone: đường dẫn phải nằm trong ít nhất một safe zone
    in_safe = any(norm_lower.startswith(sz.lower()) for sz in SAFE_ZONES)
    if not in_safe:
        return {
            "reason": (
                f"File outside safe zone. Safe zones: {', '.join(SAFE_ZONES)}"
            ),
            "details": {"file": file_path, "safe_zones": list(SAFE_ZONES)},
        }
    return None


def _run_gates(tool_name: str, tool_input: dict, tool_output, root: Path) -> dict:
    """Chạy tuần tự các cổng theo thứ tự ưu tiên.

    Cổng đầu tiên FAIL -> dừng, trả kết quả fail.
    Trả về dict: {"passed": bool, "gate": str, "reason": str, "details": dict}
    """
    # Danh sách cổng theo thứ tự (rẻ nhất trước)
    gates = [
        ("json_schema", lambda: _gate_json_schema(tool_output)),
        ("required_fields", lambda: _gate_required_fields(tool_name, tool_input, tool_output)),
        ("secret_scan", lambda: _gate_secret_scan(tool_output)),
        ("encoding_bypass", lambda: _gate_encoding_bypass(tool_name, tool_input, tool_output)),
        ("symbol_verification", lambda: _gate_symbol_verification(tool_name, tool_input, root)),
        ("file_path_validation", lambda: _gate_file_path_validation(tool_name, tool_input, root)),
    ]
    for gate_name, gate_fn in gates:
        try:
            result = gate_fn()
        except Exception as e:
            # Lỗi nội bộ cổng -> coi như fail (fail-closed cho an toàn)
            return {
                "passed": False,
                "gate": gate_name,
                "reason": f"Internal error in gate {gate_name}: {e}",
                "details": {"error": str(e)[:200]},
            }
        if result is not None:
            # Cổng fail -> block ngay, không chạy cổng còn lại
            return {
                "passed": False,
                "gate": gate_name,
                "reason": result["reason"],
                "details": result.get("details", {}),
            }
    # Tất cả cổng pass
    return {"passed": True, "gate": "all", "reason": "", "details": {}}


def main():
    """Điểm vào chính: đọc stdin, chạy cổng, xuất kết quả."""
    try:
        data = json.load(sys.stdin)
    except Exception as e:
        print(f"[schema_gate] unexpected exception: {e}", file=sys.stderr)
        # Pentest fix: parse error ở cổng an ninh phải fail-closed (block).
        result = {"passed": False, "gate": "none", "reason": "stdin parse error, blocked", "details": {}}
        print(json.dumps(result, ensure_ascii=False))
        print(
            f"[schema_gate] BLOCKED at gate 'none': stdin parse error",
            file=sys.stderr,
        )
        sys.exit(1)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    tool_output = data.get("tool_output", data.get("tool_response"))

    # Xác định repo root (dùng ahd_session nếu có, không thì fallback)
    root = Path.cwd()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ahd_session
        root = ahd_session.get_repo_root()
    except Exception as e:
        print(f"[schema_gate] unexpected exception: {e}", file=sys.stderr)
        pass

    # Xử lý: missing tool_output -> bỏ qua cổng JSON/secret (không có gì để quét)
    # nhưng vẫn chạy cổng required_fields và file_path_validation
    if tool_output is None:
        tool_output = ""

    result = _run_gates(tool_name, tool_input, tool_output, root)

    # Xuất kết quả JSON ra stdout (cho hệ thống hook đọc)
    print(json.dumps(result, ensure_ascii=False))

    if result["passed"]:
        sys.exit(0)
    else:
        # In reason ra stderr để agent thấy và sửa
        print(
            f"[schema_gate] BLOCKED at gate '{result['gate']}': {result['reason']}",
            file=sys.stderr,
        )
        sys.exit(1)


if __name__ == "__main__":
    # U15/U52: Timeout nội bộ — schema_gate phải nhanh (deterministic).
    # Pentest fix: cổng an ninh timeout phải fail-closed mặc định (block).
    # Cho phép opt-in fail-open qua env AHD_SCHEMA_GATE_FAIL_OPEN=1.
    result = {"code": 0}

    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception as e:
            print(f"[schema_gate] unexpected exception: {e}", file=sys.stderr)
            # Fail-closed mặc định: lỗi không ngờ -> BLOCK (không cho write/edit qua).
            # Opt-in fail-open qua env AHD_SCHEMA_GATE_FAIL_OPEN=1.
            fail_open = os.environ.get("AHD_SCHEMA_GATE_FAIL_OPEN", "") in ("1", "true", "yes")
            result["code"] = 0 if fail_open else 1

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        fail_open = os.environ.get("AHD_SCHEMA_GATE_FAIL_OPEN", "") in ("1", "true", "yes")
        if fail_open:
            print("[schema_gate] timeout - allowing (AHD_SCHEMA_GATE_FAIL_OPEN=1)", file=sys.stderr)
            result["code"] = 0
        else:
            print("[schema_gate] timeout - blocking (fail-closed)", file=sys.stderr)
            result["code"] = 1
    sys.exit(result["code"])
