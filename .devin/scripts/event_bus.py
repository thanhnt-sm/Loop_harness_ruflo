#!/usr/bin/env python3
"""event_bus.py — Phase D: Bus sự kiện có kiểu (typed event bus).

Mô hình pub/sub: agent A xuất bản (publish) tin nhắn vào một topic,
agent B đăng ký (subscribe) để lấy các tin nhắn chưa đọc. Mỗi topic
có lược đồ payload riêng (nếu định nghĩa) để kiểm tra kiểu trước khi
lưu. Mọi tin nhắn được ghi nối tiếp (append-only) vào file JSONL,
mỗi dòng một JSON.

Lược đồ tin nhắn:
    {
      "id": str,            # UUID định danh
      "topic": str,         # topic nhận
      "timestamp": str,     # ISO 8601
      "publisher": str,     # tên agent xuất bản
      "payload": dict,      # nội dung tin nhắn
      "provenance": [str]   # chuỗi ID tin nhắn dẫn đến tin này
    }

CLI:
    python event_bus.py --publish <topic> <message.json>
    python event_bus.py --subscribe <topic>
    python event_bus.py --history <topic>
    python event_bus.py --topics

Lưu trữ: .devin/event_bus/<topic>.jsonl (nối tiếp, mỗi dòng một JSON)

Mã thoát:
    0 — thành công
    1 — lỗi (topic sai, tin nhắn sai định dạng, v.v.)
"""
from __future__ import annotations

import argparse
import json
import re
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any
from uuid import uuid4


# Đưa thư mục hooks vào sys.path để tái sử dụng file-lock từ ahd_session.py.
_Here = Path(__file__).resolve().parent
sys.path.insert(0, str(_Here.parent / "hooks"))
from ahd_session import _acquire_lock, _release_lock, LockAcquireError  # noqa: E402

if hasattr(sys.stdout, "reconfigure"):
    sys.stdout.reconfigure(encoding="utf-8", errors="replace")
    sys.stderr.reconfigure(encoding="utf-8", errors="replace")


# ---------------------------------------------------------------------------
# Cấu hình
# ---------------------------------------------------------------------------

# Thư mục gốc của repo: cha của thư mục .devin
def _repo_root() -> Path:
    """Tìm thư mục gốc repo (chứa thư mục .devin)."""
    here = Path(__file__).resolve().parent  # .../.devin/scripts
    return here.parent.parent               # repo root


def _now_iso() -> str:
    """Trả về timestamp hiện tại ở định dạng ISO 8601 UTC."""
    return datetime.now(timezone.utc).isoformat()


# Thư mục lưu trữ event bus
def _bus_dir() -> Path:
    """Trả về thư mục .devin/event_bus, tự tạo nếu thiếu."""
    d = _repo_root() / ".devin" / "event_bus"
    d.mkdir(parents=True, exist_ok=True)
    return d


# Danh sách topic định nghĩa trước + lược đồ payload (nếu có).
# Mỗi topic có thể có schema dạng {"trường": kiểu}. None = không kiểm tra.
TOPIC_SCHEMAS: dict[str, dict | None] = {
    "analysis.findings": {
        "findings": list,
        "source": str,
    },
    "design.draft": {
        "design": str,
        "version": (int, float),
    },
    "review.findings": {
        "findings": list,
        "severity": str,
    },
    "plan.tasks": {
        "tasks": list,
    },
    "plan.quality": {
        "quality_score": (int, float),
        "notes": str,
    },
    "execute.results": {
        "task_id": str,
        "result": dict,
    },
    "verify.gates": {
        "gates": list,
        "all_pass": bool,
    },
    "quality.metrics": {
        "metric": str,
        "value": (int, float),
    },
    "drift.alerts": {
        "drift_type": str,
        "severity": str,
    },
    "system.events": None,  # sự kiện hệ thống, không ràng buộc payload
}


# ---------------------------------------------------------------------------
# Hàm tiện ích
# ---------------------------------------------------------------------------

# Pattern allowlist cho topic: chỉ chữ số, chữ cái, dấu chấm, gạch dưới, gạch ngang.
# Giới hạn độ dài 64 ký tự để tránh tên file quá dài và path traversal.
_TOPIC_PATTERN = re.compile(r"^[a-zA-Z0-9._-]{1,64}$")


def _sanitize_topic(topic: str) -> str:
    """Làm sạch topic để chống path traversal qua tên file.

    Bước 1: Thay các ký tự path separator ('/', '\\') bằng '_'.
    Bước 2: Loại bỏ ký tự ngoài allowlist.
    Bước 3: Sụp đổ nhiều dấu '_' liên tiếp và cắt đầu/cuối.
    Bước 4: Nếu sau làm sạch topic chứa '..' hoặc không khớp pattern -> đổi thành 'invalid'.
    """
    if not topic:
        return "invalid"
    safe = topic.replace("/", "_").replace("\\", "_")
    safe = re.sub(r"[^a-zA-Z0-9._-]", "_", safe)
    safe = re.sub(r"_+", "_", safe).strip("_-. ")
    if not safe or ".." in safe or not _TOPIC_PATTERN.match(safe):
        return "invalid"
    return safe


