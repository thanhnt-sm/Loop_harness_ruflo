---
name: update_from_repos
description: >-
  Update workspace an toàn theo các repo được liệt kê trong REPOS.md.
  Phát hiện upstream mới, đánh giá rủi ro, cherry-pick / copy từng phần, bảo vệ HLK và local upgrades (U01–U70),
  chạy verify, tạo báo cáo MICROSCOPIC_REVIEW_REPORT.md.
triggers:
  - "cập nhật từ REPOS.md"
  - "update from repos"
  - "check updates"
  - "merge upstream"
  - "cập nhật repo"
  - "update nuwa-skill"
  - "update AHD"
  - "cherry-pick AHD"
---

# update_from_repos — Cập nhật workspace từ upstream REPOS.md

> Cập nhật upstream là công việc **cực kỳ dễ gây hỏng kiến trúc**. Skill này buộc phải đi từng bước, verify sau mỗi bước, và **không bao giờ** bulk-merge upstream AHD.

## Cách gọi

```
/update_from_repos                       # Kiểm tra + update toàn bộ repo trong REPOS.md
/update_from_repos <repo-id>             # Chỉ update 1 repo
/update_from_repos --check               # Chỉ kiểm tra, không apply
/update_from_repos --plan-only           # Chỉ viết plan, chờ duyệt
/update_from_repos --since YYYY-MM-DD --until YYYY-MM-DD
```

`/update-from-repos` cũng được hiểu là alias.

**Ví dụ:**

```
/update_from_repos
/update_from_repos nuwa-skill
/update_from_repos ahd-main-engine
/update_from_repos --check
```

## Khi nào tự trigger (model)

- User nói bất kỳ từ khóa trong `triggers`.
- User hỏi về "cập nhật repo", "merge upstream", "cherry-pick AHD".
- `check_updates.py` phát hiện repo behind và user muốn xử lý tiếp.
- **Không tự trigger** khi user chỉ hỏi thông tin / giải thích.

## 1. Mục tiêu

Tự động hóa quy trình cập nhật workspace theo các repo trong `REPOS.md` một cách an toàn:

1. Phát hiện upstream mới.
2. Phân tích rủi ro với từng repo.
3. Chọn chiến lược merge phù hợp (direct-copy, surgical-cherry-pick, manual-canon-update).
4. Áp dụng từng phần nhỏ nhất có thể.
5. Verify sau mỗi lần áp dụng.
6. Tạo `MICROSCOPIC_REVIEW_REPORT.md` để ghi lại conflict, architecture, solution review.

## 1.1 Giải pháp tóm tắt — 7 lớp phòng thủ

> **Không làm hỏng code cũ, không làm chết code cũ.** Giải pháp là 7 lớp kiểm soát liên tiếp:

| Lớp | Tên | Nhiệm vụ |
|-----|-----|----------|
| 1 | **Pre-flight** | Branch riêng `update-repos-*`, backup, baseline verify. |
| 2 | **Detect** | `check_updates.py`, `show_diff.py`, `--dry-run`, xác định impact zone. |
| 3 | **Control** | Protected files, no overwrite without diff, no delete, no rename mất kiểm soát, preserve local customization. |
| 4 | **Apply** | Surgical cherry-pick/copy từng file, không bulk, không `--auto-commit`, không `--resolve-theirs` tự động. |
| 5 | **Verify** | `verify-workspace.ps1`, `hlk-verify-integrity.js`, `py_compile`, `tools/import_smoke_test.py`, `harness-sensor`, `git diff --stat`. |
| 6 | **Decide** | Pass mới commit; fail → rollback. |
| 7 | **Rollback + Report** | `git checkout -- .`, `git reset --hard HEAD~N` trên branch update, restore backup, điền `MICROSCOPIC_REVIEW_REPORT.md` mục 9. |

## 2. Context bắt buộc đọc trước

Trước khi làm bất kỳ update nào, đọc:

- <ref_file file="REPOS.md" />
- <ref_file file=".devin/metadata/REPOS_TRACKER.json" />
- <ref_file file=".devin/ATTRIBUTION.md" />
- <ref_file file=".devin/prompts/microscopic-review-prompt.md" />
- <ref_file file="AGENTS.md" /> (top red lines)
- <ref_file file="CLAUDE.md" /> (no auto commit/merge/push)

