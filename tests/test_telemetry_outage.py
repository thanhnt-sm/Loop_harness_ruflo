"""V5-04: Telemetry outage — deterministic fail-closed/recording invariants (§17).

Invariants (codified from V5 §17 + redteam-v5.md §0 "Telemetry outage -> fail-closed, ghi BLOCKED"):
1. OTel outage (emit fail) -> event VẪN được ghi vào fallback events.jsonl (không drop âm thầm).
2. OTel available -> không ghi fallback (event đi span).
3. Fallback write outage -> không crash, audit lỗi được surface qua stderr (không swallow).
4. Wrapper transparent: passthrough output + exit code giữ nguyên (không block hook gốc).
"""
import io
import json
import sys
from pathlib import Path

import pytest

sys.path.insert(0, str(Path(__file__).resolve().parent.parent / ".devin" / "hooks"))

import otel_instrument


def _run_main(monkeypatch, data, tmp_path, emit_ok=True):
    """Chạy otel_instrument.main() với input + môi trường được kiểm soát."""
    monkeypatch.setattr(otel_instrument.sys, "stdin", io.StringIO(json.dumps(data)))
    monkeypatch.setattr(otel_instrument, "_emit_otel_span", lambda event: emit_ok)
    tel_dir = tmp_path / "telemetry"
    monkeypatch.setattr(otel_instrument, "_get_telemetry_dir", lambda root: tel_dir)
    tel_dir.mkdir(parents=True, exist_ok=True)
    exit_code = 0
    try:
        otel_instrument.main()
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0
    return tel_dir, exit_code


def _fallback_file(tel_dir: Path) -> Path:
    return tel_dir / otel_instrument.TELEMETRY_FILE_NAME


def test_otel_outage_records_fallback_event(monkeypatch, tmp_path, capsys):
    data = {"tool_name": "Bash", "tool_input": {"command": "ls"}, "session_id": "s1"}
    tel_dir, exit_code = _run_main(monkeypatch, data, tmp_path, emit_ok=False)

    log = _fallback_file(tel_dir)
    assert log.exists()
    lines = [json.loads(l) for l in log.read_text().splitlines() if l.strip()]
    assert len(lines) == 1
    ev = lines[0]
    assert ev["tool_name"] == "Bash"
    assert ev["session_id"] == "s1"
    assert ev["status"] == "success"
    assert ev["attributes"]["tool.name"] == "Bash"
    assert ev["attributes"]["tool.input.hash"] != "ls"
    assert exit_code == 0


def test_otel_available_skips_fallback(monkeypatch, tmp_path):
    tel_dir, exit_code = _run_main(
        monkeypatch, {"tool_name": "Read", "tool_input": {}}, tmp_path, emit_ok=True
    )
    assert not _fallback_file(tel_dir).exists()
    assert exit_code == 0


def test_fallback_write_failure_is_surfaced_not_swallowed(monkeypatch, tmp_path, capsys):
    # Giả lập outage ghi thật: events.jsonl là một DIRECTORY -> open() fail IsADirectoryError
    # (deterministic kể cả chạy root, không cần monkeypatch function).
    tel_dir = tmp_path / "telemetry"
    tel_dir.mkdir(parents=True, exist_ok=True)
    (tel_dir / otel_instrument.TELEMETRY_FILE_NAME).mkdir()
    monkeypatch.setattr(otel_instrument.sys, "stdin", io.StringIO(json.dumps(
        {"tool_name": "Edit", "tool_input": {"file_path": "x"}}
    )))
    monkeypatch.setattr(otel_instrument, "_emit_otel_span", lambda event: False)
    monkeypatch.setattr(otel_instrument, "_get_telemetry_dir", lambda root: tel_dir)

    exit_code = 0
    try:
        otel_instrument.main()
    except SystemExit as e:
        exit_code = e.code if e.code is not None else 0

    captured = capsys.readouterr()
    assert "error writing telemetry log" in captured.err
    assert exit_code == 0


def test_passthrough_output_and_exit_code_preserved(monkeypatch, tmp_path, capsys):
    data = {
        "tool_name": "Bash",
        "tool_input": {"command": "echo hi"},
        "tool_output": {"exit_code": 5, "output": "hi"},
        "exit_code": 5,
    }
    tel_dir, exit_code = _run_main(monkeypatch, data, tmp_path, emit_ok=True)
    captured = capsys.readouterr()
    out = json.loads(captured.out)
    assert out["exit_code"] == 5
    assert exit_code == 5


def test_invalid_stdin_does_not_crash(monkeypatch, tmp_path):
    monkeypatch.setattr(otel_instrument.sys, "stdin", io.StringIO("not json at all{{{"))
    exit_code = 0
    try:
        otel_instrument.main()
    except SystemExit as e:
        exit_code = e.code
    assert exit_code == 0


def test_determine_status_matrix():
    assert otel_instrument._determine_status({"status": "blocked"}) == "blocked"
    assert otel_instrument._determine_status({"error": "boom"}) == "error"
    assert otel_instrument._determine_status({"exit_code": 2}) == "error"
    assert otel_instrument._determine_status(None) == "success"
    assert otel_instrument._determine_status("all good") == "success"


def test_hash_input_never_leaks_raw():
    raw = {"command": "cat /etc/shadow", "secret": "sk-verysecret"}
    h = otel_instrument._hash_input(raw)
    assert len(h) == 16
    assert "sk-verysecret" not in h
    assert "cat /etc/shadow" not in h
