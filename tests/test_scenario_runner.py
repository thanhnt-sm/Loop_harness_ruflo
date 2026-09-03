"""Tests cho scenario_runner.py + verify_env_setup.py + rubric_generator.py."""
from __future__ import annotations

import json
import sys
from pathlib import Path

import pytest

SCRIPT_DIR = Path(__file__).resolve().parent.parent / ".devin" / "scripts"
if str(SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(SCRIPT_DIR))

from brd_schema import Actor, BRD, FunctionalRequirement, NonFunctionalRequirement  # noqa: E402
from scenario_runner import (  # noqa: E402
    Evidence,
    Scenario,
    Step,
    _evaluate_assertion,
    make_scenarios_from_brd,
    run_scenario,
)
from rubric_generator import (  # noqa: E402
    BinaryRubric,
    ScoreRubric,
    generate_rubric_file,
    generate_rubrics,
)
from verify_env_setup import VerifyEnv  # noqa: E402


# --- scenario_runner ---


def test_evaluate_assertion_json_path():
    assert _evaluate_assertion("$.status", {"status": "ok"}) is True
    assert _evaluate_assertion("$.missing", {"status": "ok"}) is False
    assert _evaluate_assertion("$.items.0", {"items": ["a", "b"]}) is True
    assert _evaluate_assertion("$.items.5", {"items": ["a"]}) is False


def test_evaluate_assertion_python():
    assert _evaluate_assertion('contains "error"', "this is an error message") is True
    assert _evaluate_assertion('contains "error"', "all good") is False
    assert _evaluate_assertion("len(.) > 0", "non-empty") is True
    assert _evaluate_assertion("len(.) > 0", "") is False
    assert _evaluate_assertion("status_code == 200", {"status_code": 200}) is True
    assert _evaluate_assertion("status_code == 200", {"status_code": 500}) is False


def test_evaluate_assertion_empty():
    assert _evaluate_assertion("", "anything") is True


def test_run_scenario_all_pass():
    s = Scenario(
        scenario_id="SC-test-1",
        linked_fr="FR-001",
        actor="customer",
        use_case="test",
        steps=[
            Step(action='python -c "print(1)"', action_type="cli", expected="ok"),
            Step(action='python -c "print(2)"', action_type="cli", expected="ok"),
        ],
    )
    result = run_scenario(s)
    assert result.passed is True
    assert len(result.step_results) == 2
    assert all(r.status.value == "pass" for r in result.step_results)


def test_run_scenario_stops_on_fail():
    s = Scenario(
        scenario_id="SC-test-2",
        linked_fr="FR-001",
        actor="customer",
        use_case="test",
        steps=[
            Step(action='python -c "print(1)"', action_type="cli", expected="ok"),
            Step(action='python -c "import sys; sys.exit(1)"', action_type="cli", expected="ok"),
            Step(action='python -c "print(3)"', action_type="cli", expected="ok"),
        ],
    )
    result = run_scenario(s)
    assert result.passed is False
    assert result.failed_step == 1
    assert len(result.step_results) == 2  # step 2 không chạy


def test_run_scenario_ui_skipped():
    """UI step trả SKIP nếu chưa wire agent-browser — không phải fail."""
    s = Scenario(
        scenario_id="SC-ui-1",
        linked_fr="FR-001",
        actor="customer",
        use_case="click",
        steps=[Step(action="click button", action_type="ui", expected="dialog opens")],
    )
    result = run_scenario(s)
    # UI hiện skip; vẫn coi passed vì không có step nào fail
    assert result.passed is True
    assert result.step_results[0].status.value == "skip"


def test_run_scenario_cli_not_found():
    s = Scenario(
        scenario_id="SC-bad-1",
        linked_fr="FR-001",
        actor="x",
        use_case="y",
        steps=[Step(action="this_command_does_not_exist_xyz", action_type="cli", expected="ok")],
    )
    result = run_scenario(s)
    assert result.passed is False
    assert result.failed_step == 0
    assert "not found" in result.step_results[0].error or "WinError" in result.step_results[0].error


