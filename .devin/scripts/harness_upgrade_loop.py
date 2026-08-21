#!/usr/bin/env python3
"""harness_upgrade_loop.py — driver cho loop nâng cấp workspace.

Mỗi lần chạy = 1 iteration:
  1. Đọc/ghi loop state.
  2. Chạy pytest để lấy baseline (có thể skip nếu đã có).
  3. Phân tích failures, chọn target theo priority.
  4. Nếu không có failure target, chạy audit (qa_doc, hook, sbom) để chọn
     proactive improvement target.
  5. Gọi plan_orchestrator --init --task để lập kế hoạch cho target.
  6. Ghi state và in next_action; kiểm tra stop conditions.

Usage:
    .venv/bin/python .devin/scripts/harness_upgrade_loop.py [--max-iterations N] [--max-time-min M] [--skip-baseline]
"""
from __future__ import annotations

import argparse
import json
import re
import subprocess
import sys
import time
from datetime import datetime, timezone
from pathlib import Path
from typing import Optional

REPO_ROOT = Path(__file__).resolve().parent.parent.parent
LOOP_STATE_DIR = REPO_ROOT / ".devin" / "state"
LOOP_STATE_FILE = LOOP_STATE_DIR / "harness_upgrade_loop.json"
LOOP_LOG_FILE = LOOP_STATE_DIR / "harness_upgrade_loop.md"
LOG_FILE = REPO_ROOT / "docs" / "reports" / "harness-upgrade-log.md"

# Priority thấp = quan trọng hơn.
PRIORITY_RULES = [
    (0, r"test_destructive_block|plan_enforce"),
    (1, r"test_cve_remediation_phase3"),
    (2, r"test_cve_remediation_phase2"),
    (3, r"test_cve_remediation_phase1"),
    (4, r"test_pytest_config"),
    (5, r"test_coverage"),
    (6, r"test_opencode_harness"),
    (7, r"test_phase3_extra_cov|sbom|cosign"),
]

# Không còn bỏ qua HLK tests vì đã fix cross-platform (ESM import + file:// URL).
# Nếu cần loại trừ một target ngoài phạm vi, thêm vào đây với lý do rõ ràng.
SKIP_PATTERNS = []

# Các file/path KHÔNG được phép sửa bởi devin -p trong auto-execute;
# khớp với lời nhắc của _build_execute_task. Dùng để revert nếu devin -p vượt quyền.
RESTRICTED_PATTERNS = [
    r"^sbom/",
    r"\.env$",
    r"hook_hashes\.json$",
    r"^HLK/",
    r"^\.devin/scripts/[^/]+\.py$",
    r"^\.devin/hooks/[^/]+\.py$",
    r"^pytest\.ini$",
]

# Audit findings liên quan HLK/secrets sẽ bị bỏ qua để không vi phạm REDLINES.
AUDIT_SKIP_PATTERNS = [
    r"[Hh][Ll][Kk]",
    r"\.env",
    r"[Ss]ecrets?[/\\]",
    r"[Cc]redentials?[/\\]",
    r"\.pem",
    r"\.key",
]

DEFAULT_MAX_ITERATIONS = 10
DEFAULT_MAX_TIME_MIN = 120
DEFAULT_CONVERGENCE = 3
DEFAULT_PROACTIVE_COVERAGE_THRESHOLD = 80.0


def _python() -> Path:
    """Tìm python executable ưu tiên .venv/bin/python rồi system python."""
    venv_python = REPO_ROOT / ".venv" / "bin" / "python"
    if venv_python.exists():
        return venv_python
    return Path(sys.executable)


def _run(cmd: list[str | Path], timeout: int = 600) -> tuple[int, str, str]:
    """Chạy shell command, trả (returncode, stdout, stderr)."""
    proc = subprocess.run(
        [str(c) for c in cmd],
        capture_output=True,
        text=True,
        encoding="utf-8",
        cwd=REPO_ROOT,
        timeout=timeout,
    )
    return proc.returncode, proc.stdout, proc.stderr


