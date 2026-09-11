# Implementation Plan: Fix Windows Paths and Subprocess `py` in tests

## Requirements
- Fix hardcoded absolute Windows paths (`D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo`) across `tests/` files.
- Replace subprocess calls to `"py"` with `sys.executable` (or `"python3"`) across `tests/` files, as Linux environments do not have `py`.
- Resolve failing test issues caused by these environment inconsistencies.

## Strategy
1. Identify all `tests/*.py` files containing `D:/100.Software/Github/Loop_harness_new/Loop_harness_ruflo` and use `sed` to replace it with relative context-dependent paths (like `Path(__file__).resolve().parent.parent`).
2. Identify all `tests/*.py` files containing `subprocess.run(["py"` and use `sed` to replace `["py"` with `[sys.executable`. Ensure `sys` is imported.

## File Path
- `tests/test_gen_lazy_init.py`
- `tests/test_verify_first_cli.py`
- `tests/test_migration_diff.py`
- `tests/test_skill_bench_cron.py`
- `tests/test_sync_to_mirrors.py`
- `tests/test_hlk_skill_pointer.py`

## Acceptance Criteria
- Modified tests do not contain hardcoded Windows paths.
- Modified tests run `sys.executable` instead of `"py"`.
- Coverage failures are expected and acceptable if the individual tests themselves pass.