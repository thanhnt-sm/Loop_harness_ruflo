# MICROSCOPIC_REVIEW_REPORT

> Báo cáo vi phẫu rà soát sau khi cập nhật workspace từ upstream.
> Sinh ra bởi skill `update_from_repos` dựa trên `.devin/prompts/microscopic-review-prompt.md`.

## Metadata

| Trường | Giá trị |
|--------|---------|
| Session | <!-- ngày / branch / agent --> |
| Scope | <!-- repo nào được update --> |
| Commit applied | <!-- danh sách commit SHA / repo versions --> |
| Reviewer personas | Saboteur, New Hire, Security Auditor, Architect, Code Reviewer, Git Workflow Master |
| Attack vectors | Inside-out, Outside-in, Vertical, Horizontal |
| Last verified | `verify-workspace.ps1` + `hlk-verify-integrity.js` status |

---

## 1. Conflict Review

### 1.1 Three-way merge conflicts encountered

| File | Conflict cause | Resolution chosen | Risk level |
|------|---------------|-------------------|------------|
| | | | |

### 1.2 Silent divergences (non-conflict but semantically different)

| File | Local change | Upstream change | Verdict |
|------|-------------|-----------------|---------|
| | | | |

### 1.3 Path mapping issues

| Upstream path | Local path | Map decision | Rationale |
|---------------|------------|--------------|-----------|
| | | | |

---

## 2. Architecture Review

### 2.1 New components introduced

| Component | Type | Purpose | Integration points | Concerns |
|-----------|------|---------|---------------------|----------|
| | | | | |

### 2.2 Modified interfaces / contracts

| Interface | Before | After | Backward compatible? |
|-----------|--------|-------|----------------------|
| | | | |

### 2.3 Duplication or overlap

| Local | Upstream | Why both exist? | Recommended consolidation |
|-------|----------|-----------------|---------------------------|
| | | | |

---

## 3. Security Review

### 3.1 Network / subprocess / filesystem risk

| File | Operation | Input source | Sanitization | Verdict |
|------|-----------|--------------|--------------|---------|
| | | | | |

### 3.2 Secret exposure

| File | Potential exposure | Fix |
|------|-------------------|-----|
| | | |

### 3.3 Protected-file touch audit

| File | Touched? | Justification | User approval? |
|------|----------|---------------|----------------|
| | | | |

---

## 4. Persona Findings

### 4.1 Saboteur

- <!-- cách phá hoại có thể lợi dụng thay đổi -->

### 4.2 New Hire

- <!-- cách hiểu nhầm / dùng sai -->

### 4.3 Security Auditor

- <!-- lỗ hổng bảo mật / secret -->

### 4.4 Architect

- <!-- vấn đề kiến trúc, trùng lặp, coupling -->

### 4.5 Code Reviewer

- <!-- lỗi code, missing test, error handling -->

### 4.6 Git Workflow Master

- <!-- vấn đề branch, commit, push -->

---

## 5. Attack-Vector Findings

### 5.1 Inside-out

- <!-- component bên trong ảnh hưởng ra ngoài: skill → agent → user output -->

### 5.2 Outside-in

- <!-- user/skill bên ngoài khai thác lỗi thiết kế để lấy behavior nguy hiểm -->

### 5.3 Vertical

- <!-- xuyên suốt các tầng: prompt → slash skill → agent → hook → script → FS → git -->

### 5.4 Horizontal

- <!-- xuyên suốt sibling components: các domain-adapters / skills xung đột nhau -->

---

## 6. Recommendations

| ID | Severity | Description | Owner | Acceptance criteria |
|----|----------|-------------|-------|---------------------|
| R01 | High | | | |
| R02 | Medium | | | |
| R03 | Low | | | |

---

## 7. Verification Log

| Check | Command | Result | Timestamp |
|-------|---------|--------|-----------|
| Workspace integrity | `pwsh tools/verify-workspace.ps1` | | |
| HLK integrity | `node HLK/wrappers/hlk-verify-integrity.js` | | |
| Python compile | `python -m py_compile <new .py files>` | | |
| Git status | `git status --short` | | |

---

## 9. Regression / Old-code impact

> Phần này bắt buộc phải điền để đảm bảo update không làm hỏng hoặc "chết" code cũ.

### 9.1 Files changed / added / deleted

| File | Status | Old code impacted? | Mitigation | Verified |
|------|--------|--------------------|------------|----------|
| | | | | |

### 9.2 Deletion / rename audit

| File | Upstream action | Local action | References found | Verdict |
|------|-----------------|--------------|------------------|---------|
| | | | | |

### 9.3 Local customization preserved

| File | Customization | Upstream change | Kept? | Notes |
|------|---------------|-----------------|-------|-------|
| | | | | |

### 9.4 Import / runtime smoke

| Test | Command | Result |
|------|---------|--------|
| `py_compile` all `.py` | `python -m py_compile <files>` | |
| `import_smoke_test.py` | `python tools/import_smoke_test.py` | |
| `harness-sensor` code mode | | |

### 9.5 Regression findings

- <!-- mọi dấu hiệu code cũ bị ảnh hưởng, dù nhỏ nhất -->

## 10. Sign-off

- [ ] Tất cả findings đã ghi nhận.
- [ ] Regression / old-code impact đã điền.
- [ ] Recommendations đã ưu tiên.
- [ ] Verification log PASS.
- [ ] User đã duyệt trước khi merge/push.

---

*Template. Được điền bởi skill `update_from_repos` sau mỗi lần cập nhật workspace.*
