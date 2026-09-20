# Prompt — Vi phẫu rà soát toàn bộ hệ thống (Microscopic Adversarial Review)

## 1. Objective (Mục tiêu)

Thực hiện một cuộc rà soát **vi phẫu (microscopic)** — tức đọc từng dòng, mỗi file, mỗi quyết định kiến trúc/giải pháp trong workspace — nhằm:

- Phát hiện conflict ẩn, regression, mất mát U51–U70, mâu thuẫn giữa upstream AHD và local.
- Tấn công kiến trúc từ mọi hướng: trong → ngoài, ngoài → trong, chiều dọc, chiều ngang.
- Đánh giá tính đúng đắn, an toàn, bền vững của toàn bộ giải pháp đã merge vào `main`.
- Đưa ra danh sách vấn đề có mức độ nghiêm trọng, bằng chứng, và đề xuất fix cụ thể.

**Không được bỏ sót bất kỳ thành phần nào** trong workspace.

## 2. Context (Bối cảnh)

### 2.1. Lịch sử vừa thực hiện

- `nuwa-skill` đã update từ `72857dc` lên `27642f5` — cherry-pick core + 3 perspective cũ.
- `REPOS_TRACKER.json`, `check_updates.py`, `merge_updates.py`, `show_diff.py`, `apply_ahd_patch.py` đã tạo.
- AHD upstream từ `masteryee-labs/Tool.Agent-Harness-Deploy` đã cherry-pick **11/14 commit** trong khoảng 2026-07-15 đến 2026-08-10 bằng 3-way merge với `--resolve-theirs` (giữ upstream khi conflict) và `--allow-risky-new`.
- 3 commit bỏ qua: `5e91f62` (README translations), `d3cd4de` (Docs/Glossary), `52cfd64` (AGENTS-only).
- `main` đã push lên `origin/main`.

### 2.2. Thành phần mới/cập nhật cần rà soát kỹ

- **Kiến trúc mới:**
  - `.devin/adapters/base.py` (957 dòng, architecture adapter)
  - `.devin/scripts/sync.py` (entry file generation)
  - `.devin/scripts/distill.py`
  - `.devin/scripts/migrate.py`
- **Canon cập nhật:**
  - `.devin/canon/VERIFICATION_PROTOCOL.md`
  - `.devin/canon/MEMORY_PROTOCOL.md`
  - `.devin/canon/HARNESS_ENGINEERING.md`
- **Agents cập nhật:**
  - `.devin/agents/COMMANDER.md` (bị giảm ~111 dòng)
  - `.devin/agents/DISPATCH_TEMPLATES.md`
  - `.devin/agents/model_tiers.md`
  - `.devin/agents/workers/AUDITOR.md`
- **Skills cập nhật:**
  - `.devin/skills/auditor.md`
  - `.devin/skills/user-preference.md`
  - `.devin/skills/harness-sensor.md`
  - `.devin/skills/domain-adapters/*.md` (9 file mới)
- **Scripts cập nhật:**
  - `.devin/scripts/memory_audit.py`
- **Automation:**
  - `.devin/scripts/apply_ahd_patch.py`
  - `.devin/metadata/REPOS_TRACKER.json`
  - `.devin/metadata/AHD_PATCH_REPORT.md`

### 2.3. Tài liệu tham khảo bắt buộc đọc trước

- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.devin\metadata\AHD_PATCH_REPORT.md" />
- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.devin\metadata\REPOS_TRACKER.json" />
- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.devin\ATTRIBUTION.md" />
- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\REPOS.md" />
- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\AGENTS.md" />
- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\CLAUDE.md" />
- <ref_file file="D:\100.Software\Github\Loop_harness_new\Loop_harness_ruflo\.devin\scripts\apply_ahd_patch.py" />

## 3. Work Style (Cách làm)

### 3.1. Nguyên tắc

- **Đọc từng dòng:** không đọc lướt. Mỗi file cần đối chiếu với bản cũ và upstream.
- **Nghi ngờ mặc định:** giả định mọi thay đổi đều có khả năng gây hại cho đến khi chứng minh ngược lại.
- **Đối kháng 6 góc nhìn:**
  1. **Saboteur** — tìm cách phá hỏng, inject lỗi, bypass.
  2. **New Hire** — hiểu sai, dùng sai, bỏ qua convention.
  3. **Security Auditor** — leak secret, path traversal, command injection, privilege escalation.
  4. **Architect** — mâu thuẫn abstraction, cohesion, coupling, circular dependency.
  5. **Code Reviewer** — bug, edge case, error handling, testability.
  6. **Git Workflow Master** — history, blame, merge, lost changes, ignored files.
