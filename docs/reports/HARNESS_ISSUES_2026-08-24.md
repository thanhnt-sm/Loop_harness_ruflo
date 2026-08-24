# Harness Issue Report — 2026-08-24 19:08

## Tóm tắt

| Severity | Count | Trạng thái |
|----------|-------|------------|
| CRITICAL | 0 | ✅ PASS |
| HIGH | 0 | ✅ PASS |
| MEDIUM | 0 | ✅ PASS |
| LOW | 115 | ℹ️ INFO |
| **TOTAL** | **115** | |

## LOW (115 issues)

| # | Category | File | Line | Description | Fix |
|---|----------|------|------|-------------|-----|
| 1 | SEC-005b: Silent Error Swallow | `.devin\hooks\context_compaction.py` | 250 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 2 | SEC-005b: Silent Error Swallow | `.devin\hooks\prompt_cache_metrics.py` | 87 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 3 | SEC-005b: Silent Error Swallow | `.devin\scripts\best_of_n.py` | 101 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 4 | SEC-005b: Silent Error Swallow | `.devin\scripts\best_of_n.py` | 138 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 5 | SEC-005b: Silent Error Swallow | `.devin\scripts\cost_dashboard.py` | 43 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 6 | SEC-005b: Silent Error Swallow | `.devin\scripts\cost_dashboard.py` | 74 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 7 | SEC-005b: Silent Error Swallow | `.devin\scripts\idempotency.py` | 114 | except Exception: pass — errors swallowed silently | Add logging or re-raise |
| 8 | QUAL-002: Function Too Long | `.devin\hooks\ahd_session_lock.py` | 38 | _acquire_lock: 108 lines (> 50 limit) | Refactor into smaller functions |
| 9 | QUAL-002: Function Too Long | `.devin\hooks\coverage_enforce.py` | 248 | _update_coverage: 56 lines (> 50 limit) | Refactor into smaller functions |
| 10 | QUAL-002: Function Too Long | `.devin\hooks\coverage_enforce.py` | 357 | main: 77 lines (> 50 limit) | Refactor into smaller functions |
| 11 | QUAL-002: Function Too Long | `.devin\hooks\drift_detect.py` | 148 | _extract_features: 79 lines (> 50 limit) | Refactor into smaller functions |
| 12 | QUAL-002: Function Too Long | `.devin\hooks\drift_detect.py` | 286 | detect_drift: 127 lines (> 50 limit) | Refactor into smaller functions |
| 13 | QUAL-002: Function Too Long | `.devin\hooks\observation_masking.py` | 102 | main: 51 lines (> 50 limit) | Refactor into smaller functions |
| 14 | QUAL-002: Function Too Long | `.devin\hooks\otel_instrument.py` | 224 | main: 66 lines (> 50 limit) | Refactor into smaller functions |
| 15 | QUAL-002: Function Too Long | `.devin\hooks\plan_enforce.py` | 129 | _get_plan_state_for_task: 63 lines (> 50 limit) | Refactor into smaller functions |
| 16 | QUAL-002: Function Too Long | `.devin\hooks\plan_enforce.py` | 266 | main: 79 lines (> 50 limit) | Refactor into smaller functions |
| 17 | QUAL-002: Function Too Long | `.devin\hooks\post_tool_enforce_quality.py` | 14 | _u57_auto_quality_checks: 67 lines (> 50 limit) | Refactor into smaller functions |
| 18 | QUAL-002: Function Too Long | `.devin\hooks\post_tool_engine.py` | 29 | main: 257 lines (> 50 limit) | Refactor into smaller functions |
| 19 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_cli.py` | 42 | _run_main: 80 lines (> 50 limit) | Refactor into smaller functions |
| 20 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_encoding.py` | 92 | normalize_command: 93 lines (> 50 limit) | Refactor into smaller functions |
| 21 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_encoding.py` | 188 | _decode_ip_encoding: 63 lines (> 50 limit) | Refactor into smaller functions |
| 22 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_gates.py` | 70 | _check_context_oversized_gate: 70 lines (> 50 limit) | Refactor into smaller functions |
| 23 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_gates.py` | 143 | _check_cost_cap_gate: 72 lines (> 50 limit) | Refactor into smaller functions |
| 24 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_gates_security.py` | 25 | _check_ssrf_gate: 57 lines (> 50 limit) | Refactor into smaller functions |
| 25 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_gates_security.py` | 85 | _check_encoding_bypass_gate: 52 lines (> 50 limit) | Refactor into smaller functions |
| 26 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_gates_security.py` | 140 | _check_reflection_gate: 84 lines (> 50 limit) | Refactor into smaller functions |
| 27 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_secrets.py` | 100 | check_ssrf: 58 lines (> 50 limit) | Refactor into smaller functions |
| 28 | QUAL-002: Function Too Long | `.devin\hooks\pre_tool_secrets.py` | 240 | _pin_and_verify_url: 54 lines (> 50 limit) | Refactor into smaller functions |
| 29 | QUAL-002: Function Too Long | `.devin\hooks\schema_gate_gates.py` | 74 | _gate_symbol_verification: 62 lines (> 50 limit) | Refactor into smaller functions |
| 30 | QUAL-002: Function Too Long | `.devin\hooks\schema_gate_paths.py` | 20 | _gate_file_path_validation: 55 lines (> 50 limit) | Refactor into smaller functions |
| 31 | QUAL-002: Function Too Long | `.devin\hooks\schema_gate_secrets.py` | 87 | _gate_secret_scan: 62 lines (> 50 limit) | Refactor into smaller functions |
| 32 | QUAL-002: Function Too Long | `.devin\hooks\self_heal.py` | 190 | self_heal: 63 lines (> 50 limit) | Refactor into smaller functions |
| 33 | QUAL-002: Function Too Long | `.devin\hooks\session_start.py` | 87 | main: 57 lines (> 50 limit) | Refactor into smaller functions |
| 34 | QUAL-002: Function Too Long | `.devin\hooks\stop.py` | 95 | main: 78 lines (> 50 limit) | Refactor into smaller functions |
| 35 | QUAL-002: Function Too Long | `.devin\hooks\user_prompt_submit.py` | 16 | main: 72 lines (> 50 limit) | Refactor into smaller functions |
| 36 | QUAL-002: Function Too Long | `.devin\scripts\adaptive_compress.py` | 84 | _deep_compress: 65 lines (> 50 limit) | Refactor into smaller functions |
| 37 | QUAL-002: Function Too Long | `.devin\scripts\apply_ahd_apply.py` | 66 | apply_commit: 140 lines (> 50 limit) | Refactor into smaller functions |
| 38 | QUAL-002: Function Too Long | `.devin\scripts\apply_ahd_cli.py` | 115 | main: 104 lines (> 50 limit) | Refactor into smaller functions |
| 39 | QUAL-002: Function Too Long | `.devin\scripts\approval_gate_args.py` | 12 | _parse_args: 75 lines (> 50 limit) | Refactor into smaller functions |
| 40 | QUAL-002: Function Too Long | `.devin\scripts\approval_gate_commands.py` | 45 | _write_approval_state: 79 lines (> 50 limit) | Refactor into smaller functions |
| 41 | QUAL-002: Function Too Long | `.devin\scripts\approval_gate_interactive.py` | 18 | cmd_interactive: 80 lines (> 50 limit) | Refactor into smaller functions |
| 42 | QUAL-002: Function Too Long | `.devin\scripts\artifact_registry.py` | 191 | register: 72 lines (> 50 limit) | Refactor into smaller functions |
| 43 | QUAL-002: Function Too Long | `.devin\scripts\baseline_validator.py` | 94 | validate_baseline: 51 lines (> 50 limit) | Refactor into smaller functions |
| 44 | QUAL-002: Function Too Long | `.devin\scripts\best_of_n.py` | 31 | _verify_code_quality: 73 lines (> 50 limit) | Refactor into smaller functions |
| 45 | QUAL-002: Function Too Long | `.devin\scripts\best_of_n.py` | 142 | best_of_n: 63 lines (> 50 limit) | Refactor into smaller functions |
| 46 | QUAL-002: Function Too Long | `.devin\scripts\build_workflow.py` | 20 | main: 51 lines (> 50 limit) | Refactor into smaller functions |
| 47 | QUAL-002: Function Too Long | `.devin\scripts\checkpoint_cli.py` | 34 | cmd_save: 52 lines (> 50 limit) | Refactor into smaller functions |
| 48 | QUAL-002: Function Too Long | `.devin\scripts\checkpoint_cli.py` | 133 | cmd_restore: 67 lines (> 50 limit) | Refactor into smaller functions |
| 49 | QUAL-002: Function Too Long | `.devin\scripts\context_projection.py` | 185 | project: 56 lines (> 50 limit) | Refactor into smaller functions |
| 50 | QUAL-002: Function Too Long | `.devin\scripts\cost_dashboard.py` | 151 | _generate_dashboard: 134 lines (> 50 limit) | Refactor into smaller functions |
| 51 | QUAL-002: Function Too Long | `.devin\scripts\coverage_matrix.py` | 181 | generate_matrix: 54 lines (> 50 limit) | Refactor into smaller functions |
| 52 | QUAL-002: Function Too Long | `.devin\scripts\coverage_matrix.py` | 331 | verify_matrix: 74 lines (> 50 limit) | Refactor into smaller functions |
| 53 | QUAL-002: Function Too Long | `.devin\scripts\dag_compile.py` | 50 | parse_plan: 54 lines (> 50 limit) | Refactor into smaller functions |
| 54 | QUAL-002: Function Too Long | `.devin\scripts\dag_compile.py` | 195 | compile_plan: 57 lines (> 50 limit) | Refactor into smaller functions |
| 55 | QUAL-002: Function Too Long | `.devin\scripts\dag_execution.py` | 75 | execute: 116 lines (> 50 limit) | Refactor into smaller functions |
| 56 | QUAL-002: Function Too Long | `.devin\scripts\dag_executor_async.py` | 314 | execute_async: 100 lines (> 50 limit) | Refactor into smaller functions |
| 57 | QUAL-002: Function Too Long | `.devin\scripts\dag_schema.py` | 23 | validate_workflow: 72 lines (> 50 limit) | Refactor into smaller functions |
| 58 | QUAL-002: Function Too Long | `.devin\scripts\dag_state.py` | 32 | _load_workflow: 55 lines (> 50 limit) | Refactor into smaller functions |
| 59 | QUAL-002: Function Too Long | `.devin\scripts\dyflow.py` | 123 | _discover_python_deps: 54 lines (> 50 limit) | Refactor into smaller functions |
| 60 | QUAL-002: Function Too Long | `.devin\scripts\fable_judge_compensation.py` | 270 | run_compensation_verification: 119 lines (> 50 limit) | Refactor into smaller functions |
| 61 | QUAL-002: Function Too Long | `.devin\scripts\fsm_model_check.py` | 51 | orc_transitions: 77 lines (> 50 limit) | Refactor into smaller functions |
| 62 | QUAL-002: Function Too Long | `.devin\scripts\fsm_model_check.py` | 154 | router_transitions: 58 lines (> 50 limit) | Refactor into smaller functions |
| 63 | QUAL-002: Function Too Long | `.devin\scripts\harness_upgrade_loop.py` | 52 | _run_one_iteration: 121 lines (> 50 limit) | Refactor into smaller functions |
| 64 | QUAL-002: Function Too Long | `.devin\scripts\idempotency.py` | 165 | register: 102 lines (> 50 limit) | Refactor into smaller functions |
| 65 | QUAL-002: Function Too Long | `.devin\scripts\loop_memory_fallback.py` | 29 | _write_fallback: 79 lines (> 50 limit) | Refactor into smaller functions |
| 66 | QUAL-002: Function Too Long | `.devin\scripts\loop_memory_registry.py` | 221 | regenerate: 146 lines (> 50 limit) | Refactor into smaller functions |
| 67 | QUAL-002: Function Too Long | `.devin\scripts\merge_updates.py` | 293 | apply_vendored_copy: 62 lines (> 50 limit) | Refactor into smaller functions |
| 68 | QUAL-002: Function Too Long | `.devin\scripts\merge_updates.py` | 362 | main: 97 lines (> 50 limit) | Refactor into smaller functions |
| 69 | QUAL-002: Function Too Long | `.devin\scripts\nuwa_roi.py` | 137 | compute_roi: 51 lines (> 50 limit) | Refactor into smaller functions |
| 70 | QUAL-002: Function Too Long | `.devin\scripts\plan_dispatch.py` | 86 | analyze: 67 lines (> 50 limit) | Refactor into smaller functions |
| 71 | QUAL-002: Function Too Long | `.devin\scripts\plan_dispatch_cli.py` | 36 | main: 87 lines (> 50 limit) | Refactor into smaller functions |
| 72 | QUAL-002: Function Too Long | `.devin\scripts\plan_quality_parse.py` | 180 | _parse_task_tables: 72 lines (> 50 limit) | Refactor into smaller functions |
| 73 | QUAL-002: Function Too Long | `.devin\scripts\plan_quality_parse.py` | 255 | _parse_tasks: 60 lines (> 50 limit) | Refactor into smaller functions |
| 74 | QUAL-002: Function Too Long | `.devin\scripts\pre_task_audit.py` | 55 | audit: 77 lines (> 50 limit) | Refactor into smaller functions |
| 75 | QUAL-002: Function Too Long | `.devin\scripts\qa_doc_audit.py` | 125 | _resolve_candidate: 60 lines (> 50 limit) | Refactor into smaller functions |
| 76 | QUAL-002: Function Too Long | `.devin\scripts\qa_doc_audit.py` | 244 | audit: 60 lines (> 50 limit) | Refactor into smaller functions |
| 77 | QUAL-002: Function Too Long | `.devin\scripts\reward_shaping.py` | 61 | shape: 51 lines (> 50 limit) | Refactor into smaller functions |
| 78 | QUAL-002: Function Too Long | `.devin\scripts\reward_shaping.py` | 115 | detect_hack: 51 lines (> 50 limit) | Refactor into smaller functions |
| 79 | QUAL-002: Function Too Long | `.devin\scripts\self_consistency.py` | 100 | self_consistency_task: 54 lines (> 50 limit) | Refactor into smaller functions |
| 80 | QUAL-002: Function Too Long | `.devin\scripts\spc_monitor.py` | 256 | cmd_report: 63 lines (> 50 limit) | Refactor into smaller functions |
| 81 | QUAL-002: Function Too Long | `.devin\scripts\subagent_isolation.py` | 53 | _run_subagent: 62 lines (> 50 limit) | Refactor into smaller functions |
| 82 | QUAL-002: Function Too Long | `.devin\scripts\subagent_isolation.py` | 140 | run_subagent: 61 lines (> 50 limit) | Refactor into smaller functions |
| 83 | QUAL-002: Function Too Long | `.devin\scripts\swarm_director.py` | 73 | compile_spec: 84 lines (> 50 limit) | Refactor into smaller functions |
| 84 | QUAL-002: Function Too Long | `.devin\scripts\swarm_director.py` | 194 | dispatch: 69 lines (> 50 limit) | Refactor into smaller functions |
| 85 | QUAL-002: Function Too Long | `.devin\scripts\worktree.py` | 248 | cmd_merge: 58 lines (> 50 limit) | Refactor into smaller functions |
| 86 | QUAL-004: Missing Type Hint | `.devin\hooks\compress_terminal_output.py` | 185 | Function 'main' missing return type hint | Add return type annotation |
| 87 | QUAL-004: Missing Type Hint | `.devin\hooks\context_compaction.py` | 254 | Function 'main' missing return type hint | Add return type annotation |
| 88 | QUAL-004: Missing Type Hint | `.devin\hooks\coverage_enforce.py` | 357 | Function 'main' missing return type hint | Add return type annotation |
| 89 | QUAL-004: Missing Type Hint | `.devin\hooks\cross_family_verify.py` | 51 | Function 'main' missing return type hint | Add return type annotation |
| 90 | QUAL-004: Missing Type Hint | `.devin\hooks\observation_masking.py` | 102 | Function 'main' missing return type hint | Add return type annotation |
| 91 | QUAL-004: Missing Type Hint | `.devin\hooks\otel_instrument.py` | 224 | Function 'main' missing return type hint | Add return type annotation |
| 92 | QUAL-004: Missing Type Hint | `.devin\hooks\plan_enforce.py` | 266 | Function 'main' missing return type hint | Add return type annotation |
| 93 | QUAL-007: Missing Docstring | `.devin\hooks\compress_terminal_output.py` | 185 | Function 'main' missing docstring | Add docstring describing purpose |
| 94 | QUAL-007: Missing Docstring | `.devin\hooks\context_compaction.py` | 254 | Function 'main' missing docstring | Add docstring describing purpose |
| 95 | QUAL-007: Missing Docstring | `.devin\hooks\cross_family_verify.py` | 51 | Function 'main' missing docstring | Add docstring describing purpose |
| 96 | QUAL-007: Missing Docstring | `.devin\hooks\observation_masking.py` | 102 | Function 'main' missing docstring | Add docstring describing purpose |
| 97 | QUAL-006: Unused Import | `.devin\hooks\ahd_session.py` | 14 | 'annotations' imported but not used | Remove unused import |
| 98 | QUAL-006: Unused Import | `.devin\hooks\ahd_session_circuit.py` | 11 | 'annotations' imported but not used | Remove unused import |
| 99 | QUAL-006: Unused Import | `.devin\hooks\ahd_session_id.py` | 9 | 'annotations' imported but not used | Remove unused import |
| 100 | QUAL-006: Unused Import | `.devin\hooks\ahd_session_lock.py` | 10 | 'annotations' imported but not used | Remove unused import |
| 101 | QUAL-006: Unused Import | `.devin\hooks\ahd_session_paths.py` | 12 | 'annotations' imported but not used | Remove unused import |
| 102 | QUAL-006: Unused Import | `.devin\hooks\ahd_session_state.py` | 16 | 'annotations' imported but not used | Remove unused import |
| 103 | QUAL-006: Unused Import | `.devin\hooks\ahd_session_utils.py` | 7 | 'annotations' imported but not used | Remove unused import |
| 104 | QUAL-006: Unused Import | `.devin\hooks\compress_terminal_output.py` | 16 | 'annotations' imported but not used | Remove unused import |
| 105 | QUAL-006: Unused Import | `.devin\hooks\compress_terminal_output.py` | 21 | 'Path' imported but not used | Remove unused import |
| 106 | QUAL-006: Unused Import | `.devin\hooks\context_compaction.py` | 8 | 'annotations' imported but not used | Remove unused import |
| 107 | QUAL-006: Unused Import | `.devin\hooks\coverage_enforce.py` | 32 | 'annotations' imported but not used | Remove unused import |
| 108 | QUAL-006: Unused Import | `.devin\hooks\cross_family_verify.py` | 14 | 'annotations' imported but not used | Remove unused import |
| 109 | QUAL-006: Unused Import | `.devin\hooks\cross_family_verify.py` | 19 | 'Path' imported but not used | Remove unused import |
| 110 | QUAL-006: Unused Import | `.devin\hooks\drift_detect.py` | 33 | 'annotations' imported but not used | Remove unused import |
| 111 | QUAL-006: Unused Import | `.devin\hooks\drift_detect.py` | 39 | 'deque' imported but not used | Remove unused import |
| 112 | QUAL-006: Unused Import | `.devin\hooks\observation_masking.py` | 18 | 'annotations' imported but not used | Remove unused import |
| 113 | QUAL-006: Unused Import | `.devin\hooks\otel_instrument.py` | 29 | 'annotations' imported but not used | Remove unused import |
| 114 | QUAL-006: Unused Import | `.devin\hooks\plan_enforce.py` | 21 | 'annotations' imported but not used | Remove unused import |
| 115 | QUAL-006: Unused Import | `.devin\hooks\plan_enforce.py` | 28 | 'datetime' imported but not used | Remove unused import |

## Danh sách issues buộc fix (CRITICAL + HIGH)

✅ Không có issue CRITICAL hoặc HIGH — harness đạt tiêu chuẩn bảo mật cao.

