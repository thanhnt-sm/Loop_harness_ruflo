# BRD — Business Requirements Document (Template)

> **Slug**: `<task-slug>`
> **Owner**: `<name>`
> **Version**: `0.1.0`
> **Status**: `draft | review | approved`

## 1. Business Goal
<!-- 1-3 câu: tại sao làm task này, giá trị kinh doanh mang lại -->

## 2. Actors
<!-- Liệt kê mọi actor tương tác với hệ thống. Mỗi actor cần name, role, permissions -->

| Actor | Role | Permissions |
|-------|------|-------------|
| `<name>` | `<role>` | `<read | write | admin>` |

## 3. Functional Requirements (FR)
<!-- Mỗi FR phải có actor rõ ràng, use case, priority, acceptance criteria -->

### FR-001: <title>
- **Actor**: <name>
- **Use case**: <name>
- **Description**: <what>
- **Priority**: must | should | could | wont
- **Acceptance criteria**:
  - [ ] <criterion 1 — phải test được>
  - [ ] <criterion 2>

## 4. Non-Functional Requirements (NFR)
<!-- Performance, security, UX, scalability... -->

### NFR-001: <title>
- **Type**: perf | security | ux | scalability | reliability
- **Metric**: <đo được, vd "response_time_p95 < 200ms">
- **Threshold**: <giá trị ngưỡng>

## 5. Constraints
<!-- Ràng buộc kỹ thuật, ngân sách, thời hạn -->

## 6. Out of Scope
<!-- Những gì KHÔNG làm trong task này -->
