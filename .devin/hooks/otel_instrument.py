#!/usr/bin/env python3
"""OTel instrument — wrapper OpenTelemetry cho mọi hook/tool call.

Hook loại wrapper: bọc mọi hook (PreToolUse, PostToolUse, Stop, v.v.) để
tạo OTel span cho mỗi tool call theo GenAI semantic conventions.

Nếu opentelemetry chưa cài -> graceful degradation: ghi structured JSON log
ra file .devin/telemetry/events.jsonl.

Nhận JSON trên stdin (đa dạng theo hook type):
  {"hook_event_name": "PreToolUse", "tool_name": "Bash", "tool_input": {...}, "session_id": "..."}
  {"hook_event_name": "PostToolUse", "tool_name": "Write", "tool_input": {...}, "tool_output": {...}, "session_id": "..."}
  {"hook_event_name": "Stop", "session_id": "..."}

Span attributes (theo GenAI semantic conventions):
  - tool.name: tên tool
  - tool.input.hash: hash SHA-256 của input (che giá trị thật)
  - tool.output.status: success | error | blocked
  - tool.latency_ms: độ trễ tính bằng mili-giây
  - agent.session_id: ID session

Output: pass-through output gốc của hook được bọc (transparent wrapper).
Exit code: giống hook được bọc.

Fallback event structure (khi không có OTel):
  {"timestamp": "...", "event_type": "tool_call", "tool_name": "...",
   "session_id": "...", "latency_ms": 0, "status": "success", "attributes": {...}}
"""
from __future__ import annotations

import hashlib
import json
import sys
import threading
import time
from datetime import datetime, timezone
from pathlib import Path

# U15: Timeout nội bộ — wrapper phải nhanh, không block hook gốc.
HOOK_TIMEOUT_SECONDS = 2.0

# Đường dẫn fallback log file
TELEMETRY_DIR_NAME = "telemetry"
TELEMETRY_FILE_NAME = "events.jsonl"

# Giới hạn kích thước log file (rotate khi vượt)
MAX_LOG_LINES = 5000


def _get_telemetry_dir(root: Path) -> Path:
    """Trả đường dẫn thư mục telemetry (tạo nếu thiếu)."""
    config_root = root / ".devin"
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ahd_session
        config_root = ahd_session.get_config_root(root)
    except Exception:
        pass
    tel_dir = config_root / TELEMETRY_DIR_NAME
    tel_dir.mkdir(parents=True, exist_ok=True)
    return tel_dir


def _hash_input(tool_input) -> str:
    """Hash SHA-256 của tool_input (che giá trị thật, chỉ giữ dấu vết)."""
    try:
        if isinstance(tool_input, dict):
            text = json.dumps(tool_input, sort_keys=True, ensure_ascii=False)
        elif tool_input is None:
            text = ""
        else:
            text = str(tool_input)
        return hashlib.sha256(text.encode("utf-8")).hexdigest()[:16]
    except Exception:
        return "hash_error"


def _determine_status(tool_output) -> str:
    """Xác định status của tool call từ output.

    Trả về: success | error | blocked
    """
    if tool_output is None:
        return "success"
    if isinstance(tool_output, dict):
        # Có trường error -> error
        if tool_output.get("error"):
            return "error"
        # Có exit_code != 0 -> error
        exit_code = tool_output.get("exit_code", 0)
        if exit_code not in (0, None, ""):
            return "error"
        # Có status blocked -> blocked
        status = str(tool_output.get("status", "")).lower()
        if status == "blocked":
            return "blocked"
        if status in ("error", "failed", "failure"):
            return "error"
        return "success"
    if isinstance(tool_output, str):
        lower = tool_output.lower()
        if "blocked" in lower:
            return "blocked"
        if "error" in lower or "failed" in lower:
            return "error"
        return "success"
    return "success"


def _now_iso() -> str:
    """Trả timestamp ISO 8601 UTC hiện tại."""
    return datetime.now(timezone.utc).isoformat()


def _rotate_log(log_path: Path) -> None:
    """Rotate log file nếu vượt MAX_LOG_LINES (giữ file gọn)."""
    try:
        if not log_path.exists():
            return
        count = log_path.read_text(encoding="utf-8", errors="ignore").count("\n")
        if count >= MAX_LOG_LINES:
            backup = log_path.with_suffix(".1.jsonl")
            if backup.exists():
                backup.unlink()
            log_path.rename(backup)
    except Exception:
        pass


def _write_fallback_log(log_path: Path, event: dict) -> None:
    """Ghi event JSON vào file .jsonl (fallback khi không có OTel)."""
    try:
        _rotate_log(log_path)
        with open(log_path, "a", encoding="utf-8") as f:
            f.write(json.dumps(event, ensure_ascii=False) + "\n")
    except Exception as e:
        # Lỗi ghi -> log stderr, không block
        print(f"[otel_instrument] error writing telemetry log: {e}", file=sys.stderr)


