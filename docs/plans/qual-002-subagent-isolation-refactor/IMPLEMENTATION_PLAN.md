# Implementation Plan: Refactor `subagent_isolation.py` Functions

## Context
The file `.devin/scripts/subagent_isolation.py` contains two functions that violate the `QUAL-002: Function Too Long` rule (limit 50 lines):
1. `_run_subagent`: 62 lines
2. `run_subagent`: 61 lines

This was reported in `docs/reports/HARNESS_ISSUES_2026-09-08.md`.

## Objective
Refactor these two functions into smaller, more manageable helper functions to improve maintainability and resolve the `QUAL-002` violations. The refactored code must maintain all existing functionality and pass all tests.

## Implementation Steps
| Step | File Path | Function | Acceptance Criteria | REQ ID |
|---|---|---|---|---|
| 1 | `.devin/scripts/subagent_isolation.py` | `_run_subagent` | Extract the prompt string building into a `_build_subagent_prompt(subagent_context)` helper. Reduce `_run_subagent` to <50 lines. | REFACT-1 |
| 2 | `.devin/scripts/subagent_isolation.py` | `_run_subagent` | Extract the subprocess probe into a `_probe_executor(task_brief, executor, scripts_dir)` helper. | REFACT-2 |
| 3 | `.devin/scripts/subagent_isolation.py` | `run_subagent` | Extract the exception/fallback return dictionary into a `_build_fallback_result(subagent_id, task_brief, error_str)` helper. Reduce `run_subagent` to <50 lines. | REFACT-3 |