def _topic_file(topic: str) -> Path:
    """Trả về đường dẫn file JSONL cho topic. Tạo thư mục nếu thiếu.

    Pentest fix: sanitize topic trước khi join path; đảm bảo file nằm trong _bus_dir().
    """
    safe = _sanitize_topic(topic)
    bus = _bus_dir()
    f = bus / f"{safe}.jsonl"
    # Kiểm tra path traversal phòng trường hợp sanitize bị bypass (vd symlink).
    try:
        f.resolve().relative_to(bus.resolve())
    except ValueError:
        return bus / "invalid.jsonl"
    return f


def _topic_lock_path(topic: str) -> Path:
    """Trả về đường dẫn file-lock cho một topic."""
    safe = _sanitize_topic(topic)
    d = _bus_dir() / ".locks"
    d.mkdir(parents=True, exist_ok=True)
    f = d / f"{safe}.lock"
    try:
        f.resolve().relative_to(d.resolve())
    except ValueError:
        return d / "invalid.lock"
    return f


def _validate_topic(topic: str) -> bool:
    """Kiểm tra topic có hợp lệ (có trong danh sách định nghĩa)."""
    return topic in TOPIC_SCHEMAS


def _validate_payload(topic: str, payload: Any) -> tuple[bool, str]:
    """Kiểm tra payload theo lược đồ của topic.

    Bước 1: Lấy schema cho topic. Nếu None → bỏ qua kiểm tra.
    Bước 2: payload phải là dict.
    Bước 3: Với mỗi trường bắt buộc, kiểm tra có mặt + đúng kiểu.
    Bước 4: Trả (True, "") nếu hợp lệ, (False, lý do) nếu sai.
    """
    schema = TOPIC_SCHEMAS.get(topic)
    if schema is None:
        # Topic không có schema (hoặc system.events) → chấp nhận mọi payload.
        return True, ""
    if not isinstance(payload, dict):
        return False, "payload phải là dict (object JSON)"
    for field, expected_type in schema.items():
        if field not in payload:
            return False, f"thiếu trường bắt buộc: {field}"
        value = payload[field]
        # expected_type có thể là tuple kiểu (chấp nhận nhiều kiểu).
        types = expected_type if isinstance(expected_type, tuple) else (expected_type,)
        if not isinstance(value, types):
            type_names = " hoặc ".join(t.__name__ for t in types)
            return False, f"trường {field} phải có kiểu {type_names}"
    return True, ""


def _read_all_messages(topic: str) -> list[dict]:
    """Đọc toàn bộ tin nhắn của topic (lịch sử đầy đủ).

    Bước 1: Mở file JSONL (nếu tồn tại).
    Bước 2: Đọc từng dòng, parse JSON. Bỏ qua dòng rỗng/sai định dạng.
    """
    f = _topic_file(topic)
    if not f.exists():
        return []
    messages: list[dict] = []
    try:
        for line in f.read_text(encoding="utf-8").splitlines():
            line = line.strip()
            if not line:
                continue
            try:
                messages.append(json.loads(line))
            except json.JSONDecodeError:
                # Dòng sai định dạng → bỏ qua (đã log khi publish).
                continue
    except OSError as exc:
        print(f"[event_bus] Lỗi đọc file topic {topic}: {exc}", file=sys.stderr)
    return messages


# ---------------------------------------------------------------------------
# Các thao tác chính
# ---------------------------------------------------------------------------

def publish(topic: str, publisher: str, payload: Any,
            provenance: list[str] | None = None) -> dict:
    """Xuất bản một tin nhắn vào topic.

    Bước 1: Kiểm tra topic hợp lệ. Nếu không → tạo topic mới (ghi file mới).
    Bước 2: Kiểm tra payload theo schema. Nếu sai → từ chối + log.
    Bước 3: Tạo tin nhắn với id, timestamp, provenance.
    Bước 4: Ghi nối tiếp vào file JSONL.
    Bước 5: Trả về tin nhắn đã tạo.
    """
    # Cho phép topic ngoài danh sách (tự tạo file mới), nhưng cảnh báo.
    if not _validate_topic(topic):
        print(f"[event_bus] Cảnh báo: topic '{topic}' không trong danh sách định nghĩa, "
              f"tạo topic mới.", file=sys.stderr)

    ok, reason = _validate_payload(topic, payload)
    if not ok:
        print(f"[event_bus] Từ chối tin nhắn: payload không hợp lệ — {reason}",
              file=sys.stderr)
        return {"published": False, "reason": reason}

    message = {
        "id": str(uuid4()),
        "topic": topic,
        "timestamp": _now_iso(),
        "publisher": publisher,
        "payload": payload,
        "provenance": provenance or [],
    }

    f = _topic_file(topic)
    lock = None
    try:
        lock = _acquire_lock(_topic_lock_path(topic), timeout=5.0)
        with f.open("a", encoding="utf-8") as fh:
            fh.write(json.dumps(message, ensure_ascii=False) + "\n")
    except LockAcquireError as exc:
        print(f"[event_bus] Không lấy được khóa topic {topic}: {exc}", file=sys.stderr)
        return {"published": False, "reason": f"Không lấy được khóa: {exc}"}
    except OSError as exc:
        print(f"[event_bus] Lỗi ghi file topic {topic}: {exc}", file=sys.stderr)
        return {"published": False, "reason": str(exc)}
    finally:
        _release_lock(lock)

    return {"published": True, "message": message}


