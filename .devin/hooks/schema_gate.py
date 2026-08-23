#!/usr/bin/env python3
"""Schema gate — cổng xác định kiểm tra deterministic cho mọi output của agent.

Hook loại PostToolUse: chạy sau mỗi tool call, đưa output qua một pipeline
các cổng kiểm tra deterministic (rẻ, nhanh, không thể bị jailbreak).

Nhận JSON trên stdin:
  {"tool_name": "Write", "tool_input": {...}, "tool_output": {...}, "session_id": "..."}

Entry point này chỉ làm orchestration + timeout. Logic thực tế đã tách ra:
  - schema_gate_config.py   : constants + path_zones + helpers path
  - schema_gate_secrets.py  : chunked secret scan (CVE-2026-AHD-005)
  - schema_gate_paths.py     : file path validation gate
  - schema_gate_gates.py     : json/required/symbol/encoding gates + _run_gates

Tất cả public API được re-export để preserve compatibility với tests/downstream.

Exit codes:
   0 = tất cả cổng pass (cho phép tool call)
   1 = có cổng fail (block, trả lỗi cho agent qua stderr)
"""
from __future__ import annotations

import json
import os
import sys
import threading
from pathlib import Path

# Re-export TẤT CẢ public API từ các module con (preserve compatibility).
from schema_gate_config import (
    BLOCKED_ZONES,
    DEFAULT_SECRET_PATTERNS,
    HOOK_TIMEOUT_SECONDS,
    REQUIRED_FIELDS_BY_TOOL,
    SAFE_ZONES,
    SCAN_CHUNK_SIZE,
    SCAN_OVERLAP,
    SECRET_PATTERNS,
    _ENTROPY_TOKEN_RE,
    _ENTROPY_TRIGGER_RE,
    _KEYWORD_PRE,
    _TRIGGER_RE,
    _UPPER_ONLY_RE,
    _extract_file_path,
    _finalize_slow_indices,
    _find_jwt,
    _load_hlk_secret_patterns,
    _normalize_path,
    _resolve_under_root,
    _shannon_entropy,
    KEYWORD_PATTERN_IDX,
    SLOW_PATTERN_IDXS,
    SLOW_URL_IDXS,
)
from schema_gate_secrets import (
    _gate_secret_scan,
    _iter_chunks,
    _scan_chunk_secrets,
)
from schema_gate_paths import _gate_file_path_validation
from schema_gate_gates import (
    _gate_encoding_bypass,
    _gate_json_schema,
    _gate_required_fields,
    _gate_symbol_verification,
    _run_gates,
    detect_encoding_bypass,
)

# --- Re-export một số hằng số bổ sung để preserve API đầy đủ ---
from schema_gate_config import (
    ENTROPY_MIN_LENGTH,
    ENTROPY_THRESHOLD,
    _JWT_MIN_SEGMENT,
)


def main() -> None:
    """Điểm vào chính: đọc stdin, chạy cổng, xuất kết quả."""
    try:
        data = json.load(sys.stdin)
    except Exception as e:  # noqa: BLE001
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
    except Exception as e:  # noqa: BLE001
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
        except Exception as e:  # noqa: BLE001
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
