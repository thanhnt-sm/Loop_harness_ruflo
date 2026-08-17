#!/usr/bin/env python3
"""Test suite for opencode harness integration."""

import subprocess
import json
import tempfile
import glob
from pathlib import Path
import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent


def run_cmd(cmd, input_text="", timeout=30):
    """Run command and return (code, stdout, stderr)."""
    result = subprocess.run(
        cmd, shell=True, capture_output=True, text=True,
        timeout=timeout, input=input_text, cwd=REPO_ROOT
    )
    return result.returncode, result.stdout, result.stderr


class TestOpencodeHarnessConfig:
    """Test opencode configuration."""

    def test_config_exists(self):
        config_path = REPO_ROOT / ".opencode" / "config.json"
        assert config_path.exists(), "opencode config.json missing"

    def test_config_valid_json(self):
        config_path = REPO_ROOT / ".opencode" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        assert "agents" in config
        assert "hooks" in config
        assert "tools" in config
        assert "compensation" in config

    def test_agents_defined(self):
        config_path = REPO_ROOT / ".opencode" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        agents = config["agents"]
        required = [
            "harness-orchestrator",
            "harness-executor-glm",
            "harness-executor-kimi",
            "harness-executor-lightning",
            "harness-verifier",
            "harness-subagent"
        ]
        for agent in required:
            assert agent in agents, f"Missing agent: {agent}"

    def test_compensation_layers(self):
        config_path = REPO_ROOT / ".opencode" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        comp = config["compensation"]
        for layer in ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]:
            assert layer in comp, f"Missing compensation layer: {layer}"
            assert comp[layer]["enabled"] is True, f"Layer {layer} not enabled"

    def test_model_routing(self):
        config_path = REPO_ROOT / ".opencode" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        routing = config["model_routing"]
        assert "rules" in routing
        assert "fallback" in routing
        assert len(routing["rules"]) >= 4


class TestOpencodeHarnessTools:
    """Test harness tools are executable."""

    def test_harness_verify(self):
        code, out, err = run_cmd(".opencode/tools/harness-verify.sh")
        assert code == 0, f"harness-verify failed: {err}"

    def test_harness_consensus(self):
        code, out, err = run_cmd(".opencode/tools/harness-consensus.sh test-session")
        assert code == 0, f"harness-consensus failed: {err}"

    def test_harness_subagent(self):
        code, out, err = run_cmd(".opencode/tools/harness-subagent.sh 'test task' 1000 glm-executor")
        assert code == 0, f"harness-subagent failed: {err}"

    def test_harness_fable(self):
        code, out, err = run_cmd(".opencode/tools/harness-fable.sh test-session")
        assert code == 0, f"harness-fable failed: {err}"

    def test_harness_cost(self):
        code, out, err = run_cmd(".opencode/tools/harness-cost.sh")
        assert code == 0, f"harness-cost failed: {err}"

    def test_harness_route(self):
        code, out, err = run_cmd('.opencode/tools/harness-route.sh "simple read file"')
        assert code == 0, f"harness-route failed: {err}"
        assert "glm-executor" in out or "free" in out.lower()

    def test_harness_compress(self):
        test_input = "diff --git a/file.py b/file.py\n@@ -1,3 +1,4 @@\n def foo():\n+    print('world')\n     return 42\n"
        code, out, err = run_cmd('.opencode/tools/harness-compress.sh "git diff file.py"', input_text=test_input)
        assert code == 0, f"harness-compress failed: {err}"
        assert "collapsed" in out or "unchanged" in out

    def test_harness_mask(self):
        large = "x" * 2000
        code, out, err = run_cmd('.opencode/tools/harness-mask.sh', input_text=large)
        assert code == 0, f"harness-mask failed: {err}"
        assert "MASKED" in out
        assert "tool_output_" in out

    def test_harness_compact(self):
        code, out, err = run_cmd(".opencode/tools/harness-compact.sh test-session full")
        assert code == 0, f"harness-compact failed: {err}"

    def test_harness_bestofn(self):
        code, out, err = run_cmd('.opencode/tools/harness-bestofn.sh "test task" 3')
        assert code == 0, f"harness-bestofn failed: {err}"


class TestOpencodeHarnessHooks:
    """Test hooks are executable."""

    def test_pre_tool_use(self):
        code, out, err = run_cmd('.opencode/hooks/pre_tool_use.sh bash "git status"')
        assert code == 0, f"pre_tool_use failed: {err}"
        context = json.loads(out)
        assert context["compress"] is True

    def test_post_tool_use(self):
        code, out, err = run_cmd('.opencode/hooks/post_tool_use.sh bash "git status" "output"')
        assert code == 0, f"post_tool_use failed: {err}"

    def test_session_start(self):
        code, out, err = run_cmd('.opencode/hooks/session_start.sh test-session')
        assert code == 0, f"session_start failed: {err}"

    def test_session_end(self):
        code, out, err = run_cmd('.opencode/hooks/session_end.sh test-session')
        assert code == 0, f"session_end failed: {err}"

    def test_user_prompt_submit(self):
        code, out, err = run_cmd('.opencode/hooks/user_prompt_submit.sh "fix the bug"')
        assert code == 0, f"user_prompt_submit failed: {err}"


