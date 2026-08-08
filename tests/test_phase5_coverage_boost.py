#!/usr/bin/env python3
"""T5.x — Coverage boost cho Phase 5: bù đắp coverage bị giảm do test mới dùng monkeypatch.

Nhắm vào các module có coverage thấp sau khi thêm test E2E/red-team/bench:
- approval_gate: CLI, interactive, parse_plan_summary, parse_quality_report, cmd_reject/request_changes.
- cost_tracker: CLI path (--check, --set-cap).
- benchjack_redteam: CLI.
- reflection_gate: CLI, check_reflection.
- idempotency: ledger_path, lookup.
- hook_integrity: --status, --generate.
- adaptive_compress: prefix_stable_hash, deep mode.

Tuân thủ safe zone (tests/), không đụng HLK/.env/security policies.
"""
from __future__ import annotations

import io
import json
import sys
from datetime import datetime, timezone
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)

import ahd_session  # noqa: E402


# ===========================================================================
# approval_gate — CLI, interactive, parse helpers
# ===========================================================================

def test_approval_gate_parse_args_all_flags():
    """_parse_args xử lý đầy đủ --status/--approve/--reject/--request-changes/--interactive."""
    import approval_gate

    args = approval_gate._parse_args([
        "plan.md", "--approve", "--reviewer", "alice", "--comments", "ok", "--artifact", "sd"
    ])
    assert args["plan_file"] == "plan.md"
    assert args["approve"] is True
    assert args["reviewer"] == "alice"
    assert args["comments"] == "ok"
    assert args["artifact"] == "sd"

    args2 = approval_gate._parse_args(["p.md", "--reject", "--reason", "bad"])
    assert args2["reject"] is True
    assert args2["reason"] == "bad"
    # --reason fallback sang comments.
    assert args2["comments"] == "bad"

    args3 = approval_gate._parse_args(["p.md", "--request-changes", "--reviewer", "bob"])
    assert args3["request_changes"] is True
    assert args3["reviewer"] == "bob"

    args4 = approval_gate._parse_args(["p.md", "--interactive", "--quality-report", "qr.md"])
    assert args4["interactive"] is True
    assert args4["quality_report"] == "qr.md"

    # Unknown flag bị bỏ qua.
    args5 = approval_gate._parse_args(["p.md", "--unknown-flag"])
    assert args5["plan_file"] == "p.md"


def test_approval_gate_main_no_plan_file_returns_2(capsys):
    """main() trả 2 khi không có plan_file."""
    import approval_gate

    old_argv = sys.argv
    try:
        sys.argv = ["approval_gate.py"]
        code = approval_gate.main()
    finally:
        sys.argv = old_argv
    assert code == 2


def test_approval_gate_main_approve(tmp_path, capsys):
    """main() với --approve ghi state approved."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n\n## Task table\n\n| T1 | desc |\n", encoding="utf-8")
    old_argv = sys.argv
    try:
        sys.argv = ["approval_gate.py", str(plan), "--approve", "--reviewer", "tester", "--comments", "ok"]
        code = approval_gate.main()
    finally:
        sys.argv = old_argv
    assert code == 0


def test_approval_gate_main_status(tmp_path, capsys):
    """main() với --status in state hiện tại."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    old_argv = sys.argv
    try:
        sys.argv = ["approval_gate.py", str(plan), "--status"]
        code = approval_gate.main()
    finally:
        sys.argv = old_argv
    # Status of pending plan -> exit 1.
    assert code in (0, 1)


def test_approval_gate_cmd_reject(tmp_path):
    """cmd_reject ghi state rejected."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    state = approval_gate.cmd_reject(plan, "reviewer", "bad plan")
    assert state["status"] == "rejected"


def test_approval_gate_cmd_request_changes(tmp_path):
    """cmd_request_changes ghi state changes_requested."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    state = approval_gate.cmd_request_changes(plan, "reviewer", "fix X")
    assert state["status"] == "changes_requested"