## 3. Workflow 6 phase

### Phase 0 — Pre-flight & branch

1. `git status --short` — workspace phải sạch hoặc chỉ có thay đổi được user duyệt.
2. `git checkout main`.
3. Tạo branch tên `update-repos-<YYYYMMDD>`.
4. Backup workspace dạng zip hoặc snapshot (dùng `tools/verify-workspace.ps1` hoặc tự zip toàn bộ repo trừ `.git` vào `backups/`).
5. Chạy baseline verify:
   - `pwsh tools/verify-workspace.ps1`
   - `node HLK/wrappers/hlk-verify-integrity.js`
   - `.venv/bin/python .devin/scripts/hook_integrity.py --verify` nếu có.
6. Nếu baseline FAIL, **dừng ngay**, sửa trước khi update.

### Phase 1 — Discover & inventory

1. Chạy `.venv/bin/python .devin/scripts/check_updates.py --tracker .devin/metadata/REPOS_TRACKER.json`.
2. Đọc `UPDATES_REPORT.md` hoặc output để biết repo nào behind.
3. Phân loại từng repo theo **Decision matrix**:

| Repo type | Source examples | Strategy | Default path map | Skip pattern | User approval |
|-----------|-----------------|----------|------------------|--------------|---------------|
| **vendored-skill** | `nuwa-skill`, `comment_checker` | `merge_updates.py` direct-copy | root → `.devin/skills/<id>/` | `promo/`, `examples/` ngoài 3 cũ, large assets | Không nếu chỉ copy core |
| **main engine** | `masteryee-labs/Tool.Agent-Harness-Deploy` | `apply_ahd_patch.py` surgical cherry-pick | `.devin/canon/` → `.devin/canon/`, `.devin/skills/` → `.devin/skills/`, `.devin/agents/` → `.devin/agents/`, `scripts/` → `.devin/scripts/`, `adapters/` → `.devin/adapters/`, `core/assets/runtime/hooks/` → `.devin/hooks/` | `Docs/`, `README.md`, `.gitignore`, `tests/`, `promo/`, `.github/` | Có, từng batch commit |
| **canon-source** | `caveman`, `superpowers`, `loop-engineering` | manual-canon-update | `.devin/canon/` hoặc file canon tương ứng | Toàn bộ nếu concept đã tồn tại | Có, từng canon |

> **Lưu ý path map**: upstream AHD có thể dùng layout cũ (xem `apply_ahd_patch.py` `PATH_MAP` để biết ánh xạ sang `.devin/`). `apply_ahd_patch.py` đã hỗ trợ cả layout `.devin/` và layout cũ.

### Phase 2 — Risk analysis per repo

Với mỗi repo behind, trả lời:

1. **Impact zone là gì?** (file/thư mục nào thay đổi)
2. **Có đụng protected không?**
   - `.devin/hooks/*`
   - `.devin/config.json`, `.devin/mcp_config.json`
   - `.devin/canon/BOOT_PROTOCOL.md`, `CORE_CANON.md`, `REDLINES.md`
   - `.devin/AGENTS.md`, `.devin/AGENTS_full.md`
   - `HLK/`
   - `.claude/settings.json`
   - `.gitignore`, `.gitattributes`
   - `.env`
3. **Có mất U01–U70 không?** Kiểm tra `UPGRADE_TRACKER.json` / `UPGRADE_TRACKER_V2.json`.
4. **Có thay đổi cấu trúc path không?** (upstream `.devin/` → local `.devin/`, `scripts/` → `.devin/scripts/`)
5. **Có file mới ở thư mục rủi ro không?** (`adapters/`, `scripts/`, `tests/`)
6. **Có xóa, rename, hoặc di chuyển file cũ không?** Mỗi deletion phải được kiểm soát — ưu tiên skip, không tự động delete.
7. **Có ghi đè local customization không?** Kiểm tra các file local đã chỉnh (`.devin/skills/nuwa-skill/ATTRIBUTION.md`, `UPGRADE_TRACKER*.json`, `.devin/config.json`, examples đã cắt).

### Phase 3 — Plan & approval