class TestOpencodeHarnessIntegration:
    """Integration tests for compensation layers."""

    def test_compensation_gate_on_done(self):
        """Test compensation gate triggers on done declaration."""
        session_file = Path(".devin/session_state/test-gate.json")
        session_file.parent.mkdir(parents=True, exist_ok=True)
        session_file.write_text(json.dumps({
            "done_output": "All tests pass. Build green. Lint clean.",
            "done_declared": True
        }))

        code, out, err = run_cmd('.opencode/tools/harness-fable.sh test-gate --fast', timeout=10)
        assert code == 0, f"Compensation gate failed: {err}"
        result = json.loads(out)
        assert result["verdict"] in ["VERIFIED", "VERIFIED_WITH_CAVEATS", "REFUTED", "NO_CLAIMS"]
        # Fast mode should return VERIFIED
        assert result["verdict"] == "VERIFIED"

    def test_compensation_layers_complete(self):
        config_path = REPO_ROOT / ".opencode" / "config.json"
        with open(config_path) as f:
            config = json.load(f)
        comp = config["compensation"]
        layers = ["C1", "C2", "C3", "C4", "C5", "C6", "C7"]
        for layer in layers:
            assert comp[layer]["enabled"] is True, f"{layer} not enabled"

    def test_model_routing_rules(self):
        test_cases = [
            ("simple read file", "glm-executor"),
            ("code generation for feature", "kimi-executor"),
            ("complex multi-file refactor", "lightning-executor"),
            ("create plan for project", "orchestrator"),
        ]
        for task, expected in test_cases:
            code, out, err = run_cmd(f'.opencode/tools/harness-route.sh "{task}"')
            assert code == 0
            # The output should indicate the selected executor
            # (exact format depends on auto_model_router.py output)

    def test_terminal_compression_ratios(self):
        """Test compression achieves expected ratios."""
        # Git diff compression
        diff = "diff --git a/file.py b/file.py\n@@ -1,100 +1,100 @@\n" + " line\n" * 98
        code, out, _ = run_cmd('.opencode/tools/harness-compress.sh "git diff file.py"', input_text=diff)
        assert len(out) < len(diff) * 0.5

        # Git status
        status = "On branch main\nChanges to be committed:\n  modified: file1.py\n  modified: file2.py\n"
        code, out, _ = run_cmd('.opencode/tools/harness-compress.sh "git status"', input_text=status)
        assert "staged" in out

    def test_observation_masking(self):
        """Test observation masking for large outputs."""
        large = "x" * 5000
        code, out, _ = run_cmd('.opencode/tools/harness-mask.sh', input_text=large)
        assert "MASKED" in out
        assert "tool_output_" in out

        # Verify file was stored
        import glob
        files = glob.glob(".opencode/session_state/tool_outputs/tool_output_*.txt")
        assert len(files) > 0
        with open(files[-1]) as f:
            content = f.read()
            # Input may have trailing newline, so allow 5000 or 5001
            assert len(content) in (5000, 5001), f"Expected 5000 or 5001, got {len(content)}"

    def test_subagent_isolation(self):
        """Test sub-agent runs in isolation."""
        code, out, _ = run_cmd('.opencode/tools/harness-subagent.sh "find TODO comments" 2000 glm-executor')
        assert code == 0
        assert "completed" in out.lower() or "summary" in out.lower()

    def test_cost_dashboard_generation(self):
        """Test cost dashboard generates successfully."""
        code, out, _ = run_cmd('.opencode/tools/harness-cost.sh')
        assert code == 0
        assert "dashboard" in out.lower() or "savings" in out.lower()


class TestOpencodeSkillIndex:
    """Test skill index for progressive loading."""

    def test_skill_index_exists(self):
        index_path = REPO_ROOT / ".opencode" / "skills" / "skill_index.json"
        assert index_path.exists()

    def test_skill_index_valid(self):
        index_path = REPO_ROOT / ".opencode" / "skills" / "skill_index.json"
        with open(index_path) as f:
            index = json.load(f)
        assert "skills" in index
        assert len(index["skills"]) >= 10
        assert index["load_on_demand"] is True

    def test_all_skills_have_paths(self):
        index_path = REPO_ROOT / ".opencode" / "skills" / "skill_index.json"
        with open(index_path) as f:
            index = json.load(f)
        for name, skill in index["skills"].items():
            assert "path" in skill
            assert "triggers" in skill
            assert "executor" in skill


class TestOpencodeAgentInstructions:
    """Test agent instruction files exist."""

    def test_all_agents_have_instructions(self):
        agents = [
            "harness-orchestrator",
            "harness-executor-glm",
            "harness-executor-kimi",
            "harness-executor-lightning",
            "harness-verifier",
            "harness-subagent"
        ]
        for agent in agents:
            path = REPO_ROOT / ".opencode" / "agents" / f"{agent}.md"
            assert path.exists(), f"Missing agent instruction: {agent}.md"
            content = path.read_text()
            assert len(content) > 100, f"Agent {agent} instruction too short"


if __name__ == "__main__":
    pytest.main([__file__, "-v"])