def _find_log_iteration() -> int:
    """Tìm iteration lớn nhất trong harness-upgrade-log.md, dùng để đặt tên upgrade."""
    if not LOG_FILE.exists():
        return 1
    text = LOG_FILE.read_text(encoding="utf-8")
    nums = [int(m) for m in re.findall(r"^# ITERATION (\d+)", text, re.MULTILINE)]
    return max(nums, default=0) + 1


def _load_state() -> dict:
    """Đọc loop state."""
    if LOOP_STATE_FILE.exists():
        try:
            return json.loads(LOOP_STATE_FILE.read_text(encoding="utf-8"))
        except (json.JSONDecodeError, OSError):
            pass
    return {
        "iteration": 0,
        "start_time": datetime.now(timezone.utc).isoformat(),
        "cumulative_cost_usd": 0.0,
        "last_improvement_iteration": 0,
        "failures_history": [],
        "status": "in_progress",
        "phase": "normal",
    }


def _save_state(state: dict) -> None:
    """Ghi loop state JSON và markdown tóm tắt."""
    LOOP_STATE_DIR.mkdir(parents=True, exist_ok=True)
    LOOP_STATE_FILE.write_text(json.dumps(state, ensure_ascii=False, indent=2), encoding="utf-8")

    md = f"""# Harness Upgrade Loop State

- loop_iteration: {state.get('loop_iteration', 0)}
- log_iteration: {state.get('log_iteration', 0)}
- phase: {state.get('phase', 'normal')}
- status: {state.get('status', 'in_progress')}
- start_time: {state.get('start_time', '')}
- baseline: {state.get('passed', 0)} passed / {state.get('failed', 0)} failed / {state.get('skipped', 0)} skipped
- target: `{state.get('target', 'N/A')}`
- state_file: `{state.get('plan_state_file', 'N/A')}`
- stop_reason: {state.get('stop_reason', 'None')}
- next_action: `{state.get('next_action', 'N/A')}`
"""
    LOOP_LOG_FILE.write_text(md, encoding="utf-8")