- **Không sửa code trừ khi user phê duyệt từng fix.** Chỉ report.

### 3.2. Attack surface — phải tấn công hết

#### A. Tấn công từ trong ra ngoài (Inside-Out)

- Một component bên trong `.devin/` sai sẽ làm gì khi hook/script/agent load nó?
- `.devin/adapters/base.py` có được import bởi hook/script nào không? Nếu không, nó là dead code? Nếu có, nó có làm hỏng flow?
- `.devin/scripts/sync.py` / `distill.py` / `migrate.py` chạy lúc nào? Có gọi shell/network không? Có xóa/sửa file protected không?
- `.devin/scripts/memory_audit.py` cập nhật có làm hỏng shared state path không?
- Các canon cập nhật có mâu thuẫn với `BOOT_PROTOCOL.md` / `CORE_CANON.md` / `REDLINES.md` (không đổi) không?
- `COMMANDER.md` giảm 111 dòng: những quyết định U51–U70 nào đã bị cắt? Có phải phần quan trọng không?

#### B. Tấn công từ ngoài vào trong (Outside-In)

- User/Devin CLI đọc `AGENTS.md` → load skill/agent → có skill/agent nào trỏ đến file đã bị đổi/cắt không?
- Skill system discover `.devin/skills/domain-adapters/*.md` — 9 file mới có reference broken? Có trùng tên/skill ID? Có kích thước quá lớn (>1024 loader limit)?
- `nuwa-skill` core `SKILL.md` cập nhật có tham chiếu đến domain-adapters mới không? Nếu có, đã có đủ file chưa?
- `mcp_config.json` / `.devin/config.json` có trỏ đến file/script mới không?

#### C. Tấn công chiều dọc (Vertical — từ user xuống hardware/git/network)

- **User prompt → slash skill → agent → hook → script → file system → git → push**
  - Mỗi tầng có kiểm soát? Có điểm nào script mới (`sync.py`, `distill.py`, `migrate.py`) bị gọi ngầm không?
  - `sync.py` có tạo/overwrite file protected (`AGENTS.md`, `CORE_CANON.md`) không?
  - `distill.py` / `migrate.py` có tạo `rm -rf`, `git push`, `git reset` không?
- **Network → API GitHub → `check_updates.py` → REPOS_TRACKER** — rate limit? token leak? JSON injection?
- **Git history → `apply_ahd_patch.py` → workspace file** — path traversal qua `../`? protected file overwrite? shell escape?

#### D. Tấn công chiều ngang (Horizontal — cùng tầng, component với component)

- 9 domain-adapters có xung đột lẫn nhau không? (business-ops vs coding vs devops vs data)
- `adapters/base.py` có cùng tên namespace/hàm với `hlk-git-tools` / `harness-sensor` / `loop_memory_sync` không?
- `COMMANDER.md`, `DISPATCH_TEMPLATES.md`, `model_tiers.md` cùng thay đổi — có mâu thuẫn về orchestration flow không?
- `VERIFICATION_PROTOCOL.md`, `MEMORY_PROTOCOL.md`, `HARNESS_ENGINEERING.md` cùng cập nhật — có thuật ngữ/cấp độ anchor định nghĩa không thống nhất không?

## 4. Tool Rules (Công cụ phải dùng)

1. **Diff & blame:**
   - `git log --oneline --all --graph` để hiểu history.
   - `git diff <base>..<head> -- <file>` cho mỗi file thay đổi.
   - `git blame` để xem dòng nào bị đổi, dòng nào còn từ U51–U70.
2. **Cross-reference:**
   - `grep` tìm reference tới file/skill/function mới từ `.devin/skills/`, `.devin/agents/`, `.devin/hooks/`, `.devin/scripts/`, `.devin/canon/`.
3. **Static analysis:**
   - `python -m py_compile` cho mọi file `.py` mới.
   - Kiểm tra `import`, `subprocess`, `open()`, `Path.write`, `shutil.rmtree`, `os.remove` trong script mới.
4. **Verify:**
   - `pwsh tools/verify-workspace.ps1`
   - `node HLK/wrappers/hlk-verify-integrity.js`
   - `python .devin/scripts/hook_integrity.py --verify` nếu có.
