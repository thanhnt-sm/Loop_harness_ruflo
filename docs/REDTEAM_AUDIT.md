# Red Team Audit — Agent Harness Deploy (AHD)

> **Audit date**: 2026-07-09
> **Auditor**: Red team pass, brutal findings only
> **Scope**: Skills, agents, hooks, scripts, config, canon, integration, enforcement
> **Method**: Full source review of every .py, .md, .json in `.devin/`
>
> ⚠️ **Resolution status** (2026-08-06): Nhiều findings dưới đây đã được fix trong commit `8bba2c3` và tiếp tục được xử lý theo `.devin/reports/QA_AUDIT_2026_08_06.md`. Các mục C-03, M-04, H-01, H-02 đã được giải quyết. Hãy đối chiếu với source hiện tại trước khi dùng báo cáo này làm baseline.

---

## Executive Summary

The AHD system has **70+ upgrade patches** (U01-U70) layered on top of each other. While individual patches show security awareness, the **composite system has systemic gaps** that undermine its own enforcement model. The core problem is not any single vulnerability — it's that **most enforcement is advisory (non-blocking) and can be bypassed by the agent itself**, since the agent operates with the same filesystem permissions as the hooks.

**Critical finding**: The system's security model assumes a trust boundary between the agent and the hooks, but **no such boundary exists**. The agent can read, modify, or delete any hook file, config file, or state file. All hook-based enforcement is therefore **advisory at best**.

**Score**: 6.5/10 (improved from claimed 8.0 — the self-assessment is inflated)

---

## Critical Findings (C)

### C-01: `os` module not imported in `pre_tool_use.py` — fail-closed mode crashes

**File**: `.devin/hooks/pre_tool_use.py` (lines 279, 338, 346)
**Severity**: Critical

The hook references `os.environ.get("AHD_FAIL_CLOSED", ...)` and `os.environ.get("AHD_FAIL_OPEN", ...)` in the `main()` function and the `__main__` block, but **`import os` is missing** from the file's imports (only `json`, `re`, `sys`, `threading` are imported).

```python
# Line 279:
fail_closed = os.environ.get("AHD_FAIL_CLOSED", "0") == "1"  # NameError!
```

**Impact**: When `main()` encounters a stdin parse error and tries to check `AHD_FAIL_CLOSED`, it throws `NameError`. The `__main__` block's exception handler also references `os.environ`, causing a second `NameError`. This means:
- Fail-closed mode **never works** — it crashes instead of blocking.
- The timeout handler at line 346 also crashes, meaning the thread-based timeout protection is broken.
- On any parse error, the hook either crashes (exit code 1, which the tool framework treats as "allow") or behaves unpredictably.

**This is a live production bug** that silently disables the security gate.

### C-02: Agent can edit hook files to disable all enforcement

**Files**: All hooks in `.devin/hooks/`, all scripts in `.devin/scripts/`
**Severity**: Critical

The `schema_gate.py` defines `SAFE_ZONES` that include `.devin/skills/` and `.devin/agents/` but **not `.devin/hooks/` or `.devin/scripts/`**. However, the safe zone check is **only applied by `schema_gate.py` itself**, which is a PostToolUse hook. The `pre_tool_use.py` hook does NOT check safe zones for write/edit tools — it only checks risk contract (which is non-blocking warning only).

The agent can:
1. Edit `pre_tool_use.py` to remove all `DANGEROUS_PATTERNS`
2. Edit `schema_gate.py` to remove `BLOCKED_ZONES`
3. Edit `config.json` to remove all deny rules
4. Delete `risk_contract.json` entirely

The `risk_contract.json` warns on edits to `pre_tool_use.py` but **only emits a stderr warning** — it does not block. The REDLINES.md states "If in repo, model could edit" hooks, acknowledging this but providing no mitigation.

**Impact**: Complete bypass of all security enforcement. The agent can neuter every gate before performing destructive operations.

### C-03: `schema_gate.py` not registered in `config.json` hooks

**File**: `.devin/config.json`
**Severity**: Critical

The `schema_gate.py` hook implements file path validation, secret scanning, and symbol verification. However, **it is not registered in `config.json`** under any hook event (PreToolUse, PostToolUse, etc.). The config only registers:
- `pre_tool_use.py` (PreToolUse, exec matcher)
- `post_tool_use.py` (PostToolUse, empty matcher)
- `session_start.py`, `session_end.py`, `stop.py`, `user_prompt_submit.py`

Similarly, `coverage_enforce.py`, `drift_detect.py`, `self_heal.py`, and `otel_instrument.py` are **not registered in config.json**. They exist as code but are never invoked by the hook system.

**Impact**: The entire schema gate (path traversal prevention, blocked zone enforcement, secret scanning in output) is **dead code**. It never runs. File path validation and blocked zone checks are not enforced.

