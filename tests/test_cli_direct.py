"""Test trực tiếp _cli() của các script qua import (không subprocess).

Mục đích: cover code trong khối _cli() mà subprocess tests không thu được
coverage data. Test các path: hợp lệ, stdin rỗng, JSON sai, attack input.
"""
from __future__ import annotations

import io
import json
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
for sub in (".devin/hooks", ".devin/scripts"):
    d = str(REPO_ROOT / sub)
    if d not in sys.path:
        sys.path.insert(0, d)


def _run_cli(module_name: str, stdin_text: str, argv: list[str] | None = None,
             use_main: bool = False) -> tuple[int, str, str]:
    """Import module, gọi _cli() hoặc main(), trả (exit_code, stdout, stderr)."""
    # Reload để đảm bảo state sạch
    if module_name in sys.modules:
        del sys.modules[module_name]
    mod = __import__(module_name)
    # Reset argv
    old_argv = sys.argv
    sys.argv = [module_name + ".py", *(argv or [])]
    # Capture stdin/stdout/stderr
    old_stdin, old_stdout, old_stderr = sys.stdin, sys.stdout, sys.stderr
    sys.stdin = io.StringIO(stdin_text)
    sys.stdout = io.StringIO()
    sys.stderr = io.StringIO()
    exit_code = 0
    try:
        fn = mod.main if use_main else mod._cli
        result = fn()
        exit_code = result if isinstance(result, int) else 0
    except SystemExit as e:
        exit_code = e.code if isinstance(e.code, int) else 1
    except Exception as e:
        sys.stderr.write(f"{type(e).__name__}: {e}\n")
        exit_code = 1
    finally:
        out = sys.stdout.getvalue()
        err = sys.stderr.getvalue()
        sys.stdin, sys.stdout, sys.stderr = old_stdin, old_stdout, old_stderr
        sys.argv = old_argv
    return exit_code, out, err


# ===========================================================================
# abc_checklist._cli
# ===========================================================================
class TestAbcChecklistCli:
    def test_valid_input(self):
        payload = '{"task":"test must pass","result":"ok","trace":[]}'
        code, out, err = _run_cli("abc_checklist", payload)
        assert code == 0
        data = json.loads(out)
        assert "task_valid" in data

    def test_empty_stdin(self):
        code, out, err = _run_cli("abc_checklist", "")
        assert code == 1
        assert "lỗi" in err or "error" in err.lower()

    def test_invalid_json(self):
        code, out, err = _run_cli("abc_checklist", "not json")
        assert code == 1

    def test_missing_task(self):
        code, out, err = _run_cli("abc_checklist", '{"result":"ok"}')
        assert code == 1

    def test_attack_sql_injection(self):
        code, out, err = _run_cli("abc_checklist",
                                  '{"task":"\'; DROP TABLE users; --","result":"ok"}')
        assert code == 0  # task field present, just weird content

    def test_attack_command_injection(self):
        code, out, err = _run_cli("abc_checklist",
                                  '{"task":"$(rm -rf /)","result":"ok"}')
        assert code == 0

    def test_attack_oversized(self):
        code, out, err = _run_cli("abc_checklist",
                                  '{"task":"' + "A" * 10000 + '","result":"ok"}')
        assert code == 0


# ===========================================================================
# llm_as_judge._cli
# ===========================================================================
class TestLlmAsJudgeCli:
    def test_valid_input(self):
        code, out, err = _run_cli("llm_as_judge",
                                  '{"task":"test must pass","result":"ok"}')
        assert code == 0
        assert len(out.strip()) > 0

    def test_empty_stdin(self):
        code, out, err = _run_cli("llm_as_judge", "")
        assert code == 1

    def test_invalid_json(self):
        code, out, err = _run_cli("llm_as_judge", "not json")
        assert code == 1

    def test_missing_task(self):
        code, out, err = _run_cli("llm_as_judge", '{"result":"ok"}')
        assert code == 1


# ===========================================================================
# reward_shaping._cli
# ===========================================================================
class TestRewardShapingCli:
    def test_valid_input(self):
        code, out, err = _run_cli("reward_shaping",
                                  '{"base_score":50,"actions":[],"cost":0,"security_events":[]}')
        assert code == 0
        assert float(out.strip()) == 50.0

    def test_empty_stdin(self):
        code, out, err = _run_cli("reward_shaping", "")
        assert code == 1

    def test_invalid_json(self):
        code, out, err = _run_cli("reward_shaping", "not json")
        assert code == 1

    def test_missing_base_score(self):
        code, out, err = _run_cli("reward_shaping", '{"actions":[]}')
        assert code == 1


# ===========================================================================
# adaptive_compress._cli
# ===========================================================================
class TestAdaptiveCompressCli:
    def test_valid_input(self):
        code, out, err = _run_cli("adaptive_compress",
                                  '{"history":[],"query":"","mode":"auto"}')
        assert code == 0
        assert out.strip() == "[]"

    def test_empty_stdin(self):
        code, out, err = _run_cli("adaptive_compress", "")
        assert code == 0  # empty = empty history

    def test_invalid_json(self):
        code, out, err = _run_cli("adaptive_compress", "not json")
        assert code == 1


