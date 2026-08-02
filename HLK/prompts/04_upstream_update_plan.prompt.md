# PROMPT 04: UPSTREAM UPDATE & MAINTENANCE PLAN

## Context
Bạn là DevOps & Release Manager. Dự án Ruflo ([github.com/ruvnet/ruflo](https://github.com/ruvnet/ruflo)) cập nhật phiên bản mới liên tục. Workspace hiện tại có chứa lớp bọc HLK custom.

## Objective
Xây dựng kế hoạch và tập lệnh tự động hóa quy trình cập nhật Ruflo mà **hoàn toàn không làm hỏng hay đè mất HLK layer**.

## Strategy Guidelines
1. **Git Remote & Branching Topology**:
   - `upstream`: Trỏ về `https://github.com/ruvnet/ruflo.git`
   - `origin`: Git repo cá nhân/nội bộ lưu workspace kèm HLK.
   - Giữ lớp HLK cách ly hoàn toàn ở folder `/HLK` và quy hoạch `.gitignore`.
2. **Conflict Prevention Workflow**:
   - Hướng dẫn các bước Fetch, Rebase/Merge safe.
   - Script tự động chạy post-merge check để đảm bảo `HLK/config/hlk.config.json` và lớp bọc vẫn kích hoạt mượt mà.

## Output Required
- Hướng dẫn chi tiết từng bước (Step-by-step Maintenance Guide).
- Shell / PowerShell script mẫu (`git-upstream-sync.sh` / `git-upstream-sync.ps1`) thực hiện đồng bộ an toàn.