### C-04: `dag_executor.py` references undefined type `Any`

**File**: `.devin/scripts/dag_executor.py` (line 355)
**Severity**: Critical

```python
def complete_task(workflow: dict, task_id: str, result: Any) -> dict:
```

The type annotation `Any` is used but **never imported**. The file imports `argparse`, `json`, `sys`, `datetime`, `Path` but not `Any` from `typing`. On Python 3.12+ with `from __future__ import annotations`, this won't crash at runtime (annotations are strings), but on older Python or if annotations are evaluated, it will raise `NameError`.

Additionally, `_read_result_file` (line 409) also uses `Any` in its return type annotation.

**Impact**: Runtime crash on Python versions that evaluate annotations. Even with PEP 563, this is a latent bug.

---

## High Findings (H)

### H-01: `post_tool_use.py` has broken timeout/thread structure at file end

**File**: `.devin/hooks/post_tool_use.py` (lines 718-724)
**Severity**: High

The file's `__main__` block is malformed. The timeout thread setup code appears **inside** the `_u62_memory_confidence` function instead of at module level:

```python
# Line 718 (inside _u62_memory_confidence function body):
    # U15: Internal timeout — post-hook always exits 0, just fail silently if too slow.
    t = threading.Thread(target=main, daemon=True)
    t.start()
    t.join(timeout=HOOK_TIMEOUT_SECONDS)
    if t.is_alive():
        print("[post_tool_use] U15 timeout — exiting (non-blocking)", file=sys.stderr)
    sys.exit(0)
```

There is **no `if __name__ == "__main__":` block** at the end of the file. The thread spawn code is indented inside `_u62_memory_confidence`, meaning it only runs if that function is called — but `_u62_memory_confidence` is called from within `main()`, which is called from the thread, creating an **infinite recursive thread spawn**.

Actually, examining more carefully: the code at lines 718-724 is at the **module level** (no indentation before the comment), but it appears after the function definition without an `if __name__` guard. This means:
- When imported as a module (by other scripts), it will **immediately spawn a thread calling `main()`**.
- When run directly, it spawns a thread calling `main()`, but `main()` calls `_u62_memory_confidence` which is fine — but the thread structure is fragile.

**Impact**: Importing `post_tool_use` as a module triggers side effects. The timeout protection may not work correctly.

### H-02: `plan_dispatch.py` uses `rg` (ripgrep) without fallback — silently fails on Windows

**File**: `.devin/scripts/plan_dispatch.py` (line 114)
**Severity**: High

```python
def _grep_files(pattern: str, path: str = ".") -> list[str]:
    try:
        r = subprocess.run(
            ["rg", "-l", "--no-heading", pattern, path],
            ...
        )
```

The `_grep_files` function only tries `rg` (ripgrep). If `rg` is not installed (common on Windows), it silently returns `[]`, making `_expand_file_hints` return only the original files without dependents. This means **file conflict detection is broken** on systems without ripgrep — all subtasks appear to have no file conflicts, leading to unsafe parallel dispatch.

**Impact**: False "parallel_safe: true" on Windows without ripgrep. Workers can clobber shared files.

### H-03: `coverage_matrix.py` uses `grep` subprocess without Windows fallback

**File**: `.devin/scripts/coverage_matrix.py` (line 252)
**Severity**: High

```python
result = subprocess.run(
    ["grep", "-rE", patterns[0], str(file_path)],
    ...
)
```

The `grep` command is not available on Windows by default. The code has a fallback comment ("grep không có trên Windows") but the regex check before it should handle most cases. Still, the subprocess call will throw `FileNotFoundError` on Windows, caught by the exception handler, but the function returns `False` — meaning **function verification silently fails** on Windows.

### H-04: `approval_gate.py` has no authentication — anyone can approve

**File**: `.devin/scripts/approval_gate.py`
**Severity**: High

The approval gate stores approval state in a JSON file with a `reviewer` field, but **the reviewer name is a free-text CLI argument with no verification**:

```bash
python approval_gate.py plan.md --approve --reviewer "Anyone"
```

There is no authentication, no signature, no token verification. The agent itself can run this command to self-approve its own plan. The `--reviewer` field is purely cosmetic.

**Impact**: The human approval gate is trivially bypassed by the agent running the approval command itself.

### H-05: `state_router.py` conditions use `>= 5` hardcoded findings threshold

**File**: `.devin/scripts/state_router.py` (line 101)
**Severity**: High

```python
def _cond_analyze_to_design(state: dict) -> bool:
    return len(state.get("findings", []) or []) >= 5
```

The ANALYZE → DESIGN transition requires exactly 5+ findings. This is a **magic number** with no configuration. Small tasks may never produce 5 findings, causing an **infinite loop** in ANALYZE. The loop condition (`_cond_analyze_loop`) is `< 5`, so the router will keep returning ANALYZE forever.