5. **Compare với upstream:**
   - Clone/fetch upstream AHD nếu cần diff trực tiếp.

## 5. Output Contract (Deliverable)

Tạo một file report tên: `.devin/metadata/MICROSCOPIC_REVIEW_REPORT.md` với cấu trúc:

```markdown
# Vi phẫu Rà Soát — Loop_harness_ruflo

## Executive Summary
- Tổng số file rà soát: N
- Số vấn đề critical: X
- Số vấn đề high: Y
- Số vấn đề medium: Z
- Số vấn đề low/info: W
- Khuyến nghị tổng thể (merge OK / cần fix trước khi dùng / rollback khẩn)

## 1. Conflict Review
### 1.1 3-way merge với --resolve-theirs
| File | Upstream change | Local change | Kết quả merge | Đánh giá | Severity |

### 1.2 File bị cắt/xóa nội dung
| File | Số dòng bị cắt | Nội dung bị cắt | Ảnh hưởng | Severity |

### 1.3 File mới chưa được integrate
| File | Mục đích | Có được gọi không? | Cần gì để activate? | Severity |

## 2. Architecture Review
### 2.1 Kiến trúc mới (adapters/)
### 2.2 Orchestrator flow (COMMANDER, DISPATCH_TEMPLATES, model_tiers)
### 2.3 Skill system (domain-adapters, nuwa-skill, auditor, fable-judge, user-preference)
### 2.4 Canon consistency (VERIFICATION, MEMORY, HARNESS_ENGINEERING)

## 3. Security Review
### 3.1 Secret/API key
### 3.2 Path traversal / shell injection
### 3.3 Protected file overwrite
### 3.4 Network / subprocess risk

## 4. Outside-In / Horizontal / Vertical Attack Findings
- Liệt kê theo từng attack vector, kèm bằng chứng (file, dòng, diff snippet).

## 5. Verification Results
- verify-workspace.ps1: PASS/FAIL
- hlk-verify-integrity.js: PASS/FAIL
- py_compile: PASS/FAIL
- Other: ...

## 6. Recommendations (Prioritized)
1. **Critical — phải fix ngay:** ...
2. **High:** ...
3. **Medium:** ...
4. **Low/Info:** ...

## 7. Appendix
- Full list of files reviewed.
- Full diff stats.
```

Mỗi finding phải có:
- **Severity:** `CRITICAL` / `HIGH` / `MEDIUM` / `LOW` / `INFO`
- **Component:** file/function/skill
- **Evidence:** quote dòng cụ thể hoặc diff snippet
- **Attack scenario:** tấn công từ đâu, như thế nào
- **Impact:** nếu exploit thành công thì sao
- **Fix recommendation:** ngắn gọn, có thể thực hiện
- **Acceptance criteria:** làm sao để biết fixed

## 6. Verification (Kiểm tra lại)

Trước khi kết thúc:

1. Re-run `pwsh tools/verify-workspace.ps1` → phải PASS.
2. Re-run `node HLK/wrappers/hlk-verify-integrity.js` → phải PASS.
3. `python -m py_compile` với mọi file `.py` mới/thay đổi → phải PASS.
4. Kiểm tra `git status` phải sạch (không có thay đổi chưa commit).

## 7. Done Criteria (Khi nào xong)

- [ ] Đã rà soát 100% file trong danh sách Scope.
- [ ] Đã áp dụng cả 4 attack vector (inside-out, outside-in, vertical, horizontal).
- [ ] Đã chạy đủ 6 persona đối kháng.
- [ ] `MICROSCOPIC_REVIEW_REPORT.md` đã được tạo theo template.
- [ ] Mọi finding có severity + evidence + fix recommendation.
- [ ] verify-workspace + HLK + py_compile PASS.
- [ ] git status sạch.
- [ ] Không thực hiện sửa code trừ khi user duyệt từng fix.

## 8. Constraints (Ràng buộc)

- **KHÔNG sửa code** trong session này. Chỉ report.
- **KHÔNG chạy `git push`, `git merge`, `git commit` tự động** trừ khi user yêu cầu rõ ràng.
- **KHÔNG xóa file** trừ khi user duyệt.
- **Bảo toàn pre-existing user changes**: mọi khuyến nghị fix phải chỉ rõ local customizations nào cần giữ.
