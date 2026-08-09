# EXECUTION REPORT — Refactor 181 broad `except Exception` catches into specific exceptions

## Summary

Refactored broad `except Exception` catches into specific exception tuples across `.devin/scripts/*.py` and advisory `.devin/hooks/*.py`, preserving fail-open behavior of advisory hooks and keeping coverage >= 80%.

**Baseline:** 2034 passed, 3 skipped, 90.21% coverage.
**Final:** 2034 passed, 3 skipped, 89.50% coverage.
**Remaining `except Exception`:** 120 out of 164 baseline (44 narrowed, ~27% reduction).

## Commits

1. `9de8b43` — refactor(except): narrow broad Exception catches in scripts batch 1
2. `89d2933` — refactor(except): narrow broad Exception catches in scripts batch 2
3. `a00b905` — refactor(except): narrow broad Exception catches in scripts+hooks batch 3

## Files Changed

### Batch 1 (commit 9de8b43) — Scripts
| File | Catches narrowed | Exception mapping |
|------|-----------------|-------------------|
| `.devin/scripts/artifact_registry.py` | 7/9 | Import fallback -> `(ImportError, ModuleNotFoundError, SyntaxError, ValueError)`; JSON/file I/O -> `(json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError)`; lock sentinel cleanup -> `(OSError,)`; CLI JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/scripts/checkpoint.py` | 6/6 | JSON/file I/O -> `(json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError)` |
| `.devin/scripts/cognitive_scaffold_memory.py` | 4/4 | Import fallback -> `(ImportError, ModuleNotFoundError, SyntaxError, ValueError)`; file unlink -> `(OSError,)`; JSON read -> `(json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError)` |
| `.devin/scripts/idempotency.py` | 6/8 | Import fallback -> `(ImportError, ModuleNotFoundError, SyntaxError, ValueError)`; JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)`; file read -> `(OSError, UnicodeDecodeError)`; lock fallback kept as `except Exception as e` (safety-critical) |
| `.devin/scripts/log_rotation.py` | 3/3 | Import fallback -> `(ImportError, ModuleNotFoundError, SyntaxError, ValueError)`; file I/O -> `(OSError, UnicodeDecodeError)` |

### Batch 2 (commit 89d2933) — Scripts
| File | Catches narrowed | Exception mapping |
|------|-----------------|-------------------|
| `.devin/scripts/loop_memory_sync.py` | 8/12 | JSON/file I/O -> `(json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError)`; datetime parse -> `(ValueError, TypeError)`; archive write -> `(OSError, UnicodeDecodeError, AttributeError)`; outer wrappers kept as `except Exception as e` (safety-critical) |
| `.devin/scripts/memory_audit.py` | 2/2 | JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)`; file write -> `(OSError, UnicodeDecodeError)` |
| `.devin/scripts/nuwa_roi.py` | 4/4 | session_state ops -> `(KeyError, TypeError, ValueError, AttributeError, OSError)` |
| `.devin/scripts/plan_dispatch.py` | 2/2 | subprocess -> `(subprocess.SubprocessError, FileNotFoundError, TimeoutExpired, OSError)`; JSON/file I/O -> `(json.JSONDecodeError, TypeError, ValueError, OSError, UnicodeDecodeError)` |
| `.devin/scripts/pre_task_audit.py` | 3/4 | datetime parse -> `(ValueError, TypeError)`; file hint expand -> `(KeyError, TypeError, ValueError, AttributeError, OSError)`; outer wrapper kept as `except Exception as e` (safety-critical) |

### Batch 3 (commit a00b905) — Scripts + Hooks
| File | Catches narrowed | Notes |
|------|-----------------|-------|
| `.devin/scripts/reflection_gate.py` | 1/2 | Action validation -> `(ValueError, TypeError, KeyError, AttributeError)` |
| `.devin/scripts/state_router.py` | 1/1 | Condition eval -> `(KeyError, TypeError, ValueError, AttributeError)` |
| `.devin/scripts/swarm_director.py` | 1/2 | Order parse -> `(ValueError, TypeError, KeyError, AttributeError)`; worker raise kept as `except Exception as exc` (arbitrary worker callback) |
| `.devin/scripts/worktree.py` | 5/6 | session_state ops -> `(KeyError, TypeError, ValueError, AttributeError, OSError)`; lock/file I/O -> `(TimeoutError, OSError, FileExistsError)` / `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/scripts/cot_synthesis.py` | 1/1 | Pre-existing: CLI JSON -> `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/scripts/dag_compile.py` | 1/1 | Pre-existing: file read -> `(OSError, UnicodeDecodeError)` |
| `.devin/scripts/dag_executor.py` | 2/3 | Pre-existing: checkpoint save + task result -> `(ValueError, TypeError, KeyError, AttributeError)`; runner retry kept as `except Exception as exc` (arbitrary runner) |
| `.devin/scripts/dyflow.py` | 2/2 | Pre-existing: file read -> `(OSError, UnicodeDecodeError)`; CLI JSON -> `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/scripts/llm_as_judge.py` | 1/1 | Pre-existing: audit log -> `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/scripts/session_manager.py` | 2/2 | Pre-existing: JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)`; file write -> `(OSError, UnicodeDecodeError)` |
| `.devin/scripts/spc_monitor.py` | 2/2 | Pre-existing: JSON/file I/O -> `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/scripts/three_role.py` | 1/1 | Pre-existing: CLI JSON -> `(json.JSONDecodeError, TypeError, ValueError)` |
| `.devin/hooks/coverage_enforce.py` | 2/13 | Pre-existing: import fallbacks narrowed; generic fallbacks kept (advisory fail-open) |
| `.devin/hooks/drift_detect.py` | 1/4 | Pre-existing: specific handler added before fallback |
| `.devin/hooks/otel_instrument.py` | 2/10 | Pre-existing: specific handlers added before fallbacks |
| `.devin/hooks/post_tool_use.py` | 3/21 | Pre-existing: specific handlers added before fallbacks |
| `.devin/hooks/pre_tool_use.py` | 2/12 | Pre-existing: import fallback (lines 40-49) + urlparse (line 271) narrowed; internal gate errors (lines 404-637) NOT touched per scope |
| `.devin/hooks/self_heal.py` | 1/4 | Pre-existing: specific handler added before fallback |
| `.devin/hooks/session_end.py` | 1/1 | Pre-existing: JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)` before fallback |
| `.devin/hooks/session_start.py` | 2/4 | Pre-existing: specific handlers added before fallbacks |
| `.devin/hooks/stop.py` | 4/8 | Pre-existing: subprocess -> `(subprocess.SubprocessError, FileNotFoundError, TimeoutExpired, OSError)`; file I/O -> `(OSError, UnicodeDecodeError)`; JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)`; validation -> `(ValueError, TypeError, KeyError, AttributeError)` |
| `.devin/hooks/user_prompt_submit.py` | 1/1 | Pre-existing: JSON parse -> `(json.JSONDecodeError, TypeError, ValueError)` before fallback |
| `.devin/hook_hashes.json` | — | Regenerated to match modified hooks (fixes hook_integrity test) |