Similarly, the quality score threshold is hardcoded at `0.8` with no way to configure it per-task.

**Impact**: State machine gets stuck for small tasks. No escape hatch.

### H-06: `worktree.py` merge uses `--no-ff` but no conflict resolution guidance

**File**: `.devin/scripts/worktree.py` (line 191)
**Severity**: High

```python
rc, out, err = _git("merge", "--no-ff", branch, "-m",
                    f"Merge worktree: {worker_id} ({branch})")
if rc != 0:
    print(f"  [!] Merge failed for {worker_id}: {err}")
    info["status"] = "merge-conflict"
    _save_state(state)
    return 1
```

When merge fails, the worktree is left in a `merge-conflict` state with no automated resolution. The user is told to "resolve conflicts manually" but the repo is left with unmerged changes in the working tree. If another worktree merge is attempted, it will fail because the previous merge is still in progress.

**Impact**: Parallel workflow deadlock — one failed merge blocks all subsequent merges.

### H-07: `loop_memory_sync.py` deletes session_state files for completed sessions

**File**: `.devin/scripts/loop_memory_sync.py` (lines 444-458)
**Severity**: High

```python
for s in sessions:
    if s.get("status") == "completed" and s.get("session_id", "") not in completed_sids:
        ...
        if ss.exists():
            shutil.copy2(ss, archive_dir / f"{sid}.json")
            ss.unlink()  # DELETE original
        ...
        if ss_dir.exists():
            shutil.rmtree(ss_dir, ignore_errors=True)  # DELETE entire directory
```

Completed sessions that are not in the "recent 3" have their session_state files **deleted** (after copying to archive). This means:
- If you complete 4+ sessions, older session state is irretrievably removed from the active directory.
- The `shutil.rmtree` on `session_state/<sid>/` destroys journals, candidate memory, and any other per-session data.
- If the archive copy fails silently (exception caught), **data is lost**.

**Impact**: Data loss for completed sessions beyond the most recent 3.

### H-08: `event_bus.py` allows arbitrary topic creation — no access control

**File**: `.devin/scripts/event_bus.py` (line 192)
**Severity**: High

```python
if not _validate_topic(topic):
    print(f"[event_bus] Cảnh báo: topic '{topic}' không trong danh sách định nghĩa, "
          f"tạo topic mới.", file=sys.stderr)
```

Undefined topics are allowed with only a warning. Any agent can publish to any topic name. There is no per-agent authorization, no topic ownership, and no message authentication. A malicious or confused agent can inject messages into any topic.

**Impact**: Message spoofing, event bus poisoning.

---

## Medium Findings (M)

### M-01: `config.json` hardcodes absolute Windows paths

**File**: `.devin/config.json` (line 153)
**Severity**: Medium

```json
"command": "D:\\100.Software\\Github\\Loop_harness_new\\Loop_harness_ruflo\\.tools\\node\\node.exe D:\\100.Software\\Github\\Loop_harness_new\\Loop_harness_ruflo\\HLK\\wrappers\\hlk-hook-launcher.mjs"
```

The HLK hook launcher uses **hardcoded absolute paths** specific to one developer's machine. This breaks on any other machine, CI/CD, or even a different checkout path. The REDLINES.md explicitly says "No hardcoded paths — use registry + env expansion" but the config violates this.

### M-02: `config.json` hooks reference `bash` scripts with Windows-style backslash paths

**File**: `.devin/config.json` (lines 86, 118, 128, etc.)
**Severity**: Medium

```json
"command": "bash $APPDATA/nvm/v18.20.0/node_modules/aide-memory\\scripts\\hooks\\session-start-clear.sh"
```

These commands mix forward slashes (`$APPDATA/nvm/...`) with backslashes (`\\scripts\\hooks\\...`), which is invalid path syntax on both Windows and Unix. The `$APPDATA` env var is Windows-specific. These hooks will fail on any non-Windows system or if the aide-memory package is installed at a different path.

### M-03: `drift_detect.py` baseline requires 50 samples — never triggers in short sessions

**File**: `.devin/hooks/drift_detect.py` (line 47)
**Severity**: Medium

```python
BASELINE_MIN_SAMPLES = 50
```

The drift detector needs 50 tool calls before it can even start checking for drift. Most sessions are shorter than 50 tool calls. The drift detector is therefore **dead code for the majority of sessions**. Additionally, the baseline is built from the first 50 calls of the current session, not from historical data — so it has no real "normal behavior" reference.

### M-04: `self_heal.py` is not registered in config.json — never runs

**File**: `.devin/hooks/self_heal.py`
**Severity**: Medium

Like `schema_gate.py`, `coverage_enforce.py`, `drift_detect.py`, and `otel_instrument.py`, the self-heal hook is not registered in `config.json`. It exists as code but is never invoked. The entire 4-stage self-healing loop (Monitor → Detect → Diagnose → Recover) is **non-functional**.

