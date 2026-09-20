# Harness Issue Report — 2026-09-20 05:34

## Tóm tắt

| Severity | Count | Trạng thái |
|----------|-------|------------|
| CRITICAL | 0 | ✅ PASS |
| HIGH | 0 | ✅ PASS |
| MEDIUM | 2 | ⚠️ REVIEW |
| LOW | 195 | ℹ️ INFO |
| **TOTAL** | **197** | |

## MEDIUM (2 issues)

| # | Category | File | Line | Description | Fix |
|---|----------|------|------|-------------|-----|
| 1 | QUAL-001: File Too Long | `.devin/hooks/ahd_session_durable.py` | 662 | File has 662 lines (> 500 limit) | Split into smaller modules |
| 2 | QUAL-001: File Too Long | `.devin/hooks/context_compaction.py` | 520 | File has 520 lines (> 500 limit) | Split into smaller modules |

## LOW (195 issues)

| # | Category | File | Line | Description | Fix |
|---|----------|------|------|-------------|-----|
| 1 | QUAL-002: Function Too Long | `.devin/hooks/post_tool_engine.py` | 56 | main: 320 lines (> 50 limit) | Refactor into smaller functions |
| 2 | QUAL-002: Function Too Long | `.devin/hooks/post_tool_engine.py` | 379 | _memory_write_gate: 59 lines (> 50 limit) | Refactor into smaller functions |
| 3 | QUAL-002: Function Too Long | `.devin/hooks/coverage_enforce.py` | 248 | _update_coverage: 56 lines (> 50 limit) | Refactor into smaller functions |
| 4 | QUAL-002: Function Too Long | `.devin/hooks/coverage_enforce.py` | 357 | main: 77 lines (> 50 limit) | Refactor into smaller functions |
| 5 | QUAL-002: Function Too Long | `.devin/hooks/ahd_session_durable.py` | 413 | emit_tool_receipt: 51 lines (> 50 limit) | Refactor into smaller functions |
| 6 | QUAL-002: Function Too Long | `.devin/hooks/drift_detect.py` | 148 | _extract_features: 79 lines (> 50 limit) | Refactor into smaller functions |
| 7 | QUAL-002: Function Too Long | `.devin/hooks/drift_detect.py` | 286 | detect_drift: 127 lines (> 50 limit) | Refactor into smaller functions |
| 8 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_encoding.py` | 92 | normalize_command: 93 lines (> 50 limit) | Refactor into smaller functions |
| 9 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_encoding.py` | 188 | _decode_ip_encoding: 63 lines (> 50 limit) | Refactor into smaller functions |
| 10 | QUAL-002: Function Too Long | `.devin/hooks/stop.py` | 95 | main: 78 lines (> 50 limit) | Refactor into smaller functions |
| 11 | QUAL-002: Function Too Long | `.devin/hooks/otel_instrument.py` | 224 | main: 66 lines (> 50 limit) | Refactor into smaller functions |
| 12 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_secrets.py` | 100 | check_ssrf: 58 lines (> 50 limit) | Refactor into smaller functions |
| 13 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_secrets.py` | 240 | _pin_and_verify_url: 54 lines (> 50 limit) | Refactor into smaller functions |
| 14 | QUAL-002: Function Too Long | `.devin/hooks/observation_masking.py` | 102 | main: 53 lines (> 50 limit) | Refactor into smaller functions |
| 15 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_gates.py` | 85 | _check_context_oversized_gate: 70 lines (> 50 limit) | Refactor into smaller functions |
| 16 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_gates.py` | 158 | _check_dependency_pins_gate: 52 lines (> 50 limit) | Refactor into smaller functions |
| 17 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_gates.py` | 213 | _check_cost_cap_gate: 72 lines (> 50 limit) | Refactor into smaller functions |
| 18 | QUAL-002: Function Too Long | `.devin/hooks/post_tool_enforce_quality.py` | 14 | _u57_auto_quality_checks: 67 lines (> 50 limit) | Refactor into smaller functions |
| 19 | QUAL-002: Function Too Long | `.devin/hooks/schema_gate_paths.py` | 20 | _gate_file_path_validation: 55 lines (> 50 limit) | Refactor into smaller functions |
| 20 | QUAL-002: Function Too Long | `.devin/hooks/ahd_session_lock.py` | 38 | _acquire_lock: 108 lines (> 50 limit) | Refactor into smaller functions |
| 21 | QUAL-002: Function Too Long | `.devin/hooks/session_start.py` | 87 | main: 57 lines (> 50 limit) | Refactor into smaller functions |
| 22 | QUAL-002: Function Too Long | `.devin/hooks/plan_enforce.py` | 129 | _get_plan_state_for_task: 63 lines (> 50 limit) | Refactor into smaller functions |
| 23 | QUAL-002: Function Too Long | `.devin/hooks/plan_enforce.py` | 266 | main: 100 lines (> 50 limit) | Refactor into smaller functions |
| 24 | QUAL-002: Function Too Long | `.devin/hooks/schema_gate_gates.py` | 74 | _gate_symbol_verification: 62 lines (> 50 limit) | Refactor into smaller functions |
| 25 | QUAL-002: Function Too Long | `.devin/hooks/self_heal.py` | 190 | self_heal: 63 lines (> 50 limit) | Refactor into smaller functions |
| 26 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_cli.py` | 44 | _run_main: 91 lines (> 50 limit) | Refactor into smaller functions |
| 27 | QUAL-002: Function Too Long | `.devin/hooks/schema_gate_secrets.py` | 87 | _gate_secret_scan: 62 lines (> 50 limit) | Refactor into smaller functions |
| 28 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_gates_security.py` | 26 | _check_ssrf_gate: 68 lines (> 50 limit) | Refactor into smaller functions |
| 29 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_gates_security.py` | 97 | _check_encoding_bypass_gate: 52 lines (> 50 limit) | Refactor into smaller functions |
| 30 | QUAL-002: Function Too Long | `.devin/hooks/pre_tool_gates_security.py` | 152 | _check_reflection_gate: 84 lines (> 50 limit) | Refactor into smaller functions |
| 31 | QUAL-002: Function Too Long | `.devin/hooks/user_prompt_submit.py` | 16 | main: 72 lines (> 50 limit) | Refactor into smaller functions |
| 32 | QUAL-002: Function Too Long | `.devin/scripts/token_registry.py` | 153 | check_revocation_gate: 53 lines (> 50 limit) | Refactor into smaller functions |
| 33 | QUAL-002: Function Too Long | `.devin/scripts/coverage_matrix.py` | 181 | generate_matrix: 54 lines (> 50 limit) | Refactor into smaller functions |
| 34 | QUAL-002: Function Too Long | `.devin/scripts/coverage_matrix.py` | 331 | verify_matrix: 74 lines (> 50 limit) | Refactor into smaller functions |
| 35 | QUAL-002: Function Too Long | `.devin/scripts/pre_task_audit.py` | 55 | audit: 77 lines (> 50 limit) | Refactor into smaller functions |
| 36 | QUAL-002: Function Too Long | `.devin/scripts/harness_upgrade_loop.py` | 52 | _run_one_iteration: 121 lines (> 50 limit) | Refactor into smaller functions |
| 37 | QUAL-002: Function Too Long | `.devin/scripts/spc_monitor.py` | 256 | cmd_report: 63 lines (> 50 limit) | Refactor into smaller functions |
| 38 | QUAL-002: Function Too Long | `.devin/scripts/apply_ahd_cli.py` | 115 | main: 104 lines (> 50 limit) | Refactor into smaller functions |
| 39 | QUAL-002: Function Too Long | `.devin/scripts/qa_doc_audit.py` | 125 | _resolve_candidate: 60 lines (> 50 limit) | Refactor into smaller functions |
| 40 | QUAL-002: Function Too Long | `.devin/scripts/qa_doc_audit.py` | 244 | audit: 60 lines (> 50 limit) | Refactor into smaller functions |
| 41 | QUAL-002: Function Too Long | `.devin/scripts/baseline_validator.py` | 94 | validate_baseline: 51 lines (> 50 limit) | Refactor into smaller functions |
| 42 | QUAL-002: Function Too Long | `.devin/scripts/approval_gate_args.py` | 12 | _parse_args: 75 lines (> 50 limit) | Refactor into smaller functions |
| 43 | QUAL-002: Function Too Long | `.devin/scripts/plan_dispatch.py` | 86 | analyze: 67 lines (> 50 limit) | Refactor into smaller functions |
| 44 | QUAL-002: Function Too Long | `.devin/scripts/idempotency.py` | 166 | register: 102 lines (> 50 limit) | Refactor into smaller functions |
| 45 | QUAL-002: Function Too Long | `.devin/scripts/merge_updates.py` | 293 | apply_vendored_copy: 62 lines (> 50 limit) | Refactor into smaller functions |
| 46 | QUAL-002: Function Too Long | `.devin/scripts/merge_updates.py` | 362 | main: 97 lines (> 50 limit) | Refactor into smaller functions |
| 47 | QUAL-002: Function Too Long | `.devin/scripts/fable_judge_compensation.py` | 270 | run_compensation_verification: 119 lines (> 50 limit) | Refactor into smaller functions |
| 48 | QUAL-002: Function Too Long | `.devin/scripts/dag_compile.py` | 50 | parse_plan: 54 lines (> 50 limit) | Refactor into smaller functions |
| 49 | QUAL-002: Function Too Long | `.devin/scripts/dag_compile.py` | 195 | compile_plan: 57 lines (> 50 limit) | Refactor into smaller functions |
| 50 | QUAL-002: Function Too Long | `.devin/scripts/nuwa_roi.py` | 137 | compute_roi: 51 lines (> 50 limit) | Refactor into smaller functions |
| 51 | QUAL-002: Function Too Long | `.devin/scripts/approval_gate_commands.py` | 45 | _write_approval_state: 79 lines (> 50 limit) | Refactor into smaller functions |
| 52 | QUAL-002: Function Too Long | `.devin/scripts/dag_executor_async.py` | 314 | execute_async: 100 lines (> 50 limit) | Refactor into smaller functions |
| 53 | QUAL-002: Function Too Long | `.devin/scripts/self_consistency.py` | 100 | self_consistency_task: 54 lines (> 50 limit) | Refactor into smaller functions |
| 54 | QUAL-002: Function Too Long | `.devin/scripts/loop_memory_registry.py` | 221 | regenerate: 146 lines (> 50 limit) | Refactor into smaller functions |
| 55 | QUAL-002: Function Too Long | `.devin/scripts/cost_dashboard.py` | 157 | _generate_dashboard: 134 lines (> 50 limit) | Refactor into smaller functions |
| 56 | QUAL-002: Function Too Long | `.devin/scripts/plan_quality_parse.py` | 180 | _parse_task_tables: 72 lines (> 50 limit) | Refactor into smaller functions |
| 57 | QUAL-002: Function Too Long | `.devin/scripts/plan_quality_parse.py` | 255 | _parse_tasks: 60 lines (> 50 limit) | Refactor into smaller functions |
| 58 | QUAL-002: Function Too Long | `.devin/scripts/plan_dispatch_cli.py` | 36 | main: 87 lines (> 50 limit) | Refactor into smaller functions |
| 59 | QUAL-002: Function Too Long | `.devin/scripts/swarm_director.py` | 73 | compile_spec: 84 lines (> 50 limit) | Refactor into smaller functions |
| 60 | QUAL-002: Function Too Long | `.devin/scripts/swarm_director.py` | 194 | dispatch: 69 lines (> 50 limit) | Refactor into smaller functions |
| 61 | QUAL-002: Function Too Long | `.devin/scripts/context_projection.py` | 185 | project: 56 lines (> 50 limit) | Refactor into smaller functions |
| 62 | QUAL-002: Function Too Long | `.devin/scripts/context_projection.py` | 244 | _cli: 63 lines (> 50 limit) | Refactor into smaller functions |
| 63 | QUAL-002: Function Too Long | `.devin/scripts/checkpoint_cli.py` | 34 | cmd_save: 52 lines (> 50 limit) | Refactor into smaller functions |
| 64 | QUAL-002: Function Too Long | `.devin/scripts/checkpoint_cli.py` | 133 | cmd_restore: 67 lines (> 50 limit) | Refactor into smaller functions |
| 65 | QUAL-002: Function Too Long | `.devin/scripts/approval_gate_interactive.py` | 18 | cmd_interactive: 80 lines (> 50 limit) | Refactor into smaller functions |
| 66 | QUAL-002: Function Too Long | `.devin/scripts/apply_ahd_apply.py` | 66 | apply_commit: 140 lines (> 50 limit) | Refactor into smaller functions |
| 67 | QUAL-002: Function Too Long | `.devin/scripts/dyflow.py` | 123 | _discover_python_deps: 54 lines (> 50 limit) | Refactor into smaller functions |
| 68 | QUAL-002: Function Too Long | `.devin/scripts/worktree.py` | 248 | cmd_merge: 58 lines (> 50 limit) | Refactor into smaller functions |
| 69 | QUAL-002: Function Too Long | `.devin/scripts/dag_execution.py` | 75 | execute: 116 lines (> 50 limit) | Refactor into smaller functions |
| 70 | QUAL-002: Function Too Long | `.devin/scripts/dag_schema.py` | 23 | validate_workflow: 72 lines (> 50 limit) | Refactor into smaller functions |
| 71 | QUAL-002: Function Too Long | `.devin/scripts/dag_state.py` | 32 | _load_workflow: 55 lines (> 50 limit) | Refactor into smaller functions |
| 72 | QUAL-002: Function Too Long | `.devin/scripts/artifact_registry.py` | 191 | register: 72 lines (> 50 limit) | Refactor into smaller functions |
| 73 | QUAL-002: Function Too Long | `.devin/scripts/loop_memory_fallback.py` | 29 | _write_fallback: 79 lines (> 50 limit) | Refactor into smaller functions |
| 74 | QUAL-002: Function Too Long | `.devin/scripts/adaptive_compress.py` | 183 | _deep_compress: 65 lines (> 50 limit) | Refactor into smaller functions |
| 75 | QUAL-002: Function Too Long | `.devin/scripts/fsm_model_check.py` | 51 | orc_transitions: 77 lines (> 50 limit) | Refactor into smaller functions |
| 76 | QUAL-002: Function Too Long | `.devin/scripts/fsm_model_check.py` | 154 | router_transitions: 58 lines (> 50 limit) | Refactor into smaller functions |
| 77 | QUAL-002: Function Too Long | `.devin/scripts/best_of_n.py` | 31 | _verify_code_quality: 81 lines (> 50 limit) | Refactor into smaller functions |
| 78 | QUAL-002: Function Too Long | `.devin/scripts/best_of_n.py` | 153 | best_of_n: 63 lines (> 50 limit) | Refactor into smaller functions |
| 79 | QUAL-002: Function Too Long | `.devin/scripts/reward_shaping.py` | 61 | shape: 51 lines (> 50 limit) | Refactor into smaller functions |
| 80 | QUAL-002: Function Too Long | `.devin/scripts/reward_shaping.py` | 115 | detect_hack: 51 lines (> 50 limit) | Refactor into smaller functions |
| 81 | QUAL-002: Function Too Long | `.devin/scripts/build_workflow.py` | 20 | main: 51 lines (> 50 limit) | Refactor into smaller functions |
| 82 | QUAL-004: Missing Type Hint | `.devin/hooks/post_tool_engine.py` | 56 | Function 'main' missing return type hint | Add return type annotation |
| 83 | QUAL-004: Missing Type Hint | `.devin/hooks/coverage_enforce.py` | 357 | Function 'main' missing return type hint | Add return type annotation |
| 84 | QUAL-007: Missing Docstring | `.devin/hooks/post_tool_engine.py` | 56 | Function 'main' missing docstring | Add docstring describing purpose |
| 85 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 16 | 'annotations' imported but not used | Remove unused import |
| 86 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'MAX_ITERATIONS_WITHOUT_STATE_WRITE' imported but not used | Remove unused import |
| 87 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'MIN_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 88 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'MAX_OUTPUT_SIZE_COMPRESSION' imported but not used | Remove unused import |
| 89 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'DEFAULT_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 90 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'MAX_FAILURE_THRESHOLD' imported but not used | Remove unused import |
| 91 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | '_CONTEXT_FLAGS_CACHE' imported but not used | Remove unused import |
| 92 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | '_CONTEXT_FLAGS_LOADED' imported but not used | Remove unused import |
| 93 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | '_STATE_WRITE_COUNTER' imported but not used | Remove unused import |
| 94 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | '_STATE_WRITE_BATCH' imported but not used | Remove unused import |
| 95 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'CONTEXT_OVERSIZE_THRESHOLD' imported but not used | Remove unused import |
| 96 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'CANDIDATE_MEMORY_MAX' imported but not used | Remove unused import |
| 97 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'CANDIDATE_MEMORY_PER_HOUR' imported but not used | Remove unused import |
| 98 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | 'CANDIDATE_MEMORY_WINDOW_SECONDS' imported but not used | Remove unused import |
| 99 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 28 | '_SECRET_PATTERNS' imported but not used | Remove unused import |
| 100 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 46 | '_redact' imported but not used | Remove unused import |
| 101 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 46 | '_response_size' imported but not used | Remove unused import |
| 102 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 46 | '_extract_file_path' imported but not used | Remove unused import |
| 103 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 46 | '_extract_command' imported but not used | Remove unused import |
| 104 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 52 | '_compute_sha256' imported but not used | Remove unused import |
| 105 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 52 | '_track_file_sha' imported but not used | Remove unused import |
| 106 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 56 | '_repeated_failure_count' imported but not used | Remove unused import |
| 107 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 56 | '_extract_candidate_memory' imported but not used | Remove unused import |
| 108 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 56 | '_memory_rate_limited' imported but not used | Remove unused import |
| 109 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 56 | '_audit_candidate' imported but not used | Remove unused import |
| 110 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 62 | '_append_bounded_jsonl' imported but not used | Remove unused import |
| 111 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 62 | '_rotate' imported but not used | Remove unused import |
| 112 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 66 | '_u57_auto_quality_checks' imported but not used | Remove unused import |
| 113 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 66 | '_u58_done_detection' imported but not used | Remove unused import |
| 114 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 66 | '_u59_skill_auto_router' imported but not used | Remove unused import |
| 115 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 71 | '_u60_loop_enforcement' imported but not used | Remove unused import |
| 116 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 71 | '_u61_state_write_verification' imported but not used | Remove unused import |
| 117 | QUAL-006: Unused Import | `.devin/hooks/post_tool_use.py` | 71 | '_u62_memory_confidence' imported but not used | Remove unused import |
| 118 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 3 | 'annotations' imported but not used | Remove unused import |
| 119 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'HOOK_TIMEOUT_SECONDS' imported but not used | Remove unused import |
| 120 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'MAX_ITERATIONS_WITHOUT_STATE_WRITE' imported but not used | Remove unused import |
| 121 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'MIN_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 122 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'MAX_OUTPUT_SIZE_COMPRESSION' imported but not used | Remove unused import |
| 123 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'DEFAULT_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 124 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'MAX_FAILURE_THRESHOLD' imported but not used | Remove unused import |
| 125 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | '_CONTEXT_FLAGS_CACHE' imported but not used | Remove unused import |
| 126 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | '_CONTEXT_FLAGS_LOADED' imported but not used | Remove unused import |
| 127 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | '_STATE_WRITE_COUNTER' imported but not used | Remove unused import |
| 128 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | '_STATE_WRITE_BATCH' imported but not used | Remove unused import |
| 129 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'CONTEXT_OVERSIZE_THRESHOLD' imported but not used | Remove unused import |
| 130 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'VALID_CORRECT_ACTIONS' imported but not used | Remove unused import |
| 131 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'CANDIDATE_MEMORY_PER_HOUR' imported but not used | Remove unused import |
| 132 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | 'CANDIDATE_MEMORY_WINDOW_SECONDS' imported but not used | Remove unused import |
| 133 | QUAL-006: Unused Import | `.devin/hooks/post_tool_bounded.py` | 9 | '_SECRET_PATTERNS' imported but not used | Remove unused import |
| 134 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 3 | 'annotations' imported but not used | Remove unused import |
| 135 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'HOOK_TIMEOUT_SECONDS' imported but not used | Remove unused import |
| 136 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'MAX_ITERATIONS_WITHOUT_STATE_WRITE' imported but not used | Remove unused import |
| 137 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'MIN_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 138 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'MAX_OUTPUT_SIZE_COMPRESSION' imported but not used | Remove unused import |
| 139 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'DEFAULT_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 140 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'MAX_FAILURE_THRESHOLD' imported but not used | Remove unused import |
| 141 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | '_CONTEXT_FLAGS_CACHE' imported but not used | Remove unused import |
| 142 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | '_CONTEXT_FLAGS_LOADED' imported but not used | Remove unused import |
| 143 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | '_STATE_WRITE_COUNTER' imported but not used | Remove unused import |
| 144 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | '_STATE_WRITE_BATCH' imported but not used | Remove unused import |
| 145 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'CANDIDATE_MEMORY_MAX' imported but not used | Remove unused import |
| 146 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'CANDIDATE_MEMORY_WINDOW_SECONDS' imported but not used | Remove unused import |
| 147 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | '_SECRET_PATTERNS' imported but not used | Remove unused import |
| 148 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'MAX_TOOL_CALLS_PER_TASK' imported but not used | Remove unused import |
| 149 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'REPETITION_THRESHOLD' imported but not used | Remove unused import |
| 150 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'CONTEXT_BUDGET_KILL_PCT' imported but not used | Remove unused import |
| 151 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 11 | 'PROGRESSIVE_TOOL_LIMIT' imported but not used | Remove unused import |
| 152 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 34 | '_redact' imported but not used | Remove unused import |
| 153 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 35 | '_compute_sha256' imported but not used | Remove unused import |
| 154 | QUAL-006: Unused Import | `.devin/hooks/post_tool_engine.py` | 53 | 'mcp_guard_call' imported but not used | Remove unused import |
| 155 | QUAL-006: Unused Import | `.devin/hooks/cross_family_verify.py` | 14 | 'annotations' imported but not used | Remove unused import |
| 156 | QUAL-006: Unused Import | `.devin/hooks/cross_family_verify.py` | 19 | 'Path' imported but not used | Remove unused import |
| 157 | QUAL-006: Unused Import | `.devin/hooks/ahd_session_circuit.py` | 11 | 'annotations' imported but not used | Remove unused import |
| 158 | QUAL-006: Unused Import | `.devin/hooks/coverage_enforce.py` | 32 | 'annotations' imported but not used | Remove unused import |
| 159 | QUAL-006: Unused Import | `.devin/hooks/ahd_session_utils.py` | 7 | 'annotations' imported but not used | Remove unused import |
| 160 | QUAL-006: Unused Import | `.devin/hooks/ahd_session_durable.py` | 13 | 'annotations' imported but not used | Remove unused import |
| 161 | QUAL-006: Unused Import | `.devin/hooks/drift_detect.py` | 33 | 'annotations' imported but not used | Remove unused import |
| 162 | QUAL-006: Unused Import | `.devin/hooks/drift_detect.py` | 39 | 'deque' imported but not used | Remove unused import |
| 163 | QUAL-006: Unused Import | `.devin/hooks/post_tool_mcp_guard.py` | 11 | 'annotations' imported but not used | Remove unused import |
| 164 | QUAL-006: Unused Import | `.devin/hooks/post_tool_mcp_guard.py` | 16 | 'Optional' imported but not used | Remove unused import |
| 165 | QUAL-006: Unused Import | `.devin/hooks/post_tool_mcp_guard.py` | 17 | 'Path' imported but not used | Remove unused import |
| 166 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 3 | 'annotations' imported but not used | Remove unused import |
| 167 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'HOOK_TIMEOUT_SECONDS' imported but not used | Remove unused import |
| 168 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'MAX_ITERATIONS_WITHOUT_STATE_WRITE' imported but not used | Remove unused import |
| 169 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'MIN_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 170 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'MAX_OUTPUT_SIZE_COMPRESSION' imported but not used | Remove unused import |
| 171 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'DEFAULT_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 172 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'MAX_FAILURE_THRESHOLD' imported but not used | Remove unused import |
| 173 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | '_CONTEXT_FLAGS_CACHE' imported but not used | Remove unused import |
| 174 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | '_CONTEXT_FLAGS_LOADED' imported but not used | Remove unused import |
| 175 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | '_STATE_WRITE_COUNTER' imported but not used | Remove unused import |
| 176 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | '_STATE_WRITE_BATCH' imported but not used | Remove unused import |
| 177 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'CONTEXT_OVERSIZE_THRESHOLD' imported but not used | Remove unused import |
| 178 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'CANDIDATE_MEMORY_MAX' imported but not used | Remove unused import |
| 179 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | 'VALID_CORRECT_ACTIONS' imported but not used | Remove unused import |
| 180 | QUAL-006: Unused Import | `.devin/hooks/post_tool_memory_candidate.py` | 13 | '_SECRET_PATTERNS' imported but not used | Remove unused import |
| 181 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 3 | 'annotations' imported but not used | Remove unused import |
| 182 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 7 | 'timezone' imported but not used | Remove unused import |
| 183 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'HOOK_TIMEOUT_SECONDS' imported but not used | Remove unused import |
| 184 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'DEFAULT_COMPRESSION_THRESHOLD' imported but not used | Remove unused import |
| 185 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | '_CONTEXT_FLAGS_CACHE' imported but not used | Remove unused import |
| 186 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | '_CONTEXT_FLAGS_LOADED' imported but not used | Remove unused import |
| 187 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | '_STATE_WRITE_COUNTER' imported but not used | Remove unused import |
| 188 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | '_STATE_WRITE_BATCH' imported but not used | Remove unused import |
| 189 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'CONTEXT_OVERSIZE_THRESHOLD' imported but not used | Remove unused import |
| 190 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'CANDIDATE_MEMORY_MAX' imported but not used | Remove unused import |
| 191 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'VALID_CORRECT_ACTIONS' imported but not used | Remove unused import |
| 192 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'CANDIDATE_MEMORY_PER_HOUR' imported but not used | Remove unused import |
| 193 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | 'CANDIDATE_MEMORY_WINDOW_SECONDS' imported but not used | Remove unused import |
| 194 | QUAL-006: Unused Import | `.devin/hooks/post_tool_enforce_loop.py` | 12 | '_SECRET_PATTERNS' imported but not used | Remove unused import |
| 195 | QUAL-006: Unused Import | `.devin/hooks/ahd_session_state.py` | 16 | 'annotations' imported but not used | Remove unused import |

## Danh sách issues buộc fix (CRITICAL + HIGH)

✅ Không có issue CRITICAL hoặc HIGH — harness đạt tiêu chuẩn bảo mật cao.

