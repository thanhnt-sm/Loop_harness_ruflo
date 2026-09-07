# Implementation Plan

> **Mẫu kế hoạch triển khai (implementation plan)** cho kiến trúc AHD 3-Phase.
> Agent điền các phần `[FILL IN: ...]` trong giai đoạn Plan, **sau** khi SDD được duyệt.
> Mỗi Task phải có ID duy nhất, ánh xạ REQ ID, và tiêu chí chấp nhận (acceptance criteria) rõ ràng.

---

## Metadata

| Trường | Giá trị |
|--------|---------|
| **Status** | `[FILL IN: Draft / In Review / Approved / Rejected]` |
| **Risk Tier** | `[FILL IN: P0 / P1 / P2 / P3]` |
| **Quality Score** | `[FILL IN: 0.0–10.0]` |
| **SDD Reference** | `[FILL IN: đường dẫn file SDD hoặc SDD-ID]` |
| **Required Tools** | `[FILL IN: danh sách tool cần thiết, ví dụ: write, edit, bash, read, grep, glob, task, skill]` |

---

## 1. Context Analysis

### 1.1 Relevant Files

| File | Vai trò | Lý do liên quan |
|------|---------|-----------------|
| `[FILL IN: đường dẫn]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

### 1.2 Key Findings

- `[FILL IN: phát hiện quan trọng khi đọc codebase — điểm cần chú ý]`
- `[FILL IN: ...]`
- `[FILL IN: ...]`

### 1.3 Existing Patterns

| Pattern | Vị trí | Có tái dùng? |
|---------|--------|--------------|
| `[FILL IN: ...]` | `[FILL IN: file/hàm]` | `[FILL IN: Yes/No — lý do]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

---

## 2. Implementation Phases

> Lặp lại block dưới cho **mỗi** phase. Đặt tên: `### 2.x Phase <số>: <tên>`

### 2.1 Phase 1: `[FILL IN: tên phase]`

| Khía cạnh | Mô tả |
|-----------|-------|
| **Goal** (mục tiêu) | `[FILL IN: ...]` |
| **Dependencies** (phụ thuộc phase khác) | `[FILL IN: Phase 0 / không]` |
| **Parallelizable** (chạy song song?) | `[FILL IN: Yes/No — với phase nào]` |

**Task table:**

| Task ID | Description | File Path | Function | Acceptance Criteria | REQ ID | Risk |
|---------|-------------|-----------|----------|---------------------|--------|------|
| T1.1 | `[FILL IN: việc cần làm]` | `[FILL IN: đường dẫn]` | `[FILL IN: tên hàm/class]` | `[FILL IN: tiêu chí hoàn thành]` | `[FILL IN: REQ-xxx]` | `[FILL IN: Low/Med/High]` |
| T1.2 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| T1.3 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

### 2.2 Phase 2: `[FILL IN: tên phase]`

| Khía cạnh | Mô tả |
|-----------|-------|
| **Goal** | `[FILL IN: ...]` |
| **Dependencies** | `[FILL IN: Phase 1]` |
| **Parallelizable** | `[FILL IN: ...]` |

**Task table:**

| Task ID | Description | File Path | Function | Acceptance Criteria | REQ ID | Risk |
|---------|-------------|-----------|----------|---------------------|--------|------|
| T2.1 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| T2.2 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

### 2.3 Phase 3: `[FILL IN: tên phase]`

| Khía cạnh | Mô tả |
|-----------|-------|
| **Goal** | `[FILL IN: ...]` |
| **Dependencies** | `[FILL IN: ...]` |
| **Parallelizable** | `[FILL IN: ...]` |

**Task table:**

| Task ID | Description | File Path | Function | Acceptance Criteria | REQ ID | Risk |
|---------|-------------|-----------|----------|---------------------|--------|------|
| T3.1 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| T3.2 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

---

## 3. Dependency Graph

```mermaid
%% [FILL IN: Mermaid DAG — biểu đồ phụ thuộc giữa các task/phase]
%% Ví dụ:
%% flowchart LR
%%   T1.1 --> T1.2
%%   T1.2 --> T2.1
%%   T1.2 --> T2.2
%%   T2.1 --> T3.1
%%   T2.2 --> T3.1
```