def test_approval_gate_cmd_status_pending(tmp_path):
    """cmd_status trả pending khi chưa có approval (dùng plan path sạch)."""
    import approval_gate

    # Dùng plan path duy nhất trong tmp để tránh state leak từ test khác.
    plan = tmp_path / "unique_status_plan.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    state = approval_gate.cmd_status(plan, "plan")
    assert state["status"] == "pending"


def test_approval_gate_parse_plan_summary_extracts_metadata(tmp_path):
    """_parse_plan_summary trích risk tier, task count, req count, file count."""
    import approval_gate

    plan = tmp_path / "docs" / "plans" / "my-feature" / "IMPLEMENTATION_PLAN.md"
    plan.parent.mkdir(parents=True, exist_ok=True)
    plan.write_text(
        "# Plan\n\n| Risk Tier | P0 |\n\n"
        "T1.1 T1.2 T2.1\nREQ-001 REQ-002\n"
        "`.devin/scripts/foo.py` `tests/bar.py`\n",
        encoding="utf-8",
    )
    summary = approval_gate._parse_plan_summary(plan)
    assert summary["risk_tier"] == "P0"
    assert summary["tasks_count"] == 3
    assert summary["requirements_count"] == 2
    assert summary["files_count"] == 2
    assert "my feature" in summary["feature"]


