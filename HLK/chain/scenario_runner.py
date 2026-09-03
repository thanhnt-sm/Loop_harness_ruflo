#!/usr/bin/env python3
"""scenario_runner.py — Chạy kịch bản verify trong môi trường cô lập.

Mục đích: replay 1 scenario (precondition + steps + expected outcome) trong
VerifyEnv đã boot sẵn, thu thập evidence (screenshot, log, json, http),
trả về ScenarioResult với step-by-step trace.

Spec: docs/plans/harness-upgrade-verify-first/IMPLEMENTATION_PLAN.md section 4.2

Design:
- Mỗi scenario chạy trong fresh subprocess (không share state với scenario khác).
- Step execution: dùng subprocess cho CLI step, dùng verify_env_setup cho HTTP/API.
- Evidence: lưu vào .devin/state/scenarios/<scenario_id>/

Tuân thủ safe zone (.devin/scripts/).
"""
from __future__ import annotations

import json
import shlex
import subprocess
import sys
from dataclasses import dataclass, field
from enum import Enum
from pathlib import Path
from typing import Any, Literal, Optional

_SCRIPT_DIR = Path(__file__).resolve().parent
if str(_SCRIPT_DIR) not in sys.path:
    sys.path.insert(0, str(_SCRIPT_DIR))

from brd_schema import BRD  # noqa: E402
from verify_env_setup import EnvHandle  # noqa: E402
__all__ = [
    "Evidence",
    "Scenario",
    "ScenarioResult",
    "Step",
    "StepResult",
    "StepStatus",
    "make_scenarios_from_brd",
    "run_scenario",
]



Difficulty = Literal["happy", "edge", "adversarial"]
ActionType = Literal["ui", "api", "cli", "simulator"]
EvidenceType = Literal["screenshot", "log", "json", "http"]


class StepStatus(str, Enum):
    PENDING = "pending"
    PASS = "pass"
    FAIL = "fail"
    SKIP = "skip"


@dataclass
class Evidence:
    type: EvidenceType
    path: str
    assertion: str  # python expression hoặc JSON path


@dataclass
class Step:
    action: str  # command, URL, hoặc instruction string
    action_type: ActionType
    expected: str
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class Scenario:
    scenario_id: str  # SC-<actor>-<uc>-<idx>
    linked_fr: str  # FR-001
    actor: str
    use_case: str
    difficulty: Difficulty = "happy"
    preconditions: list[str] = field(default_factory=list)
    steps: list[Step] = field(default_factory=list)
    expected_outcome: str = ""
    evidence: list[Evidence] = field(default_factory=list)


@dataclass
class StepResult:
    step_idx: int = 0
    action: str = ""
    status: StepStatus = StepStatus.PENDING
    output: str = ""
    error: str = ""
    evidence_collected: list[str] = field(default_factory=list)


@dataclass
class ScenarioResult:
    scenario_id: str
    passed: bool
    step_results: list[StepResult] = field(default_factory=list)
    failed_step: Optional[int] = None
    error: str = ""
    duration_ms: int = 0


def _evaluate_assertion(assertion: str, evidence_data: Any) -> bool:
    """Evaluate assertion. Hỗ trợ:
    - JSON path: $.field.subfield
    - Python expression: contains "text", len(x) > 0, status_code == 200
    - Empty/missing assertion → True (vacuously satisfied)
    """
    if not assertion:
        return True
    s = assertion.strip()
    # JSON path
    if s.startswith("$"):
        parts = [p for p in s.split(".") if p and p != "$"]
        cur: Any = evidence_data
        for p in parts:
            if isinstance(cur, dict):
                cur = cur.get(p)
            elif isinstance(cur, list) and p.isdigit():
                idx = int(p)
                cur = cur[idx] if 0 <= idx < len(cur) else None
            else:
                return False
            if cur is None:
                return False
        return bool(cur)
    # Python expression — safe subset: only allow attribute access + comparison
    # KHÔNG dùng eval() thật; thay bằng restricted check
    try:
        if s.startswith('contains "') and s.endswith('"'):
            needle = s[len('contains "'):-1]
            return needle in str(evidence_data)
        if s.startswith("len(") and s.endswith(") > 0"):
            return len(str(evidence_data)) > 0
        if s.startswith("status_code == "):
            expected = int(s.split("==")[1].strip())
            return isinstance(evidence_data, dict) and evidence_data.get("status_code") == expected
        # Fallback: exact match
        return str(evidence_data) == s
    except Exception:
        return False


def _run_cli_step(action: str, env: Optional[EnvHandle], timeout: int = 60) -> StepResult:
    """Chạy 1 CLI step, capture output."""
    try:
        cmd = shlex.split(action) if not action.startswith("http") else None
        if cmd is None:
            return StepResult(step_idx=-1, action=action, status=StepStatus.SKIP, error="URL action không thuộc CLI")
        proc = subprocess.run(
            cmd,
            capture_output=True,
            text=True,
            timeout=timeout,
            env={**__import__("os").environ} if env is None else None,
        )
        return StepResult(
            step_idx=-1, action=action,
            status=StepStatus.PASS if proc.returncode == 0 else StepStatus.FAIL,
            output=proc.stdout[:5000],
            error=proc.stderr[:1000] if proc.returncode != 0 else "",
        )
    except subprocess.TimeoutExpired:
        return StepResult(step_idx=-1, action=action, status=StepStatus.FAIL, error=f"timeout after {timeout}s")
    except FileNotFoundError as e:
        return StepResult(step_idx=-1, action=action, status=StepStatus.FAIL, error=f"command not found: {e}")
    except Exception as e:
        return StepResult(step_idx=-1, action=action, status=StepStatus.FAIL, error=str(e))