---

## 4. Requirement Coverage Matrix

> Mỗi REQ ID từ SDD phải xuất hiện ít nhất 1 lần. Coverage Status: Covered / Partial / Missing.

| REQ ID | Description | File Path | Function | Coverage Status |
|--------|-------------|-----------|----------|-----------------|
| REQ-001 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: Covered/Partial/Missing]` |
| REQ-002 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| REQ-003 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

**Tổng kết coverage:**

- Total REQ: `[FILL IN: số]`
- Covered: `[FILL IN: số]`
- Partial: `[FILL IN: số]`
- Missing: `[FILL IN: số]`

---

## 5. Risk Assessment

| Risk | Tier | Mitigation | Rollback |
|------|------|------------|----------|
| `[FILL IN: rủi ro cụ thể]` | `[FILL IN: P0/P1/P2/P3]` | `[FILL IN: cách giảm thiểu]` | `[FILL IN: cách quay lui]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

---

## 6. Test Strategy

### 6.1 Unit Tests

| Task ID | Test file | Cases | Coverage target | Gate |
|---------|-----------|-------|-----------------|------|
| `[FILL IN: T1.1]` | `[FILL IN: đường dẫn]` | `[FILL IN: số case]` | `[FILL IN: %]` | `[FILL IN: tất cả pass]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

### 6.2 Integration Tests

| Scenario | Test file | Services involved | Gate |
|----------|-----------|-------------------|------|
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

### 6.3 End-to-End (E2E) Tests

| Scenario | Test file | Entry point | Expected outcome | Gate |
|----------|-----------|-------------|------------------|------|
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

---

## 7. Rollback Plan

| Bước | Trigger | Hành động | RTO | Người chịu trách nhiệm |
|------|---------|-----------|-----|------------------------|
| 1 | `[FILL IN: lỗi nào]` | `[FILL IN: revert commit / redeploy old image]` | `[FILL IN: thời gian]` | `[FILL IN: ...]` |
| 2 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
| 3 | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` | `[FILL IN: ...]` |

**Data rollback (nếu có):**

- `[FILL IN: backup snapshot trước deploy ở đâu]`
- `[FILL IN: cách restore]`

---

## 8. Approval Checklist

> 10 tiêu chí D1–D10. Mỗi tiêu chí phải được đánh dấu **[✓]** hoặc **[✗]** kèm ghi chú.

| ID | Tiêu chí | Trạng thái | Ghi chú |
|----|----------|------------|---------|
| D1 | SDD đã được duyệt và tham chiếu đúng | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D2 | Mọi REQ ID có ít nhất 1 Task bao phủ | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D3 | Dependency graph không có chu trình (cycle) | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D4 | Mỗi Task có acceptance criteria rõ ràng | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D5 | Risk assessment bao phủ mọi Task High risk | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D6 | Test strategy có unit + integration + E2E | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D7 | Rollback plan có RTO và người chịu trách nhiệm | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D8 | Không có thay đổi phá vỡ backward-compat chưa ghi rõ | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D9 | Không có thao tác phá hủy (drop/delete/force) không có guard | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |
| D10 | Adversarial review findings từ SDD đã được mitigate | `[FILL IN: ✓/✗]` | `[FILL IN: ...]` |

---

## 9. Approval Decision

| Trường | Giá trị |
|--------|---------|
| **Decision** | `[FILL IN: Approved / Rejected / Approved with Conditions]` |
| **Reviewer** | `[FILL IN: tên agent/người duyệt]` |
| **Date** | `[FILL IN: YYYY-MM-DD]` |
| **Conditions** | `[FILL IN: điều kiện nếu "Approved with Conditions", ngược lại "N/A"]` |
| **Comments** | `[FILL IN: ghi chú thêm]` |

---

## Changelog

| Phiên bản | Ngày | Thay đổi | Tác giả |
|-----------|------|----------|---------|
| `[FILL IN: v0.1]` | `[FILL IN: YYYY-MM-DD]` | `[FILL IN: ...]` | `[FILL IN: ...]` |
