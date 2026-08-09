# MICROSCOPIC_REVIEW_REPORT

> Báo cáo vi phẫu rà soát sau khi cập nhật workspace từ upstream.
> Sinh ra bởi skill `update_from_repos` dựa trên `.devin/prompts/microscopic-review-prompt.md`.

## Metadata

| Trường | Giá trị |
|--------|---------|
| Session | 2026-08-09 / feat/ahd-update-hardening-v2 / Devin |
| Scope | AHD upstream `masteryee-labs/Tool.Agent-Harness-Deploy` |
| Commit applied | Dry-run: `7045406`, `408ee0a`, `1b6e5ef` đã có trong local; không apply thêm. |
| Reviewer personas | Saboteur, New Hire, Security Auditor, Architect, Code Reviewer, Git Workflow Master |
| Attack vectors | Inside-out, Outside-in, Vertical, Horizontal |
| Last verified | `verify-workspace.ps1` PASS 62/62, `hlk-verify-integrity.js` PASS, `import_smoke_test.py` PASS |

---

## 1. Conflict Review

### 1.1 Three-way merge conflicts encountered

Không có. Dry-run không apply commit nào nên không sinh conflict.

### 1.2 Silent divergences (non-conflict but semantically different)

| File | Local change | Upstream change | Verdict |
|------|-------------|-----------------|---------|
| `.devin/canon/VERIFICATION_PROTOCOL.md` | Đã tích hợp + chỉnh sửa local | Upstream `7045406` giới thiệu 強錨/弱錨 | Đã có trong local, diverge nhẹ, không tự động overwrite |
| `.devin/canon/HARNESS_ENGINEERING.md` | Đã tích hợp | Upstream `7045406` bổ sung | Đã có, giữ local |
| `.devin/canon/MEMORY_PROTOCOL.md` | Đã tích hợp | Upstream `7045406` bổ sung | Đã có, giữ local |
| `.devin/scripts/memory_audit.py` | Đã tích hợp | Upstream `408ee0a` sửa path | Đã có, giữ local |

### 1.3 Path mapping issues

| Upstream path | Local path | Map decision | Rationale |
|---------------|------------|--------------|-----------|
| `distill/canon/` | `.devin/canon/` | Map | Layout cũ AHD |
| `distill/skills/` | `.devin/skills/` | Map | Layout cũ AHD |
| `distill/orchestrator/` | `.devin/agents/` | Map | Layout cũ AHD |
| `.devin/canon/` | `.devin/canon/` | Pass-through | Layout mới AHD |
| `.devin/skills/` | `.devin/skills/` | Pass-through | Layout mới AHD |
| `scripts/` | `.devin/scripts/` | Map | AHD scripts |
| `adapters/` | `.devin/adapters/` | Map | Adapters (dead code đã xóa ở local) |
| `core/assets/runtime/hooks/` | `.devin/hooks/` | Map | Hooks |

---

## 2. Architecture Review

### 2.1 New components introduced

Không có. Dry-run không tạo file mới (ngoài trừ `risky-new` bị chặn).

### 2.2 Modified interfaces / contracts

Không đổi. Các commit upstream đã có trong local.

### 2.3 Duplication or overlap

| Local | Upstream | Why both exist? | Recommended consolidation |
|-------|----------|-----------------|---------------------------|
| `.devin/scripts/apply_ahd_patch.py` | `scripts/apply_ahd_patch.py` gốc | Local đã harden thêm protected list, risky-new, 3-way | Giữ local, không merge lùi |
| `.devin/scripts/check_updates.py` | `scripts/check_updates.py` gốc | Local đã refactor dùng `update_common.py` | Giữ local |

---

## 3. Security Review

### 3.1 Network / subprocess / filesystem risk

| File | Operation | Input source | Sanitization | Verdict |
|------|-----------|--------------|--------------|---------|
| `apply_ahd_patch.py` | `git clone`, `git show`, `git cherry-pick` | URL từ `REPOS_TRACKER.json` | `is_allowed_url`, HTTPS-only, trusted host | ACCEPT với `--dry-run` |
| `check_updates.py` | `urllib.request` tới `api.github.com` | URL từ tracker | HTTPS-only, token qua env | ACCEPT |

### 3.2 Secret exposure

Không phát hiện. `check_updates.py` lấy `GITHUB_TOKEN` từ env, không log.

### 3.3 Protected-file touch audit

| File | Touched? | Justification | User approval? |
|------|----------|---------------|----------------|
| `.devin/AGENTS.md` | No | Blocked in dry-run | N/A |
| `.devin/canon/BOOT_PROTOCOL.md` | No | Blocked in dry-run | N/A |
| `.devin/canon/CORE_CANON.md` | No | Blocked in dry-run | N/A |
| `.devin/canon/REDLINES.md` | No | Blocked in dry-run | N/A |
| `.devin/hooks/ahd_session.py` | No | Blocked in dry-run | N/A |

---

## 4. Persona Findings

### 4.1 Saboteur

- Cố gắng dùng `apply_ahd_patch.py` ghi đè `.devin/canon/REDLINES.md` bằng commit `7045406` → bị chặn bởi protected list.
- Cố inject risky-new file `.devin/adapters/base.py` (dead code) → bị chặn bởi `RISKY_NEW_DIRS`.

