"""Tests cho auto_pr_runner.py — auto-merge gate."""
from __future__ import annotations

import json
import sys
from pathlib import Path
from unittest import mock

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from auto_pr_runner import (  # noqa: E402
    GateCheck,
    GateResult,
    GateVerdict,
    is_kill_switch_active,
    load_config,
    check_adversarial_consensus,
    check_coverage_matrix,
    check_fable_judge,
    check_llm_judge_rubric,
    check_rate_limit,
    run_gates,
    should_auto_merge,
    write_audit_log,
)


def test_load_config_default():
    cfg = load_config()
    assert cfg["auto_pr"]["enabled"] is True
    assert "gates" in cfg["auto_pr"]


def test_check_coverage_matrix_pass():
    c = check_coverage_matrix(["src/foo.py", "tests/test_foo.py"], brd_id="x")
    assert c.result == GateResult.PASS


def test_check_coverage_matrix_fail():
    c = check_coverage_matrix(["src/foo.py"], brd_id="x")
    assert c.result == GateResult.FAIL


def test_check_adversarial_consensus_pass():
    c = check_adversarial_consensus("just a normal diff")
    assert c.result == GateResult.PASS


def test_check_adversarial_consensus_fail():
    diff = "TODO: x\n" * 10
    c = check_adversarial_consensus(diff)
    assert c.result == GateResult.FAIL


def test_check_llm_judge_rubric_skip():
    c = check_llm_judge_rubric(None)
    assert c.result == GateResult.SKIP


def test_check_llm_judge_rubric_pass(tmp_path):
    rubric = tmp_path / "rubric.json"
    rubric.write_text(json.dumps({
        "binary_rubrics": [{"rubric_id": "RB-001"}],
        "score_rubrics": [],
    }), encoding="utf-8")
    c = check_llm_judge_rubric(rubric)
    assert c.result == GateResult.PASS


def test_check_fable_judge_pass():
    c = check_fable_judge({"status": "done", "evidence": "test passed"})
    assert c.result == GateResult.PASS


def test_check_fable_judge_fable_detected():
    """Agent báo 'done' nhưng không có evidence → fable."""
    c = check_fable_judge({"status": "done"})
    assert c.result == GateResult.FAIL


def test_run_gates_all_pass():
    v = run_gates(
        pr_files=["src/foo.py", "tests/test_foo.py"],
        pr_diff="normal diff",
        task_result={"status": "done", "evidence": "x"},
    )
    assert v.passed is True
    assert v.failed_gates == []


def test_run_gates_with_coverage_fail():
    v = run_gates(
        pr_files=["src/foo.py"],
        pr_diff="normal diff",
        task_result={"status": "done", "evidence": "x"},
    )
    assert v.passed is False
    assert "coverage_matrix" in v.failed_gates


