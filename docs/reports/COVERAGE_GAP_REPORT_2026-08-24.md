# Coverage Gap Analysis Report

**Date:** 2026-08-24
**Scope:** Analysis of 9 pre-existing test files with coverage failures
**Status:** All tests PASS, but coverage below `fail-under=80` threshold

---

## Executive Summary

| Test File | Tests Collected | Tests Passed | Tests Failed | Tests Error | Coverage % | Threshold |
|-----------|----------------|--------------|--------------|-------------|------------|-----------|
| test_cost_guard.py | 5 | 5 | 0 | 0 | 6% | 80% |
| test_apply_ahd_patch_verify.py | 2 | 2 | 0 | 0 | 1% | 80% |
| test_coverage_boost3.py | 49 | 49 | 0 | 0 | 10% | 80% |
| test_coverage_boost5.py | 130 | 130 | 0 | 0 | 15% | 80% |
| test_targeted_coverage_boost.py | 333 | 333 | 0 | 0 | ~15% | 80% |
| test_cve_remediation_phase2.py | 51 | 51 | 0 | 0 | 10% | 80% |
| test_harness_architecture_supreme.py | 38 | 38 | 0 | 0 | ~10% | 80% |
| test_import_smoke.py | 2 | 2 | 0 | 0 | 10% | 80% |
| test_opencode_harness.py | 31 | 30 | 0 | 1 (skipped) | 1% | 80% |
| test_targeted_coverage_low_modules.py | 175 | 175 | 0 | 0 | ~15% | 80% |

**Total:** 816 tests collected, 815 passed, 0 failed, 1 skipped

> **Key Finding:** The user's description of "14 failed + 36 errors" does not match current state — all tests PASS. The actual issue is **systemic low coverage** across `.devin/scripts/` and `.devin/hooks/` modules because tests only exercise a small subset of the codebase.

---

## Root Cause Analysis

### 1. Missing Module Coverage (0% Coverage)

The following modules in `.devin/scripts/` and `.devin/hooks/` have **0% coverage** because no test imports or exercises them:

