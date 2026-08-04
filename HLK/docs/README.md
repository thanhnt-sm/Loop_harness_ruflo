# HLK Documentation Hub

> Thư mục tài liệu **Harness & Logic Knowledge Layer (HLK)** — tài liệu vận hành, cấu hình, nâng cấp và khắc phục sự cố.
>
> **Lưu ý quan trọng**: HLK ban đầu được thiết kế cho Ruflo/Claude Flow V3. Từ commit `c327869`, workspace chuyển sang **Agent Harness Deploy (AHD)** làm động cơ chính. HLK hiện giữ vai trò **security layer** (sanitizer + vault-bridge) tích hợp với AHD qua config.json hooks. Các tài liệu lịch sử (01-08, 10, 15) vẫn tham chiếu Ruflo — đọc với ngữ cảnh đó. Xem `AGENTS.md` + `REPOS.md` ở root để hiểu kiến trúc hiện tại.

---

## Mục lục

| STT | Tài liệu | Nội dung chính |
|-----|----------|----------------|
| 1 | [01-tong-quan-va-kien-truc.md](./01-tong-quan-va-kien-truc.md) | Tổng quan, kiến trúc, phiên bản, tầm nhìn *(tham chiếu Ruflo — lịch sử)* |
| 2 | [02-thanh-phan-va-luong-hoat-dong.md](./02-thanh-phan-va-luong-hoat-dong.md) | Các thành phần, luồng dữ liệu, mô hình hoạt động |
| 3 | [03-cau-hinh-best-practice.md](./03-cau-hinh-best-practice.md) | Cấu hình `.claude/settings.json`, `hlk.config.json`, Docker, secrets |
| 5 | [05-van-hanh-runbook-va-playbook.md](./05-van-hanh-runbook-va-playbook.md) | Runbook thường ngày, playbook xử lý sự cố, bảo mật |
| 6 | [06-checklist-va-khac-phuc-su-co.md](./06-checklist-va-khac-phuc-su-co.md) | Checklist, checkpoint, troubleshooting |
| 7 | [07-dong-goi-va-cai-dat.md](./07-dong-goi-va-cai-dat.md) | Đóng gói, cài đặt, cập nhật HLK package |
| 8 | [08-git-tools.md](./08-git-tools.md) | Git tools: doctor, commit, push, safe-sync |
| 10 | [10-setup-max-power.md](./10-setup-max-power.md) | **Setup MAX POWER** — script `setup-max-power.mjs`, 3 CLI, provider tuning *(tham chiếu Ruflo — lịch sử)* |
| 15 | [15-full-setup-guide.md](./15-full-setup-guide.md) | **Hướng dẫn đầy đủ** — 2 lệnh cài, sẵn sàng gửi task cho AI *(tham chiếu Ruflo — lịch sử)* |
| RT | [REDTEAM_REPORT.md](./REDTEAM_REPORT.md) | **Red Team Report** — 7-expert council tấn công toàn diện (Security, Token, Quality, Architecture, Performance, Flow, Cognitive) |
| UP | [UPGRADE_PLAN.md](./UPGRADE_PLAN.md) | **Upgrade Plan** — 40 upgrades chi tiết (P0-P3) với spec, acceptance criteria, verification steps, dependency graph |

> **Đã loại bỏ**: `04-workflow-ruflo-best-practice.md` và `09-ruflo-hlk-lifecycle.md` — Ruflo-specific, không còn áp dụng sau AHD deployment.

---

## Bắt đầu nhanh

1. **Hiểu kiến trúc hiện tại**: xem [`../../AGENTS.md`](../../AGENTS.md) (AHD main engine) + [`../../REPOS.md`](../../REPOS.md) (toàn bộ repos tham khảo).
2. **Git tools HLK**: xem [08-git-tools.md](./08-git-tools.md).
3. **Giải quyết lỗi**: xem [06-checklist-va-khac-phuc-su-co.md](./06-checklist-va-khac-phuc-su-co.md).
4. **Đóng gói / cài mới / cập nhật**: xem [07-dong-goi-va-cai-dat.md](./07-dong-goi-va-cai-dat.md).
5. **Cấu hình HLK**: xem [03-cau-hinh-best-practice.md](./03-cau-hinh-best-practice.md).

---

## Quy ước

- Các từ kỹ thuật như `MCP`, `AgentDB`, `HNSW`, `LLM` sẽ được giải thích khi xuất hiện lần đầu.
- Mermaid diagram được dùng để minh họa; có thể copy vào Notion/Confluence/Word.
- Code block chỉ mang tính tham khảo; kiểm tra đường dẫn thực tế trước khi chạy.
- Tài liệu đánh dấu *(tham chiếu Ruflo — lịch sử)*: viết khi HLK còn chạy trên Ruflo. Logic HLK core (sanitizer, vault-bridge, hooks) vẫn đúng, nhưng các tham chiếu Ruflo-specific (claude-flow CLI, v3 packages, swarm) không còn áp dụng.
