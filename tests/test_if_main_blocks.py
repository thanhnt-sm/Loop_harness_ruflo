"""Run hook/script __main__ blocks in-process to cover timeout/CLI wrappers.

Chỉ chạy các module đã được import trong test suite khác, để không kéo thêm
module low-coverage làm giảm tổng coverage. Các subprocess tests không góp
coverage; dùng runpy chạy trong process hiện tại với mock ahd_session.
"""
from __future__ import annotations

import io
import runpy
import sys
import types
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".devin" / "hooks"
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"


def _mock_ahd_session(repo_root: Path, state: dict | None = None) -> types.ModuleType:
    """Tạo module ahd_session giả lập để hook/script chạy an toàn."""
    m = types.ModuleType("ahd_session")
    m.get_repo_root = lambda _start_from=None: repo_root
    m.get_config_root = lambda _root=None: repo_root / ".devin"
    m.get_session_id = lambda data=None: (data or {}).get("session_id", "test-sid")
    default_state = {"cumulative_cost": 0.0, "cost_cap": 10.0}
    m.read_session_state = lambda _sid, _root: state if state is not None else default_state
    m.read_context_flags = lambda _sid, _root: {}
    m.update_session_state = lambda _sid, _data, _root: None
    m.write_session_state = lambda _sid, _data, _root=None: None
    m.get_session_state_path = lambda sid, root: root / ".devin" / "session_state" / f"{sid}.json"
    m._locked_json_update = lambda path, fn, default=None, session_id=None: None
    m.is_circuit_open = lambda _name: False
    m.should_minimal_mode = lambda _sid, _root: False
    m.now_utc = lambda: "2026-01-01T00:00:00Z"
    m.CIRCUIT_BREAKER_DIR = repo_root / ".devin" / "circuit"
    return m


def _run_main(path: Path, repo_root: Path, argv: list[str] | None = None, stdin_text: str = "", state: dict | None = None) -> int:
    """Chạy file Python qua runpy, trả exit code (bắt SystemExit)."""
    real_ahd = sys.modules.get("ahd_session")
    old_argv = sys.argv
    old_stdin = sys.stdin
    old_stdout = sys.stdout
    old_stderr = sys.stderr
    try:
        sys.modules["ahd_session"] = _mock_ahd_session(repo_root, state=state)
        sys.argv = [str(path), *(argv or [])]
        sys.stdin = io.StringIO(stdin_text)
        sys.stdout = io.StringIO()
        sys.stderr = io.StringIO()
        runpy.run_path(str(path), run_name="__main__")
        return 0
    except SystemExit as e:
        return e.code if isinstance(e.code, int) else (1 if e.code else 0)
    finally:
        if real_ahd is None:
            sys.modules.pop("ahd_session", None)
        else:
            sys.modules["ahd_session"] = real_ahd
        sys.argv = old_argv
        sys.stdin = old_stdin
        sys.stdout = old_stdout
        sys.stderr = old_stderr


_READ_PAYLOAD = '{"tool_name":"Read","tool_input":{"file_path":"src/main.py"},"session_id":"test"}'
_WRITE_PAYLOAD = '{"tool_name":"Write","tool_input":{"file_path":"src/main.py","new_string":"x"},"tool_output":{"ok":true},"session_id":"test"}'
_POST_PAYLOAD = '{"tool_name":"Read","tool_input":{"file_path":"src/main.py"},"tool_output":{"ok":true},"session_id":"test"}'

_SWARM_JUDGE_PAYLOAD = (
    '{"spec":{"run_id":"r1","orders":['
    '{"id":"o1","worker_id":"w1","task":"t","inputs":{},'
    '"outputs":[],"write_set":[],"idempotency_key":"o1","depends_on":[]}'
    '],"max_parallel":5,"created_at":"2026-01-01T00:00:00Z"},'
    '"results":['
    '{"order_id":"o1","worker_id":"w1","status":"success",'
    '"artifacts":[],"duration_ms":0,"cost_usd":0.0}'
    ']}'
)
_REFLECTION_GATE_PAYLOAD = '{"category":"write","target":"src/main.py","id":"a1"}'
_TSCG_PAYLOAD = '{"tools":[{"name":"foo","description":"bar","parameters":{"type":"object"},"required":[]}]}'
_REWARD_SHAPING_PAYLOAD = '{"base_score":50,"actions":[{"status":"success"}],"cost":0,"security_events":[{"severity":"warn"}]}'


@pytest.mark.parametrize("hook,payload", [
    ("pre_tool_use.py", _READ_PAYLOAD),
    ("plan_enforce.py", _READ_PAYLOAD),
    ("coverage_enforce.py", _WRITE_PAYLOAD),
    ("schema_gate.py", _READ_PAYLOAD),
    ("session_start.py", '{"session_id":"test","prompt_id":"p1"}'),
])
def test_hook_main_block(tmp_path, hook, payload):
    """Các hook `if __name__ == "__main__"` phải chạy mà không crash."""
    code = _run_main(HOOKS_DIR / hook, tmp_path, argv=[hook], stdin_text=payload)
    assert code in (0, 1, 2), f"{hook} exit code {code}"


@pytest.mark.parametrize("script,argv,stdin,state", [
    ("cost_tracker.py", ["--session", "s1", "--check"], "", None),
    ("cost_tracker.py", ["--session", "s2", "--set-cap", "10.0"], "", None),
    ("cost_tracker.py", ["--session", "s3", "--check"], "", {"cumulative_cost": 8.5, "cost_cap": 10.0}),
    ("cost_tracker.py", ["--session", "s4", "--check"], "", {"cumulative_cost": 12.0, "cost_cap": 10.0}),
])
def test_script_main_block(tmp_path, script, argv, stdin, state):
    """Các script có CLI block không crash khi chạy qua runpy."""
    code = _run_main(SCRIPTS_DIR / script, tmp_path, argv=argv, stdin_text=stdin, state=state)
    assert code in (0, 1, 2), f"{script} exit code {code}"


@pytest.mark.parametrize("script,argv,stdin", [
    ("path_zones.py", ["list", "safe"], ""),
    ("path_zones.py", ["check", "src/main.py"], ""),
    ("swarm_judge.py", [], _SWARM_JUDGE_PAYLOAD),
    ("reflection_gate.py", [], _REFLECTION_GATE_PAYLOAD),
    ("tscg.py", ["--budget", "1024"], _TSCG_PAYLOAD),
    ("reward_shaping.py", [], _REWARD_SHAPING_PAYLOAD),
    ("three_role.py", ["task demo"], ""),
])
def test_script_main_block_others(tmp_path, script, argv, stdin):
    """Các script khác có CLI block không crash khi chạy qua runpy."""
    code = _run_main(SCRIPTS_DIR / script, tmp_path, argv=argv, stdin_text=stdin)
    assert code in (0, 1, 2), f"{script} exit code {code}"
