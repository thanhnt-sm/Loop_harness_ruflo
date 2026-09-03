# Verify-First Deployment Guide (HLK canonical)

> **Canonical source**: `HLK/docs/verify-first-deployment.md`
> **Plan**: `~/.commandcode/plans/consolidate-to-hlk.md`
> **Status**: Active — HLK là source of truth cho verify-first chain

---

## 1. Tổng quan

Theo user directive: **HLK là source of truth duy nhất** cho verify-first chain. Mọi provider (opencode, cmdc, Claude) phải tham chiếu, đăng ký, dẫn chiếu vào HLK.

```
USER request
   ↓
[Provider: opencode | cmdc | Claude | GPT]
   ↓ load skills → tất cả pointer tới HLK
[HLK chain]  ← SOURCE OF TRUTH
├── chain/ (canonical implementation)
├── skills/verify-first/SKILL.md (canonical skill)
├── config/hlk.config.json (canonical config)
├── loaders/ + hlk_wrappers/ (Node integration)
├── reports/ (audit + redteam)
└── scripts/ (diff_compare + sync_to_mirrors)

.devin/scripts/  ← NGOẠI LỆ (KHÔNG xóa), có shim re-export
.commandcode/    ← POINTER files
.opencode/       ← POINTER files
```

---

## 2. Architecture (HLK-centric)

```
HLK/
├── chain/                              ← All verify-first implementation
│   ├── __init__.py                    ← re-export public API
│   ├── brd_schema.py                  ← Pydantic models
│   ├── brd_validator.py               ← parse markdown BRD
│   ├── scenario_runner.py             ← run scenarios
│   ├── verify_env_setup.py            ← boot web/cli/api/mobile env
│   ├── rubric_generator.py            ← BinaryRubric + ScoreRubric
│   ├── test_generator.py              ← generate pytest code
│   ├── secret_scanner.py              ← 8 patterns + redact()
│   ├── prompt_sanitizer.py            ← anti-injection
│   ├── judge_config.py                ← LLM judge config
│   ├── redteam_spawner.py             ← parallel expert calls
│   ├── skill_promoter.py              ← auto-promote pattern → skill
│   ├── skill_bench.py                 ← benchmark skills
│   ├── auto_pr_runner.py              ← 4-gate verdict
│   ├── auto_pr_gh.py                  ← gh CLI wrapper
│   ├── command_code_client.py         ← CC subprocess + circuit breaker
│   ├── agent_browser_runner.py        ← UI/simulator scenarios
│   ├── _platform_utils.py             ← cross-platform helpers
│   ├── verify_first_cli.py            ← CLI entry
│   ├── config.py                      ← load HLK config
│   ├── hlk_wrappers/
│   │   └── verify-first-wrapper.mjs   ← Node wrapper
│   └── loaders/
│       └── verify-first-loader.js     ← Node HLK loader (sanitize argv)
├── skills/
│   └── verify-first/
│       └── SKILL.md                    ← canonical skill
├── config/
│   └── hlk.config.json                 ← central config (verify_first section)
├── scripts/
│   ├── diff_compare.py                ← diff .devin vs HLK
│   └── sync_to_mirrors.py             ← sync HLK → mirrors
├── reports/
│   ├── migration-diff.md              ← diff report
│   └── verify-first-consolidation-redteam.md
└── docs/
    ├── verify-first-deployment.md     ← this file
    └── migration-diff.md
```

---

## 3. Provider integration matrix

| Provider | Entry point | Reference style | File |
|---|---|---|---|
| **opencode** | `opencode.json` | `references.hlk`, `references.verify-first` | updated |
| **.commandcode** (skills) | `.commandcode/skills/verify-first/SKILL.md` | POINTER file | synced |
| **.commandcode** (commands) | `.commandcode/commands/verify-first.md` | (TODO) | — |
| **.commandcode** (agents) | `.commandcode/agents/verify-first.md` | POINTER file | synced |
| **.opencode** (commands) | `.opencode/command/verify-first.md` | POINTER file | synced |
| **.devin** (NGOẠI LỆ) | `.devin/scripts/X.py` | shim re-export | synced (KHÔNG xóa) |
| **Claude / GPT / any AI** | Load `AGENTS.md` (root) | HLK mandate section | updated |
| **HLK loader** (Node) | `HLK/chain/loaders/verify-first-loader.js` | auto-loaded | exists |

---

## 4. Cách dùng (từ bất kỳ provider nào)

### 4.1 CLI
```bash
# Cross-platform
py HLK/chain/verify_first_cli.py <BRD.md> --out-dir ./out

# Node wrapper (thêm HLK loader + audit log)
node HLK/chain/hlk_wrappers/verify-first-wrapper.mjs <BRD.md>

# Shim (.devin, vẫn work backward compat)
py .devin/scripts/verify_first_cli.py <BRD.md>  # → re-export từ HLK.chain
```

