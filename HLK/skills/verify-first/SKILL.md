---
name: verify-first
description: Verify-First chain — BRD → Scenario → Rubric → Test → Gate. Dùng khi user cung cấp BRD.md và muốn generate scenarios/rubrics/tests + gate verdict tự động. Canonical source tại HLK/skills/verify-first/SKILL.md.
keywords:
  - verify-first
  - BRD
  - scenario
  - rubric
  - gate
  - audit
---

# Skill: verify-first (HLK canonical)

## Canonical source

**Source of truth**: `HLK/chain/` (Python modules) + `HLK/chain/loaders/verify-first-loader.js` (Node loader).

**CLI entry**: `HLK/chain/verify_first_cli.py` (mirror tại `scripts/verify_first_cli.py`).

**Config**: `HLK/chain/config.py` (load từ `HLK/config/hlk.config.json`).

## Khi nào dùng

Kích hoạt khi:
- User cung cấp file `BRD.md` và muốn chạy chain verify-first
- User nói "verify first", "run chain", "BRD → gate", "rubric generation", "scenario generation"
- CI/CD trigger tự động chạy gate trên mỗi PR

## Cách dùng

### CLI
```bash
# Cross-platform (Windows + macOS + Linux)
py HLK/chain/verify_first_cli.py docs/plans/my-task/BRD.md --out-dir ./out

# Wrapper (Node) — thêm HLK loader + audit log
node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs docs/plans/my-task/BRD.md
```

### Python API
```python
import sys
sys.path.insert(0, "HLK")
from chain import (
    BRD, parse_brd_file, make_scenarios_from_brd,
    generate_rubric_file, generate_from_rubric_file,
    run_scenario, should_auto_merge,
)

brd = parse_brd_file("BRD.md")
scenarios = make_scenarios_from_brd(brd)
rubric_path = generate_rubric_file(brd, "rubric.json")
tests = generate_from_rubric_file(rubric_path, "tests/")
verdict = should_auto_merge(
    pr_files=[...], pr_diff="...",
    branch_prefix="verify-first/",
    pr_title="verify-first: ...",
    rubric_file=rubric_path,
    mode="simulate",  # an toàn
)
```

### Gate verdict
4 checks: coverage_matrix, adversarial_consensus, llm_judge_rubric, fable_judge.
- Tất cả PASS → audit log written, có thể auto-merge
- 1 check FAIL → block, return GateVerdict(passed=False, failed_gates=[...])

## Cross-platform

Scripts dùng `HLK/chain/_platform_utils.py`:
- `get_python_cmd()` → "py" (Windows) hoặc "python3" (POSIX)
- `is_windows()` / `is_macos()` / `is_linux()` / `is_posix()`
- `run_python(args)` — wrapper subprocess cross-platform
- `ensure_utf8_output()` — fix Windows console encoding

## Architecture

```
USER request
   ↓
[Provider: opencode | cmdc | Claude | GPT]
   ↓ load skills (this file or pointer)
[HLK chain]
   ↓
HLK/chain/ (canonical implementation)
├── __init__.py        ← re-export
├── brd_schema.py
├── brd_validator.py
├── scenario_runner.py
├── verify_env_setup.py
├── rubric_generator.py
├── test_generator.py
├── secret_scanner.py
├── prompt_sanitizer.py
├── judge_config.py
├── redteam_spawner.py
├── skill_promoter.py
├── skill_bench.py
├── auto_pr_runner.py
├── auto_pr_gh.py
├── command_code_client.py
├── agent_browser_runner.py
├── _platform_utils.py
├── verify_first_cli.py
├── config.py
├── hlk_wrappers/
│   └── verify-first-wrapper.mjs
└── loaders/
    └── verify-first-loader.js
```

## Migrations / wrappers

- `.devin/scripts/X.py` — shim re-export từ `HLK.chain.X` (backward compat, KHÔNG xóa)
- `.commandcode/skills/verify-first/SKILL.md` — pointer tới file này
- `.opencode/command/verify-first.md` — pointer tới file này
- `scripts/verify_first_cli.py` — CLI mirror (giữ cho convenience)

## Sync mechanism

`HLK/scripts/sync_to_mirrors.py` — đồng bộ HLK → .devin/ + .commandcode/ + .opencode/ (1 chiều, KHÔNG xóa file ở mirror).

## Tests

- `tests/test_migration_diff.py` — verify HLK/chain/ có 17 modules
- `tests/test_hlk_config.py` — verify config loader
- `tests/test_hlk_chain_imports.py` — verify tất cả modules import OK
- `tests/test_sync_to_mirrors.py` — verify sync không xóa file ở mirror

## Security

- P0 cc_cli_path allowlist (validated ở `_validate_cc_cli_path`)
- P1 human confirm cho mode="live"
- P1 secret scan trong `live_auto_merge` (8 patterns)
- P1 audit path validation (chỉ ghi vào `.devin/state/`)
- P1 log rotation (file > 10MB → rename theo date)
- P1 prompt redaction (CC client redact secrets trước khi gửi)
- P2 prompt injection protection (sanitize trước khi gửi redteam)

## References

- `HLK/docs/migration-diff.md` — diff report .devin vs HLK
- `HLK/docs/verify-first-deployment.md` — deployment guide
- `HLK/reports/verify-first-consolidation-redteam.md` — redteam review
- `docs/plans/harness-upgrade-verify-first/` — original plan artifacts
- `docs/plans/verify-first-residual/` — Phase 2-3 plan
- `docs/plans/fix-p0-and-deferred/` — P0 fix plan
- `docs/plans/hardening-and-scale/` — P1 hardening plan