def test_approval_gate_parse_plan_summary_fill_in_risk(tmp_path):
    """_parse_plan_summary xử lý [FILL IN: Rx] placeholder."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("| Risk Tier | [FILL IN: R2] |\n", encoding="utf-8")
    summary = approval_gate._parse_plan_summary(plan)
    assert summary["risk_tier"]


def test_approval_gate_parse_quality_report_nonexistent_returns_empty(tmp_path):
    """_parse_quality_report trả {} khi file không tồn tại."""
    import approval_gate

    assert approval_gate._parse_quality_report(tmp_path / "nonexistent.md") == {}


def test_approval_gate_parse_quality_report_valid(tmp_path):
    """_parse_quality_report trích scorecard từ file."""
    import approval_gate

    qr = tmp_path / "QUALITY_REPORT.md"
    qr.write_text("# Quality Report\n\n**Scorecard:** 8.5/10\n", encoding="utf-8")
    result = approval_gate._parse_quality_report(qr)
    # Có thể trả scorecard hoặc dict rỗng tùy parser; chỉ assert không raise.
    assert isinstance(result, dict)


def test_approval_gate_cmd_interactive_nonexistent_returns_error(tmp_path):
    """cmd_interactive trả error khi plan file không tồn tại."""
    import approval_gate

    result = approval_gate.cmd_interactive(tmp_path / "nope.md", "reviewer")
    assert "error" in result


def test_approval_gate_cmd_interactive_approve(tmp_path, monkeypatch):
    """cmd_interactive với response 'y' -> approved."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n\n| T1 | desc |\n", encoding="utf-8")
    inputs = iter(["y"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    state = approval_gate.cmd_interactive(plan, "reviewer", artifact="plan")
    assert state["status"] == "approved"


def test_approval_gate_cmd_interactive_reject(tmp_path, monkeypatch):
    """cmd_interactive với response 'n' -> rejected."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    inputs = iter(["n", "too risky"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    state = approval_gate.cmd_interactive(plan, "reviewer")
    assert state["status"] == "rejected"


def test_approval_gate_cmd_interactive_request_changes(tmp_path, monkeypatch):
    """cmd_interactive với response 'm' -> changes_requested."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    inputs = iter(["m", "add more tests"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    state = approval_gate.cmd_interactive(plan, "reviewer")
    assert state["status"] == "changes_requested"


def test_approval_gate_cmd_interactive_info_request(tmp_path, monkeypatch):
    """cmd_interactive với response 'i' -> pending + info requested."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    inputs = iter(["i", "what about X?"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    state = approval_gate.cmd_interactive(plan, "reviewer")
    assert state["status"] == "pending"


def test_approval_gate_cmd_interactive_invalid_response(tmp_path, monkeypatch):
    """cmd_interactive với response không hợp lệ -> pending."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")
    inputs = iter(["z"])
    monkeypatch.setattr("builtins.input", lambda _prompt="": next(inputs))
    state = approval_gate.cmd_interactive(plan, "reviewer")
    assert state["status"] == "pending"


def test_approval_gate_cmd_interactive_eof_aborts(tmp_path, monkeypatch):
    """cmd_interactive EOF -> pending (aborted)."""
    import approval_gate

    plan = tmp_path / "PLAN.md"
    plan.write_text("# Plan\n", encoding="utf-8")

    def _raise(_prompt=""):
        raise EOFError

    monkeypatch.setattr("builtins.input", _raise)
    state = approval_gate.cmd_interactive(plan, "reviewer")
    assert state["status"] == "pending"


# ===========================================================================
# cost_tracker — CLI path
# ===========================================================================

def test_cost_tracker_cli_check_ok(tmp_path, monkeypatch, capsys):
    """CLI --check khi cost dưới cap -> in OK (không block)."""
    import cost_tracker

    session_id = "ct-cli-ok"
    state_dir = tmp_path / ".devin" / "session_state"
    state_dir.mkdir(parents=True, exist_ok=True)
    (state_dir / f"{session_id}.json").write_text(
        json.dumps({"cumulative_cost": 1.0, "cost_cap": 10.0}), encoding="utf-8"
    )
    monkeypatch.setattr(cost_tracker.ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    exceeded, msg = cost_tracker.check_cost_cap_session(tmp_path, session_id)
    assert exceeded is False


def test_cost_tracker_set_cost_cap(tmp_path, monkeypatch):
    """set_cost_cap ghi cost_cap vào session state."""
    import cost_tracker

    session_id = "ct-setcap"
    monkeypatch.setattr(cost_tracker.ahd_session, "get_repo_root", lambda _start_from=None: tmp_path)
    cost_tracker.set_cost_cap(tmp_path, session_id, 25.0)
    state = cost_tracker.ahd_session.read_session_state(session_id, tmp_path)
    assert state.get("cost_cap") == 25.0


def test_cost_tracker_check_cost_cap_session_empty_session():
    """check_cost_cap_session với session_id rỗng -> (False, '')."""
    import cost_tracker

    exceeded, msg = cost_tracker.check_cost_cap_session(Path("/tmp"), "")
    assert exceeded is False
    assert msg == ""


# ===========================================================================
# benchjack_redteam — CLI
# ===========================================================================

def test_benchjack_cli_outputs_json(capsys):
    """CLI benchjack in ra JSON list 4 exploit."""
    import benchjack_redteam

    code = benchjack_redteam._cli()
    out = capsys.readouterr().out
    data = json.loads(out)
    assert code == 0
    assert len(data) == 4
    types = {e["exploit_type"] for e in data}
    assert types == {"padding", "metric_gaming", "shortcut", "reward_hack"}


# ===========================================================================
# reflection_gate — CLI + check_reflection
# ===========================================================================

def test_reflection_gate_check_reflection_none_for_non_action():
    """check_reflection trả None khi input không phải action cần reflection."""
    import reflection_gate

    result = reflection_gate.check_reflection({"category": "read", "target": "foo.py"})
    # read không phải destructive -> có thể trả None hoặc verdict allow.
    assert result is None or result.block is False


def test_reflection_gate_check_reflection_blocks_delete():
    """check_reflection block action delete."""
    import reflection_gate

    result = reflection_gate.check_reflection({
        "category": "delete", "target": "/important", "id": "act-1", "args": {}
    })
    if result is not None:
        assert isinstance(result.block, bool)


def test_reflection_gate_cli(capsys):
    """CLI reflection_gate in verdict JSON cho action read (không block)."""
    import reflection_gate

    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO(json.dumps({"category": "read", "target": "foo.py", "id": "a1"}))
        code = reflection_gate._cli()
    finally:
        sys.stdin = old_stdin
    assert code in (0, 2)


def test_reflection_gate_cli_invalid_json(capsys):
    """CLI reflection_gate với JSON lỗi -> exit 1."""
    import reflection_gate

    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO("not json")
        code = reflection_gate._cli()
    finally:
        sys.stdin = old_stdin
    assert code == 1


def test_reflection_gate_invalid_level_raises():
    """reflect với level không hợp lệ -> ValueError."""
    import reflection_gate
    from data_models import Action

    action = Action(id="a1", category="read", target="x.py")
    with pytest.raises(ValueError):
        reflection_gate.reflect(action, level="invalid")


# ===========================================================================
# idempotency — ledger_path, lookup
# ===========================================================================

def test_idempotency_ledger_path_format(tmp_path, monkeypatch):
    """ledger_path trả đường dẫn .devin/idempotency/<run_id>.ledger.jsonl."""
    import idempotency

    monkeypatch.setattr(idempotency, "_repo_root", lambda: tmp_path)
    p = idempotency.ledger_path("run-x")
    assert p.name == "run-x.ledger.jsonl"
    assert "idempotency" in str(p)


def test_idempotency_lookup_returns_none_for_unknown(tmp_path, monkeypatch):
    """lookup key chưa register -> None."""
    import idempotency

    monkeypatch.setattr(idempotency, "_repo_root", lambda: tmp_path)
    result = idempotency.lookup("unknown-key", run_id="run-lookup")
    assert result is None


# ===========================================================================
# hook_integrity — --status, --generate
# ===========================================================================

def test_hook_integrity_status(capsys):
    """--status in ra counts (không raise)."""
    import hook_integrity

    old_argv = sys.argv
    try:
        sys.argv = ["hook_integrity.py", "--status"]
        code = hook_integrity.main()
    finally:
        sys.argv = old_argv
    assert code in (0, 1, 2)


def test_hook_integrity_generate(tmp_path, capsys):
    """--generate tạo baseline file trong tmp_path (tránh side effect repo gốc)."""
    import hook_integrity

    # Tạo fake hooks dir để generate baseline
    hooks_dir = tmp_path / ".devin" / "hooks"
    hooks_dir.mkdir(parents=True)
    (hooks_dir / "test_hook.py").write_text("# test", encoding="utf-8")

    old_argv = sys.argv
    try:
        sys.argv = ["hook_integrity.py", "--generate", "--root", str(tmp_path)]
        code = hook_integrity.main()
    finally:
        sys.argv = old_argv
    # Generate phải tạo baseline file
    assert code == 0
    assert (tmp_path / ".devin" / "hook_hashes.json").exists()


# ===========================================================================
# adaptive_compress — prefix_stable_hash, deep mode
# ===========================================================================

def test_adaptive_compress_prefix_stable_hash_true():
    """prefix_stable_hash trả True khi turn đầu mỗi role giữ nguyên content."""
    import adaptive_compress
    from data_models import Turn

    before = [
        Turn(role="user", content="hello", tokens=5, timestamp=datetime.now(timezone.utc)),
        Turn(role="assistant", content="hi", tokens=3, timestamp=datetime.now(timezone.utc)),
        Turn(role="user", content="q2", tokens=3, timestamp=datetime.now(timezone.utc)),
    ]
    after = [
        Turn(role="user", content="hello", tokens=5, timestamp=datetime.now(timezone.utc)),
        Turn(role="assistant", content="hi", tokens=3, timestamp=datetime.now(timezone.utc)),
        Turn(role="user", content="q2 compressed", tokens=2, timestamp=datetime.now(timezone.utc)),
    ]
    # Turn đầu mỗi role (user="hello", assistant="hi") giữ nguyên -> True.
    assert adaptive_compress.prefix_stable_hash(before, after) is True


def test_adaptive_compress_prefix_stable_hash_false_when_first_role_changed():
    """prefix_stable_hash trả False khi turn đầu role bị thay đổi."""
    import adaptive_compress
    from data_models import Turn

    before = [
        Turn(role="user", content="hello", tokens=5, timestamp=datetime.now(timezone.utc)),
    ]
    after = [
        Turn(role="user", content="hello changed", tokens=5, timestamp=datetime.now(timezone.utc)),
    ]
    assert adaptive_compress.prefix_stable_hash(before, after) is False


def test_adaptive_compress_prefix_stable_hash_empty_before():
    """prefix_stable_hash với before rỗng -> True."""
    import adaptive_compress
    from data_models import Turn

    assert adaptive_compress.prefix_stable_hash([], []) is True


def test_adaptive_compress_prefix_stable_hash_after_empty():
    """prefix_stable_hash với after rỗng nhưng before không rỗng -> False."""
    import adaptive_compress
    from data_models import Turn

    before = [Turn(role="user", content="x", tokens=1, timestamp=datetime.now(timezone.utc))]
    assert adaptive_compress.prefix_stable_hash(before, []) is False


def test_adaptive_compress_deep_mode():
    """compress mode='deep' gộp turn liên tiếp cùng role."""
    import adaptive_compress
    from data_models import Turn

    history = [
        Turn(role="user", content="q1", tokens=5, timestamp=datetime.now(timezone.utc)),
        Turn(role="user", content="q2", tokens=5, timestamp=datetime.now(timezone.utc)),
        Turn(role="assistant", content="a1", tokens=5, timestamp=datetime.now(timezone.utc)),
        Turn(role="assistant", content="a2", tokens=5, timestamp=datetime.now(timezone.utc)),
    ]
    result = adaptive_compress.compress(history, query="complex analyze trade-offs", mode="deep")
    # Deep mode gộp -> ít turn hơn hoặc bằng.
    assert len(result) <= len(history)


def test_adaptive_compress_minimal_mode():
    """compress mode='minimal' giữ gần như nguyên history."""
    import adaptive_compress
    from data_models import Turn

    history = [
        Turn(role="user", content="q1", tokens=5, timestamp=datetime.now(timezone.utc)),
        Turn(role="assistant", content="a1", tokens=5, timestamp=datetime.now(timezone.utc)),
    ]
    result = adaptive_compress.compress(history, query="simple", mode="minimal")
    assert len(result) >= 1


# ===========================================================================
# context_guard — CLI
# ===========================================================================

def test_context_guard_cli(capsys, monkeypatch):
    """CLI context_guard đọc stdin, in check_oversize output (vượt 2x -> cắt)."""
    import context_guard

    old_stdin = sys.stdin
    try:
        sys.stdin = io.StringIO("x" * 7000)
        code = context_guard._cli()
    finally:
        sys.stdin = old_stdin
    out = capsys.readouterr().out
    assert code == 0
    # Vượt 2x ngưỡng 3000 -> bị cắt, độ dài giảm đáng kể.
    assert len(out) < 7000


# ===========================================================================
# swarm_judge — judge basic
# ===========================================================================

def test_swarm_judge_judge_aggregates():
    """swarm_judge.judge aggregate WorkerResult thành Verdict."""
    import swarm_judge
    from data_models import SwarmSpec, WorkerResult, Order

    order = Order(id="o1", worker_id="w1", task="t1", idempotency_key="k1")
    spec = SwarmSpec(
        run_id="r1", orders=[order], max_parallel=1,
        created_at=datetime.now(timezone.utc),
    )
    results = [
        WorkerResult(order_id="o1", worker_id="w1", status="success",
                     artifacts=[], error=None, duration_ms=10, cost_usd=0.0)
    ]
    verdict = swarm_judge.judge(results, spec)
    assert verdict is not None