def _emit_otel_span(event: dict) -> bool:
    """Thử phát OTel span. Trả True nếu thành công, False nếu OTel không có.

    Sử dụng GenAI semantic conventions cho span attributes.
    """
    try:
        # Import opentelemetry (optional — có thể chưa cài)
        from opentelemetry import trace
        from opentelemetry.trace import Status, StatusCode

        tracer = trace.get_tracer("ahd.hooks.otel_instrument")
        span_name = f"tool.{event.get('tool_name', 'unknown')}"
        with tracer.start_as_current_span(span_name) as span:
            # Gán attributes theo GenAI semantic conventions
            span.set_attribute("tool.name", event.get("tool_name", ""))
            span.set_attribute("tool.input.hash", event.get("attributes", {}).get("tool.input.hash", ""))
            span.set_attribute("tool.output.status", event.get("status", "success"))
            span.set_attribute("tool.latency_ms", event.get("latency_ms", 0))
            span.set_attribute("agent.session_id", event.get("session_id", ""))
            span.set_attribute("hook.event_type", event.get("event_type", ""))
            # Gán status của span
            status = event.get("status", "success")
            if status == "error":
                span.set_status(Status(StatusCode.ERROR))
            else:
                span.set_status(Status(StatusCode.OK))
        return True
    except Exception:
        # opentelemetry chưa cài hoặc lỗi -> fallback
        return False


def _build_event(data: dict, latency_ms: float) -> dict:
    """Xây event dict từ dữ liệu hook đầu vào."""
    tool_name = data.get("tool_name", "")
    tool_input = data.get("tool_input", {})
    tool_output = data.get("tool_output", data.get("tool_response"))
    session_id = data.get("session_id", "")
    hook_event = data.get("hook_event_name", data.get("hook_event", "unknown"))
    status = _determine_status(tool_output)
    input_hash = _hash_input(tool_input)

    return {
        "timestamp": _now_iso(),
        "event_type": hook_event,
        "tool_name": tool_name,
        "session_id": session_id,
        "latency_ms": round(latency_ms, 2),
        "status": status,
        "attributes": {
            "tool.name": tool_name,
            "tool.input.hash": input_hash,
            "tool.output.status": status,
            "tool.latency_ms": round(latency_ms, 2),
            "agent.session_id": session_id,
        },
    }


def main():
    """Điểm vào chính: đọc stdin, phát span/log, pass-through output."""
    start_time = time.monotonic()

    try:
        data = json.load(sys.stdin)
    except Exception:
        # Không parse được -> không có gì để instrument, exit 0
        sys.exit(0)

    # Xác định repo root
    root = Path.cwd()
    try:
        sys.path.insert(0, str(Path(__file__).resolve().parent))
        import ahd_session
        root = ahd_session.get_repo_root()
    except Exception:
        pass

    latency_ms = (time.monotonic() - start_time) * 1000.0
    event = _build_event(data, latency_ms)

    # Thử phát OTel span; nếu không có OTel -> ghi fallback log
    otel_ok = _emit_otel_span(event)
    if not otel_ok:
        tel_dir = _get_telemetry_dir(root)
        log_path = tel_dir / TELEMETRY_FILE_NAME
        _write_fallback_log(log_path, event)

    # Pass-through: in lại output gốc nếu có (transparent wrapper)
    # Hook wrapper không thay đổi output của hook được bọc
    tool_output = data.get("tool_output", data.get("tool_response"))
    if tool_output is not None:
        # In output gốc ra stdout để hệ thống hook下游 đọc
        try:
            if isinstance(tool_output, (dict, list)):
                print(json.dumps(tool_output, ensure_ascii=False))
            else:
                print(str(tool_output))
        except Exception:
            pass

    # Exit code: giống hook được bọc (mặc định 0)
    exit_code = data.get("exit_code", 0)
    try:
        exit_code = int(exit_code)
    except Exception:
        exit_code = 0
    sys.exit(exit_code)


if __name__ == "__main__":
    # U15: Timeout nội bộ — wrapper fail-open (không block hook gốc)
    result = {"code": 0}

    def _run():
        try:
            main()
        except SystemExit as e:
            result["code"] = e.code if e.code is not None else 0
        except Exception as e:
            # Lỗi không ngờ -> log stderr, exit 0 (không block)
            print(f"[otel_instrument] error: {e}", file=sys.stderr)
            result["code"] = 0

    t = threading.Thread(target=_run, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[otel_instrument] timeout - exit 0 (fail-open)", file=sys.stderr)
        result["code"] = 0
    sys.exit(result["code"])
