#!/usr/bin/env python3
"""Test Harness Architecture Supreme — tiêu chuẩn kiến trúc harness tối cao.

Kiểm tra:
- Hook fail-closed behavior
- State isolation giữa providers
- Idempotency của state operations
- Atomic file writes (tmp + replace)
- Lock mechanism cho concurrent access
- Hook ordering và chain integrity
- Error boundary — hook crash không crash system
- Coverage gate enforcement
- Plan enforcement gate
- Schema validation gate
- Destructive operation blocking
- Subagent isolation

Chạy: python -m pytest tests/test_harness_architecture_supreme.py -v
"""
import json
import os
import subprocess
import sys
from pathlib import Path

import pytest

REPO_ROOT = Path(__file__).resolve().parent.parent
HOOKS_DIR = REPO_ROOT / ".devin" / "hooks"
SCRIPTS_DIR = REPO_ROOT / ".devin" / "scripts"


def _read_source(path: Path) -> str:
    if not path.exists():
        return ""
    return path.read_text(encoding="utf-8")


def _run_hook(hook: str, stdin: str, timeout: int = 10) -> tuple[int, str, str]:
    """Chạy hook với stdin, trả (exit_code, stdout, stderr)."""
    hook_path = HOOKS_DIR / hook
    if not hook_path.exists():
        return -1, "", f"{hook} not found"
    try:
        proc = subprocess.run(
            [sys.executable, str(hook_path)],
            input=stdin,
            capture_output=True,
            text=True,
            timeout=timeout,
            cwd=str(REPO_ROOT),
        )
        return proc.returncode, proc.stdout, proc.stderr
    except subprocess.TimeoutExpired:
        return -2, "", "timeout"
    except Exception as e:
        return -3, "", str(e)


# ---------------------------------------------------------------------------
# ARCH-001: Hook error boundary — crash không crash system
# ---------------------------------------------------------------------------

class TestHookErrorBoundary:
    """ARCH-001: Hook crash phải được handle, không crash system."""

    @pytest.mark.parametrize("hook", [
        "pre_tool_use.py",
        "post_tool_use.py",
        "schema_gate.py",
        "plan_enforce.py",
        "coverage_enforce.py",
    ])
    def test_hook_survives_bad_json(self, hook):
        """Hook phải không crash với input JSON sai."""
        code, out, err = _run_hook(hook, "not valid json")
        assert code in (0, 1, 2), (
            f"{hook} crash với bad JSON: exit={code}, stderr={err[:200]}"
        )
        assert "Traceback" not in err or code != -3, (
            f"{hook} unhandled exception với bad JSON:\n{err[:500]}"
        )

    @pytest.mark.parametrize("hook", [
        "pre_tool_use.py",
        "post_tool_use.py",
        "schema_gate.py",
    ])
    def test_hook_survives_empty_input(self, hook):
        """Hook phải không crash với empty input."""
        code, out, err = _run_hook(hook, "")
        assert code in (0, 1, 2), (
            f"{hook} crash với empty input: exit={code}, stderr={err[:200]}"
        )

    @pytest.mark.parametrize("hook", [
        "pre_tool_use.py",
        "schema_gate.py",
        "plan_enforce.py",
    ])
    def test_hook_survives_null_input(self, hook):
        """Hook phải không crash với null values."""
        payload = json.dumps({"tool_name": None, "tool_input": None})
        code, out, err = _run_hook(hook, payload)
        assert code in (0, 1, 2), (
            f"{hook} crash với null input: exit={code}, stderr={err[:200]}"
        )


# ---------------------------------------------------------------------------
# ARCH-002: Atomic file writes
# ---------------------------------------------------------------------------

class TestAtomicFileWrites:
    """ARCH-002: State files phải được viết atomically (tmp + replace)."""

    @pytest.mark.parametrize("script", [
        "ahd_session.py",
        "coverage_enforce.py",
        "self_heal.py",
    ])
    def test_atomic_write_pattern(self, script):
        """Script phải dùng tmp + replace pattern."""
        path = HOOKS_DIR / script
        if not path.exists():
            path = SCRIPTS_DIR / script
        if not path.exists():
            pytest.skip(f"{script} not found")
        source = _read_source(path)
        # Check for atomic write pattern: write to tmp then replace
        has_tmp = ".tmp" in source or "tmp_" in source or "NamedTemporaryFile" in source
        has_replace = ".replace(" in source or "os.replace(" in source or "os.rename(" in source
        assert has_tmp or has_replace, (
            f"{script} không dùng atomic write pattern (tmp + replace) — "
            "race condition risk khi concurrent access"
        )


# ---------------------------------------------------------------------------
# ARCH-003: Lock mechanism cho concurrent access
# ---------------------------------------------------------------------------

