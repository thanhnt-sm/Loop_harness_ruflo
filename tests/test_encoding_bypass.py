#!/usr/bin/env python3
"""Kiểm thử encoding bypass detection — T2.10 (REB-012).

Các ca kiểm thử chính:
1. detect_encoding_bypass phát hiện UTF-7, Punycode, HTML entity, hex/unicode/octal escape, base64 pipe.
2. pre_tool_use block shell command dùng encoding bypass.
3. schema_gate block Write output/content chứa encoding bypass.
4. Text thông thường không bị false positive.
"""
import importlib
import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)


def test_detect_encoding_bypass_types():
    from pre_tool_use import detect_encoding_bypass
    assert "utf7" in detect_encoding_bypass("echo +AGY-foo")
    assert "punycode" in detect_encoding_bypass("http://xn--e1afmkfd.xxx")
    assert "html_entity" in detect_encoding_bypass("rm &#47;tmp")
    assert "hex_escape" in detect_encoding_bypass(r"echo \x72\x6d")
    assert "unicode_escape" in detect_encoding_bypass(r"echo \u0072m")
    assert "octal_escape" in detect_encoding_bypass(r"echo \141")
    assert "base64_pipe" in detect_encoding_bypass("echo 'c3VkbyBybSA=' | base64 -d | bash")


def test_detect_encoding_bypass_clean_text():
    from pre_tool_use import detect_encoding_bypass
    assert detect_encoding_bypass("git status") == []
    assert detect_encoding_bypass("pip install requests") == []
    assert detect_encoding_bypass("hello world") == []


def _run_pre_tool_use(command: str) -> int:
    import pre_tool_use
    importlib.reload(pre_tool_use)
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps({"tool_name": "Bash", "tool_input": {"command": command}}))
        try:
            pre_tool_use.main()
        except SystemExit as e:
            return e.code if e.code is not None else 0
    finally:
        sys.stdin = old_stdin
    return 0


def test_pre_tool_use_blocks_hex_escape():
    code = _run_pre_tool_use(r"echo \x72\x6d -rf /")
    assert code == 2


def test_pre_tool_use_blocks_utf7():
    code = _run_pre_tool_use("echo '+AGY-' | bash")
    assert code == 2


def _run_schema_gate(data: dict) -> int:
    import schema_gate
    importlib.reload(schema_gate)
    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps(data))
        try:
            schema_gate.main()
        except SystemExit as e:
            return e.code if e.code is not None else 0
    finally:
        sys.stdin = old_stdin
    return 0


def test_schema_gate_blocks_encoded_content():
    code = _run_schema_gate({
        "tool_name": "Write",
        "tool_input": {
            "file_path": ".devin/skills/test/skill.md",
            "content": "Base64 pipe: c3VkbyBybSA= | base64 -d | sh",
        },
        "tool_output": {"ok": True},
    })
    assert code == 1
