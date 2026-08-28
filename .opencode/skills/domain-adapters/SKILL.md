---
name: domain-adapters
description: >-
  Index wrapper cho bộ domain adapters (fraud table) của fable-judge trong
  `.devin/skills/domain-adapters/`. Dùng khi cần chọn bảng fraud cho đúng domain
  (code, data, devops, research, finance, legal, marketing, design, business-ops)
  trước khi đánh giá output không phải code. Expose trigger /domain.
metadata:
  provider: devin
  source: .devin/skills/domain-adapters/
  hasSubfiles: true
---

# domain-adapters (opencode wrapper)

Bộ adapter là các **fraud table** theo domain dùng bởi `fable-judge` khi đánh giá
output không phải code. Chọn đúng adapter theo domain của task rồi nạp bảng fraud đó
vào quá trình đánh giá.

## Các adapter có sẵn (trong `.devin/skills/domain-adapters/`)

| Domain | File | Khi nào dùng |
|--------|------|--------------|
| Code / software engineering | `generic.md` | Mặc định, mọi output code |
| Data analysis / ML | `data.md` | Task phân tích dữ liệu, model, ML |
| Infra / DevOps | `devops.md` | Task hạ tầng, CI/CD, deploy |
| Documentation / research | `research.md` | Task tài liệu, nghiên cứu |
| Finance | `finance.md` | Task tài chính, kế toán |
| Legal | `legal.md` | Task pháp lý, hợp đồng |
| Marketing | `marketing.md` | Task marketing, content |
| Design | `design.md` | Task thiết kế, UX/UI |
| Business ops | `business-ops.md` | Task vận hành doanh nghiệp |

## Cách dùng

1. Xác định domain của output/task.
2. Đọc file adapter tương ứng từ `.devin/skills/domain-adapters/<domain>.md`.
3. Dùng bảng `Fraud pattern → Evidence to hunt` trong adapter đó khi đánh giá.
4. Nếu không chắc domain → dùng `generic.md` (bảng fraud chung).

> Đây là wrapper index; nguồn canonical là `.devin/skills/domain-adapters/`.
> Không sửa đổi file `.md` trong thư mục gốc `.devin/skills/domain-adapters/`.