1. Viết plan ngắn: repo nào update trước, chiến lược gì, thứ tự commit.
2. Với AHD, **không bao giờ bulk merge**. Phải list từng commit từ upstream trong khoảng `current..upstream`.
3. Hỏi user duyệt plan trước khi execute, trừ khi user đã ra lệnh tự động rõ ràng.

### Phase 4 — Execute per repo

#### 4.1 vendored-skill (nuwa-skill)

- Clone upstream tạm.
- Diff local vs upstream: `.venv/bin/python .devin/scripts/show_diff.py --source-id nuwa-skill`.
- Chạy dry-run trước: `.venv/bin/python .devin/scripts/merge_updates.py --source-id <id> --dry-run`.
- Liệt kê **tất cả file đã tồn tại ở target** mà upstream cũng có. Phân loại:
  - **core file** (`SKILL.md`, `README*.md`, `COMMUNITY.md`, `CONTRIBUTING.md`, `LICENSE`, `references/`, `scripts/`): copy nếu upstream mới hơn.
  - **local customization** (`ATTRIBUTION.md`, ví dụ cũ, file user đã sửa): **không tự động overwrite** — diff + báo user từng file.
- **Không copy** `promo/`, large images, examples ngoài 3 examples đã có (trừ khi user yêu cầu).
- **Không xóa** file ở target chỉ vì upstream không còn.
- Cập nhật `ATTRIBUTION.md` bằng cách *append* thông tin upstream mới, không xóa phần local.
- Update `REPOS.md`.
- Commit: `chore: update <repo-id> to <sha>`.
- Chạy `verify-workspace.ps1` + `hlk-verify-integrity.js` + `tools/import_smoke_test.py` (nếu skill có `.py`).

#### 4.2 AHD main engine (surgical cherry-pick)

- Clone upstream tạm: `git clone --depth 100 <url> <temp>`. Nếu khoảng commit > 100, tăng depth hoặc clone full.
- List commit: `git log --since=<last> --until=<today> --oneline --reverse`.
- Với mỗi commit:
  1. `git show <sha> --stat` để biết files.
  2. Map path upstream → local (vd `.devin/canon/` → `.devin/canon/`, `.devin/skills/` → `.devin/skills/`, `.devin/agents/` → `.devin/agents/`, `scripts/` → `.devin/scripts/`, `adapters/` → `.devin/adapters/`, `core/assets/runtime/hooks/` → `.devin/hooks/`).
  3. Skip: `Docs/`, `README.md`, `.gitignore`, `tests/`, `promo/`, `.github/`.
  4. Nếu commit chứa protected file → dùng `apply_ahd_patch.py --allow-partial` để chỉ apply non-protected.
  5. Không dùng `--auto-commit`; apply vào working tree, review rồi mới commit thủ công.
  6. Không dùng `--resolve-theirs` trừ khi user đã đọc diff và đồng ý rõ ràng.
  7. Nếu file diverged → dùng `apply_ahd_patch.py --3way`.
  8. Kiểm tra danh sách `skipped` của `apply_ahd_patch.py`: **không được có `delete:`** — nếu có, xác nhận đó là deletion do upstream và quyết định có skip không.
  9. Sau khi apply, chạy `py_compile` và **import smoke test** cho mọi file `.py` mới/đổi.
  10. Kiểm tra `git diff --stat` — không có file cũ bị xóa bất ngờ.
  11. Commit từng cherry-pick: `cherry-pick AHD <sha>: <msg>`.
  12. Verify + HLK + import smoke sau mỗi commit.

#### 4.3 canon-source

- Chỉ update khi commit upstream có khái niệm mới hoàn toàn không có trong local canon.
- Không tự động overwrite `.devin/canon/*.md`.
- Hỏi user từng canon.

### Phase 5 — Verification

Sau mỗi repo / commit:

1. `pwsh tools/verify-workspace.ps1` — PASS.
2. `node HLK/wrappers/hlk-verify-integrity.js` — PASS.
3. `.venv/bin/python -m py_compile` với mọi file `.py` mới/đổi.
4. `.venv/bin/python tools/import_smoke_test.py` (hoặc import test tương đương) — PASS.
5. `harness-sensor` code mode nếu có thay đổi `.py`/`.md`.
6. `git diff --stat` — kiểm tra không có file cũ bị xóa bất ngờ.
7. `git status --short` — phải sạch hoặc chỉ có file dự kiến.
8. Kiểm tra `UPGRADE_TRACKER.json` / `UPGRADE_TRACKER_V2.json` — U01–U70 không bị mất hoặc downgrade.