def test_is_kill_switch_active_false(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    assert is_kill_switch_active() is False


def test_is_kill_switch_active_true(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    (tmp_path / ".devin" / "state" / "auto_pr_disabled").touch()
    assert is_kill_switch_active() is True


def test_should_auto_merge_blocked_by_kill_switch(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    (tmp_path / ".devin" / "state" / "auto_pr_disabled").touch()
    v = should_auto_merge(
        pr_files=["tests/test_x.py"],
        pr_diff="ok", branch_prefix="verify-first/",
        pr_title="verify-first: x",
    )
    assert v.passed is False
    assert "Kill switch" in v.error


def test_should_auto_merge_blocked_by_title(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = should_auto_merge(
        pr_files=["tests/test_x.py"],
        pr_diff="ok", branch_prefix="verify-first/",
        pr_title="feat: random change",  # không match allowlist
    )
    assert v.passed is False
    assert "allowlist" in v.error


def test_should_auto_merge_blocked_by_file(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = should_auto_merge(
        pr_files=["HLK/foo.py"],  # blocked
        pr_diff="ok", branch_prefix="verify-first/",
        pr_title="verify-first: leak HLK",
    )
    assert v.passed is False
    assert "blocked" in v.error.lower()


def test_should_auto_merge_happy_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = should_auto_merge(
        pr_files=["src/foo.py", "tests/test_foo.py"],
        pr_diff="+ new feature", branch_prefix="verify-first/",
        pr_title="verify-first: add foo",
        task_result={"status": "done", "evidence": "test pass"},
    )
    assert v.passed is True


def test_check_rate_limit_no_audit_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    ok, msg = check_rate_limit("verify-first/", load_config()["auto_pr"])
    assert ok is True
    assert "0/1" in msg


def test_check_rate_limit_at_max(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    audit = tmp_path / ".devin" / "state" / "auto_pr_audit.jsonl"
    audit.parent.mkdir(parents=True)
    today = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
    audit.write_text(
        json.dumps({"timestamp": f"{today}T00:00:00Z", "branch_prefix": "verify-first/"}) + "\n",
        encoding="utf-8",
    )
    ok, msg = check_rate_limit("verify-first/", load_config()["auto_pr"])
    assert ok is False
    assert "Rate limit" in msg


def test_write_audit_log(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    v = GateVerdict(
        passed=True,
        checks=[GateCheck(name="coverage_matrix", result=GateResult.PASS)],
    )
    # Mock audit path validation cho test env (production đã có .devin)
    with mock.patch("auto_pr_runner._validate_audit_path", return_value=(True, "")):
        write_audit_log("https://github.com/x/y/pull/1", "verify-first/", v, brd_id="b1", scenario_count=5)
    p = tmp_path / ".devin" / "state" / "auto_pr_audit.jsonl"
    assert p.exists()
    entries = [json.loads(l) for l in p.read_text(encoding="utf-8").splitlines() if l.strip()]
    assert len(entries) == 1
    assert entries[0]["pr_url"].endswith("/1")
    assert entries[0]["brd_id"] == "b1"


# --- Phase 2 hardening: audit_path validation ---


def test_validate_audit_path_accept_default(tmp_path, monkeypatch):
    """Default AUDIT_LOG_PATH (.devin/state/auto_pr_audit.jsonl) → valid."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    (tmp_path / ".devin" / "state" / "auto_pr_audit.jsonl").touch()
    from auto_pr_runner import _validate_audit_path, AUDIT_LOG_PATH
    ok, err = _validate_audit_path(AUDIT_LOG_PATH)
    assert ok is True
    assert err == ""


def test_validate_audit_path_accept_subpath(tmp_path, monkeypatch):
    """Path con của .devin/state/ → valid."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    sub = tmp_path / ".devin" / "state" / "subdir" / "audit.jsonl"
    from auto_pr_runner import _validate_audit_path
    ok, _ = _validate_audit_path(sub)
    assert ok is True


def test_validate_audit_path_reject_outside(tmp_path, monkeypatch):
    """Path ngoài .devin/state/ → reject."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    bad = tmp_path / "etc" / "passwd"
    from auto_pr_runner import _validate_audit_path
    ok, err = _validate_audit_path(bad)
    assert ok is False
    assert "không nằm trong" in err


def test_validate_audit_path_reject_traversal(tmp_path, monkeypatch):
    """Path với .. → reject (resolve về ngoài .devin/state)."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    bad = tmp_path / ".devin" / "state" / ".." / ".." / "etc" / "passwd"
    from auto_pr_runner import _validate_audit_path
    ok, err = _validate_audit_path(bad)
    assert ok is False


def test_validate_audit_path_reject_non_path(tmp_path, monkeypatch):
    monkeypatch.chdir(tmp_path)
    from auto_pr_runner import _validate_audit_path
    ok, err = _validate_audit_path("not a Path object")
    assert ok is False
    assert "Path" in err


def test_write_audit_log_validates_path(tmp_path, monkeypatch):
    """Khi path invalid (mock để bypass check) → raise ValueError."""
    monkeypatch.chdir(tmp_path)
    from auto_pr_runner import write_audit_log, _validate_audit_path
    v = GateVerdict(
        passed=True,
        checks=[GateCheck(name="coverage_matrix", result=GateResult.PASS)],
    )
    with mock.patch("auto_pr_runner._validate_audit_path", return_value=(False, "mocked fail")):
        with pytest.raises(ValueError, match="audit path validation failed"):
            write_audit_log("url", "prefix/", v)


# --- Phase 4 hardening: log rotation ---


def test_rotate_audit_log_no_rotate_when_small(tmp_path, monkeypatch):
    """Khi file < threshold → không rotate."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    audit = tmp_path / ".devin" / "state" / "auto_pr_audit.jsonl"
    audit.write_text("small content\n", encoding="utf-8")
    with mock.patch("auto_pr_runner.AUDIT_LOG_PATH", audit), \
         mock.patch("auto_pr_runner._audit_log_path", return_value=audit):
        from auto_pr_runner import rotate_audit_log
        rotated = rotate_audit_log(max_size_mb=10.0)
        assert rotated is False
        assert audit.exists()


def test_rotate_audit_log_when_large(tmp_path, monkeypatch):
    """Khi file > threshold → rotate sang <name>_<date>.jsonl."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    audit = tmp_path / ".devin" / "state" / "auto_pr_audit.jsonl"
    # Tạo file 11MB (lớn hơn threshold 10MB)
    audit.write_bytes(b"x" * (11 * 1024 * 1024))
    with mock.patch("auto_pr_runner.AUDIT_LOG_PATH", audit), \
         mock.patch("auto_pr_runner._audit_log_path", return_value=audit):
        from auto_pr_runner import rotate_audit_log
        rotated = rotate_audit_log(max_size_mb=10.0)
        assert rotated is True
        # File gốc đã được rename
        assert not audit.exists()
        # Archive file tồn tại với date suffix
        today = __import__("datetime").datetime.utcnow().strftime("%Y-%m-%d")
        archive = tmp_path / ".devin" / "state" / f"auto_pr_audit_{today}.jsonl"
        assert archive.exists()


def test_rotate_audit_log_no_file(tmp_path, monkeypatch):
    """Khi file không tồn tại → return False."""
    monkeypatch.chdir(tmp_path)
    (tmp_path / ".devin" / "state").mkdir(parents=True)
    audit = tmp_path / ".devin" / "state" / "auto_pr_audit.jsonl"
    with mock.patch("auto_pr_runner.AUDIT_LOG_PATH", audit), \
         mock.patch("auto_pr_runner._audit_log_path", return_value=audit):
        from auto_pr_runner import rotate_audit_log
        rotated = rotate_audit_log()
        assert rotated is False


def test_write_audit_log_calls_rotate(tmp_path, monkeypatch):
    """write_audit_log phải gọi rotate_audit_log trước khi ghi."""
    monkeypatch.chdir(tmp_path)
    v = GateVerdict(
        passed=True,
        checks=[GateCheck(name="coverage_matrix", result=GateResult.PASS)],
    )
    with mock.patch("auto_pr_runner._validate_audit_path", return_value=(True, "")), \
         mock.patch("auto_pr_runner.rotate_audit_log") as mock_rotate:
        write_audit_log("url", "prefix/", v)
        mock_rotate.assert_called_once()


# --- Phase 2: Human confirm cho mode=live ---

from auto_pr_runner import _human_confirm  # noqa: E402


def test_human_confirm_accepts_y(monkeypatch):
    """User gõ 'y' → return True."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    assert _human_confirm("title", ["a.py"], ["coverage", "adversarial"]) is True


def test_human_confirm_accepts_yes(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "yes")
    assert _human_confirm("title", ["a.py"], ["g"]) is True


def test_human_confirm_rejects_n(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    assert _human_confirm("title", ["a.py"], ["g"]) is False


def test_human_confirm_rejects_empty(monkeypatch):
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "")
    assert _human_confirm("title", ["a.py"], ["g"]) is False


def test_human_confirm_rejects_when_non_interactive(monkeypatch):
    """Khi stdin không phải TTY (CI/CD) → auto-decline, return False."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: False)
    assert _human_confirm("title", ["a.py"], ["g"]) is False


def test_human_confirm_handles_eof(monkeypatch):
    """Khi input() raise EOFError → return False."""
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    def raise_eof(_):
        raise EOFError
    monkeypatch.setattr("builtins.input", raise_eof)
    assert _human_confirm("title", ["a.py"], ["g"]) is False


def test_should_auto_merge_live_requires_confirm(monkeypatch, tmp_path):
    """Khi mode='live' + interactive + user decline → block."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "n")
    monkeypatch.delenv("AHD_AUTO_PR_SKIP_CONFIRM", raising=False)
    v = should_auto_merge(
        pr_files=["tests/test_x.py"],
        pr_diff="ok", branch_prefix="verify-first/",
        pr_title="verify-first: x",
        task_result={"status": "done", "evidence": "x"},
        mode="live",
        force=True,
    )
    assert v.passed is False
    assert "declined" in v.error or "non-interactive" in v.error


def test_should_auto_merge_live_skip_confirm_env(monkeypatch, tmp_path):
    """Khi env AHD_AUTO_PR_SKIP_CONFIRM=1 → bypass confirm, gọi live_auto_merge."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setenv("AHD_AUTO_PR_SKIP_CONFIRM", "1")
    with mock.patch("auto_pr_runner._validate_audit_path", return_value=(True, "")), \
         mock.patch("auto_pr_runner._human_confirm") as mock_confirm, \
         mock.patch("auto_pr_gh.live_auto_merge") as mock_live:
        mock_live.return_value = {"success": True, "pr_url": "https://github.com/x/y/pull/1", "merge_sha": "abc", "reason": "merged"}
        v = should_auto_merge(
            pr_files=["tests/test_x.py"],
            pr_diff="ok diff", branch_prefix="verify-first/",
            pr_title="verify-first: x",
            task_result={"status": "done", "evidence": "x"},
            mode="live",
            force=True,
        )
        mock_confirm.assert_not_called()
        mock_live.assert_called_once()
    assert v.passed is True


def test_should_auto_merge_live_require_human_confirm_false(monkeypatch, tmp_path):
    """Khi require_human_confirm=False → bypass confirm."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.delenv("AHD_AUTO_PR_SKIP_CONFIRM", raising=False)
    # Mock audit path validation (test env khác production repo)
    with mock.patch("auto_pr_runner._validate_audit_path", return_value=(True, "")), \
         mock.patch("auto_pr_gh.live_auto_merge") as mock_live:
        mock_live.return_value = {"success": True, "pr_url": "https://github.com/x/y/pull/1", "merge_sha": "abc", "reason": "merged"}
        v = should_auto_merge(
            pr_files=["tests/test_x.py"],
            pr_diff="ok diff", branch_prefix="verify-first/",
            pr_title="verify-first: x",
            task_result={"status": "done", "evidence": "x"},
            mode="live",
            force=True,
            require_human_confirm=False,
        )
        mock_live.assert_called_once()
    assert v.passed is True


def test_should_auto_merge_live_user_accepts(monkeypatch, tmp_path):
    """Khi mode='live' + user confirm 'y' → proceed to live_auto_merge."""
    monkeypatch.chdir(tmp_path)
    monkeypatch.setattr("sys.stdin.isatty", lambda: True)
    monkeypatch.setattr("builtins.input", lambda *_: "y")
    monkeypatch.delenv("AHD_AUTO_PR_SKIP_CONFIRM", raising=False)
    with mock.patch("auto_pr_runner._validate_audit_path", return_value=(True, "")), \
         mock.patch("auto_pr_gh.live_auto_merge") as mock_live:
        mock_live.return_value = {"success": True, "pr_url": "https://github.com/x/y/pull/1", "merge_sha": "abc", "reason": "merged"}
        v = should_auto_merge(
            pr_files=["tests/test_x.py"],
            pr_diff="ok", branch_prefix="verify-first/",
            pr_title="verify-first: x",
            task_result={"status": "done", "evidence": "x"},
            mode="live",
            force=True,
        )
        mock_live.assert_called_once()
    assert v.passed is True


def test_should_auto_merge_simulate_no_confirm(monkeypatch, tmp_path):
    """Khi mode='simulate' → không hỏi confirm."""
    monkeypatch.chdir(tmp_path)
    with mock.patch("auto_pr_runner._human_confirm") as mock_confirm, \
         mock.patch("auto_pr_runner._validate_audit_path", return_value=(True, "")):
        v = should_auto_merge(
            pr_files=["tests/test_x.py"],
            pr_diff="ok", branch_prefix="verify-first/",
            pr_title="verify-first: x",
            task_result={"status": "done", "evidence": "x"},
        )
        mock_confirm.assert_not_called()
    assert v.passed is True