def _run_pytest_baseline() -> tuple[int, int, int, list[str]]:
    """Chạy pytest với coverage để lấy baseline và refresh coverage.json."""
    print("[harness_upgrade_loop] Chạy pytest -q --tb=no --cov=.devin --cov-report=json để lấy baseline...")
    rc, out, err = _run([_python(), "-m", "pytest", "-q", "--tb=no", "--cov=.devin", "--cov-report=json", "--cov-fail-under=0"], timeout=600)
    output = out + "\n" + err

    # Ghi log ngắn để debug nếu parse sai
    with open(LOOP_LOG_FILE.with_name("harness_upgrade_loop.last_pytest.log"), "w", encoding="utf-8") as f:
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
        print(f"[harness_upgrade_loop] qa_doc_audit lỗi: {err[:200]}", file=sys.stderr)

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
    Bỏ qua target đã thử mà coverage không cải thiện."""
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


def _check_stop(state: dict, args) -> Optional[str]:
    """Kiểm tra stop conditions. Không dừng khi all_tests_pass để cho phép audit.

    Giá trị 0 = vô hạn (bỏ qua condition đó)."""
    if args.max_iterations and state["loop_iteration"] >= args.max_iterations:
        return f"max_iterations ({args.max_iterations})"

    start = datetime.fromisoformat(state["start_time"])
    elapsed_min = (datetime.now(timezone.utc) - start).total_seconds() / 60
    if args.max_time_min and elapsed_min >= args.max_time_min:
        return f"max_time ({args.max_time_min} min)"

    history = state.get("failures_history", [])
    if args.convergence and len(history) >= args.convergence:
        recent = history[-args.convergence:]
        if all(h == state["failed"] for h in recent):
            return f"convergence ({args.convergence} iterations no improvement)"
    return None


def _is_plan_done(state: dict) -> bool:
    """Kiểm tra plan state file đã DONE hay chưa."""
    plan_file = state.get("plan_state_file", "")
    if not plan_file:
        return True
    try:
        data = json.loads(Path(plan_file).read_text(encoding="utf-8"))
        return data.get("current_state") == "DONE" or data.get("state") == "DONE"
    except (OSError, json.JSONDecodeError):
        return True


def _build_execute_task(target: str) -> str:
    """Xây dựng prompt chặt cho devin -p dựa trên target.

    Giới hạn: chỉ sửa tests, .cmd/.sh wrappers nếu cần, hoặc file config tối thiểu.
    KHÔNG sửa source .devin/scripts/*.py, .devin/hooks/*.py, sbom/, hook_hashes.json,
    .env, HLK/, hoặc các security policy."""
    base = (
        "You are in a harness upgrade loop. Make the smallest safe change, "
        "preferably in tests/ or cross-platform wrapper files, then run pytest to verify. "
        "DO NOT modify source code in .devin/scripts/*.py, .devin/hooks/*.py, "
        "sbom/python.sbom.json, .devin/hook_hashes.json, .env, HLK/, or security policies. "
        "DO NOT regenerate SBOM or hook hashes unless explicitly needed."
    )
    if target.startswith("proactive:improve coverage for "):
        module = target[len("proactive:improve coverage for "):]
        return (
            f"{base} Improve test coverage for {module}. "
            f"Add focused unit tests in tests/ (or .devin/scripts/test_*.py if appropriate) "
            f"that exercise the uncovered lines. Run pytest for that module to verify."
        )

    if target.startswith("audit:"):
        parts = target.split(":", 3)
        if len(parts) >= 3:
            source = parts[1]
            detail = parts[2]
            return (
                f"{base} Fix the {source} audit finding: {detail}. "
                f"Verify with the relevant audit script after the fix."
            )
        return f"{base} Fix the audit finding: {target}."

    # Test target
    return (
        f"{base} Fix the failing test {target}. "
        f"If the test fails because a Windows external command is missing, "
        f"add cross-platform wrappers (e.g. .cmd) or adjust the test to use venv python directly. "
        f"Run the failing test to verify."
    )


def _changed_files() -> set[str]:
    """Trả về set file đang thay đổi hoặc untracked so với HEAD (git status --porcelain)."""
    rc, out, _ = _run(["git", "status", "--porcelain"], timeout=30)
    if rc != 0:
        return set()
    files: set[str] = set()
    for line in out.splitlines():
        if line.startswith("?? ") or line.startswith("!! "):
            # Untracked / ignored
            files.add(line[3:].strip())
        elif len(line) >= 3:
            files.add(line[2:].strip().split(" -> ", 1)[-1])
    return files


def _revert_unauthorized_changes(before: set[str]) -> list[str]:
    """Revert các file bị devin -p sửa nằm trong RESTRICTED_PATTERNS và chưa dirty trước đó.

    Trả về danh sách file đã revert/xóa.
    """
    after = _changed_files()
    new_changed = after - before
    unauthorized = [f for f in new_changed if any(re.search(p, f) for p in RESTRICTED_PATTERNS)]
    if not unauthorized:
        return []
    print(f"[harness_upgrade_loop] devin -p chạm file cấm: {unauthorized}", file=sys.stderr)
    tracked = [f for f in unauthorized if Path(f).exists() and _run(["git", "ls-files", "--error-unmatch", f], timeout=10)[0] == 0]
    untracked = [f for f in unauthorized if f not in tracked]
    if tracked:
        _run(["git", "checkout", "HEAD", "--"] + tracked, timeout=30)
    for f in untracked:
        Path(f).unlink(missing_ok=True)
        # Nếu là thư mục rỗng do devin -p tạo, xóa luôn
        p = Path(f).parent
        try:
            if p != REPO_ROOT and p.exists() and not any(p.iterdir()):
                p.rmdir()
        except OSError:
            pass
    return unauthorized


def _auto_execute_target(target: str, timeout: int = 1800) -> tuple[int, str, str]:
    """Tự động gọi devin -p để thực thi target.

    Trả (rc, stdout, stderr) như _run().
    Sau khi chạy xong, kiểm tra và revert các thay đổi trái phép.
    """
    before = _changed_files()
    task = _build_execute_task(target)
    print(f"[harness_upgrade_loop] Auto-execute target via devin -p: {target}")
    # devin CLI phải có trên PATH
    rc, out, err = _run(
        ["devin", "-p", "--permission-mode", "accept-edits", "--", task],
        timeout=timeout,
    )
    if rc == 0:
        unauthorized = _revert_unauthorized_changes(before)
        if unauthorized:
            return 1, "", f"Unauthorized changes reverted: {unauthorized}"
    return rc, out, err


def _get_target_coverage(target: str) -> Optional[float]:
    """Lấy percent_covered của module trong target proactive từ coverage.json."""
    prefix = "proactive:improve coverage for "
    if not target.startswith(prefix):
        return None
    module = target[len(prefix):]
    cov_file = REPO_ROOT / "coverage.json"
    if not cov_file.exists():
        return None
    try:
        data = json.loads(cov_file.read_text(encoding="utf-8"))
    except (OSError, json.JSONDecodeError):
        return None
    # Tìm key khớp module (có thể dùng \ hoặc /)
    for fname, info in data.get("files", {}).items():
        if Path(fname).as_posix() == module:
            return float(info.get("summary", {}).get("percent_covered", 0))
    return None


def _plan_target(target: str) -> dict:
    """Gọi plan_orchestrator để lập kế hoạch cho target."""
    task = f"fix {target}"
    print(f"[harness_upgrade_loop] Khởi tạo plan cho target: {target}")
    rc, out, err = _run([_python(), ".devin/scripts/plan_orchestrator.py", "--init", "--task", task], timeout=60)
    if rc != 0:
        print(f"[harness_upgrade_loop] plan_orchestrator lỗi: {err}", file=sys.stderr)
        return {}
    try:
        return json.loads(out)
    except json.JSONDecodeError:
        print(f"[harness_upgrade_loop] Không parse được output plan: {out[:200]}", file=sys.stderr)
        return {}


def _run_one_iteration(state: dict, args) -> bool:
    """Chạy một iteration của loop. Trả True nếu nên tiếp tục, False nếu dừng."""
    loop_iteration = state.get("loop_iteration", 0) + 1
    state["loop_iteration"] = loop_iteration
    state.setdefault("log_iteration", _find_log_iteration())
    if loop_iteration == 1:
        state["start_time"] = datetime.now(timezone.utc).isoformat()

    if not args.skip_baseline:
        passed, failed, skipped, failures = _run_pytest_baseline()
    else:
        passed = state.get("passed", 0)
        failed = state.get("failed", 0)
        skipped = state.get("skipped", 0)
        failures = state.get("failures", [])

    state.update({
        "passed": passed,
        "failed": failed,
        "skipped": skipped,
        "failures": failures,
    })

    history = state.get("failures_history", [])
    history.append(failed)
    limit = args.convergence if args.convergence else 1000
    state["failures_history"] = history[-limit:]

    # Nếu đang có plan chưa DONE thì chờ (cho executor bên ngoài thực hiện)
    if not args.infinite and state.get("plan_state_file") and not _is_plan_done(state):
        print(f"[harness_upgrade_loop] Iteration {loop_iteration}: đang chờ plan hoàn thành -> {state['plan_state_file']}")
        _save_state(state)
        return True

    failed_targets = set(state.get("failed_targets", []))
    target = _pick_target(failures)
    if target and target in failed_targets:
        target = None
    if not target:
        state["phase"] = "audit"
        audit_target = _pick_audit_target()
        if audit_target and audit_target not in failed_targets:
            target = audit_target

    if not target:
        state["phase"] = "proactive"
        proactive_target = _pick_proactive_target(state, failed_targets)
        if proactive_target and proactive_target not in failed_targets:
            target = proactive_target

    if not target:
        if audit_target:
            state["phase"] = "audit"
        else:
            state["phase"] = "proactive"
        stop_reason = _check_stop(state, args)
        if stop_reason:
                state["status"] = "stopped"
                state["stop_reason"] = stop_reason
                _save_state(state)
                print(f"[harness_upgrade_loop] STOP: {stop_reason}")
                print(f"[harness_upgrade_loop] Baseline: {passed} passed / {failed} failed / {skipped} skipped")
                return False

    state["target"] = target or "wait"
    state["phase"] = state.get("phase", "normal")

    if args.infinite and target:
        # Trong --infinite, tự động thực thi target qua devin -p
        # Ghi coverage trước để so sánh sau
        before_cov: Optional[float] = None
        if target.startswith("proactive:"):
            before_cov = _get_target_coverage(target)
            attempts = state.setdefault("proactive_attempts", {})
            if before_cov is not None:
                attempts[target] = before_cov

        rc, out, err = _auto_execute_target(target, timeout=1800)
        if rc == 0:
            print("[harness_upgrade_loop] Auto-execute thành công.")
            # Với proactive target, kiểm tra coverage đã tăng chưa
            if target.startswith("proactive:"):
                after_cov = _get_target_coverage(target)
                if after_cov is None or (before_cov is not None and after_cov <= before_cov):
                    print(f"[harness_upgrade_loop] Coverage không cải thiện ({before_cov}% -> {after_cov}%), đánh dấu failed target.", file=sys.stderr)
                    state["failed_targets"] = state.get("failed_targets", []) + [target]
                else:
                    print(f"[harness_upgrade_loop] Coverage cải thiện từ {before_cov}% lên {after_cov}%")
                    state["last_improvement_iteration"] = loop_iteration
            else:
                state["last_improvement_iteration"] = loop_iteration
            # Xóa target cũ để iteration sau tìm target mới
            state.pop("target", None)
            state.pop("plan_state_file", None)
            state.pop("next_action", None)
            state.pop("plan_output", None)
        else:
            print(f"[harness_upgrade_loop] Auto-execute thất bại (rc={rc}).", file=sys.stderr)
            # Đánh dấu target này để không chọn lại trong iteration tới
            state["failed_targets"] = state.get("failed_targets", []) + [target]
    else:
        # Chế độ plan-only (hoặc non-infinite)
        plan = _plan_target(target) if target else {}
        state["plan_state_file"] = plan.get("state_file", "")
        state["next_action"] = plan.get("next_action", {}).get("action", "")
        state["plan_output"] = plan

    _save_state(state)

    print(f"\n[harness_upgrade_loop] === LOOP ITERATION {loop_iteration} (log iter {state.get('log_iteration', 0)}) ===")
    print(f"Phase: {state['phase']}")
    print(f"Baseline: {passed} passed / {failed} failed / {skipped} skipped")
    print(f"Target: {target or 'wait'}")
    if args.infinite and target:
        print("Auto-execute đã chạy; iteration kế tiếp sẽ lấy baseline mới.")
    else:
        plan = state.get("plan_output", {})
        print(f"Plan state file: {plan.get('state_file', 'N/A')}")
        print(f"Next action: {plan.get('next_action', {}).get('action', 'N/A')}")
        print("\nTiếp tục bằng cách thực hiện next_action và gọi --step với kết quả.")
        print("Sau khi xong, chạy lại script này để lấy baseline mới.")
    return True


def main(argv: list[str] | None = None) -> int:
    parser = argparse.ArgumentParser(description="Harness upgrade loop driver")
    parser.add_argument("--max-iterations", type=int, default=DEFAULT_MAX_ITERATIONS)
    parser.add_argument("--max-time-min", type=int, default=DEFAULT_MAX_TIME_MIN)
    parser.add_argument("--convergence", type=int, default=DEFAULT_CONVERGENCE)
    parser.add_argument("--skip-baseline", action="store_true", help="Không chạy pytest, dùng state cũ")
    parser.add_argument("--infinite", action="store_true", help="Chạy vòng lặp vô tận")
    parser.add_argument("--sleep", type=int, default=10, help="Giây chờ giữa các iteration trong --infinite")
    args = parser.parse_args(argv)

    if args.infinite:
        args.max_iterations = 0
        args.convergence = 0
        if args.max_time_min == DEFAULT_MAX_TIME_MIN:
            args.max_time_min = 0

    while True:
        state = _load_state()
        if args.infinite and state.get("status") == "stopped":
            state["status"] = "in_progress"
            state["stop_reason"] = None
            state["start_time"] = datetime.now(timezone.utc).isoformat()
            state["failures_history"] = []
        should_continue = _run_one_iteration(state, args)
        if not should_continue:
            return 0
        if not args.infinite:
            return 0
        print(f"[harness_upgrade_loop] Ngủ {args.sleep}s trước iteration tiếp theo...")
        time.sleep(args.sleep)


if __name__ == "__main__":
    try:
        sys.stdout.reconfigure(encoding="utf-8")
        sys.stderr.reconfigure(encoding="utf-8")
    except (AttributeError, OSError):
        pass
    sys.exit(main())