| Module | Path | Lines | Status |
|--------|------|-------|--------|
| abc_checklist.py | `.devin/scripts/abc_checklist.py` | 69 | 0% |
| adaptive_compress.py | `.devin/scripts/adaptive_compress.py` | 123 | 0% |
| apply_ahd_apply.py | `.devin/scripts/apply_ahd_apply.py` | 151 | 13% |
| apply_ahd_cli.py | `.devin/scripts/apply_ahd_cli.py` | 158 | 15% |
| apply_ahd_commit.py | `.devin/scripts/apply_ahd_commit.py` | 63 | 21% |
| apply_ahd_map.py | `.devin/scripts/apply_ahd_map.py` | 63 | 27% |
| apply_ahd_merge.py | `.devin/scripts/apply_ahd_merge.py` | 32 | 16% |
| apply_ahd_normalize.py | `.devin/scripts/apply_ahd_normalize.py` | 71 | 17% |
| apply_ahd_patch.py | `.devin/scripts/apply_ahd_patch.py` | 11 | 91% |
| apply_ahd_verify.py | `.devin/scripts/apply_ahd_verify.py` | 47 | 70% |
| approval_gate.py | `.devin/scripts/approval_gate.py` | 39 | 0% |
| approval_gate_archive.py | `.devin/scripts/approval_gate_archive.py` | 43 | 0% |
| approval_gate_args.py | `.devin/scripts/approval_gate_args.py` | 55 | 0% |
| approval_gate_audit.py | `.devin/scripts/approval_gate_audit.py` | 16 | 0% |
| approval_gate_commands.py | `.devin/scripts/approval_gate_commands.py` | 48 | 0% |
| approval_gate_constants.py | `.devin/scripts/approval_gate_constants.py` | 27 | 0% |
| approval_gate_crypto.py | `.devin/scripts/approval_gate_crypto.py` | 57 | 0% |
| approval_gate_interactive.py | `.devin/scripts/approval_gate_interactive.py` | 77 | 0% |
| approval_gate_state.py | `.devin/scripts/approval_gate_state.py` | 58 | 0% |
| approval_gate_summary.py | `.devin/scripts/approval_gate_summary.py` | 49 | 0% |
| artifact_registry.py | `.devin/scripts/artifact_registry.py` | 212 | 0% |
| auto_model_router.py | `.devin/scripts/auto_model_router.py` | 93 | 0% |
| baseline_validator.py | `.devin/scripts/baseline_validator.py` | 79 | 0% |
| benchjack_redteam.py | `.devin/scripts/benchjack_redteam.py` | 22 | 0% |
| best_of_n.py | `.devin/scripts/best_of_n.py` | 111 | 0% |
| blackboard.py | `.devin/scripts/blackboard.py` | 58 | 0% |
| blackboard_cli.py | `.devin/scripts/blackboard_cli.py` | 54 | 0% |
| blackboard_constants.py | `.devin/scripts/blackboard_constants.py` | 17 | 0% |
| blackboard_core.py | `.devin/scripts/blackboard_core.py` | 174 | 0% |
| build_workflow.py | `.devin/scripts/build_workflow.py` | 43 | 0% |
| check_updates.py | `.devin/scripts/check_updates.py` | 121 | 0% |
| checkpoint.py | `.devin/scripts/checkpoint.py` | 14 | 0% |
| checkpoint_cli.py | `.devin/scripts/checkpoint_cli.py` | 162 | 10% |
| checkpoint_core.py | `.devin/scripts/checkpoint_core.py` | 93 | 62% |
| checkpoint_redact.py | `.devin/scripts/checkpoint_redact.py` | 54 | 69% |
| checkpoint_sanitize.py | `.devin/scripts/checkpoint_sanitize.py` | 36 | 78% |
| checkpoint_workflow.py | `.devin/scripts/checkpoint_workflow.py` | 38 | 16% |
| cognitive_scaffold_memory.py | `.devin/scripts/cognitive_scaffold_memory.py` | 130 | 0% |
| context_guard.py | `.devin/scripts/context_guard.py` | 42 | 0% |
| context_projection.py | `.devin/scripts/context_projection.py` | 150 | 0% |
| cosign_verify.py | `.devin/scripts/cosign_verify.py` | 35 | 0% |
| cost_dashboard.py | `.devin/scripts/cost_dashboard.py` | 192 | 0% |
| cost_ledger.py | `.devin/scripts/cost_ledger.py` | 135 | 48-58% |
| cost_tracker.py | `.devin/scripts/cost_tracker.py` | 93 | 17-28% |
| cot_synthesis.py | `.devin/scripts/cot_synthesis.py` | 128 | 0% |
| coverage_matrix.py | `.devin/scripts/coverage_matrix.py` | 272 | 0-56% |
| dag_analysis.py | `.devin/scripts/dag_analysis.py` | 59 | 0% |
| dag_callbacks.py | `.devin/scripts/dag_callbacks.py` | 71 | 0% |
| dag_cli.py | `.devin/scripts/dag_cli.py` | 74 | 93% |
| dag_compile.py | `.devin/scripts/dag_compile.py` | 131 | 0% |
| dag_config.py | `.devin/scripts/dag_config.py` | 24 | 50% |
| dag_execution.py | `.devin/scripts/dag_execution.py` | 109 | 81% |
| dag_executor.py | `.devin/scripts/dag_executor.py` | 56 | 80% |
| dag_executor_async.py | `.devin/scripts/dag_executor_async.py` | 247 | 0% |
| dag_failure.py | `.devin/scripts/dag_failure.py` | 39 | 18% |
| dag_operations.py | `.devin/scripts/dag_operations.py` | 31 | 94% |
| dag_schema.py | `.devin/scripts/dag_schema.py` | 80 | 55% |
| dag_state.py | `.devin/scripts/dag_state.py` | 101 | 65% |
| dag_types.py | `.devin/scripts/dag_types.py` | 13 | 85% |
| data_models.py | `.devin/scripts/data_models.py` | 184 | 90% |
| dyflow.py | `.devin/scripts/dyflow.py` | 182 | 0% |
| event_bus.py | `.devin/scripts/event_bus.py` | 190 | 0% |
| fable_judge_compensation.py | `.devin/scripts/fable_judge_compensation.py` | 137 | 0% |
| fsm_model_check.py | `.devin/scripts/fsm_model_check.py` | 199 | 0% |
| graph_engine/* | `.devin/scripts/graph_engine/` | 386 | 0% |
| hardening_flags.py | `.devin/scripts/hardening_flags.py` | 35 | 0% |
| harness_upgrade_*.py | `.devin/scripts/harness_upgrade_*.py` | 269 | 0% |

### 2. Hook Modules with Low Coverage

| Module | Path | Coverage | Missing Lines |
|--------|------|----------|---------------|
| ahd_session_circuit.py | `.devin/hooks/ahd_session_circuit.py` | 37% | 32-54, 59-60, 65-67, 72-73, 81-99 |
| ahd_session_id.py | `.devin/hooks/ahd_session_id.py` | 38-69% | 51-65, 74-83, 94-116 |
| ahd_session_lock.py | `.devin/hooks/ahd_session_lock.py` | 24% | 32-35, 59-120, 152, 157-183 |
| ahd_session_paths.py | `.devin/hooks/ahd_session_paths.py` | 46-65% | 42-43, 50-62, 78, 91-97, 102, 135-138, 143 |
| ahd_session_state.py | `.devin/hooks/ahd_session_state.py` | 30-54% | 34-44, 52-61, 69-86, 91-99, 107-143, 159-166, 171, 176-177, 188-195 |
| pre_tool_callgraph.py | `.devin/hooks/pre_tool_callgraph.py` | 18-59% | 25-32, 37-41, 46-54, 59-60, 65-66, 71-82, 87-88, 93-103, 108-127, 132-142, 147-180 |
| pre_tool_cli.py | `.devin/hooks/pre_tool_cli.py` | 42-70% | 39, 46-54, 57-122, 138-142, 149-155 |
| pre_tool_common.py | `.devin/hooks/pre_tool_common.py` | 27-36% | 15, 25-38 |
| pre_tool_dangerous.py | `.devin/hooks/pre_tool_dangerous.py` | 34-55% | 19-21, 88-108 |
| pre_tool_encoding.py | `.devin/hooks/pre_tool_encoding.py` | 7-69% | 23-56, 70-89, 106-185, 197-251 |
| pre_tool_gates.py | `.devin/hooks/pre_tool_gates.py` | 21-61% | 24-25, 35-40, 44-45, 83-140, 155-215 |
| pre_tool_gates_security.py | `.devin/hooks/pre_tool_gates_security.py` | 8-61% | 34-82, 100-137, 148-224, 232-267 |
| pre_tool_sandbox.py | `.devin/hooks/pre_tool_sandbox.py` | 17-24% | 19-28, 33-34, 39-64, 76-92, 97-105 |
| pre_tool_secrets.py | `.devin/hooks/pre_tool_secrets.py` | 15-77% | 32-33, 38-45, 53-70, 75-82, 94-97, 107-158, 163-165, 170-185, 194-197, 202-204, 208-215, 220-227, 232-237, 251-294 |
| pre_tool_use.py | `.devin/hooks/pre_tool_use.py` | 79% | 113-117 |
| pre_tool_workspace.py | `.devin/hooks/pre_tool_workspace.py` | 26% | 15-16, 28-45 |

---

## Test Infrastructure Analysis

### Current Test Structure

```
tests/
├── conftest.py                 # Shared fixtures (patched_root, etc.)
├── test_cost_guard.py          # 5 tests - cost cap enforcement
├── test_apply_ahd_patch_verify.py  # 2 tests - verify pipeline
├── test_coverage_boost3.py     # 49 tests - dag_executor, coverage_enforce, pre_tool_use
├── test_coverage_boost5.py     # 130 tests - ahd_session, blackboard, event_bus, pre_tool_use
├── test_targeted_coverage_boost.py  # 333 tests - CLI blocks, fallback locks, edge cases
├── test_cve_remediation_phase2.py   # 51 tests - CVE regression tests
├── test_harness_architecture_supreme.py  # 38 tests - architectural guards
├── test_import_smoke.py        # 2 tests - import smoke test
├── test_opencode_harness.py    # 31 tests - opencode integration
├── test_targeted_coverage_low_modules.py  # 175 tests - low-coverage modules
└── test_*.py (100+ more)       # Other test files
```

### Coverage Configuration (pytest.ini)

```ini
[tool.pytest.ini_options]
addopts = "--cov=.devin/scripts --cov=.devin/hooks --cov=tools --cov-fail-under=80 --cov-report=term-missing"
```

**Issue:** The coverage source includes ALL `.devin/scripts/` and `.devin/hooks/` modules, but tests only exercise a fraction of them.

---

## Untested Paths by Category

### Category 1: CLI Entry Points (0% coverage)
Modules with `_cli()`, `_main()`, or `main()` functions that are never invoked in tests:
- `apply_ahd_cli.py`, `approval_gate_args.py`, `approval_gate_commands.py`
- `checkpoint_cli.py`, `cot_synthesis.py`, `dag_cli.py`, `dyflow.py`
- `artifact_registry.py`, `idempotency.py`, `migrate_state.py`
- `cognitive_scaffold_memory.py`, `coverage_matrix.py`, `cost_tracker.py`
- `adaptive_compress.py`, `context_projection.py`, `tscg.py`, `llm_as_judge.py`

### Category 2: Error Handling Paths
Exception handling branches not exercised:
- `ahd_session_lock.py` lines 59-120 (filelock fallback, timeout handling)
- `pre_tool_encoding.py` lines 70-89, 106-185 (encoding bypass detection variants)
- `pre_tool_gates_security.py` lines 148-224 (security gate error paths)
- `pre_tool_secrets.py` lines 107-158 (secret detection edge cases)
- `artifact_registry.py` lines 18-343 (corrupt JSON, missing files, lock timeout)
- `idempotency.py` (corrupt ledger lines, non-serializable results)

### Category 3: Fallback/Alternative Paths
Code paths for when primary mechanism fails:
- `ahd_session_lock.py` - OS lock fallback when `filelock` unavailable
- `artifact_registry.py` - sentinel file lock fallback
- `idempotency.py` - filelock fallback when ahd_session lock fails
- `pre_tool_use.py` lines 113-117 - cost cap gate with no session state

### Category 4: Platform-Specific Code
Windows-specific or Unix-specific branches:
- `migrate_state.py` symlink tests (skipped on Windows)
- `pre_tool_encoding.py` octal/hex/UTF-7 detection
- `pre_tool_gates_security.py` shell command parsing variants

---

## Test Logic Errors Identified

Based on web search best practices and code review:

| Issue | Location | Impact |
|-------|----------|--------|
| **No dynamic context tracking** | pytest.ini | Can't identify which test covers which line |
| **Missing branch coverage** | pytest.ini | `--cov-branch` not enabled; conditional branches untested |
| **Subprocess coverage gap** | `test_opencode_harness.py` | Shell scripts run via subprocess - not traced |
| **Import-time coverage** | `test_import_smoke.py` | Module imports at test collection time not measured |
| **Parallel test coverage** | CI config | `parallel=true` not set; xdist workers don't combine data |
| **Exclude patterns missing** | pyproject.toml | `if TYPE_CHECKING`, `__main__`, `raise NotImplementedError` not excluded |

---

## Fixture Mismatches

| Test File | Fixture Issue | Resolution |
|-----------|---------------|------------|
| `test_cost_guard.py` | `patched_root` creates `.devin/session_state` but `cost_tracker` expects `cost_ledger` | Align fixture with ledger structure |
| `test_targeted_coverage_boost.py` | `_run_main` reloads modules but doesn't reset global state between tests | Add `monkeypatch` cleanup for module globals |
| `test_cve_remediation_phase2.py` | `_run_pre_tool_use` uses `monkeypatch` for some gates but direct assignment for others | Standardize on `monkeypatch.setattr` |
| `test_harness_architecture_supreme.py` | `_run_hook` uses subprocess - no coverage of hook internals | Add unit tests for hook functions directly |

---

## Missing Functions (Not Tested)

### High Priority (Security/Critical Path)
1. `ahd_session_lock.py`: `_acquire_lock()`, `_release_lock()` - fallback paths
2. `pre_tool_encoding.py`: `detect_encoding_bypass()`, `normalize_command()` - all variants
3. `pre_tool_gates_security.py`: SSRF, reflection, encoding bypass gates
4. `pre_tool_secrets.py`: `detect_hlk_secret()`, secret redaction
5. `cost_ledger.py`: `append_entry()`, `verify_ledger()` - HMAC signing/verification
6. `approval_gate_crypto.py`: Ed25519 sign/verify, key rotation
7. `coverage_matrix.py`: `verify_matrix()`, `_sha256_chunked()` - file hash verification

### Medium Priority (Core Functionality)
8. `artifact_registry.py`: `register()`, `get()`, `list_artifacts()` - CLI + fallback locks
9. `idempotency.py`: `register()`, `lookup()`, `_read_ledger()` - corrupt ledger handling
10. `migrate_state.py`: `_move_files()`, `_create_symlink()`, `migrate()` - symlink edge cases
10. `cognitive_scaffold_memory.py`: `record()`, `recall()`, `_redact_text()` - secret redaction
11. `dyflow.py`: `_normalize_module_to_path()`, `_resolve_relative_import()`, `_topo_sort()`
12. `cot_synthesis.py`: `_fit_to_budget()`, `_coherence()`, `synthesize()`
13. `adaptive_compress.py`: `_summarize()`, `_prefix_hash()`, `_estimate_tokens()`
14. `context_projection.py`: `_read_single_file()`, `_extract_chunks_from_json()`

---

## Recommendations

### Immediate Actions (High Impact)

1. **Enable branch coverage** in `pyproject.toml`:
   ```toml
   [tool.coverage.run]
   branch = true
   
   [tool.coverage.report]
   exclude_lines = [
       "pragma: no cover",
       "if TYPE_CHECKING:",
       "raise NotImplementedError",
       "if __name__ == .__main__.:",
   ]
   ```

2. **Add `--cov-context=test`** to identify which test covers each line

3. **Set `parallel = true`** for xdist compatibility

4. **Exclude 0-coverage modules** from `source` or add targeted tests:
   - Option A: Move untested modules to separate package excluded from coverage
   - Option B: Add `test_<module>.py` for each 0% module

### Medium-term Actions

5. **Convert subprocess tests to unit tests** for `test_opencode_harness.py` and `test_harness_architecture_supreme.py` to get internal coverage

6. **Add parametrized tests** for encoding bypass variants (already done in `test_cve_remediation_phase2.py` - good pattern)

7. **Add mutation testing** (`mutmut`) for critical modules to verify test quality

8. **Create test utilities** for common patterns:
   - `mock_ahd_session()` - standardized session mocking
   - `mock_repo_root()` - consistent repo root patching
   - `capture_hook_output()` - hook stdin/stdout capture

### Long-term Actions

9. **Implement diff coverage** (via `diff-cover`) for PR gates

10. **Add coverage reporting to CI** with artifact upload (Codecov/GitHub Actions)

11. **Ratchet coverage threshold** gradually: 20% → 40% → 60% → 80%

---

## Web Search Best Practices Applied

From the web search results (pytest-cov 2026 guide, Scientific Python guide, Honeybadger):

| Best Practice | Current Status | Action |
|---------------|----------------|--------|
| Use `pytest-cov` plugin (not `coverage run`) | ✅ Using `--cov` flags | Keep |
| Enable branch coverage | ❌ Not enabled | Add `branch = true` |
| Use `term-missing` with `skip_covered` | ✅ Using `term-missing` | Add `skip_covered = true` |
| Set `source` explicitly | ❌ Using paths in `--cov` | Move to `pyproject.toml` `source_pkgs` |
| Combine parallel coverage data | ❌ Not configured | Add `parallel = true` |
| Exclude unreachable code patterns | ❌ No exclusions | Add `exclude_lines` patterns |
| Use diff coverage for PRs | ❌ Not implemented | Add `diff-cover` to CI |
| Mutation testing for quality | ❌ Not used | Add `mutmut` nightly job |
| Ratchet threshold, not absolute | ❌ Fixed at 80% | Lower threshold, ratchet up |

---

## Conclusion

**The "14 failed + 36 errors" mentioned in the query do not exist in the current test run.** All 816 tests pass. The real issue is that the coverage threshold (80%) is unattainable with the current test suite because:

1. **~200+ modules** in `.devin/scripts/` and `.devin/hooks/` have **0% coverage**
2. Tests only exercise ~15% of the codebase (dag_executor, ahd_session, pre_tool_use, blackboard, event_bus, coverage_matrix, cost_tracker, artifact_registry, idempotency, migrate_state, cognitive_scaffold_memory, dyflow, cot_synthesis, adaptive_compress, context_projection)
3. Coverage configuration lacks branch coverage, exclusions, and parallel support

**Recommended path forward:**
1. Lower `fail-under` to current actual coverage (~15-20%)
2. Enable branch coverage and exclusions
3. Add targeted test files for high-priority 0% modules (security/critical path first)
4. Implement diff coverage for PR gate
5. Ratchet threshold up over time

This approach aligns with industry best practices: "require that coverage does not fall, and require full coverage on changed lines" rather than chasing absolute percentages.