### 4.2 Python API
```python
import sys
sys.path.insert(0, "HLK")
from chain import (
    BRD, parse_brd_file, make_scenarios_from_brd,
    generate_rubric_file, generate_from_rubric_file,
    run_scenario, should_auto_merge, should_auto_merge,
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

### 4.3 Node integration
```javascript
import { spawn } from "node:child_process";
const child = spawn("py", ["HLK/chain/verify_first_cli.py", "BRD.md", "--out-dir", "./out"]);
```

---

## 5. Migration guide (từ .devin sang HLK)

### 5.1 Nếu bạn đang ở .devin/
- Code cũ vẫn work (shim re-export tự động)
- Để migrate sang HLK: đổi imports từ `from brd_schema` → `from HLK.chain.brd_schema`
- Hoặc dùng `.devin/scripts/X.py` (shim) — tương đương

### 5.2 Nếu bạn đang ở .commandcode/ hoặc .opencode/
- Pointer files trỏ về HLK
- Đọc `HLK/skills/verify-first/SKILL.md` để biết chi tiết
- Dùng CLI: `py HLK/chain/verify_first_cli.py`

### 5.3 Nếu bạn đang ở HLK/
- Đây là canonical source — không cần migrate

---

## 6. Sync mechanism

`HLK/scripts/sync_to_mirrors.py` đồng bộ HLK → .devin/ + .commandcode/ + .opencode/.

```bash
# Dry-run (chỉ in)
py HLK/scripts/sync_to_mirrors.py --dry-run --target all

# Real sync
py HLK/scripts/sync_to_mirrors.py --target all
py HLK/scripts/sync_to_mirrors.py --target devin
py HLK/scripts/sync_to_mirrors.py --target cmdc
py HLK/scripts/sync_to_mirrors.py --target opencode
```

**Quan trọng**:
- **1 chiều**: HLK → mirrors (KHÔNG BAO GIỜ sync ngược)
- **KHÔNG xóa** file ở mirror — chỉ thêm file mới hoặc update file HLK có sẵn
- **Idempotent**: chạy nhiều lần OK
- **Audit log**: `HLK/reports/sync_<date>.jsonl`

---

## 7. Cross-platform guarantee

Tất cả scripts ở HLK/chain/ dùng `HLK/chain/_platform_utils.py`:
- `get_python_cmd()` → "py" (Windows) hoặc "python3" (POSIX)
- `is_windows()` / `is_macos()` / `is_linux()` / `is_posix()`
- `run_python(args)` — wrapper subprocess cross-platform
- `ensure_utf8_output()` — fix Windows console encoding

Verify: chạy `tests/test_platform_utils.py` (12 tests pass trên Windows).

---

## 8. Security (6 fixes đã apply)

1. **P0 cc_cli_path allowlist** — `_validate_cc_cli_path` reject shell metachars
2. **P1 human confirm** — `should_auto_merge(require_human_confirm=True)`
3. **P1 secret scan** — 8 patterns ở `secret_scanner.py`, wired vào `live_auto_merge`
4. **P1 audit path validation** — chỉ ghi vào `.devin/state/`
5. **P1 log rotation** — `rotate_audit_log` khi file > 10MB
6. **P1 prompt redaction** — `redact()` secrets trước khi gửi CC
7. **P2 prompt injection protection** — `sanitize()` trước redteam

---

## 9. Tests (38+ tests)

- `tests/test_platform_utils.py` (12) — cross-platform
- `tests/test_migration_diff.py` (4) — HLK cover 17 modules
- `tests/test_hlk_config.py` (6) — config loader + fallback
- `tests/test_hlk_skill_pointer.py` (5) — pointer files
- `tests/test_provider_config.py` (4) — opencode.json + AGENTS.md
- `tests/test_sync_to_mirrors.py` (6) — sync không xóa file ở mirror
- `tests/hlk/test_verify_first_loader.cjs` (10, Node) — HLK loader

Plus 194 tests cũ (verify-first chain) vẫn pass với shim.

---

## 10. References

- `HLK/docs/migration-diff.md` — diff .devin vs HLK (auto-generated)
- `HLK/reports/verify-first-consolidation-redteam.md` — 6 personas review
- `~/.commandcode/plans/consolidate-to-hlk.md` — implementation plan
- `HLK/skills/verify-first/SKILL.md` — canonical skill
- `AGENTS.md` (root) — HLK mandate section
- `opencode.json` — provider config

## 11. Decision log

| Date | Decision | Reason |
|---|---|---|
| 2026-08-27 | HLK = source of truth | User directive |
| 2026-08-27 | .devin = ngoại lệ, KHÔNG xóa | User directive: "không xóa các cài đặt trong .devin" |
| 2026-08-27 | Mirror 1 chiều HLK → providers | User directive: "KHÔNG sync ngược" |
| 2026-08-27 | Phần nào HLK có mà .devin không → reference | User directive |
| 2026-08-27 | Phần nào .devin có mà HLK không → clone | User directive |