## Test Results

| Batch | Command | Result |
|-------|---------|--------|
| Baseline | `python -m pytest tests/ -q --cov=.devin --cov-fail-under=80` | 2034 passed, 3 skipped, 90.21% |
| Batch 1 | same | 2034 passed, 3 skipped, 90.19% |
| Batch 2 | same | 2034 passed, 3 skipped, 89.13% |
| Batch 3 | same | 2034 passed, 3 skipped, 89.50% |

## Intentionally Kept `except Exception` (safety-critical)

These catches were intentionally kept as `except Exception as e` with stderr log because they protect safety-critical fallback paths where any exception must trigger the fallback:

- **Lock acquire/release fallbacks** (artifact_registry, idempotency, log_rotation): lock libraries can raise arbitrary exceptions; tests mock generic `Exception`/`RuntimeError` to trigger fallback.
- **Outer wrappers** (loop_memory_sync `_safe_regenerate`, `run_inline`, `main`, `_write_fallback`; pre_task_audit `run_inline`): last-resort error boundaries that must not crash the harness.
- **Worker/runner callbacks** (swarm_director line 244, dag_executor line 536): arbitrary user code can raise anything; retry logic needs to catch all.
- **Advisory hook fallbacks** (post_tool_use, coverage_enforce, otel_instrument, stop, etc.): per plan, advisory hooks keep `except Exception` as final fallback to preserve fail-open behavior.

## Out-of-Scope (not touched per plan)

- `.devin/hooks/schema_gate.py` — security fail-closed hook (6 catches)
- `.devin/hooks/plan_enforce.py` — not in scope
- `.devin/hooks/pre_tool_use.py` lines 404-637 — internal gate errors (9 catches)
- `HLK/`, `.env`, security policies

## Remaining Work (105 in-scope `except Exception` fallbacks)

The advisory hooks use the pattern: specific handler first + `except Exception:` fallback. Per plan rule 4, the fallbacks should have `as e` + stderr log. The pre-existing changes added specific handlers but many fallbacks still use bare `except Exception:` without `as e`. These remain to be updated in a future batch:

- `.devin/hooks/coverage_enforce.py`: 11 fallbacks without `as e`
- `.devin/hooks/post_tool_use.py`: 18 fallbacks without `as e`
- `.devin/hooks/otel_instrument.py`: 8 fallbacks without `as e`
- `.devin/hooks/pre_tool_use.py`: 9 internal gate fallbacks (out of scope) + 2 import/urlparse fallbacks without `as e`
- `.devin/hooks/stop.py`: 7 fallbacks without `as e`
- `.devin/hooks/session_start.py`: 4 fallbacks without `as e`
- `.devin/hooks/self_heal.py`: 1 fallback without `as e`
- `.devin/hooks/drift_detect.py`: 1 fallback without `as e`
- `.devin/scripts/`: ~15 remaining fallbacks (mix of safety-critical with `as e` and a few without)

## Risks / Notes

- **Pre-existing changes**: Batches 1-2 were done fresh. Batch 3 incorporated pre-existing uncommitted changes from a previous session (both scripts and hooks). These changes aligned with the refactor goal and were verified by tests.
- **hook_hashes.json**: Regenerated to match modified hooks. The hook_integrity test would fail without this update.
- **`.bak` files**: Untracked backup files from the previous session remain in `.devin/scripts/` and `.devin/hooks/`. These should be cleaned up separately.
- **Coverage drop**: 90.21% -> 89.50% (0.71% drop, still well above 80% threshold). The drop is from the pre-existing hook changes adding specific exception handlers that are harder to test (the fallback `except Exception:` paths are no longer exercised by tests that trigger generic exceptions).
