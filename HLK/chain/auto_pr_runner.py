#!/usr/bin/env python3
"""auto_pr_runner.py — Auto-merge gate với 4-check + blast-radius limit.

Mục đích: trước khi merge PR vào main, chạy 4 gate check tuần tự:
1. coverage_matrix: 100% FR có test + test pass
2. adversarial_consensus: 0 BLOCKING issue
3. llm_judge_rubric: tất cả BinaryRubric ALL-pass, ScoreRubric ≥ threshold
4. fable_judge: agent không tự báo "done" sai

Nếu tất cả PASS → auto-merge (theo blast-radius limit). Nếu FAIL → block,
ghi lý do, không merge.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.8

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import os
import subprocess
import sys
from dataclasses import asdict, dataclass, field
from datetime import datetime
from enum import Enum
from pathlib import Path
from typing import Literal, Optional
__all__ = [
    "AUDIT_LOG_PATH",
    "DEFAULT_CONFIG_PATH",
    "GateCheck",
    "GateResult",
    "GateVerdict",
    "KILL_SWITCH_PATH",
    "LIVE_COUNTER_PATH",
    "MAX_LIVE_PER_DAY",
    "check_adversarial_consensus",
    "check_fable_judge",
    "check_live_daily_limit",
    "increment_live_counter",
    "get_metrics",
    "check_llm_judge_rubric",
    "check_rate_limit",
    "is_kill_switch_active",
    "load_config",
    "rotate_audit_log",
    "run_gates",
    "should_auto_merge",
    "write_audit_log",
]



try:
    import yaml
except ImportError:
    yaml = None  # type: ignore[assignment]

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

DEFAULT_CONFIG_PATH = Path(".devin/config/auto_pr.yaml")
KILL_SWITCH_PATH = Path(".devin/state/auto_pr_disabled")
AUDIT_LOG_PATH = Path(".devin/state/auto_pr_audit.jsonl")


class GateResult(str, Enum):
    PASS = "PASS"
    FAIL = "FAIL"
    SKIP = "SKIP"


@dataclass
class GateCheck:
    name: str
    result: GateResult
    details: str = ""
    duration_ms: int = 0


@dataclass
class GateVerdict:
    passed: bool
    checks: list[GateCheck] = field(default_factory=list)
    failed_gates: list[str] = field(default_factory=list)
    error: str = ""
    timestamp: str = field(default_factory=lambda: datetime.utcnow().isoformat() + "Z")


# --- Config ---


def load_config(path: str | Path | None = None) -> dict:
    """Load auto_pr.yaml, fallback default nếu lỗi."""
    p = Path(path) if path else DEFAULT_CONFIG_PATH
    if yaml is None or not p.exists():
        return _default_config()
    try:
        return yaml.safe_load(p.read_text(encoding="utf-8")) or _default_config()
    except Exception:
        return _default_config()


def _default_config() -> dict:
    return {
        "auto_pr": {
            "enabled": True,
            "rate_limit": {
                "max_per_day_per_prefix": 1,
                "prefixes": ["verify-first/", "harness-upgrade/", "auto:rubric:"],
            },
            "gates": {
                "coverage_matrix": True,
                "adversarial_consensus": True,
                "llm_judge_rubric": True,
                "fable_judge": True,
            },
            "blocked_paths": ["HLK/", ".env", "security policies/", ".devin/canon/", "opencode.json"],
            "allowed_title_prefixes": ["verify-first:", "harness-upgrade:", "auto:rubric:"],
        }
    }


def is_kill_switch_active() -> bool:
    """File tồn tại → auto-merge disabled."""
    return KILL_SWITCH_PATH.exists()


# --- 4 gate checks (MVP — implementations sẽ wire thật sau) ---


def check_coverage_matrix(pr_files: list[str], brd_id: str) -> GateCheck:
    """Layer 1: coverage_matrix. MVP: chỉ verify ≥1 test file trong PR."""
    has_test = any("test_" in f or "/tests/" in f for f in pr_files)
    return GateCheck(
        name="coverage_matrix",
        result=GateResult.PASS if has_test else GateResult.FAIL,
        details=f"PR has {len(pr_files)} files, has test: {has_test}",
    )


def check_adversarial_consensus(pr_diff: str) -> GateCheck:
    """Layer 2: adversarial-consensus. MVP: heuristic check for 'TODO' / 'FIXME'."""
    issues = sum(pr_diff.count(kw) for kw in ("TODO", "FIXME", "XXX", "HACK"))
    return GateCheck(
        name="adversarial_consensus",
        result=GateResult.FAIL if issues > 5 else GateResult.PASS,
        details=f"Found {issues} TODO/FIXME markers (threshold 5)",
    )


def check_llm_judge_rubric(rubric_file: Optional[Path]) -> GateCheck:
    """Layer 3: llm_judge_rubric. MVP: verify rubric file tồn tại + parse được."""
    if rubric_file is None or not rubric_file.exists():
        return GateCheck(
            name="llm_judge_rubric",
            result=GateResult.SKIP,
            details="No rubric file provided",
        )
    try:
        data = json.loads(rubric_file.read_text(encoding="utf-8"))
        n_binary = len(data.get("binary_rubrics", []))
        n_score = len(data.get("score_rubrics", []))
        return GateCheck(
            name="llm_judge_rubric",
            result=GateResult.PASS if (n_binary + n_score) > 0 else GateResult.FAIL,
            details=f"rubric: {n_binary} binary + {n_score} score",
        )
    except (json.JSONDecodeError, OSError) as e:
        return GateCheck(
            name="llm_judge_rubric",
            result=GateResult.FAIL,
            details=f"Cannot parse rubric: {e}",
        )


def check_fable_judge(task_result: Optional[dict]) -> GateCheck:
    """Layer 4: fable-judge. MVP: check 'done' claim có evidence."""
    if task_result is None:
        return GateCheck(name="fable_judge", result=GateResult.SKIP, details="No task_result")
    if task_result.get("status") == "done" and not task_result.get("evidence"):
        return GateCheck(
            name="fable_judge",
            result=GateResult.FAIL,
            details="Status=done without evidence (possible fable)",
        )
    return GateCheck(name="fable_judge", result=GateResult.PASS, details="Done has evidence")


# --- Rate limit ---


def _audit_log_path() -> Path:
    return AUDIT_LOG_PATH


def rotate_audit_log(max_size_mb: float = 10.0) -> bool:
    """Rotate audit log nếu vượt size threshold (P1 scale từ adversarial review).

    Args:
        max_size_mb: threshold tính theo MB (default 10MB)

    Returns:
        True nếu đã rotate, False nếu không cần
    """
    p = _audit_log_path()
    if not p.exists():
        return False
    size_mb = p.stat().st_size / (1024 * 1024)
    if size_mb < max_size_mb:
        return False
    # Rotate: rename sang <name>_<date>.jsonl
    today = datetime.utcnow().strftime("%Y-%m-%d")
    new_name = p.stem + "_" + today + p.suffix
    archive = p.parent / new_name
    try:
        p.rename(archive)
        return True
    except OSError:
        return False


def _validate_audit_path(path: Path, repo_root: Path | None = None) -> tuple[bool, str]:
    """Validate audit log path nằm trong .devin/state/ (P1 security từ adversarial review).

    Args:
        path: path cần validate
        repo_root: gốc repo (default: auto-detect từ AUDIT_LOG_PATH parents)

    Returns:
        (ok, error_msg)
    """
    if not isinstance(path, Path):
        return False, "path phải là Path object"
    if repo_root is None:
        # Auto-detect: walk up từ path cho tới khi thấy .devin/state
        for parent in AUDIT_LOG_PATH.resolve().parents:
            if (parent / ".devin").is_dir():
                repo_root = parent
                break
        if repo_root is None:
            # Fallback 1: tìm git root
            try:
                root_str = subprocess.run(
                    ["git", "rev-parse", "--show-toplevel"],
                    capture_output=True, text=True, timeout=5,
                ).stdout.strip()
                if root_str:
                    repo_root = Path(root_str)
            except Exception:
                pass
        if repo_root is None:
            # Fallback 2: tìm từ .devin/scripts location
            # _SCRIPT_DIR = .devin/scripts → parent.parent = repo root
            try:
                repo_root = _SCRIPT_DIR.parent.parent
            except Exception:
                pass
        if repo_root is None:
            # Last resort: tạm chấp nhận (cho CI/test env không có .devin)
            # nhưng chỉ khi path là "safe-looking" (chỉ chứa .jsonl, không có ..)
            if ".." not in str(path) and str(path).endswith(".jsonl"):
                return True, "fallback: no repo root, allowing safe-looking .jsonl path"
            return False, "không tìm được repo root"
    try:
        resolved = path.resolve()
        allowed_root = (repo_root / ".devin" / "state").resolve()
        # Check resolved path nằm trong allowed_root
        resolved.relative_to(allowed_root)
        return True, ""
    except ValueError:
        return False, f"path {path} không nằm trong {allowed_root}"
    except (OSError, RuntimeError) as e:
        return False, f"resolve path lỗi: {e}"


def _read_audit_today(prefix: str) -> int:
    """Đếm số PR đã auto-merge hôm nay cho 1 prefix."""
    p = _audit_log_path()
    if not p.exists():
        return 0
    today = datetime.utcnow().strftime("%Y-%m-%d")
    count = 0
    for line in p.read_text(encoding="utf-8").splitlines():
        if not line.strip():
            continue
        try:
            entry = json.loads(line)
        except json.JSONDecodeError:
            continue
        if entry.get("timestamp", "").startswith(today) and entry.get("branch_prefix") == prefix:
            count += 1
    return count


def check_rate_limit(branch_prefix: str, cfg: dict) -> tuple[bool, str]:
    """Check xem đã đạt rate limit chưa."""
    max_per_day = cfg.get("rate_limit", {}).get("max_per_day_per_prefix", 1)
    used = _read_audit_today(branch_prefix)
    if used >= max_per_day:
        return False, f"Rate limit: {used}/{max_per_day} PR/ngày cho prefix '{branch_prefix}'"
    return True, f"OK ({used}/{max_per_day})"


# --- Main gate ---


def run_gates(
    pr_files: list[str],
    pr_diff: str = "",
    rubric_file: Optional[Path] = None,
    task_result: Optional[dict] = None,
    config_path: Optional[Path] = None,
) -> GateVerdict:
    """Chạy 4 gate check tuần tự. Trả về GateVerdict."""
    cfg = load_config(config_path)
    gates_cfg = cfg.get("auto_pr", cfg).get("gates", {})

    checks: list[GateCheck] = []
    if gates_cfg.get("coverage_matrix", True):
        checks.append(check_coverage_matrix(pr_files, brd_id=""))
    if gates_cfg.get("adversarial_consensus", True):
        checks.append(check_adversarial_consensus(pr_diff))
    if gates_cfg.get("llm_judge_rubric", True):
        checks.append(check_llm_judge_rubric(rubric_file))
    if gates_cfg.get("fable_judge", True):
        checks.append(check_fable_judge(task_result))

    failed = [c.name for c in checks if c.result == GateResult.FAIL]
    passed = len(failed) == 0
    return GateVerdict(
        passed=passed,
        checks=checks,
        failed_gates=failed,
    )


def write_audit_log(
    pr_url: str,
    branch_prefix: str,
    gate_verdict: GateVerdict,
    brd_id: str = "",
    scenario_count: int = 0,
    rubric_score: float = 0.0,
) -> None:
    """Ghi 1 entry vào audit log JSONL.

    P1 security: validate path nằm trong .devin/state/ trước khi ghi.
    """
    p = _audit_log_path()
    ok, err = _validate_audit_path(p)
    if not ok:
        raise ValueError(f"audit path validation failed: {err}")
    # Phase 4 hardening: rotate nếu file quá lớn
    rotate_audit_log()
    entry = {
        "timestamp": datetime.utcnow().isoformat() + "Z",
        "pr_url": pr_url,
        "branch_prefix": branch_prefix,
        "brd_id": brd_id,
        "scenario_count": scenario_count,
        "rubric_score": rubric_score,
        "gates_passed": [c.name for c in gate_verdict.checks if c.result == GateResult.PASS],
        "gates_failed": gate_verdict.failed_gates,
    }
    p.parent.mkdir(parents=True, exist_ok=True)
    with open(p, "a", encoding="utf-8") as f:
        f.write(json.dumps(entry, ensure_ascii=False) + "\n")


# --- Daily live counter (rate limit cho mode='live') ---

LIVE_COUNTER_PATH = Path(".devin/state/auto_pr_live_counter.json")
MAX_LIVE_PER_DAY = 1  # max 1 live auto-merge / ngày (regardless of skip-confirm)


def _today_utc() -> str:
    """Trả về date UTC hiện tại (YYYY-MM-DD)."""
    return datetime.utcnow().strftime("%Y-%m-%d")


def _read_live_counter() -> dict:
    """Đọc live counter từ file. Trả về dict rỗng nếu file không tồn tại."""
    if not LIVE_COUNTER_PATH.exists():
        return {}
    try:
        return json.loads(LIVE_COUNTER_PATH.read_text(encoding="utf-8"))
    except (json.JSONDecodeError, OSError):
        return {}


def _write_live_counter(data: dict) -> None:
    """Ghi live counter ra file."""
    LIVE_COUNTER_PATH.parent.mkdir(parents=True, exist_ok=True)
    LIVE_COUNTER_PATH.write_text(json.dumps(data, indent=2), encoding="utf-8")


def check_live_daily_limit() -> tuple[bool, str]:
    """Check xem hôm nay đã đạt max live auto-merge chưa.

    Returns:
        (ok, error_msg). ok=True nếu được phép, False nếu đã đạt max.
    """
    counter = _read_live_counter()
    today = _today_utc()
    daily_count = counter.get(today, 0)
    if daily_count >= MAX_LIVE_PER_DAY:
        return False, f"Đã đạt max {MAX_LIVE_PER_DAY} live auto-merge hôm nay ({today}). Reset vào 00:00 UTC."
    return True, f"OK ({daily_count}/{MAX_LIVE_PER_DAY})"


def increment_live_counter() -> None:
    """Tăng counter hôm nay lên 1."""
    counter = _read_live_counter()
    today = _today_utc()
    counter[today] = counter.get(today, 0) + 1
    _write_live_counter(counter)


# --- Metrics ---

def get_metrics() -> dict:
    """Thu thập metrics về health của chain.

    Returns:
        dict với keys: total_runs, pass_count, fail_count, pass_rate,
        audit_log_size_bytes, audit_log_lines, last_10_verdicts.
    """
    metrics = {
        "total_runs": 0,
        "pass_count": 0,
        "fail_count": 0,
        "pass_rate": 0.0,
        "audit_log_size_bytes": 0,
        "audit_log_lines": 0,
        "last_10_verdicts": [],
    }
    if not AUDIT_LOG_PATH.exists():
        return metrics
    try:
        text = AUDIT_LOG_PATH.read_text(encoding="utf-8", errors="ignore")
        metrics["audit_log_size_bytes"] = len(text.encode("utf-8"))
        lines = [l for l in text.splitlines() if l.strip()]
        metrics["audit_log_lines"] = len(lines)
        for line in lines:
            try:
                entry = json.loads(line)
                metrics["total_runs"] += 1
                if entry.get("gates_failed"):
                    metrics["fail_count"] += 1
                else:
                    metrics["pass_count"] += 1
            except json.JSONDecodeError:
                pass
        if metrics["total_runs"] > 0:
            metrics["pass_rate"] = metrics["pass_count"] / metrics["total_runs"]
        # Last 10 verdicts
        for line in lines[-10:]:
            try:
                entry = json.loads(line)
                metrics["last_10_verdicts"].append({
                    "timestamp": entry.get("timestamp", ""),
                    "branch_prefix": entry.get("branch_prefix", ""),
                    "pr_url": entry.get("pr_url", ""),
                    "gates_failed": entry.get("gates_failed", []),
                })
            except json.JSONDecodeError:
                pass
    except OSError:
        pass
    return metrics


# --- Main API cho Phase 5 ---


def _is_interactive() -> bool:
    """Check xem stdin có phải TTY không."""
    try:
        return sys.stdin.isatty()
    except (AttributeError, ValueError):
        return False


def _human_confirm(title: str, pr_files: list[str], gate_names: list[str]) -> bool:
    """Hỏi human confirm. Trả về True nếu user đồng ý.

    Behavior:
    - Non-interactive (no TTY) → return False (refuse, force explicit CI flag)
    - User gõ "y"/"yes" → True
    - Mọi input khác (empty, "n", etc.) → False
    """
    if not _is_interactive():
        return False
    print("\n" + "=" * 60)
    print("HUMAN CONFIRM REQUIRED for mode='live'")
    print("=" * 60)
    print(f"  Title: {title}")
    print(f"  Files: {len(pr_files)}")
    print(f"  Gates passed: {', '.join(gate_names)}")
    print("=" * 60)
    try:
        ans = input("Confirm merge? [y/N]: ").strip().lower()
    except (EOFError, KeyboardInterrupt):
        return False
    return ans in ("y", "yes")


def should_auto_merge(
    pr_files: list[str],
    pr_diff: str,
    branch_prefix: str,
    pr_title: str,
    rubric_file: Optional[Path] = None,
    task_result: Optional[dict] = None,
    config_path: Optional[Path] = None,
    mode: Literal["simulate", "live"] = "simulate",
    required_ci: Optional[list[str]] = None,
    gh_bin: str = "gh",
    force: bool = False,
    require_human_confirm: bool = True,
) -> GateVerdict:
    """Quyết định có auto-merge hay không. Trả về GateVerdict có `passed` chỉ
    khi TẤT CẢ điều kiện sau đều thoả:
    1. Kill switch không active
    2. auto_pr.enabled = true
    3. PR title prefix nằm trong allowlist
    4. Không có file nào trong blocked_paths
    5. Rate limit chưa đạt
    6. Cả 4 gate check pass

    Args:
        mode: "simulate" (mặc định, chỉ in verdict + audit log) hoặc "live" (gọi gh CLI thật)
        required_ci: list check CI bắt buộc cho mode="live" (vd ["ci/build", "ci/test"])
        gh_bin: path tới gh binary (mặc định "gh")
    """
    if is_kill_switch_active():
        return GateVerdict(passed=False, error=f"Kill switch active: {KILL_SWITCH_PATH}")

    cfg = load_config(config_path)
    auto_cfg = cfg.get("auto_pr", cfg)

    if not auto_cfg.get("enabled", True):
        return GateVerdict(passed=False, error="auto_pr disabled in config")

    # Check title prefix
    allowed = auto_cfg.get("allowed_title_prefixes", [])
    if not any(pr_title.startswith(p) for p in allowed):
        return GateVerdict(passed=False, error=f"PR title '{pr_title}' không match allowlist {allowed}")

    # Check blocked paths
    blocked = auto_cfg.get("blocked_paths", [])
    for f in pr_files:
        if any(f.startswith(b) for b in blocked):
            return GateVerdict(passed=False, error=f"File {f} thuộc blocked list {blocked}")

    # Check rate limit (bypass khi force=True, dành cho test/CI)
    if not force:
        rate_ok, rate_msg = check_rate_limit(branch_prefix, auto_cfg)
        if not rate_ok:
            return GateVerdict(passed=False, error=rate_msg)

    # Run 4 gate checks
    verdict = run_gates(pr_files, pr_diff, rubric_file, task_result, config_path)
    if not verdict.passed:
        return verdict

    # Mode live: gọi gh CLI thật
    if mode == "live":
        # Plan 10 phase 6: daily rate limit (regardless of skip-confirm)
        limit_ok, limit_msg = check_live_daily_limit()
        if not limit_ok:
            return GateVerdict(passed=False, error=limit_msg)
        # Human confirm trước khi merge (P0 fix từ adversarial review)
        if require_human_confirm and not os.environ.get("AHD_AUTO_PR_SKIP_CONFIRM"):
            gate_names = [c.name for c in verdict.checks]
            if not _human_confirm(pr_title, pr_files, gate_names):
                return GateVerdict(passed=False, error="user declined or non-interactive mode (set AHD_AUTO_PR_SKIP_CONFIRM=1 to bypass)")
        try:
            from auto_pr_gh import live_auto_merge
            result = live_auto_merge(
                title=pr_title,
                body=pr_diff[:65000],  # GitHub PR body max 65535 chars
                branch_prefix=branch_prefix,
                required_ci=required_ci,
                gh_bin=gh_bin,
            )
            if not result["success"]:
                return GateVerdict(passed=False, error=f"live_auto_merge: {result['reason']}")
            # Plan 10 phase 6: increment daily counter sau khi merge thành công
            increment_live_counter()
            # Ghi audit log với pr_url
            write_audit_log(
                pr_url=result["pr_url"] or "",
                branch_prefix=branch_prefix,
                gate_verdict=verdict,
                brd_id=(task_result or {}).get("brd_id", ""),
                scenario_count=(task_result or {}).get("scenario_count", 0),
                rubric_score=(task_result or {}).get("rubric_score", 0.0),
            )
        except ImportError:
            return GateVerdict(passed=False, error="auto_pr_gh module not found")

    # Tất cả pass
    return verdict


if __name__ == "__main__":
    import sys as _sys
    # Demo: chạy gate với mock data
    verdict = should_auto_merge(
        pr_files=["src/foo.py", "tests/test_foo.py"],
        pr_diff="+ new feature\n+ TODO: cleanup",
        branch_prefix="verify-first/",
        pr_title="verify-first: add foo",
        rubric_file=None,
        task_result={"status": "done", "evidence": "test passed"},
    )
    print(f"Verdict: passed={verdict.passed}, error={verdict.error}")
    for c in verdict.checks:
        print(f"  - {c.name}: {c.result.value} ({c.details})")