### M-05: `spc_monitor.py` uses `statistics.stdev` which crashes on n=1

**File**: `.devin/scripts/spc_monitor.py` (line 102)
**Severity**: Medium

```python
def _mean_std(values: list) -> tuple:
    ...
    if len(values) < 2:
        return mean, 0.0
    std = statistics.stdev(values)
```

The guard checks `len(values) < 2` but `statistics.stdev` requires at least 2 data points. This is correct, but `statistics.fmean` (line 99) can also fail on empty lists — the guard `if not values` handles this. However, the SPC monitor is not integrated into any hook or script — it's a standalone CLI tool that nobody calls.

### M-06: `blackboard.py` has no concurrency control — race conditions on region files

**File**: `.devin/scripts/blackboard.py`
**Severity**: Medium

The blackboard reads and writes region JSON files without any file locking. Multiple agents writing to the same region concurrently will **lose updates**. The `_save_region` function does a direct `write_text` without atomic rename or lock:

```python
def _save_region(region: str, data: dict) -> bool:
    f = _region_file(region)
    try:
        f.write_text(json.dumps(data, ...), encoding="utf-8")
```

Compare with `ahd_session.py` which uses `_locked_json_write` with atomic temp+rename. The blackboard doesn't use any of these patterns.

### M-07: `checkpoint.py` saves timestamps with `datetime.now()` (no timezone)

**File**: `.devin/scripts/checkpoint.py` (lines 149, 159, 269)
**Severity**: Medium

```python
"timestamp": datetime.now().isoformat(),
```

All timestamps use `datetime.now()` without timezone info, while the rest of the system uses `datetime.now(timezone.utc)`. This creates **timezone inconsistency** — checkpoint timestamps are in local time while everything else is UTC. Comparing timestamps across systems will produce wrong results.

### M-08: `dag_compile.py` orphan task detection flags legitimate root tasks

**File**: `.devin/scripts/dag_compile.py` (lines 184-191)
**Severity**: Medium

```python
orphans = ids - has_deps - is_depended_on
if orphans and len(nodes) > 1:
    errors.append(f"orphan task (không liên kết): {sorted(orphans)}")
```

A task with no dependencies that nothing depends on is flagged as orphan. But this is legitimate for **standalone tasks** or **single-task workflows**. The `len(nodes) > 1` guard helps but doesn't handle the case of multiple independent root tasks (a valid DAG pattern).

### M-09: `plan_quality_check.py` file path regex is too greedy

**File**: `.devin/scripts/plan_quality_check.py` (line 176)
**Severity**: Medium

```python
file_m = re.search(r"[\w/\\]+\.\w{1,6}", raw)
```

This regex matches any word-like string with a dot and 1-6 char extension. It will match version numbers (`v1.0`), IP addresses (`192.168.001`), and other non-file-path strings. This can cause false positives in task parsing, leading to incorrect coverage matrix entries.

### M-10: `pre_tool_use.py` dangerous patterns miss `rm -rf` without space variations

**File**: `.devin/hooks/pre_tool_use.py` (line 131)
**Severity**: Medium

```python
(r"\brm\s+(-[a-z]*r[a-z]*f|--recursive\s+--force)\s+(/|/\*|~|\$HOME|\.\.|\*|\.)", "rm -rf with broad target"),
```

The pattern requires `rm` followed by flags containing both `r` and `f`. But it misses:
- `rm --recursive --force` (with `--force` before `--recursive`)
- `rm -fr` (f before r — the pattern `-[a-z]*r[a-z]*f` requires r before f)
- `find . -delete` (alternative deletion command)
- `rsync --delete` (alternative deletion)

### M-11: `risk_contract.json` check is non-blocking — only warns

**File**: `.devin/hooks/pre_tool_use.py` (line 231-271)
**Severity**: Medium

The `_check_risk_contract` function only prints a warning to stderr. It never blocks the tool call (`sys.exit(2)`). An agent modifying `config.json` to remove all deny entries will get a warning but the edit proceeds. The risk contract is **advisory only**.

### M-12: `session_start.py` sets `boot_complete=false` but no hook enforces it

**File**: `.devin/hooks/session_start.py`
**Severity**: Medium

The session start hook sets `boot_complete: False` in session_state. The docstring says "Work tools will be blocked until boot_complete=true." But **no PreToolUse hook checks `boot_complete`**. The `pre_tool_use.py` hook only checks context_oversized and dangerous commands — it never reads `boot_complete`. The `user_prompt_submit.py` hook only injects a context reminder. The BOOT enforcement is **purely advisory**.

---

## Low Findings (L)

### L-01: `dag_executor.py` `_repo_root()` assumes fixed directory depth

**File**: `.devin/scripts/dag_executor.py` (line 69)
**Severity**: Low

