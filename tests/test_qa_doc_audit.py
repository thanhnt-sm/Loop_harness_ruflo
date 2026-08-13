#!/usr/bin/env python3
"""Kiểm thử qa_doc_audit stale reference detection."""
import sys
from pathlib import Path

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/scripts", ".devin/hooks"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import qa_doc_audit  # noqa: E402


def test_extract_markdown_links():
    text = "[link](.devin/canon/CORE_CANON.md)\n[ref]: docs/USAGE.md"
    refs = list(qa_doc_audit._extract_markdown_links(text))
    assert ".devin/canon/CORE_CANON.md" in refs
    assert "docs/USAGE.md" in refs


def test_resolve_existing_relative():
    root = qa_doc_audit.REPO_ROOT
    candidate = ".devin/canon/CORE_CANON.md"
    resolved = qa_doc_audit._resolve_candidate(root / "README.md", candidate)
    assert resolved == root / candidate


def test_audit_runs_and_returns_report():
    report = qa_doc_audit.audit()
    assert isinstance(report, dict)
    assert "scanned_files" in report
    assert "hardcoded_paths" in report


def test_audit_hardcoded_configs_clean():
    # config.json hiện tại không được còn nvm hardcode
    report = qa_doc_audit.audit()
    nvm_hits = [
        h for h in report["hardcoded_paths"]
        if "nvm" in h["match"] or "AppData" in h["match"]
    ]
    assert nvm_hits == [], f"config vẫn còn nvm/AppData hardcode: {nvm_hits}"


def test_audit_hardcoded_pattern_matches(tmp_path):
    # Đảm bảo pattern bắt được dạng nvm vX.Y.Z
    sample = "${USER_HOME}\\AppData\\Roaming\\nvm\\v18.20.0\\node_modules\\aide-memory"
    for pat in qa_doc_audit.HARDCODED_PATH_PATTERNS:
        import re
        assert re.search(pat, sample), f"{pat} không khớp mẫu nvm hardcode"
