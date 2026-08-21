# PROMPT 07: RUFLO HARDENING IMPLEMENTATION

## Context
Dựa trên Báo cáo 03 (kiến trúc 3 tầng), Báo cáo 05 (data leak hardening), Báo cáo 06 (telemetry/AgentDB audit), bạn sẽ triển khai các bước hardening thực tế cho repo `thanhnt-sm/Loop_harness_ruflo`.

## Nhiệm vụ
1. Kiểm tra `HLK/config/hlk.config.json`, `HLK/security/sanitizer.js`, `HLK/security/vault-bridge.js` — đảm bảo fail-closed, redact patterns đầy đủ, vault precedence an toàn.
2. Xác minh `HLK/wrappers/hlk-loader.js` và `HLK/wrappers/hlk-hook-bridge.mjs` chặn/redact đúng công cụ `Bash`, `ApplyPatch`, `Write`, `Edit`.
3. Đảm bảo `agentdb.rvf` / `*.rvf` không còn trong git index; `.gitignore` và `.gitattributes` bảo vệ HLK config.
4. Ghi báo cáo tiếng Việt vào `HLK/reports/07_hardening_implementation.md`, kết thúc bằng mục `## Learnings` gồm 3-7 gạch đầu dòng.

> Response Requirements: Tiếng Việt, ngắn gọn, tập trung vào code/config thực tế.