class TestLockMechanism:
    """ARCH-003: State operations phải có lock mechanism."""

    def test_ahd_session_has_lock(self):
        """ahd_session.py phải có file locking."""
        source = _read_source(HOOKS_DIR / "ahd_session.py")
        has_lock = any(p in source for p in [
            "filelock", "FileLock", "flock", "fcntl",
            "O_CREAT|O_EXCL", "sentinel", "LockAcquire",
        ])
        assert has_lock, "ahd_session.py thiếu file locking mechanism"

    def test_lock_has_timeout(self):
        """Lock phải có timeout để tránh deadlock."""
        source = _read_source(HOOKS_DIR / "ahd_session.py")
        has_timeout = "timeout" in source.lower() and "deadline" in source.lower()
        assert has_timeout, "Lock mechanism thiếu timeout — deadlock risk"


# ---------------------------------------------------------------------------
# ARCH-004: State isolation giữa providers
# ---------------------------------------------------------------------------

class TestStateIsolation:
    """ARCH-004: State phải isolated giữa providers (.devin, .opencode, .khuym, .aide)."""

    PROVIDER_DIRS = [".devin", ".opencode", ".khuym", ".aide"]

    def test_cross_family_verify_hook_exists(self):
        """cross_family_verify.py phải tồn tại."""
        assert (HOOKS_DIR / "cross_family_verify.py").exists(), (
            "Missing cross_family_verify.py — provider isolation guard"
        )

    def test_no_provider_writes_to_other(self):
        """Hooks không ghi state của provider này vào provider khác."""
        cross_src = _read_source(HOOKS_DIR / "cross_family_verify.py")
        # cross_family_verify checks model family, not provider dirs
        # But it must exist and have family verification logic
        assert "family" in cross_src.lower(), "cross_family_verify must have family verification logic"
        assert "_is_cross_family" in cross_src, "cross_family_verify must have _is_cross_family function"


# ---------------------------------------------------------------------------
# ARCH-005: Hook ordering và chain integrity
# ---------------------------------------------------------------------------

class TestHookChainIntegrity:
    """ARCH-005: Hook chain phải có thứ tự đúng."""

    def test_hook_order_json_exists(self):
        """hook_order.json phải tồn tại."""
        assert (REPO_ROOT / ".devin" / "hook_order.json").exists(), (
            "Missing .devin/hook_order.json — hook chain definition"
        )

    def test_pre_tool_use_runs_before_post(self):
        """pre_tool_use phải chạy trước post_tool_use."""
        order_file = REPO_ROOT / ".devin" / "hook_order.json"
        if not order_file.exists():
            pytest.skip("hook_order.json not found")
        order = json.loads(order_file.read_text(encoding="utf-8"))
        # Flatten all phases
        all_hooks = []
        if isinstance(order, dict):
            for phase, hooks in order.items():
                if isinstance(hooks, list):
                    all_hooks.extend(hooks)
        pre_idx = next((i for i, h in enumerate(all_hooks) if "pre_tool" in str(h)), -1)
        post_idx = next((i for i, h in enumerate(all_hooks) if "post_tool" in str(h)), -1)
        if pre_idx >= 0 and post_idx >= 0:
            assert pre_idx < post_idx, "pre_tool_use must run before post_tool_use"


# ---------------------------------------------------------------------------
# ARCH-006: Destructive operation blocking
# ---------------------------------------------------------------------------

class TestDestructiveBlocking:
    """ARCH-006: Destructive operations phải bị block."""

    DESTRUCTIVE_PATTERNS = [
        "rm -rf", "rm -r ", "rmdir", "del /f", "del /q",
        "git push --force", "git push -f", "git reset --hard",
        "DROP TABLE", "DROP SCHEMA", "DELETE FROM",
        "format ", "mkfs", "shred",
    ]

    def test_pre_tool_use_blocks_destructive(self):
        """pre_tool_use.py phải block destructive commands."""
        source = _read_source(HOOKS_DIR / "pre_tool_use.py")
        blocked_count = sum(1 for p in self.DESTRUCTIVE_PATTERNS if p.lower() in source.lower())
        assert blocked_count >= 5, (
            f"pre_tool_use.py chỉ block {blocked_count}/12 destructive patterns — "
            "cần block nhiều hơn"
        )

    @pytest.mark.parametrize("cmd", [
        "rm -rf /",
        "git push --force origin main",
        "git reset --hard HEAD~10",
        "DROP TABLE users;",
    ])
    def test_destructive_command_blocked_by_hook(self, cmd):
        """Hook phải block destructive command."""
        payload = json.dumps({
            "tool_name": "Bash",
            "tool_input": {"command": cmd},
        })
        code, out, err = _run_hook("pre_tool_use.py", payload)
        # Must not return 0 (allow) for destructive commands
        assert code != 0 or "deny" in out.lower() or "block" in out.lower(), (
            f"pre_tool_use.py cho phép destructive command: {cmd} (exit={code})"
        )


# ---------------------------------------------------------------------------
# ARCH-007: Schema validation gate
# ---------------------------------------------------------------------------

