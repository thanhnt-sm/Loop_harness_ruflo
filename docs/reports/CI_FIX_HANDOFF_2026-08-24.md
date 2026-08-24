# Session Handoff — Fix CI Workflow Failures (Dependabot + Supply-Chain)

> Ngày: 2026-08-24
> Trạng thái: đã fix root cause, CHƯA commit/push. Cần session mới verify + commit + push.

---

## 1. Vấn đề

Hai nhóm CI workflow fail trên `main` (merge các dependabot PR):

| Run | Workflow | Step fail |
|-----|----------|-----------|
| #16 filelock-3.32.3 | supply-chain | `Install deps (hash-pinned, fail on drift)` |
| #16 filelock-3.32.3 | CI/CD Pipeline | `Run pytest` |
| #17 pydantic-core-2.48.0 | supply-chain + CI | tương tự |

Danh sách đầy đủ ~25 run fail (do user liệt kê) gồm nhiều commit `debug:`/`fix:` lịch sử — đã được fix dần, KHÔNG cần xử lý lại.

## 2. Root causes (đã xác định chính xác)

1. **Dependabot PR #17 bump `pydantic-core` 2.46.4 → 2.48.0 độc lập**:
   `pydantic==2.13.4` pin `pydantic-core==2.46.4` CHÍNH XÁC (`==`). Bump lệch → `pip install --require-hashes` fail `ResolutionImpossible`. Đây là nguyên nhân trực tiếp của step `Install deps` fail.

2. **Dependabot PR #16 bump `filelock` 3.12.4 → 3.32.3**:
   Vi phạm pin documented `<3.13` (filelock 3.13+ eager import asyncio ~6s → hook vượt timeout 2.5s). Cũng làm SBOM drift.

3. **SBOM (`sbom/python.sbom.json`) stale** so với lock (filelock 3.32.2, typing-inspection 0.4.2, typing_extensions 4.15.0, cffi 2.1.0, cryptography 49.0.0, annotated-types 0.7.0).

4. **CI pytest fail `test_workspace_layout_gate_blocks_root_markdown`** (`DID NOT RAISE SystemExit`): đã được fix bởi PR #20 (`fix: regenerate hook hash baseline for pre_tool_workspace.py` — sửa `pre_tool_workspace.py`, bỏ 7 dòng). Sau merge không còn fail. **Không cần sửa thêm.**

## 3. Giải pháp đã thực hiện (chưa commit)

### 3.1 Revert 2 PR dependabot
- `git checkout 3b02e67 -- requirements-lock.txt pyproject.toml` (đã STAGED)
  - `filelock==3.12.4` (về đúng pin), `pydantic-core==2.46.4` (khớp pydantic 2.13.4)
  - pyproject: `filelock>=3.0,<3.13` (bỏ `<3.33`)
- Verified: `pip install --require-hashes --dry-run -r requirements-lock.txt` → PASS (hết conflict).

### 3.2 Fix SBOM (sbom/python.sbom.json)
Cập nhật 6 component cho khớp lock: filelock 3.12.4, annotated-types 0.8.0, cffi 2.1.1, cryptography 50.0.0, typing-inspection 0.4.4, typing_extensions 4.16.0.

### 3.3 dependabot.yml — ignore/group rules
Thêm `ignore` cho: `filelock`, `pydantic-core`, `typing-extensions`, `typing-inspection` + `groups.pydantic` (patterns `pydantic*`). Ngăn bump độc lập phá hash-pinned lock.

### 3.4 tools/check_deps.py (NEW — guard tool)
Kiểm deterministic (no network):
- filelock thỏa pin `<3.13` (parse pyproject.toml)
- pydantic-core khớp version pydantic yêu cầu (importlib.metadata)
- SBOM lock-relevant components khớp lock (chống SBOM drift)

Exit 0 = PASS, 1 = FAIL. Đã test: lock đúng → EXIT 0; lock giả (filelock 3.32.3 + pydantic-core 2.48.0) → EXIT 1 với message rõ.

### 3.5 Wire guard vào CI + pre-commit
- `supply-chain.yml`: thêm step `Check dependency lock consistency` (chạy `python tools/check_deps.py`) TRƯỚC `Install deps`.
- `ci.yml`: pin `filelock<3.13` trong dòng `pip install` (trước đó unpinned → cài 3.32.x).
- `.githooks/pre-commit`: thêm **Gate 5 — Dependency lock consistency** (chỉ chạy khi stage `requirements-lock.txt`/`pyproject.toml`/`sbom/`).

### 3.6 AGENTS.md — section "Dependency Management (BẮT BUỘC)"
6 quy tắc cho AI agent: không sửa tay lock, filelock pin `<3.13`, pydantic-core pin `==` bởi pydantic, SBOM khớp lock, chạy `check_deps.py`, không commit debug noise.

## 4. Files đã thay đổi (MY changes — phân biệt với background loop)

**Thay đổi của tôi (cần commit/push):**
- `requirements-lock.txt` (staged) — revert filelock + pydantic-core
- `pyproject.toml` (staged) — revert `<3.33` → `<3.13`
- `sbom/python.sbom.json` — fix 6 component stale
- `.github/dependabot.yml` — ignore/group rules
- `.github/workflows/supply-chain.yml` — step check_deps
- `.github/workflows/ci.yml` — pin filelock<3.13
- `.githooks/pre-commit` — Gate 5
- `AGENTS.md` — section Dependency Management
- `tools/check_deps.py` (NEW)

**Background AHD loop đang sửa (KHÔNG commit):**
- `.devin/hook_order.json`, `.devin/loop_state.md`, `.devin/loop_state_archive.md`
- `docs/reports/COST_DASHBOARD.md`, `docs/reports/HARNESS_ISSUES_2026-08-24.md`

## 5. Đã verify

- `python tools/check_deps.py` → PASS (EXIT 0)
- `pip install --require-hashes --dry-run -r requirements-lock.txt` → PASS (hết ResolutionImpossible)
- `python tools/check_governance.py` → 0 errors, 1 warning pre-existing (plan fix-14... thiếu execution report, KHÔNG liên quan)
- pytest: đã chạy ~52% + `-x` đến 2161 passed, fail duy nhất `test_workspace_layout_gate_blocks_root_markdown` đã được PR #20 fix (sau merge pass). Chưa chạy hết full suite đến cuối.

## 6. TODO còn lại (session mới)

- [ ] Chạy full `pytest tests/ -q --tb=short --override-ini="addopts=-ra"` tới cuối, xác nhận 0 fail (chỉ còn skip đã biết).
- [ ] Commit (message tiếng Anh, theo git convention). Gợi ý:
  - `fix(deps): revert dependabot filelock+pydantic-core bumps that broke --require-hashes`
  - `chore(ci): add dependency lock consistency guard + dependabot ignore rules`
- [ ] Push + theo dõi 2 workflow (supply-chain + CI) xanh.
- [ ] (Tuỳ chọn) nếu `check_governance.py --plan-act` cần, viết execution report cho plan đang có.