def subscribe(topic: str, last_read: int = 0) -> dict:
    """Lấy các tin nhắn chưa đọc cho topic, có file-lock khi đọc."""
    lock = None
    try:
        lock = _acquire_lock(_topic_lock_path(topic), timeout=5.0)
        messages = _read_all_messages(topic)
        unread = messages[last_read:]
        return {
            "topic": topic,
            "unread_count": len(unread),
            "messages": unread,
            "next_offset": len(messages),
        }
    except LockAcquireError as exc:
        print(f"[event_bus] Không lấy được khóa topic {topic}: {exc}", file=sys.stderr)
        return {"topic": topic, "unread_count": 0, "messages": [], "next_offset": 0, "error": str(exc)}
    finally:
        _release_lock(lock)


def history(topic: str) -> dict:
    """Lấy toàn bộ lịch sử tin nhắn của topic, có file-lock."""
    lock = None
    try:
        lock = _acquire_lock(_topic_lock_path(topic), timeout=5.0)
        messages = _read_all_messages(topic)
        return {
            "topic": topic,
            "total": len(messages),
            "messages": messages,
        }
    except LockAcquireError as exc:
        print(f"[event_bus] Không lấy được khóa topic {topic}: {exc}", file=sys.stderr)
        return {"topic": topic, "total": 0, "messages": [], "error": str(exc)}
    finally:
        _release_lock(lock)


def list_topics() -> dict:
    """Liệt kê tất cả topic có định nghĩa + topic đã có file lưu trữ."""
    defined = list(TOPIC_SCHEMAS.keys())
    # Thêm các topic đã có file nhưng không trong danh sách định nghĩa.
    existing_files = set()
    bus = _bus_dir()
    if bus.exists():
        for f in bus.glob("*.jsonl"):
            existing_files.add(f.stem)
    extra = sorted(existing_files - set(defined))
    return {
        "defined_topics": defined,
        "additional_topics": extra,
        "total": len(defined) + len(extra),
    }


# ---------------------------------------------------------------------------
# CLI
# ---------------------------------------------------------------------------

def _read_message_file(path: str) -> tuple[str, Any, list[str]]:
    """Đọc file JSON chứa thông tin xuất bản.

    Trả về (publisher, payload, provenance). File có dạng:
        {"publisher": "...", "payload": {...}, "provenance": [...]}
    Nếu chỉ có payload (dict đơn) → publisher mặc định "unknown".
    """
    try:
        text = Path(path).read_text(encoding="utf-8")
        data = json.loads(text)
    except (OSError, json.JSONDecodeError) as exc:
        print(f"[event_bus] Không đọc được file tin nhắn {path}: {exc}",
              file=sys.stderr)
        return "", None, []
    if isinstance(data, dict) and "payload" in data:
        publisher = data.get("publisher", "unknown")
        payload = data.get("payload")
        provenance = data.get("provenance", [])
        return publisher, payload, provenance
    # Dict đơn → coi toàn bộ là payload.
    return "unknown", data, []


def _build_arg_parser() -> argparse.ArgumentParser:
    """Xây dựng trình phân tích tham số dòng lệnh."""
    ap = argparse.ArgumentParser(
        description="Phase D: Bus sự kiện có kiểu (typed event bus)"
    )
    ap.add_argument("--publish", nargs=2, metavar=("topic", "message.json"),
                    help="Xuất bản tin nhắn vào topic")
    ap.add_argument("--subscribe", metavar="topic",
                    help="Lấy tin nhắn chưa đọc cho topic")
    ap.add_argument("--history", metavar="topic",
                    help="Lấy toàn bộ lịch sử tin nhắn của topic")
    ap.add_argument("--offset", type=int, default=0,
                    help="Chỉ mục bắt đầu cho --subscribe (mặc định 0)")
    ap.add_argument("--topics", action="store_true",
                    help="Liệt kê tất cả topic")
    return ap


def main(argv: list[str] | None = None) -> int:
    """Hàm chính: phân tích tham số, thực thi, in kết quả JSON."""
    ap = _build_arg_parser()
    args = ap.parse_args(argv)

    if not any([args.publish, args.subscribe, args.history, args.topics]):
        ap.print_help(sys.stderr)
        return 1

    if args.publish:
        topic, msg_path = args.publish
        publisher, payload, provenance = _read_message_file(msg_path)
        if payload is None:
            return 1
        result = publish(topic, publisher, payload, provenance)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0 if result.get("published") else 1

    if args.subscribe:
        result = subscribe(args.subscribe, args.offset)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.history:
        result = history(args.history)
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    if args.topics:
        result = list_topics()
        print(json.dumps(result, ensure_ascii=False, indent=2))
        return 0

    return 0


if __name__ == "__main__":
    sys.exit(main())