Nếu FAIL → rollback bằng `git checkout -- .` hoặc restore backup, tìm root cause, fix, chạy lại.

### Phase 5.5 — Escalation & stop conditions

Dừng ngay và báo user khi:

1. Bất kỳ verify nào FAIL.
2. Protected file bị đụng.
3. Conflict 3-way không thể giải quyết tự động.
4. Upstream commit chứa destructive command (`rm -rf`, `DROP`, `TRUNCATE`, format disk).
5. User nói "dừng", "hủy", "cancel", "stop".
6. Không xác định được path map an toàn.
7. Branch hiện tại là `main`/`master` mà không có `--force` rõ ràng.

### Phase 5.6 — Rollback

Nếu bất kỳ verify nào FAIL hoặc user yêu cầu quay lại:

1. **Không panic commit**.
2. Chưa commit: `git checkout -- .` hoặc `git restore .` để phục hồi working tree.
3. Đã commit trên branch update: `git revert <sha>` hoặc `git reset --hard HEAD~N` — **chỉ trên branch update, chưa merge/push**.
4. Nếu git không cứu được: restore từ backup trong `backups/`.
5. Chạy lại verify để xác nhận sạch.
6. Ghi lý do vào `MICROSCOPIC_REVIEW_REPORT.md`.

### Phase 6 — Microscopic review & report

1. Chạy prompt từ <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.devin\prompts\microscopic-review-prompt.md" />.
2. Tạo / cập nhật <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.devin\metadata\MICROSCOPIC_REVIEW_REPORT.md" />.
3. Report phải có:
   - Conflict review
   - Architecture review
   - Security review
   - Inside-out / outside-in / vertical / horizontal findings
   - Recommendations prioritized
4. Không sửa code trong phase review trừ khi user duyệt từng fix.

## 4. Red Team — attack vectors & failure modes

Skill này phải tự vấn đề ở mọi khâu. Áp dụng 6 persona:

### Saboteur

- "Nếu tôi là kẻ phá hoại, tôi sẽ cố gắng dùng `apply_ahd_patch.py` để ghi đè `.devin/hooks/ahd_session.py` bằng cách đánh lừa protected list." → protected list phải include `.devin/hooks/` prefix, không chỉ 1 file.
- "Tôi sẽ cố gắng đưa upstream commit chỉ rename file protected thành unprotected rồi apply." → verify sau mỗi commit phát hiện.
- "Tôi sẽ inject `rm -rf` qua `apply_ahd_patch.py` hoặc một script mới." → review mọi script mới, tìm `shutil.rmtree`, `os.remove`, `subprocess` trước khi chạy.

### New Hire

- "Tôi sẽ chạy `apply_ahd_patch.py` với path sai, nó clone sai repo." → validate URL với `REPOS_TRACKER.json` trước.
- "Tôi sẽ quên verify sau mỗi commit." → workflow bắt buộc verify.
- "Tôi sẽ không backup." → Phase 0 bắt buộc backup.

### Security Auditor

- Secret/API key trong `check_updates.py`? Phải lấy từ `GITHUB_TOKEN` env, không hardcode.
- `apply_ahd_patch.py` chạy `subprocess` với path đầu vào? Validate path, chặn `../`.
- `apply_ahd_patch.py` tạo file ở đâu? Phải nằm trong `.devin/` và không đè lên protected.
- `apply_ahd_patch.py` có đọc `registry.json` từ đâu? Có path traversal không?

### Architect

- `adapters/` layer mới xung đột với hooks/scripts cũ? Có 2 cách làm cùng việc?
- Domain-adapters 9 file có convention chung? Có `skill_id`/`trigger` trùng?
- `COMMANDER.md` bị cắt 111 dòng, mất chỉ dẫn nào? So sánh với bản cũ bằng `git show`.

### Code Reviewer