def _run_api_step(action: str, timeout: int = 30) -> StepResult:
    """Gọi 1 HTTP endpoint, parse response."""
    if not action.startswith(("http://", "https://")):
        return StepResult(step_idx=-1, action=action, status=StepStatus.SKIP, error="Not an HTTP URL")
    try:
        import urllib.request
        with urllib.request.urlopen(action, timeout=timeout) as resp:
            body = resp.read().decode("utf-8", errors="ignore")
            try:
                data = json.loads(body)
            except json.JSONDecodeError:
                data = body
            return StepResult(
                step_idx=-1, action=action,
                status=StepStatus.PASS if 200 <= resp.status < 400 else StepStatus.FAIL,
                output=json.dumps({"status_code": resp.status, "body": data})[:5000],
            )
    except Exception as e:
        return StepResult(step_idx=-1, action=action, status=StepStatus.FAIL, error=str(e))


def run_scenario(scenario: Scenario, env: Optional[EnvHandle] = None) -> ScenarioResult:
    """Chạy scenario, trả về ScenarioResult với step-by-step trace.

    Behavior: nếu 1 step FAIL → stop ngay, đánh failed_step.
    """
    import time
    start = time.time()
    step_results: list[StepResult] = []
    failed_step: Optional[int] = None
    evidence_dir = Path(f".devin/state/scenarios/{scenario.scenario_id}")
    evidence_dir.mkdir(parents=True, exist_ok=True)

    for i, step in enumerate(scenario.steps):
        if step.action_type == "cli":
            r = _run_cli_step(step.action, env)
        elif step.action_type == "api":
            r = _run_api_step(step.action)
        elif step.action_type in ("ui", "simulator"):
            # UI/simulator: gọi agent_browser_runner
            try:
                from agent_browser_runner import run_browser_step
                browser_r = run_browser_step(
                    action=step.action,
                    action_type=step.action_type,
                    scenario_id=scenario.scenario_id,
                    evidence_dir=evidence_dir,
                )
                if browser_r.success:
                    r = StepResult(
                        step_idx=i, action=step.action,
                        status=StepStatus.PASS,
                        output=browser_r.output,
                    )
                elif browser_r.fallback_used:
                    # CC không available → SKIP (backward compatible)
                    r = StepResult(
                        step_idx=i, action=step.action,
                        status=StepStatus.SKIP,
                        error=browser_r.error or "agent-browser fallback",
                    )
                else:
                    r = StepResult(
                        step_idx=i, action=step.action,
                        status=StepStatus.FAIL,
                        error=browser_r.error or "agent-browser step failed",
                    )
                if browser_r.evidence_path:
                    r.evidence_collected.append(str(browser_r.evidence_path))
            except ImportError:
                r = StepResult(
                    step_idx=i, action=step.action,
                    status=StepStatus.SKIP,
                    error="agent_browser_runner module not found",
                )
        else:
            r = StepResult(step_idx=i, action=step.action, status=StepStatus.SKIP, error=f"unknown action_type: {step.action_type}")
        # Lưu evidence
        if r.output and step.evidence:
            for ev in step.evidence:
                p = evidence_dir / Path(ev.path).name
                try:
                    p.write_text(r.output, encoding="utf-8")
                    r.evidence_collected.append(str(p))
                except OSError:
                    pass
        step_results.append(r)
        if r.status == StepStatus.FAIL:
            failed_step = i
            break

    passed = failed_step is None
    return ScenarioResult(
        scenario_id=scenario.scenario_id,
        passed=passed,
        step_results=step_results,
        failed_step=failed_step,
        duration_ms=int((time.time() - start) * 1000),
    )


def make_scenarios_from_brd(brd: BRD) -> list[Scenario]:
    """Tự sinh skeleton scenarios từ BRD. Mỗi FR → 1 happy + 1 edge scenario.

    Đây là scaffolding — user phải edit step.action cụ thể sau.
    """
    scenarios: list[Scenario] = []
    for idx, fr in enumerate(brd.functional_requirements, start=1):
        slug = f"{fr.actor}-{fr.use_case}".replace(" ", "-")[:64]
        happy = Scenario(
            scenario_id=f"SC-{slug}-happy",
            linked_fr=fr.id,
            actor=fr.actor,
            use_case=fr.use_case,
            difficulty="happy",
            preconditions=[f"actor={fr.actor} đã authenticated"],
            steps=[
                Step(
                    action=f"<CLI/API call để thực hiện {fr.use_case}>",
                    action_type="cli",
                    expected=fr.description,
                    evidence=[Evidence(type="log", path=f"{fr.id}.log", assertion="len(.) > 0")],
                )
            ],
            expected_outcome=fr.description,
        )
        edge = Scenario(
            scenario_id=f"SC-{slug}-edge",
            linked_fr=fr.id,
            actor=fr.actor,
            use_case=fr.use_case,
            difficulty="edge",
            preconditions=happy.preconditions,
            steps=[
                Step(
                    action=f"<invalid input cho {fr.use_case}>",
                    action_type="cli",
                    expected="Hệ thống từ chối + error message rõ ràng",
                    evidence=[Evidence(type="log", path=f"{fr.id}-edge.log", assertion='contains "error"')],
                )
            ],
            expected_outcome="Hệ thống từ chối invalid input",
        )
        scenarios.extend([happy, edge])
    return scenarios