```python
def _repo_root() -> Path:
    here = Path(__file__).resolve().parent  # .../.devin/scripts
    return here.parent.parent               # repo root
```

This hardcodes the assumption that the script is always at `<repo>/.devin/scripts/`. If deployed to a different config root (`.claude/`, `.codex/`), it returns the wrong path. Compare with `ahd_session.get_repo_root()` which walks up to find `.git` or `.agents`.

### L-02: `event_bus.py` and `blackboard.py` also hardcode `_repo_root()`

**Files**: `.devin/scripts/event_bus.py` (line 53), `.devin/scripts/blackboard.py` (line 51)
**Severity**: Low

Same pattern as L-01. These scripts assume `here.parent.parent` is the repo root, breaking cross-tool deployment.

### L-03: `spc_monitor.py` comments are in Vietnamese without diacritics

**File**: `.devin/scripts/spc_monitor.py`
**Severity**: Low

The entire file uses Vietnamese without diacritics (e.g., "chi so" instead of "chỉ số"), inconsistent with the project's convention of Vietnamese with diacritics. This is a style inconsistency, not a functional bug.

### L-04: `checkpoint.py` and `spc_monitor.py` don't use `ahd_session` helpers

**Files**: `.devin/scripts/checkpoint.py`, `.devin/scripts/spc_monitor.py`
**Severity**: Low

These scripts define their own `_repo_root()`, `_load_json()`, `_save_json()` functions instead of using `ahd_session`. This means they don't benefit from the inter-process locking, per-session locks, or config root resolution that `ahd_session` provides.

### L-05: `plan_dispatch.py` worktree assignment is sequential, not conflict-aware

**File**: `.devin/scripts/plan_dispatch.py` (line 294)
**Severity**: Low

```python
def _assign_worktrees(subtasks, allocation, session_id=""):
    wt_idx = 0
    for st in subtasks:
        wt_name = f"builder-{chr(ord('a') + wt_idx)}"
```

Worktrees are assigned sequentially (builder-a, builder-b, ...). If there are more than 26 subtasks, `chr(ord('a') + 26)` produces `{` which is an invalid worktree name. Also, conflicting subtasks (that must be serialized) get different worktrees, when they should share one to avoid parallel execution.

### L-06: `coverage_enforce.py` has dead code on line 48

**File**: `.devin/hooks/coverage_enforce.py` (line 48)
**Severity**: Low

```python
PLAN_STATE_DIR = ".devin" / "plan_state" if False else None  # placeholder, dùng Path runtime
```

This line is confusing dead code. `".devin" / "plan_state"` would fail anyway (str / str is invalid in Python), but the `if False` makes it evaluate to `None`. It should be removed.

### L-07: `self_heal.py` `_load_json` type check is broken

**File**: `.devin/hooks/self_heal.py` (line 91)
**Severity**: Low

```python
if isinstance(data, type(default)) if default is not None else True:
```

This expression is confusing and potentially wrong. If `default` is `{"entries": []}` (a dict), `type(default)` is `dict`, and it checks `isinstance(data, dict)`. But if `default` is `{}` (empty dict) and the file contains a list, it returns the default `{}` instead of the actual data. The logic should just check `isinstance(data, dict)` when a dict is expected.

### L-08: `plan_quality_check.py` D3 (DAG acyclic) passes when no Mermaid graph exists

**File**: `.devin/scripts/plan_quality_check.py` (line 320)
**Severity**: Low

```python
if not edges:
    return {"id": "D3", "name": "Dependency Correctness", "pass": True,
            "detail": "Không có Mermaid graph hoặc không có edge (bỏ qua)"}
```

If the plan has no Mermaid graph, D3 automatically passes. A plan with no dependency information gets a free pass on dependency correctness, which defeats the purpose of the check.

### L-09: `post_tool_use.py` `_redact` function can crash on certain inputs

**File**: `.devin/hooks/post_tool_use.py` (line 57)
**Severity**: Low

```python
text = pat.sub(lambda m: m.group(0)[:m.group(0).find("=") + 1] + "***" if "=" in m.group(0) else "***", text)
```

If `m.group(0).find("=")` returns `-1` (no `=` found), then `m.group(0)[:-1+1]` = `m.group(0)[:0]` = `""`, which is fine. But the `"=" in m.group(0)` check should prevent this. Still, the logic is convoluted and hard to verify.

### L-10: `config.json` deny list missing `Remove-Item` without `-Recurse`

**File**: `.devin/config.json` (line 48-69)
**Severity**: Low

The deny list includes `Exec(rm -rf:*)` but not `Exec(Remove-Item:*)` without the `-Recurse` flag. The tool_registry.json lists `Remove-Item -Recurse -Force` as L4, but `Remove-Item` alone (which can still delete files) is not denied. An agent could use `Remove-Item file.txt` to delete individual files without triggering the deny rule.

