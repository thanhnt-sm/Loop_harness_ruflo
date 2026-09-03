# Migration Diff: .devin/ vs HLK/

Generated: `D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\HLK\scripts\diff_compare.py`

## Section 1: HLK có, .devin KHÔNG có

Các file đã có ở HLK nhưng `.devin/scripts/` chưa có:

- (none)

## Section 2: .devin có, HLK KHÔNG có — CẦN CLONE

Các file ở `.devin/scripts/` cần clone sang `HLK/chain/`:

- `_platform_utils.py`
- `agent_browser_runner.py`
- `auto_pr_gh.py`
- `auto_pr_runner.py`
- `brd_schema.py`
- `brd_validator.py`
- `command_code_client.py`
- `judge_config.py`
- `prompt_sanitizer.py`
- `redteam_spawner.py`
- `rubric_generator.py`
- `scenario_runner.py`
- `secret_scanner.py`
- `skill_bench.py`
- `skill_promoter.py`
- `test_generator.py`
- `verify_env_setup.py`

## Section 3: Cả hai đều có

0 files đã có ở cả 2 nơi:


## Section 4: Config files

### Section 4a: cả hai đều có


### Section 4b: .devin chỉ có, HLK thiếu (CẦN CLONE/CENTRALIZE)

- `auto_pr.yaml`
- `llm_judge.yaml`

### Section 4c: HLK chỉ có, .devin thiếu

- `hlk.config.json`
- `secrets.env.example`

## Section 5: Plan (clone theo priority)

1. **Priority 1**: Clone scripts ở Section 2 sang `HLK/chain/` (preserving code, update docstring).
2. **Priority 2**: Update CLI import path từ `from brd_validator` → `from HLK.chain.brd_validator` (hoặc relative).
3. **Priority 3**: Clone config files ở Section 4b sang `HLK/config/`, hoặc gộp vào `hlk.config.json`.
4. **Priority 4**: Tạo wrapper files ở `.commandcode/`, `.opencode/`, `.devin/scripts/` (re-export shim) trỏ về HLK.
5. **Priority 5**: Verify toàn bộ tests pass + governance clean.

**Summary**: 17 scripts + 2 configs cần clone. Sau khi clone xong, Section 2 + 4b = 0.
