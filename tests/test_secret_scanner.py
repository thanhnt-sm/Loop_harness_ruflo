"""Tests cho secret_scanner.py."""
from __future__ import annotations

import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

import secret_scanner  # noqa: E402
from secret_scanner import Finding, has_secret, scan, scan_summary  # noqa: E402


# --- Detect từng pattern ---


def test_detect_aws_access_key():
    text = "AKIAIOSFODNN7EXAMPLE"
    findings = scan(text)
    assert len(findings) == 1
    assert findings[0].type == "aws_access_key"
    assert findings[0].match_preview == "AKIA***MPLE"


def test_detect_aws_secret_key():
    text = 'aws_secret_access_key = "wJalrXUtnFEMI/K7MDENG/bPxRfiCYEXAMPLEKEY"'
    findings = scan(text)
    assert any(f.type == "aws_secret_key" for f in findings)


def test_detect_github_pat():
    text = "GITHUB_TOKEN=ghp_1234567890abcdefghijklmnopqrstuvwxyz"
    findings = scan(text)
    assert any(f.type == "github_pat" for f in findings)


def test_detect_github_oauth():
    text = "gho_abcdefghijklmnopqrstuvwxyz1234567890"
    findings = scan(text)
    assert any(f.type == "github_oauth" for f in findings)


def test_detect_slack_token():
    text = "SLACK_TOKEN=xoxb-" + "1234567890-abcdefghijklmnopqrstuvwx"
    findings = scan(text)
    assert any(f.type == "slack_token" for f in findings)


def test_detect_pem_private_key():
    text = "-----BEGIN RSA PRIVATE KEY-----\nMIIEowIBAAKCAQEA..."
    findings = scan(text)
    assert any(f.type == "pem_private_key" for f in findings)


def test_detect_stripe_live_key():
    # Tránh trigger generic_api_key pattern (vì có "KEY" keyword)
    text = "value=sk_live_" + "abcdefghijklmnopqrstuvwx"
    findings = scan(text)
    assert any(f.type == "stripe_live_key" for f in findings)


def test_detect_generic_api_key():
    text = 'api_key = "abcdefghijklmnop12345"'
    findings = scan(text)
    assert any(f.type == "generic_api_key" for f in findings)


# --- Negative cases ---


def test_no_secret_normal_code():
    text = """
def hello():
    return "Hello, World!"

class MyClass:
    def __init__(self, name):
        self.name = name
"""
    findings = scan(text)
    assert findings == []


def test_no_secret_short_random_string():
    """Random string < 16 chars không phải generic_api_key."""
    text = 'key = "abc123"'
    findings = scan(text)
    # generic_api_key cần ≥16 chars
    assert not any(f.type == "generic_api_key" for f in findings)


def test_no_secret_empty_text():
    assert scan("") == []


# --- has_secret / scan_summary ---


def test_has_secret_true():
    assert has_secret("AKIAIOSFODNN7EXAMPLE") is True


def test_has_secret_false():
    assert has_secret("just normal code") is False


def test_scan_summary_no_secret():
    summary = scan_summary("normal code")
    assert summary == "no secret detected"


def test_scan_summary_with_secret():
    summary = scan_summary("AKIAIOSFODNN7EXAMPLE")
    assert "aws_access_key" in summary
    assert "AKIA***MPLE" in summary  # masked


# --- Line tracking ---


def test_line_number_correct():
    text = "line 1\nline 2\nAKIAIOSFODNN7EXAMPLE on line 3"
    findings = scan(text)
    assert len(findings) >= 1
    assert any(f.line_no == 3 for f in findings)


def test_multiple_findings_sorted_by_line():
    text = """
AKIAIOSFODNN7EXAMPLE
ghp_1234567890abcdefghijklmnopqrstuvwxyz
-----BEGIN RSA PRIVATE KEY-----
"""
    findings = scan(text)
    line_nos = [f.line_no for f in findings]
    assert line_nos == sorted(line_nos)


# --- Mask ---


def test_mask_short():
    masked = secret_scanner._mask("abc")
    assert "*" in masked


def test_mask_long():
    masked = secret_scanner._mask("AKIAIOSFODNN7EXAMPLE")
    assert masked.startswith("AKIA")
    assert masked.endswith("MPLE")
    assert "***" in masked
