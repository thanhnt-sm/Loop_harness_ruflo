#!/usr/bin/env python3
"""harness_upgrade_target.py — Target selection cho harness upgrade loop.

Chứa _pick_target, _audit_finding_allowed, _first_audit_finding,
_pick_audit_target, _pick_proactive_target, _refresh_coverage_json,
_run_pytest_baseline.
"""

from __future__ import annotations

import sys
import json
import re
import time
from pathlib import Path
from typing import Optional

# Thêm thư mục .devin/scripts để import khi chạy trực tiếp
sys.path.insert(0, str(Path(__file__).resolve().parent))

from harness_upgrade_constants import (
    REPO_ROOT,
    PRIORITY_RULES,
    SKIP_PATTERNS,
    AUDIT_SKIP_PATTERNS,
    DEFAULT_PROACTIVE_COVERAGE_THRESHOLD,
)
from harness_upgrade_utils import _python, _run


def _run_pytest_baseline() -> tuple[int, int, int, list[str]]:
    """Chạy pytest với coverage để lấy baseline và refresh coverage.json."""
    print("[harness_upgrade_loop] Chạy pytest -q --tb=no --cov=.devin --cov-report=json để lấy baseline...")
    rc, out, err = _run([_python(), "-m", "pytest", "-q", "--tb=no", "--cov=.devin", "--cov-report=json", "--cov-fail-under=0"], timeout=600)
    output = out + "\n" + err

    # Ghi log ngắn để debug nếu parse sai
    with open(REPO_ROOT / ".devin" / "state" / "harness_upgrade_loop.last_pytest.log", "w", encoding="utf-8") as f:
        f.write(output)

    passed = failed = skipped = 0
    m = re.search(r"(\d+) passed(?:, (\d+) failed)?(?:, (\d+) skipped)?", output)
    if m:
        passed = int(m.group(1))
        failed = int(m.group(2) or 0)
        skipped = int(m.group(3) or 0)

    failures = re.findall(r"^FAILED ([^\s]+)", output, re.MULTILINE)
    # Nếu regex summary bỏ qua failed (0 failed), dùng số FAILED dòng để chính xác hơn
    if failures and not failed:
        failed = len(failures)
    return passed, failed, skipped, failures


def _pick_target(failures: list[str]) -> Optional[str]:
    """Chọn failure ưu tiên cao nhất, bỏ qua các target thuộc HLK/ hoặc tool ngoài."""
    if not failures:
        return None
    filtered = [f for f in failures if not any(re.search(p, f) for p in SKIP_PATTERNS)]
    if not filtered:
        return None
    scored: list[tuple[int, str]] = []
    for f in filtered:
        score = 999
        for prio, pattern in PRIORITY_RULES:
            if re.search(pattern, f):
                score = min(score, prio)
        scored.append((score, f))
    scored.sort()
    return scored[0][1]


def _audit_finding_allowed(finding: str) -> bool:
    """Kiểm tra audit finding không liên quan HLK/secrets."""
    return not any(re.search(p, finding) for p in AUDIT_SKIP_PATTERNS)


def _first_audit_finding(report: dict) -> Optional[str]:
    """Trích finding đầu tiên an toàn từ báo cáo qa_doc_audit."""
    for key in ("missing_paths", "stale_refs", "hardcoded_paths"):
        items = report.get(key, [])
        for item in items:
            text = json.dumps(item, ensure_ascii=False)
            if _audit_finding_allowed(text):
                target = item.get("target") or item.get("match") or item.get("path") or text
                return f"qa_doc_audit:{key}:{target}"
    return None


def _pick_audit_target() -> Optional[str]:
    """Chọn proactive target từ các audit scripts.

    Priority: qa_doc_audit -> hook_integrity --verify -> sbom_verify.
    Trả về string dạng 'audit:<source>:<detail>' hoặc None nếu tất cả pass.
    """
    # 1. qa_doc_audit (nhanh, deterministic)
    rc, out, err = _run([_python(), ".devin/scripts/qa_doc_audit.py"], timeout=60)
    if rc == 0:
        try:
            report = json.loads(out)
            finding = _first_audit_finding(report)
            if finding:
                return f"audit:{finding}"
        except json.JSONDecodeError:
            pass
    else:
        print(f"[harness_upgrade_loop] qa_doc_audit lỗi: {err[:200]}", file=__import__("sys").stderr)

    # 2. hook_integrity SHA256
    rc, out, err = _run([_python(), ".devin/scripts/hook_integrity.py", "--verify"], timeout=30)
    if rc != 0:
        return "audit:hook_integrity_verify"

    # 3. hook_integrity order
    rc, out, err = _run([_python(), ".devin/scripts/hook_integrity.py", "--verify-order"], timeout=30)
    if rc != 0:
        return "audit:hook_integrity_order"

    # 4. sbom_verify
    rc, out, err = _run([_python(), ".devin/scripts/sbom_verify.py"], timeout=60)
    if rc != 0:
        return "audit:sbom_verify"

    return None


def _refresh_coverage_json() -> None:
    """Tạo coverage.json nếu thiếu hoặc cũ hơn 1 giờ."""
    cov_file = REPO_ROOT / "coverage.json"
    if cov_file.exists():
        mtime = cov_file.stat().st_mtime
        if (time.time() - mtime) < 3600:
            return
    print("[harness_upgrade_loop] Tạo coverage.json để tìm proactive target...")
    _run(
        [_python(), "-m", "pytest", "-q", "--tb=no", "--cov=.devin", "--cov-report=json", "--cov-fail-under=0"],
        timeout=600,
    )


def _pick_proactive_target(state: dict, failed_targets: set[str], threshold: float = DEFAULT_PROACTIVE_COVERAGE_THRESHOLD) -> Optional[str]:
    """Chọn file .devin/scripts có coverage thấp nhất dưới ngưỡng.

    Trả về string dạng 'proactive:improve coverage for <path>'.
    Bỏ qua target đã thử mà coverage không cải thiện.
    """
    _refresh_coverage_json()
    cov_file = REPO_ROOT / "coverage.json"
    if not cov_file.exists():
        return None
    try:
        data = json.loads(cov_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None

    attempts: dict[str, float] = state.setdefault("proactive_attempts", {})
    files: list[tuple[str, float]] = []
    for fname, info in data.get("files", {}).items():
        pct = info.get("summary", {}).get("percent_covered", 100.0)
        if pct >= threshold:
            continue
        # Chuẩn hóa path separator trên Windows
        posix = Path(fname).as_posix()
        # Chỉ quan tâm các script có thể test
        if "/__pycache__/" in posix or posix.endswith("__init__.py"):
            continue
        if not (posix.startswith(".devin/scripts/") or posix.startswith("tools/")):
            continue
        target = f"proactive:improve coverage for {posix}"
        if target in failed_targets:
            continue
        # Nếu target đã thử và coverage không tăng thì bỏ qua
        if target in attempts and pct <= attempts[target]:
            continue
        files.append((target, pct))

    if not files:
        return None
    files.sort(key=lambda x: x[1])
    return files[0][0]