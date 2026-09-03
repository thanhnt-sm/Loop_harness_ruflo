# BRD — Sample BRD for tests

> **Slug**: `sample-brd`
> **Owner**: `test-fixture`
> **Version**: `1.0.0`
> **Status**: `draft`

## 1. Business Goal
Demo BRD để test parser. Đảm bảo mọi field bắt buộc đều có, mọi FR có actor + acceptance criteria, mọi NFR có metric đo được.

## 2. Actors

| Actor | Role | Permissions |
|-------|------|-------------|
| `customer` | End user đặt hàng | read |
| `admin` | Quản trị viên hệ thống | admin |
| `support` | Nhân viên hỗ trợ | write |

## 3. Functional Requirements (FR)

### FR-001: Customer đăng ký tài khoản
- **Actor**: customer
- **Use case**: register
- **Description**: Customer tạo tài khoản mới bằng email + password
- **Priority**: must
- **Acceptance criteria**:
  - [ ] Email hợp lệ được chấp nhận
  - [ ] Email trùng lặp bị từ chối
  - [ ] Password ≥ 8 ký tự được yêu cầu

### FR-002: Admin xem danh sách user
- **Actor**: admin
- **Use case**: list_users
- **Description**: Admin xem được danh sách tất cả user với phân trang
- **Priority**: should
- **Acceptance criteria**:
  - [ ] Danh sách hiển thị tên + email
  - [ ] Phân trang 20 user/page

## 4. Non-Functional Requirements (NFR)

### NFR-001: API response time
- **Type**: perf
- **Metric**: response_time_p95
- **Threshold**: < 200ms

### NFR-002: Password storage security
- **Type**: security
- **Metric**: hash_algorithm
- **Threshold**: bcrypt with cost ≥ 12

## 5. Constraints
- Sử dụng Python 3.11+
- Deploy on Linux

## 6. Out of Scope
- Mobile app
- Payment integration