---

## Bypass Analysis

### Bypass 1: Hook file modification (C-02)

**Path**: Agent edits `pre_tool_use.py` → removes `DANGEROUS_PATTERNS` → runs `rm -rf /`
**Blocked by**: Nothing. Risk contract only warns.
**Mitigation needed**: OS-level file permissions on hook files, or external CI gate.

### Bypass 2: Self-approval (H-04)

**Path**: Agent runs `python approval_gate.py plan.md --approve --reviewer "human"`
**Blocked by**: Nothing. No authentication.
**Mitigation needed**: External approval mechanism (e.g., GitHub PR review, signed tokens).

### Bypass 3: Schema gate bypass (C-03)

**Path**: Agent writes to `.env` or `HLK/` → schema_gate never runs → write succeeds
**Blocked by**: Nothing. Schema gate is not registered.
**Mitigation needed**: Register schema_gate in config.json PostToolUse hooks.

### Bypass 4: BOOT protocol skip (M-12)

**Path**: Agent ignores BOOT protocol → starts working immediately → no hook blocks work tools
**Blocked by**: Nothing. `boot_complete` is never checked by any enforcement hook.
**Mitigation needed**: Add `boot_complete` check to `pre_tool_use.py`.

### Bypass 5: Command obfuscation via environment variables

**Path**: Agent runs `cmd=$VAR; $cmd` where `$VAR` expands to `rm -rf /`
**Blocked by**: Partially. `normalize_command` replaces `$VAR` with `EXPANDED_VAR`, but the actual command string still contains `EXPANDED_VAR` not `rm -rf /`, so the pattern won't match.
**Impact**: The normalization prevents matching the dangerous pattern because the expanded form is replaced with a placeholder, not the actual value.

### Bypass 6: Worktree branch name collision

**Path**: Two sessions create worktrees with the same `worker_id` → second create fails
**Blocked by**: `cmd_create` checks `if target.exists()`. But if the first worktree was created by a different session, the second session gets a confusing error with no context about the conflicting session.

### Bypass 7: Event bus message injection

**Path**: Agent publishes false "verify.gates" message with `all_pass: true`
**Blocked by**: Nothing. No message authentication or publisher verification.
**Impact**: State router transitions to REPORT based on fabricated verification results.

---

## Missing Enforcement

### 1. No hook enforces `boot_complete` before work tools
**Status**: `session_start.py` sets the flag, but no PreToolUse hook checks it.

### 2. No hook enforces `fable_judge_required` before task completion
**Status**: `post_tool_use.py` sets the flag, but no Stop hook checks it before allowing the session to end.

### 3. No hook enforces `budget_exceeded` or `time_limit`
**Status**: `post_tool_use.py` prints warnings but never blocks. The agent can ignore budget limits.

### 4. No hook enforces coverage gaps before session end
**Status**: `coverage_enforce.py` is not registered. Even if it were, it's advisory (exit 0 always).

### 5. No hook enforces plan approval before execution
**Status**: `approval_gate.py` exists but is a standalone script. No hook checks approval status before allowing Write/Edit tools.

### 6. No hook enforces `parallel_safe` before parallel dispatch
**Status**: `plan_dispatch.py` outputs `parallel_safe` but nothing enforces it. The Commander can ignore the flag.

### 7. No hook enforces maker ≠ checker
**Status**: Canon states "producer never verifies" but no hook checks whether the verifying agent is different from the producing agent.

### 8. No hook enforces red line #1 (backup before overwrite)
**Status**: REDLINES.md says ".bak existing config before writing" but no hook creates backups or checks for their existence before Write/Edit.

### 9. No hook enforces red line #5 (no skipping verification)
**Status**: REDLINES.md says "every deploy/change ends with verify or read-back" but no hook checks for verification after edits.

### 10. No hook enforces red line #16 (no explanatory comments)
**Status**: `post_tool_use.py` U57 checks for slop patterns but doesn't block. Comment discipline is advisory.

---

## Integration Issues

### I-01: `dag_compile.py` output format incompatible with `dag_executor.py` input

**File**: `.devin/scripts/dag_compile.py` vs `.devin/scripts/dag_executor.py`

`dag_compile.py` produces:
```json
{"nodes": [{"task_id": "...", "deps": [...]}], "edges": [{"from": "...", "to": "..."}]}
```

`dag_executor.py` expects:
```json
{"workflow_id": "...", "tasks": [{"id": "...", "dependencies": [...], "goal": "...", "agent": "..."}]}
```

The field names don't match: `nodes` vs `tasks`, `task_id` vs `id`, `deps` vs `dependencies`. The executor's `_load_workflow` checks for `"tasks"` key which the compiler doesn't produce. **These two scripts cannot work together** without a manual format conversion.

### I-02: `state_router.py` not connected to any hook or script