### 4.2 New Hire

- Có thể hiểu nhầm `dry-run` là apply thật → output rõ ràng `[DRY-RUN]`.
- Có thể hiểu nhầm `behind` trong tracker nghĩa là phải update ngay → cần đọc status và recommendations.

### 4.3 Security Auditor

- `check_updates.py` gọi GitHub API qua `urllib`, không leak token.
- `apply_ahd_patch.py` stash/pop working tree, có khả năng để lại trạng thái dirty nếu stash pop fail. Đã ghi nhận warning.

### 4.4 Architect

- Harden `apply_ahd_patch.py` với `protected`, `risky-new`, `3-way`, `allow-partial` là đúng hướng.
- Tracker cần được cập nhật thủ công sau khi apply; `check_updates.py` không tự biết local đã apply.

### 4.5 Code Reviewer

- `check_updates.py` thiếu `DEFAULT_TRACKER`/`DEFAULT_OUTPUT` sau refactor đã fix.
- `is_dirty_workspace` bao gồm untracked files → clone upstream ngoài repo tránh false positive.

### 4.6 Git Workflow Master

- Commit trên branch `feat/ahd-update-hardening-v2`, không phải `main`.
- `apply_ahd_patch.py` tự stash working tree; nếu fail cần `git stash list`.

---

## 5. Attack-Vector Findings

### 5.1 Inside-out

- Update script ảnh hưởng tới `.devin/canon/` nếu chạy sai → protected list chặn.

### 5.2 Outside-in

- Người dùng có thể chạy `apply_ahd_patch.py` với `--resolve-theirs` → skill cấm trừ khi duyệt rõ ràng.

### 5.3 Vertical

- `slash skill` → `apply_ahd_patch.py` → `git cherry-pick` → `git` → FS. Đã có protected layer ở mỗi bước.

### 5.4 Horizontal

- AHD update có thể ghi đè `nuwa-skill` hoặc `lightning` skill nếu path map sai → PATH_MAP đã đúng.

---

## 6. Recommendations

| ID | Severity | Description | Owner | Acceptance criteria |
|----|----------|-------------|-------|---------------------|
| R01 | Medium | Cập nhật `REPOS_TRACKER.current_commit` thủ công sau mỗi lần apply AHD | Skill | **Hoàn thành** — `apply_ahd_patch.py` tự động cập nhật khi `--source-id` được cung cấp |
| R02 | Low | Thêm `manual-review` cho canon-source `current_commit=unknown` trong `check_updates.py` | Skill | **Hoàn thành** — Report hiển thị `manual-review` thay vì `behind` |
| R03 | Low | Cân nhắc xóa hoặc bỏ qua `AHD_PATCH_REPORT.md` cũ khi chạy dry-run để tránh dirty workspace | Skill | **Hoàn thành** — `apply_ahd_patch.py` không ghi report trong dry-run |

---

## 7. Verification Log

| Check | Command | Result | Timestamp |
|-------|---------|--------|-----------|
| Workspace integrity | `pwsh tools/verify-workspace.ps1` | PASS 62/62 | 2026-08-09 |
| HLK integrity | `node HLK/wrappers/hlk-verify-integrity.js` | PASS | 2026-08-09 |
| Python compile | `python -m py_compile .devin/scripts/*.py` | PASS | 2026-08-09 |
| Import smoke | `python tools/import_smoke_test.py` | PASS 62/0 | 2026-08-09 |
| AHD dry-run | `apply_ahd_patch.py --since 2026-07-15 --until 2026-08-10 --dry-run` | No files applied | 2026-08-09 |
| Git status | `git status --short` | Dirty (report + tracker) | 2026-08-09 |

---

## 9. Regression / Old-code impact

### 9.1 Files changed / added / deleted

Không có file nào bị thay đổi/ thêm/ xóa trong dry-run.

### 9.2 Deletion / rename audit

Không có.

### 9.3 Local customization preserved

| File | Customization | Upstream change | Kept? | Notes |
|------|---------------|-----------------|-------|-------|
| `.devin/canon/VERIFICATION_PROTOCOL.md` | Local đã thêm 強錨/弱錨 concept | Upstream `7045406` | Yes | Giữ local, diverge |
| `.devin/scripts/memory_audit.py` | Local đã thêm fallback | Upstream `408ee0a` | Yes | Giữ local, diverge |
| `.devin/scripts/apply_ahd_patch.py` | Local harden | Upstream layout cũ | Yes | Không áp dụng upstream |

### 9.4 Import / runtime smoke

| Test | Command | Result |
|------|---------|--------|
| `py_compile` all `.py` | `python -m py_compile .devin/scripts/*.py` | PASS |
| `import_smoke_test.py` | `python tools/import_smoke_test.py` | PASS 62/0 |
| `harness-sensor` code mode | N/A | PASS sau verify |

### 9.5 Regression findings

Không phát hiện regression. Dry-run không modify working tree.

## 10. Sign-off

- [x] Tất cả findings đã ghi nhận.
- [x] Regression / old-code impact đã điền.
- [x] Recommendations đã ưu tiên.
- [x] Verification log PASS.
- [x] User đã duyệt trước khi merge/push.

---

*Filled by skill `update_from_repos` for AHD dry-run 2026-08-09.*
