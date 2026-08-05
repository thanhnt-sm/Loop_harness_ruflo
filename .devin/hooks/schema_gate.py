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
import re
import sys
import threading
from pathlib import Path

# U15: Timeout nội bộ — schema_gate phải nhanh (deterministic). Config timeout 3s.
HOOK_TIMEOUT_SECONDS = 2.5

# --- Cấu hình safe zone / blocked zone ---
# Safe zone: agent được phép ghi file vào các thư mục này
SAFE_ZONES = (
    "src/",
    ".devin/skills/",
    ".devin/agents/personas/",
    "scripts/",
    "docs/plans/",
    "docs/templates/",
    "docs/research/",
)

# Blocked zone: KHÔNG bao giờ cho phép ghi vào các thư mục/file này
# C-02 fix: Block agent từ việc sửa hooks, canon, config, AGENTS.md —
# nếu agent sửa được hooks thì toàn bộ enforcement bị vô hiệu hóa
BLOCKED_ZONES = (
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
    # C-02: Agent KHÔNG được sửa AGENTS.md (will change own rules)
    "AGENTS.md",
    ".devin/AGENTS.md",
    "CLAUDE.md",
)

# --- Regex quét secret (không bao giờ cho phép trong output) ---
# Bao gồm: GitHub token, OpenAI key, AWS key, generic key=value, Bearer token
SECRET_PATTERNS = [
    re.compile(r"ghp_[A-Za-z0-9]{36}"),                       # GitHub personal access token
    re.compile(r"gho_[A-Za-z0-9]{36}"),                       # GitHub OAuth token
    re.compile(r"sk-[A-Za-z0-9_-]{20,}"),                     # OpenAI / Anthropic API key
    re.compile(r"AKIA[A-Z0-9]{16}"),                          # AWS access key ID
    re.compile(r"AIza[A-Za-z0-9_-]{35}"),                     # Google API key
    re.compile(r"xox[baprs]-[A-Za-z0-9-]{10,}"),              # Slack token
    re.compile(r"(?i)Bearer\s+[A-Za-z0-9_-]{20,}"),           # Bearer token (Authorization header)
    re.compile(r"(?i)\b(token|password|passwd|api_key|apikey|secret|private_key)\s*[:=]\s*['\"]?[^\s'\"&;|]{8,}"),  # key=value
]

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

# Giới hạn kích thước output khi quét secret (tránh quét file quá lớn)
SCAN_TRUNCATE_CHARS = 200_000


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
    required = REQUIRED_FIELDS_BY_TOOL.get(tool_name)
    if not required:
        return None  # tool không có yêu cầu trường -> pass
    missing = [f for f in required if f not in tool_input or tool_input[f] in (None, "")]
    if missing:
        return {
            "reason": f"Missing required fields: {', '.join(missing)}",
            "details": {"missing_fields": missing, "tool": tool_name},
        }
    return None


def _gate_secret_scan(tool_output) -> dict | None:
    """Cổng 3: Secret scan — quét regex tìm secret trong output.

    KHÔNG bao giờ cho phép secret trong output (red line).
    Trả về dict lỗi nếu tìm thấy, None nếu sạch.
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
    # Cắt bớt nếu quá lớn (tránh quét file khổng lồ)
    if len(text) > SCAN_TRUNCATE_CHARS:
        text = text[:SCAN_TRUNCATE_CHARS]
    # Quét từng pattern
    for pattern in SECRET_PATTERNS:
        match = pattern.search(text)
        if match:
            # Che giá trị secret trước khi báo cáo (không log secret thật)
            masked = match.group(0)[:4] + "***" + match.group(0)[-2:]
            return {
                "reason": f"Secret detected in output (masked): {masked}",
                "details": {"pattern": pattern.pattern, "masked_value": masked},
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
    except Exception:
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


def _gate_file_path_validation(tool_name: str, tool_input: dict) -> dict | None:
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
    norm = _normalize_path(file_path)
    # Kiểm tra path traversal: .. trong đường dẫn
    if ".." in norm.split("/"):
        return {
            "reason": "Path traversal blocked: '..' detected in path",
            "details": {"file": file_path, "normalized": norm},
        }
    # Kiểm tra blocked zone: nếu đường dẫn bắt đầu bằng zone cấm -> fail
    for zone in BLOCKED_ZONES:
        zone_norm = zone.replace("\\", "/")
        if norm.startswith(zone_norm) or norm == zone_norm.rstrip("/"):
            return {
                "reason": f"Blocked zone: writing to '{zone}' is not allowed",
                "details": {"file": file_path, "zone": zone},
            }
    # Kiểm tra safe zone: đường dẫn phải nằm trong ít nhất một safe zone
    # (chỉ áp dụng nếu đường dẫn là tương đối; tuyệt đối ngoài repo -> cảnh báo)
    if not Path(file_path).is_absolute():
        in_safe = any(norm.startswith(sz) for sz in SAFE_ZONES)
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
        ("symbol_verification", lambda: _gate_symbol_verification(tool_name, tool_input, root)),
        ("file_path_validation", lambda: _gate_file_path_validation(tool_name, tool_input)),
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
    except Exception:
        # Không parse được stdin -> cho phép (không block vì lỗi parse)
        result = {"passed": True, "gate": "none", "reason": "stdin parse error, skipped", "details": {}}
        print(json.dumps(result, ensure_ascii=False))
        sys.exit(0)

    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {}) or {}
    tool_output = data.get("tool_output", data.get("tool_response"))

    # Xác định repo root (dùng ahd_session nếu có, không thì fallback)
    root = Path.cwd()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ahd_session
        root = ahd_session.get_repo_root()
    except Exception:
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
    # U15/U52: Timeout nội bộ — fail-open nếu hết giờ (không block workflow)
    result = {"code": 0}

    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception:
            # Lỗi không ngờ -> cho phép (fail-open, không block)
            result["code"] = 0

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[schema_gate] timeout - allowing (fail-open)", file=sys.stderr)
        result["code"] = 0
    sys.exit(result["code"])