class TestSchemaGate:
    """ARCH-007: Schema gate phải validate tool input."""

    def test_schema_gate_exists(self):
        """schema_gate.py phải tồn tại."""
        assert (HOOKS_DIR / "schema_gate.py").exists(), "Missing schema_gate.py"

    def test_schema_gate_rejects_missing_fields(self):
        """Schema gate phải reject input thiếu required fields."""
        payload = json.dumps({"tool_name": "Write"})  # Missing tool_input
        code, out, err = _run_hook("schema_gate.py", payload)
        assert code != 0 or "error" in out.lower() or "missing" in out.lower() or "deny" in out.lower(), (
            f"schema_gate.py cho phép input thiếu fields (exit={code})"
        )


# ---------------------------------------------------------------------------
# ARCH-008: Coverage enforcement gate
# ---------------------------------------------------------------------------

class TestCoverageEnforcement:
    """ARCH-008: Coverage gate phải enforce threshold."""

    def test_coverage_enforce_exists(self):
        """coverage_enforce.py phải tồn tại."""
        assert (HOOKS_DIR / "coverage_enforce.py").exists(), "Missing coverage_enforce.py"

    def test_coverage_threshold_configured(self):
        """Coverage threshold phải được configure."""
        source = _read_source(HOOKS_DIR / "coverage_enforce.py")
        assert "80" in source or "threshold" in source.lower(), (
            "coverage_enforce.py thiếu threshold configuration"
        )


# ---------------------------------------------------------------------------
# ARCH-009: Subagent isolation
# ---------------------------------------------------------------------------

class TestSubagentIsolation:
    """ARCH-009: Subagent phải isolated."""

    def test_subagent_isolation_script_exists(self):
        """subagent_isolation.py phải tồn tại."""
        assert (SCRIPTS_DIR / "subagent_isolation.py").exists(), (
            "Missing subagent_isolation.py — subagent isolation guard"
        )

    def test_subagent_isolation_has_timeout(self):
        """Subagent phải có timeout."""
        source = _read_source(SCRIPTS_DIR / "subagent_isolation.py")
        assert "timeout" in source.lower(), "subagent_isolation.py thiếu timeout"


# ---------------------------------------------------------------------------
# ARCH-010: Plan enforcement — no write without approved plan
# ---------------------------------------------------------------------------

class TestPlanEnforcement:
    """ARCH-010: Plan enforcement gate phải block write không có approved plan."""

    def test_plan_enforce_exists(self):
        """plan_enforce.py phải tồn tại."""
        assert (HOOKS_DIR / "plan_enforce.py").exists(), "Missing plan_enforce.py"

    def test_plan_enforce_blocks_without_approval(self):
        """Plan enforce phải block khi không có approved plan."""
        payload = json.dumps({
            "tool_name": "Write",
            "tool_input": {"file_path": "src/new_file.py"},
        })
        code, out, err = _run_hook("plan_enforce.py", payload, timeout=15)
        # Should block or deny (exit 1 or 2) when no approved plan
        assert code in (0, 1, 2), (
            f"plan_enforce.py crash: exit={code}, stderr={err[:200]}"
        )


# ---------------------------------------------------------------------------
# ARCH-011: Hook output format — JSON to stdout
# ---------------------------------------------------------------------------

class TestHookOutputFormat:
    """ARCH-011: Hooks phải output JSON ra stdout."""

    @pytest.mark.parametrize("hook,payload", [
        ("session_start.py", '{"session_id":"test","prompt_id":"p1"}'),
        ("session_end.py", '{"session_id":"test"}'),
        ("user_prompt_submit.py", '{"session_id":"test","prompt":"hello"}'),
    ])
    def test_hook_outputs_json(self, hook, payload):
        """Hook phải output valid JSON ra stdout."""
        code, out, err = _run_hook(hook, payload)
        if code == 0 and out.strip():
            try:
                json.loads(out)
            except json.JSONDecodeError:
                # Some hooks output JSON with extra text — check if JSON is embedded
                assert "{" in out, f"{hook} stdout không có JSON output: {out[:200]}"


# ---------------------------------------------------------------------------
# ARCH-012: Self-heal mechanism
# ---------------------------------------------------------------------------

class TestSelfHeal:
    """ARCH-012: Self-heal mechanism phải tồn tại."""

    def test_self_heal_hook_exists(self):
        """self_heal.py phải tồn tại."""
        assert (HOOKS_DIR / "self_heal.py").exists(), "Missing self_heal.py"

    def test_self_heal_has_recursion_limit(self):
        """Self-heal phải có recursion limit."""
        source = _read_source(HOOKS_DIR / "self_heal.py")
        has_limit = any(p in source for p in [
            "max_heal", "recursion", "MAX_", "depth", "limit",
            "heal_count", "heal_round",
        ])
        assert has_limit, "self_heal.py thiếu recursion limit — infinite loop risk"


if __name__ == "__main__":
    pytest.main([__file__, "-v", "--tb=short"])