The state router defines a complete state machine (ANALYZE → DESIGN → PLAN → ... → DONE) but is never invoked by any hook or script. It's a standalone CLI that must be called manually. The `dag_executor.py` has its own state management that doesn't use the router.

### I-03: `checkpoint.py` expects `nodes`/`edges` from `dag_compile.py` but uses different field names

`checkpoint.py` reads `workflow.get("nodes", [])` and `n["task_id"]`, which matches `dag_compile.py` output. But it also reads `n.get("deps", [])` which matches. However, `dag_executor.py` uses `tasks` with `dependencies`. So `checkpoint.py` works with `dag_compile.py` but not with `dag_executor.py`.

### I-04: Multiple `_repo_root()` implementations with different behavior

- `ahd_session.get_repo_root()`: git rev-parse → walk up for markers → cwd
- `dag_executor.py`: `here.parent.parent` (hardcoded depth)
- `event_bus.py`: `here.parent.parent` (hardcoded depth)
- `blackboard.py`: `here.parent.parent` (hardcoded depth)
- `checkpoint.py`: walk up for `.devin` directory
- `spc_monitor.py`: walk up for `.devin` directory
- `drift_detect.py`: walk up for `.devin` directory
- `self_heal.py`: walk up for `.devin` directory

Scripts that don't use `ahd_session` have inconsistent root resolution. In deployed configs (`.claude/`, `.codex/`), the hardcoded `here.parent.parent` will be wrong.

### I-05: `plan_dispatch.py` imports from `plan_dispatch` in `pre_task_audit.py` — circular risk

**File**: `.devin/scripts/pre_task_audit.py` (line 27)

```python
from plan_dispatch import _expand_file_hints, _get_active_sessions
```

`pre_task_audit.py` imports from `plan_dispatch.py`, which imports `ahd_session` from `hooks/`. If `plan_dispatch.py` is not on the path, the import fails and `pre_task_audit.py` falls back to a no-op (exception caught). But the import adds `plan_dispatch.py`'s module-level code (including `ROOT = _get_repo_root()`) to the import chain, which can have side effects.

### I-06: `cost_tracker` module referenced but not found

**File**: `.devin/hooks/post_tool_use.py` (line 315)

```python
from cost_tracker import _estimate_cost, check_cost_cap
```

The `cost_tracker` module is imported but **does not exist** in `.devin/scripts/` or `.devin/hooks/`. The import is wrapped in a try/except, so it silently fails, meaning **cost tracking is non-functional**. The `cumulative_cost` and `cost_cap` fields in session_state are never updated.

---

## Enforcement Audit — Can Phases/Gates Be Skipped?

| Phase/Gate | Enforcement Mechanism | Can Skip? | How? |
|---|---|---|---|
| BOOT protocol | `session_start.py` sets `boot_complete=false` | **Yes** | No hook checks `boot_complete` before work tools |
| Plan quality check (10-D) | `plan_quality_check.py` standalone CLI | **Yes** | Not invoked by any hook; agent can skip |
| Approval gate | `approval_gate.py` standalone CLI | **Yes** | No hook checks approval before Write/Edit; agent can self-approve |
| DAG compile | `dag_compile.py` standalone CLI | **Yes** | Not invoked by any hook |
| DAG execute | `dag_executor.py` standalone CLI | **Yes** | Not invoked by any hook |
| Coverage enforcement | `coverage_enforce.py` not registered | **Yes** | Hook never runs |
| Drift detection | `drift_detect.py` not registered | **Yes** | Hook never runs |
| Self-heal | `self_heal.py` not registered | **Yes** | Hook never runs |
| Schema gate | `schema_gate.py` not registered | **Yes** | Hook never runs |
| OTel instrument | `otel_instrument.py` not registered | **Yes** | Hook never runs |
| Risk contract | `pre_tool_use.py` warns only | **Yes** | Warning is non-blocking |
| Dangerous commands | `pre_tool_use.py` blocks (exit 2) | **No** (if hook works) | But C-01 bug may crash the hook |
| Context oversized | `pre_tool_use.py` blocks at counter ≥ 4 | **Partial** | Agent can clear the flag manually |
| Secret in output | `schema_gate.py` (not registered) | **Yes** | Hook never runs |
| Path traversal | `schema_gate.py` (not registered) | **Yes** | Hook never runs |
| Safe zone enforcement | `schema_gate.py` (not registered) | **Yes** | Hook never runs |
| Fable-judge verification | `post_tool_use.py` sets flag | **Yes** | No hook blocks completion if flag is set |
| Budget cap | `post_tool_use.py` warns only | **Yes** | Warning is non-blocking |
| Time limit | `post_tool_use.py` warns only | **Yes** | Warning is non-blocking |
| Backup before overwrite | None | **Yes** | No enforcement at all |
| Maker ≠ checker | None | **Yes** | No enforcement at all |
| Comment discipline | `post_tool_use.py` U57 warns | **Yes** | Warning is non-blocking |