- Mọi script `.py` mới phải `py_compile` PASS.
- Error handling cho I/O, network, `git` subprocess.
- Idempotent — chạy lại `apply_ahd_patch.py` có an toàn không?
- File `MICROSCOPIC_REVIEW_REPORT.md` không được chứa secret.

### Git Workflow Master

- `git status` phải sạch trước khi bắt đầu.
- Không force-push, không `git reset --hard` tự động.
- Commit message phải rõ ràng: `chore:`, `feat:`, `cherry-pick AHD <sha>`.
- Push chỉ khi user yêu cầu rõ ràng.

### Regression Hunter

Persona chuyên tìm cách làm **code cũ bị hỏng hoặc biến mất** sau update:

- "Tôi sẽ update AHD với 1 commit xóa `.devin/hooks/post_tool_use.py` bằng cách rename nó. Nếu skill apply, file cũ sẽ mất và hook chain chết." → `apply_ahd_patch.py` skip deletion; kiểm tra `skipped` có `delete:`; verify `hooks/` vẫn còn.
- "Tôi sẽ dùng `merge_updates.py` copy `nuwa-skill` mới, nó sẽ overwrite `ATTRIBUTION.md` và 3 examples cũ đã được cắt gọn." → diff từng file tồn tại, preserve local customization.
- "Tôi sẽ dùng `--resolve-theirs` để ghi đè `COMMANDER.md` mà không review, cắt mất 111 dòng local upgrades." → cấm tự động `--resolve-theirs`.
- "Tôi sẽ tạo `adapters/base.py` mới import module `foo` mà local đã xóa/rename. Import smoke test sẽ bắt." → chạy import smoke sau mỗi commit.
- "Tôi sẽ chạy update trên `main` branch thay vì branch tạm, gây hỏng history." → Phase 0 tạo branch `update-repos-...`.
- "Tôi sẽ clone `--depth 100` nhưng AHD có 150 commit mới, bỏ sót 50 commit giữa, tạo ra bán update lệch pha." → tăng depth hoặc full clone khi cần.

## 5. Protected files & policies

**Tuyệt đối không đụng** trong quá trình update tự động:

- `.devin/hooks/*`
- `.devin/config.json`
- `.devin/mcp_config.json`
- `.devin/canon/BOOT_PROTOCOL.md`
- `.devin/canon/CORE_CANON.md`
- `.devin/canon/REDLINES.md`
- `.devin/AGENTS.md`
- `.devin/AGENTS_full.md`
- `HLK/`
- `.claude/settings.json`
- `.gitignore`
- `.gitattributes`
- `.env`, `*.env`, `secrets.*`

Nếu user yêu cầu update 1 file trong danh sách trên, phải:

1. Backup file.
2. Hiển thị diff đầy đủ.
3. Giải thích tác động.
4. Hỏi user đồng ý từng dòng.

## 6. Tools & scripts

| Script | Mục đích |
|--------|----------|
| `.devin/scripts/check_updates.py` | Kiểm tra upstream mới, cập nhật `REPOS_TRACKER.json` và `UPDATES_REPORT.md` |
| `.devin/scripts/show_diff.py` | Diff local vs upstream cho 1 source |
| `.devin/scripts/merge_updates.py` | Merge direct-copy cho vendored-skill, có backup + rollback |
| `.devin/scripts/apply_ahd_patch.py` | Surgical cherry-pick AHD, map path, 3-way merge, skip protected |
| `tools/verify-workspace.ps1` | Integrity check workspace |
| `HLK/wrappers/hlk-verify-integrity.js` | HLK layer check |

Tham số quan trọng của `apply_ahd_patch.py`:

- `--dry-run`: xem trước.
- `--allow-partial`: apply non-protected khi commit có protected.
- `--3way`: dùng `git merge-file` cho file diverged.
- `--resolve-theirs`: **chỉ dùng khi user đồng ý rõ ràng**, vì nó có thể ghi đè local upgrades.
- `--allow-risky-new`: tạo file mới trong `adapters/`, `scripts/` — **chỉ dùng khi user đồng ý rõ ràng**.

## 7. Output artifacts

Sau mỗi lần chạy skill, output gồm:

1. `UPDATES_REPORT.md` — tóm tắt repo nào behind.
2. `AHD_PATCH_REPORT.md` — từng commit AHD, file apply/skip.
3. `MICROSCOPIC_REVIEW_REPORT.md` — rà soát vi phẫu toàn bộ.
4. Commit log rõ ràng trên branch update.
5. `REPOS.md` cập nhật commit SHA.
6. `REPOS_TRACKER.json` cập nhật status/last_check.

## 8. Done criteria

- [ ] Mọi repo trong `REPOS.md` đã được kiểm tra status.
- [ ] Các repo behind đã được xử lý theo đúng strategy.
- [ ] Mỗi thay đổi đã commit riêng với message rõ ràng.
- [ ] `verify-workspace.ps1` PASS sau mỗi lần apply.
- [ ] `hlk-verify-integrity.js` PASS sau mỗi lần apply.
- [ ] `py_compile` PASS cho mọi file `.py` mới/đổi.
- [ ] `tools/import_smoke_test.py` PASS cho `.devin/scripts/` và `.devin/hooks/`.
- [ ] `git diff --stat` không có file cũ bị xóa bất ngờ.
- [ ] `git status` sạch.
- [ ] `UPGRADE_TRACKER*.json` không bị mất hoặc downgrade.
- [ ] `MICROSCOPIC_REVIEW_REPORT.md` đã tạo/cập nhật.
- [ ] Không có protected file bị đụng trừ khi user đồng ý.
- [ ] Không có local customization bị overwrite mà không diff.
- [ ] Không push trừ khi user yêu cầu.

## 9. Constraints

- **Không tự động `git push`, `git merge` vào `main`, `git reset --hard`, `rm -rf`.**
- **Không bulk-merge AHD.**
- **Không tự động overwrite protected files.**
- **Không thêm dependency mới mà không check.**
- **Mọi sửa code phải verify ngay lập tức.**
- **Báo user trước khi chạy bất kỳ command destructive nào.**

## 10. Trigger activation

Khi user nói bất kỳ từ khóa nào trong danh sách triggers, kích hoạt skill này và chạy theo đúng 6 phase. Nếu user nói "tự động", vẫn phải tuân thủ protected list và verify.

## 11. Regression / Old-code protection

> **Code cũ là tài sản.** Mục tiêu của update là thêm giá trị mới, không phải thay thế code cũ.

### 11.1 Nguyên tắc bất khả xâm phạm

- **Không xóa** file cũ chỉ vì upstream xóa.
- **Không rename** file cũ theo upstream nếu có import/reference cũ.
- **Không overwrite** file cũ mà không diff review.
- **Không downgrade** U01–U70 hoặc local upgrades.
- **Không chạy trực tiếp trên `main`**.

### 11.2 Kiểm soát overwrite

Với mọi file đã tồn tại ở target:

1. `show_diff.py` hoặc `git diff --no-index local upstream`.
2. Nếu chỉ upstream mới hơn (không đụng local customization) → overwrite.
3. Nếu có local customization → giữ local, append/báo user.
4. Nếu không chắc → dừng, hỏi user.

### 11.3 Kiểm soát deletion

- `apply_ahd_patch.py` mặc định **skip deletion** (`new_text is None` → `skipped.append(f"delete:{mapped}")`).
- `merge_updates.py` mặc định **không xóa** file target chỉ vì upstream không có.
- Nếu user yêu cầu xóa file cũ → hiển thị lý do, tìm references, hỏi từng file.

### 11.4 Kiểm soát rename

- Upstream rename → tạo file mới ở path mới, **giữ file cũ**.
- Kiểm tra references: grep `old_filename` trong workspace.
- Nếu có references → không xóa old; thêm new; cập nhật references sau khi user duyệt.

### 11.5 Verification chống regression

Ngoài `verify-workspace.ps1` và `hlk-verify-integrity.js`:

- `py_compile` mọi `.py` mới/đổi.
- `tools/import_smoke_test.py` để phát hiện `ModuleNotFoundError` do rename/delete.
- `harness-sensor` code mode khi sửa `.py`.
- `git diff --stat` để phát hiện deletion bất ngờ.
- `git diff` từng file quan trọng (`COMMANDER.md`, `AGENTS.md`, `*.py`) để xác nhận chỉ thay đổi dự kiến.
- Kiểm tra `UPGRADE_TRACKER*.json` — không mất entries.