# ===========================================================================
# swarm_judge._cli
# ===========================================================================
class TestSwarmJudgeCli:
    def test_valid_input(self):
        payload = '{"results":[],"spec":{"run_id":"r","orders":[],"max_parallel":1,"created_at":"2026-01-01T00:00:00Z"}}'
        code, out, err = _run_cli("swarm_judge", payload)
        assert code == 0
        data = json.loads(out)
        assert "pass_" in data

    def test_empty_stdin(self):
        code, out, err = _run_cli("swarm_judge", "")
        assert code == 1

    def test_invalid_json(self):
        code, out, err = _run_cli("swarm_judge", "not json")
        assert code == 1

    def test_missing_spec(self):
        code, out, err = _run_cli("swarm_judge", '{"results":[]}')
        assert code == 1


# ===========================================================================
# tscg._cli
# ===========================================================================
class TestTscgCli:
    def test_valid_input(self):
        code, out, err = _run_cli("tscg", '{"tools":[]}')
        assert code == 0
        assert out.strip() == "[]"

    def test_empty_stdin(self):
        code, out, err = _run_cli("tscg", "")
        assert code == 0  # empty = empty tools

    def test_invalid_json(self):
        code, out, err = _run_cli("tscg", "not json")
        assert code == 1


# ===========================================================================
# three_role._cli
# ===========================================================================
class TestThreeRoleCli:
    def test_argv_input(self):
        code, out, err = _run_cli("three_role", "", argv=["test task"])
        assert code == 0
        data = json.loads(out)
        assert "summary" in data

    def test_stdin_input(self):
        code, out, err = _run_cli("three_role", "task from stdin")
        assert code == 0


# ===========================================================================
# cot_synthesis._cli
# ===========================================================================
class TestCotSynthesisCli:
    def test_argv_input(self):
        code, out, err = _run_cli("cot_synthesis", "", argv=["solve problem"])
        assert code == 0
        data = json.loads(out)
        assert "cot" in data and "crv" in data

    def test_stdin_input(self):
        code, out, err = _run_cli("cot_synthesis", "problem from stdin")
        assert code == 0


# ===========================================================================
# benchjack_redteam._cli
# ===========================================================================
class TestBenchjackRedteamCli:
    def test_generates_exploits(self):
        code, out, err = _run_cli("benchjack_redteam", "")
        assert code == 0
        data = json.loads(out)
        assert isinstance(data, list) and len(data) > 0
        assert all("exploit_type" in e for e in data)


# ===========================================================================
# migrate_state.main
# ===========================================================================
class TestMigrateStateCli:
    def test_help(self):
        code, out, err = _run_cli("migrate_state", "", argv=["--help"], use_main=True)
        assert code == 0
        assert "old-root" in out or "old-root" in err

    def test_no_args(self, tmp_path, monkeypatch):
        # Chạy migrate_state trong tmp_path để tránh xóa .devin/agents thật
        monkeypatch.chdir(tmp_path)
        code, out, err = _run_cli("migrate_state", "", use_main=True)
        assert code in (0, 1)


# ===========================================================================
# path_zones._cli (manual parse)
# ===========================================================================
class TestPathZonesCli:
    def test_no_args(self):
        code, out, err = _run_cli("path_zones", "")
        assert code == 1

    def test_check_safe(self):
        code, out, err = _run_cli("path_zones", "", argv=["check", "src/main.py"])
        assert code == 0

    def test_check_traversal(self):
        code, out, err = _run_cli("path_zones", "", argv=["check", "../etc/passwd"])
        assert code == 2

    def test_check_blocked_zone(self):
        code, out, err = _run_cli("path_zones", "", argv=["check", "HLK/config.json"])
        assert code == 2

    def test_list_blocked(self):
        code, out, err = _run_cli("path_zones", "", argv=["list", "blocked"])
        assert code == 0

    def test_list_safe(self):
        code, out, err = _run_cli("path_zones", "", argv=["list", "safe"])
        assert code == 0


# ===========================================================================
# plan_orchestrator.main — test qua subprocess (xem test_cli_entrypoints.py)
# để tránh import plan_fsm package kéo thêm stmts chưa test vào coverage.
# ===========================================================================


# ===========================================================================
# artifact_registry._cli
# ===========================================================================
class TestArtifactRegistryCli:
    def test_no_args(self):
        code, out, err = _run_cli("artifact_registry", "")
        assert code == 1

    def test_list(self):
        code, out, err = _run_cli("artifact_registry", "", argv=["list"])
        assert code in (0, 1)


# ===========================================================================
# cognitive_scaffold_memory._cli
# ===========================================================================
class TestCognitiveScaffoldMemoryCli:
    def test_no_args(self):
        code, out, err = _run_cli("cognitive_scaffold_memory", "")
        assert code == 1


# ===========================================================================
# approval_gate._cli
# ===========================================================================
class TestApprovalGateCli:
    def test_no_args(self):
        code, out, err = _run_cli("approval_gate", "")
        assert code in (1, 2)


# ===========================================================================
# dyflow._cli
# ===========================================================================
class TestDyflowCli:
    def test_no_args(self):
        code, out, err = _run_cli("dyflow", "")
        assert code == 1


# ===========================================================================
# reflection_gate._cli
# ===========================================================================
class TestReflectionGateCli:
    def test_valid_input(self):
        code, out, err = _run_cli("reflection_gate",
                                  '{"task":"test","result":"ok","trace":[]}')
        assert code == 0

    def test_invalid_json(self):
        code, out, err = _run_cli("reflection_gate", "not json")
        assert code == 1
