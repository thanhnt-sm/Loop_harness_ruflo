#!/usr/bin/env python3
"""Pre-tool-use hook — guards against dangerous operations + enforces context compaction.

Entry point mỏng (plan refactor-long-files, section 2.13). Toàn bộ logic đã tách
vào 8 module: pre_tool_encoding, pre_tool_secrets, pre_tool_callgraph,
pre_tool_sandbox, pre_tool_dangerous, pre_tool_gates, pre_tool_cli.

File này CHỈ re-export API để giữ nguyên giao diện `pre_tool_use.*` cho các test
và harness. Chạy: `python pre_tool_use.py` -> gọi main() (threading timeout wrapper).

Exit codes:
  0 = allow the tool call
  2 = block the tool call (stderr shown to user)
  other non-zero = error (tool decides; usually allow)
"""
import ahd_session  # giữ attribute pre_tool_use.ahd_session (test monkeypatch)
import sys

# Destructive patterns blocked by this hook (also defined in pre_tool_dangerous.py)
# Listed here for test coverage and as a secondary defense layer.
DESTRUCTIVE_BLOCKLIST = [
    "rm -rf", "rm -r ", "rmdir", "del /f", "del /q",
    "git push --force", "git push -f", "git reset --hard",
    "DROP TABLE", "DROP SCHEMA", "DELETE FROM",
    "format ", "mkfs", "shred",
]

# --- Context-oversized gate config (source of truth; gates đọc động từ đây) ---
OVERSIZED_NOTE_THRESHOLD = 0   # counter >= this -> note
OVERSIZED_WARN_THRESHOLD = 2   # counter >= this -> warning
OVERSIZED_BLOCK_THRESHOLD = 4  # counter >= this -> block non-compaction tools

# Tools that are always allowed even during compaction block (needed to actually compact)
COMPACTION_SAFE_TOOLS = frozenset({
    "read", "Read", "grep", "Grep", "glob", "Glob", "find_file_by_name",
    "write", "Write", "edit", "Edit",
    "notebook_read", "notebook_edit",
    "todo_write", "TodoWrite",
    "skill", "Skill",
})

# --- Re-export toàn bộ API từ các submodule ---
from pre_tool_encoding import (
    detect_encoding_bypass,
    analyze_shell_structure,
    normalize_command,
    _decode_ip_encoding,
)
from pre_tool_secrets import (
    _hlk_repo_root,
    _hlk_secret_patterns,
    detect_hlk_secret,
    check_ssrf,
    _extract_urls,
    _log_ssrf_block,
    _ssrf_allowlist,
    _pin_and_verify_url,
    _ssrf_pin_ttl,
    _ssrf_pins_path,
    _load_ssrf_pins,
    _save_ssrf_pins,
    _resolve_host,
    URL_RE,
    DEFAULT_SSRF_ALLOWLIST,
)
from pre_tool_callgraph import (
    _load_tool_registry,
    _get_tool_tier,
    _get_tool_metadata,
    _get_call_graph_config,
    _get_session_call_stack,
    _update_session_call_stack,
    _get_current_call_depth,
    _enforce_call_depth,
    _enforce_allowed_chains,
    _log_call_violation,
    _check_call_graph_gate,
)
from pre_tool_sandbox import (
    _seatbelt_available,
    _get_seatbelt_profile_path,
    _run_hook_sandboxed,
    _check_sandbox_gate,
)
from pre_tool_dangerous import (
    _DANGEROUS_PATTERNS_RAW,
    DANGEROUS_PATTERNS,
    WARN_PATTERNS,
    _check_bash_workspace_layout_gate,
)
from pre_tool_gates import (
    _gate_error,
    _check_context_oversized_gate,
    _check_cost_cap_gate,
    _check_ssrf_gate,
    _check_encoding_bypass_gate,
    _check_reflection_gate,
    _check_risk_contract,
    _check_workspace_layout_gate,
    _WRITE_TOOLS,
    _check_reflection,
    validate_workspace_path,
    is_allowed_root_file,
    is_junk_path,
    ALLOWED_ROOT_FILES,
    ALLOWED_ROOT_PATTERNS,
    check_cost_cap,
)
from pre_tool_cli import main, HOOK_TIMEOUT_SECONDS


if __name__ == "__main__":
    try:
        main()
    except Exception:
        # Fail-closed: block on unexpected error
        sys.exit(2)