**Summary**: Of 21 identified gates/enforcement points, **18 can be skipped** by the agent. Only the dangerous command gate in `pre_tool_use.py` is actually blocking — and even that is compromised by the missing `os` import bug (C-01).

---

## Prioritized Recommendations

### P0 — Fix immediately (production bugs)

1. **Fix C-01**: Add `import os` to `pre_tool_use.py`. This is a one-line fix that restores fail-closed mode.
2. **Fix C-03**: Register `schema_gate.py`, `coverage_enforce.py`, `drift_detect.py`, `self_heal.py`, and `otel_instrument.py` in `config.json` under appropriate hook events.
3. **Fix C-04**: Add `from typing import Any` to `dag_executor.py`.
4. **Fix H-01**: Restructure `post_tool_use.py` `__main__` block to be at module level with proper `if __name__ == "__main__":` guard.

### P1 — Fix soon (security gaps)

5. **Fix C-02**: Make hook files read-only (OS-level) or move enforcement to an external CI gate that the agent cannot bypass.
6. **Fix H-04**: Add authentication to `approval_gate.py` — require a signed token or external approval mechanism.
7. **Fix H-02**: Add `grep`/`findstr` fallback in `plan_dispatch.py` when `rg` is unavailable.
8. **Fix H-07**: Don't delete session_state files — move to archive only, or use a configurable retention policy.
9. **Fix M-12**: Add `boot_complete` check to `pre_tool_use.py` to block work tools until BOOT is complete.
10. **Fix I-01**: Align `dag_compile.py` output format with `dag_executor.py` input format.
11. **Fix I-06**: Create `cost_tracker.py` or remove the import from `post_tool_use.py`.

### P2 — Improve (reliability)

12. **Fix M-01**: Replace hardcoded paths in `config.json` with env var expansion or relative paths.
13. **Fix M-06**: Add file locking to `blackboard.py` using `ahd_session._locked_json_write`.
14. **Fix M-07**: Use `datetime.now(timezone.utc)` consistently in `checkpoint.py`.
15. **Fix L-01/L-02**: Replace hardcoded `_repo_root()` with `ahd_session.get_repo_root()` in all scripts.
16. **Fix H-05**: Make the findings threshold configurable in `state_router.py` or add an escape hatch for small tasks.
17. **Fix H-06**: Add merge conflict detection and automatic `--abort` with retry guidance in `worktree.py`.

### P3 — Polish (consistency)

18. **Fix L-03**: Add diacritics to `spc_monitor.py` comments.
19. **Fix L-06**: Remove dead code in `coverage_enforce.py` line 48.
20. **Fix L-07**: Simplify `self_heal.py` `_load_json` type checking.
21. **Fix L-08**: Make D3 fail (not pass) when no Mermaid graph is present, or mark as "N/A".
22. **Fix M-10**: Expand dangerous command patterns in `pre_tool_use.py` to cover `rm -fr`, `find -delete`, `rsync --delete`.
23. **Fix L-10**: Add `Remove-Item` to deny list in `config.json`.

---

## Appendix: Files Reviewed

### Skills (25)
`plan`, `adversarial-consensus`, `lightning`, `glm`, `kimi`, `auditor`, `claim-grader`, `comment_checker`, `context-compactor`, `fable-judge`, `gap-scan`, `graph-verify`, `harness-sensor`, `init_deep`, `loop-memory`, `memory-audit`, `slop-detector`, `systematic_debugging`, `tdd`, `user-preference`, `using-skills`, `aide-memory`, `hlk-git-tools`, `hlk-integrity-check`, `nuwa-skill`

### Agents (5)
`COMMANDER.md`, `lightning-executor/AGENT.md`, `glm-executor/AGENT.md`, `kimi-executor/AGENT.md`

### Hooks (12)
`pre_tool_use.py`, `post_tool_use.py`, `stop.py`, `session_start.py`, `session_end.py`, `user_prompt_submit.py`, `schema_gate.py`, `coverage_enforce.py`, `drift_detect.py`, `self_heal.py`, `otel_instrument.py`, `ahd_session.py`

### Scripts (17)
`approval_gate.py`, `plan_quality_check.py`, `dag_compile.py`, `dag_executor.py`, `plan_dispatch.py`, `worktree.py`, `loop_memory_sync.py`, `pre_task_audit.py`, `session_manager.py`, `coverage_matrix.py`, `state_router.py`, `event_bus.py`, `blackboard.py`, `spc_monitor.py`, `checkpoint.py`, `memory_audit.py`

### Config (4)
`config.json`, `mcp_config.json`, `risk_contract.json`, `tool_registry.json`

### Canon (3)
`BOOT_PROTOCOL.md`, `REDLINES.md`, `CORE_CANON.md`
