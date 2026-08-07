#!/usr/bin/env python3
"""Kiểm thử event_bus.py — T2.3 (REB-002).

Các ca kiểm thử chính:
1. publish/subscribe cơ bản.
2. Đồng thời publish 100 tin nhắn → không bị interleave/corrupt.
3. Lịch sử đầy đủ.
4. Payload không hợp lệ bị từ chối.
5. Topic ngoài danh sách vẫn được tạo.
6. Replay từ offset.
"""
import json
import sys
from concurrent.futures import ThreadPoolExecutor
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"
if str(SCRIPTS_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPTS_DIR))

import event_bus  # noqa: E402


@pytest.fixture
def root(tmp_path, monkeypatch):
    """Dùng thư mục tạm cho event_bus, không động đến repo thật."""
    monkeypatch.setattr(event_bus, "_repo_root", lambda: tmp_path)
    yield tmp_path


# ---------------------------------------------------------------------------
# 1. publish/subscribe cơ bản
# ---------------------------------------------------------------------------
def test_publish_and_subscribe(root):
    event_bus.publish("system.events", "agent-1", {"type": "boot"})
    res = event_bus.subscribe("system.events")
    assert res["unread_count"] == 1
    assert res["messages"][0]["payload"] == {"type": "boot"}


# ---------------------------------------------------------------------------
# 2. Đồng thời publish 100 tin nhắn → không interleave
# ---------------------------------------------------------------------------
def test_concurrent_publish_no_interleave(root):
    def worker(args):
        i, k = args
        return event_bus.publish("system.events", f"agent_{i}", {"idx": i * 10 + k})

    items = [(i, k) for i in range(10) for k in range(10)]
    with ThreadPoolExecutor(max_workers=10) as ex:
        results = list(ex.map(worker, items))

    assert all(r["published"] for r in results)

    topic_file = root / ".devin" / "event_bus" / "system.events.jsonl"
    assert topic_file.exists()
    lines = topic_file.read_text(encoding="utf-8").splitlines()
    assert len(lines) == 100
    parsed = []
    for line in lines:
        line = line.strip()
        if not line:
            continue
        parsed.append(json.loads(line))
    assert len(parsed) == 100


# ---------------------------------------------------------------------------
# 3. Lịch sử đầy đủ
# ---------------------------------------------------------------------------
def test_history(root):
    event_bus.publish("system.events", "agent-1", {"seq": 1})
    event_bus.publish("system.events", "agent-1", {"seq": 2})
    res = event_bus.history("system.events")
    assert res["total"] == 2
    assert res["messages"][0]["payload"] == {"seq": 1}
    assert res["messages"][1]["payload"] == {"seq": 2}


# ---------------------------------------------------------------------------
# 4. Payload không hợp lệ bị từ chối
# ---------------------------------------------------------------------------
def test_invalid_payload_rejected(root):
    res = event_bus.publish("analysis.findings", "agent-1", {"wrong": "field"})
    assert res["published"] is False


# ---------------------------------------------------------------------------
# 5. Topic ngoài danh sách vẫn được tạo
# ---------------------------------------------------------------------------
def test_unknown_topic_allowed(root):
    res = event_bus.publish("custom.topic", "agent-1", {"x": 1})
    assert res["published"] is True


# ---------------------------------------------------------------------------
# 6. Replay từ offset
# ---------------------------------------------------------------------------
def test_replay_offset(root):
    event_bus.publish("system.events", "agent-1", {"seq": 1})
    event_bus.publish("system.events", "agent-1", {"seq": 2})
    event_bus.publish("system.events", "agent-1", {"seq": 3})
    res = event_bus.subscribe("system.events", last_read=1)
    assert res["unread_count"] == 2
    assert res["next_offset"] == 3
