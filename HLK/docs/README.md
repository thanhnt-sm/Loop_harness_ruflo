# HLK Documentation Hub

> Thư mục tài liệu **Harness & Logic Knowledge Layer (HLK)** — tài liệu vận hành, cấu hình, nâng cấp và khắc phục sự cố cho hệ thống Ruflo/Claude Flow V3.

---

## Mục lục

| STT | Tài liệu | Nội dung chính |
|-----|----------|----------------|
| 1 | [01-tong-quan-va-kien-truc.md](./01-tong-quan-va-kien-truc.md) | Tổng quan, kiến trúc, phiên bản, tầm nhìn |
| 2 | [02-thanh-phan-va-luong-hoat-dong.md](./02-thanh-phan-va-luong-hoat-dong.md) | Các thành phần, luồng dữ liệu, mô hình hoạt động |
| 3 | [03-cau-hinh-best-practice.md](./03-cau-hinh-best-practice.md) | Cấu hình `.claude/settings.json`, `hlk.config.json`, Docker, secrets |
| 4 | [04-workflow-ruflo-best-practice.md](./04-workflow-ruflo-best-practice.md) | **Flow làm việc Ruflo best practice** — 6 bước, recipes copy-paste, anti-patterns |
| 5 | [05-van-hanh-runbook-va-playbook.md](./05-van-hanh-runbook-va-playbook.md) | Runbook thường ngày, playbook xử lý sự cố, bảo mật |
| 6 | [06-checklist-va-khac-phuc-su-co.md](./06-checklist-va-khac-phuc-su-co.md) | Checklist, checkpoint, troubleshooting |
| 7 | [07-dong-goi-va-cai-dat.md](./07-dong-goi-va-cai-dat.md) | Đóng gói, cài đặt, cập nhật HLK package |
| 8 | [08-git-tools.md](./08-git-tools.md) | Git tools: doctor, commit, push, safe-sync |
| 9 | [09-ruflo-hlk-lifecycle.md](./09-ruflo-hlk-lifecycle.md) | Vòng đời Ruflo + HLK copy-paste đầy đủ |
| 10 | [10-setup-max-power.md](./10-setup-max-power.md) | **Setup MAX POWER** — script `setup-max-power.mjs` / `update-max-power.mjs`, 3 CLI, provider tuning |

---

## Bắt đầu nhanh

1. **Cài đặt tự động MAX POWER**: xem [10-setup-max-power.md](./10-setup-max-power.md).
2. **Cách làm việc với Ruflo**: xem [04-workflow-ruflo-best-practice.md](./04-workflow-ruflo-best-practice.md).
3. **Kích hoạt HLK**: xem [03-cau-hinh-best-practice.md](./03-cau-hinh-best-practice.md).
4. **Giải quyết lỗi**: xem [06-checklist-va-khac-phuc-su-co.md](./06-checklist-va-khac-phuc-su-co.md).
5. **Đóng gói / cài mới / cập nhật**: xem [07-dong-goi-va-cai-dat.md](./07-dong-goi-va-cai-dat.md).
6. **Git tools**: xem [08-git-tools.md](./08-git-tools.md).
7. **Vòng đời copy-paste**: xem [09-ruflo-hlk-lifecycle.md](./09-ruflo-hlk-lifecycle.md).

---

## Quy ước

- Các từ kỹ thuật như `MCP`, `AgentDB`, `HNSW`, `LLM` sẽ được giải thích khi xuất hiện lần đầu.
- Mermaid diagram được dùng để minh họa; có thể copy vào Notion/Confluence/Word.
- Code block chỉ mang tính tham khảo; kiểm tra đường dẫn thực tế trước khi chạy.
