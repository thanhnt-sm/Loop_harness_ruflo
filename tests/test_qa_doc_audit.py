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