def test_make_scenarios_from_brd():
    brd = BRD(
        title="Test BRD",
        business_goal="Generate scenarios from BRD here",
        version="1.0.0",
        owner="me",
        actors=[Actor(name="customer", role="end user")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="customer", use_case="register",
                description="User tạo tài khoản", priority="must",
                acceptance_criteria=["Email hợp lệ", "Password OK"]
            ),
            FunctionalRequirement(
                id="FR-002", actor="customer", use_case="login",
                description="User đăng nhập", priority="should",
                acceptance_criteria=["Token trả về"]
            ),
        ]
    )
    scenarios = make_scenarios_from_brd(brd)
    # 2 FR × 2 difficulty (happy + edge) = 4
    assert len(scenarios) == 4
    happy_fr001 = next(s for s in scenarios if s.linked_fr == "FR-001" and s.difficulty == "happy")
    edge_fr002 = next(s for s in scenarios if s.linked_fr == "FR-002" and s.difficulty == "edge")
    assert happy_fr001.actor == "customer"
    assert "register" in happy_fr001.scenario_id


# --- verify_env_setup ---


def test_verify_env_construct():
    env = VerifyEnv(
        type="web",
        boot_cmd=["npm", "run", "dev"],
        ready_signal=r"Local:.*http://localhost:3000",
        ready_timeout_seconds=10,
    )
    assert env.type == "web"
    assert env.boot_cmd == ["npm", "run", "dev"]
    assert env.ready_timeout_seconds == 10


# --- rubric_generator ---


def test_generate_binary_for_must_fr():
    brd = BRD(
        title="Test BRD", business_goal="Long enough business goal",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="x", use_case="y", description="long enough",
                priority="must", acceptance_criteria=["criterion 1 valid", "criterion 2 valid", "criterion 3 valid"]
            )
        ]
    )
    binary, _ = generate_rubrics(brd)
    assert len(binary) == 1
    assert binary[0].pass_criteria == "ALL"
    assert len(binary[0].checks) == 3


def test_generate_binary_for_should_fr():
    brd = BRD(
        title="Test BRD", business_goal="Long enough business goal",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="x", use_case="y", description="long enough",
                priority="should", acceptance_criteria=["criterion 1 valid", "criterion 2 valid"]
            )
        ]
    )
    binary, _ = generate_rubrics(brd)
    assert binary[0].pass_criteria == "AT_LEAST_80_PCT"


def test_generate_skips_wont_fr():
    brd = BRD(
        title="Test BRD", business_goal="Long enough business goal",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="x", use_case="y", description="long enough",
                priority="wont", acceptance_criteria=["criterion 1 valid"]
            )
        ]
    )
    binary, _ = generate_rubrics(brd)
    assert len(binary) == 0


def test_generate_score_for_nfr():
    brd = BRD(
        title="Test BRD", business_goal="Long enough business goal",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        non_functional_requirements=[
            NonFunctionalRequirement(id="NFR-001", type="perf", metric="response_time_p95", threshold="< 200ms"),
            NonFunctionalRequirement(id="NFR-002", type="security", metric="hash_algorithm", threshold="bcrypt cost ≥ 12"),
        ]
    )
    _, score = generate_rubrics(brd)
    assert len(score) == 2
    assert score[0].metric == "response_time_p95"
    assert score[0].threshold == 2
    assert "0" in score[0].scoring
    assert score[1].metric == "hash_algorithm"


def test_generate_rubric_file(tmp_path):
    brd = BRD(
        title="Test", business_goal="Long enough business goal here",
        version="1.0.0", owner="me",
        actors=[Actor(name="x", role="x")],
        functional_requirements=[
            FunctionalRequirement(
                id="FR-001", actor="x", use_case="y", description="long enough",
                priority="must", acceptance_criteria=["criterion 1 valid dài"]
            )
        ],
        non_functional_requirements=[
            NonFunctionalRequirement(id="NFR-001", type="perf", metric="response_time_p95", threshold="< 200ms")
        ]
    )
    out = tmp_path / "rubric.json"
    p = generate_rubric_file(brd, out)
    assert p.exists()
    data = json.loads(p.read_text(encoding="utf-8"))
    assert len(data["binary_rubrics"]) == 1
    assert len(data["score_rubrics"]) == 1
    assert data["binary_rubrics"][0]["pass_criteria"] == "ALL"
