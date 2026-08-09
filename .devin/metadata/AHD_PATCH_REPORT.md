# AHD Cherry-Pick Report

Upstream: C:\Users\thant\AppData\Local\Temp\ahd-upstream
Range: 2026-07-15 .. 2026-08-10

## 06122a0 — 新增註解與版本紀律防護（三層機制）
- **status**: blocked
- **applied**: none
- **skipped**: protected:.devin/AGENTS.md, protected:.devin/canon/CORE_CANON.md, protected:.devin/canon/REDLINES.md, unmapped:distill/repo_entry_header.md

## 5e91f62 — 更新 README 並新增 10 種語言（共 13 語言）+ SEO/AEO/GEO/LLMO 優化
- **status**: skipped
- **applied**: none
- **skipped**: none

## d95c0b4 — 蒸餾 Fable 5 執行紀律：verbatim gates + fable-judge + 9 領域 adapter
- **status**: applied
- **applied**: .devin/skills/domain-adapters/business-ops.md, .devin/skills/domain-adapters/coding.md, .devin/skills/domain-adapters/data.md, .devin/skills/domain-adapters/design.md, .devin/skills/domain-adapters/devops.md, .devin/skills/domain-adapters/finance.md, .devin/skills/domain-adapters/legal.md, .devin/skills/domain-adapters/marketing.md, .devin/skills/domain-adapters/research.md
- **skipped**: diverged:.devin/canon/VERIFICATION_PROTOCOL.md, diverged:.devin/agents/workers/AUDITOR.md, diverged:.devin/skills/auditor.md, exists:.devin/skills/domain-adapters/TEMPLATE.md, exists:.devin/skills/fable-judge.md

## 52cfd64 — 更新  Agent-Harness-Deploy
- **status**: blocked
- **applied**: none
- **skipped**: protected:.devin/AGENTS.md

## e1c379b — 修正開源前私人資訊清理：Yee-World-Life 引用改為 masteryee-labs + 修復 Glossary 編碼亂碼
- **status**: skipped
- **applied**: none
- **skipped**: diverged:.devin/agents/COMMANDER.md, diverged:.devin/agents/DISPATCH_TEMPLATES.md

## adf1197 — 修正全域設定與 MCP 跨專案污染問題
- **status**: blocked
- **applied**: none
- **skipped**: unmapped:.gitignore, risky-new:.devin/scripts/migrate.py, unmapped:tests/test_scope_and_migrate.py

## 1c46ba8 — 蒸餾 YWL 概念進 AHD 架構：project_rules + 快查表 + 模型升降級
- **status**: blocked
- **applied**: none
- **skipped**: protected:.devin/AGENTS.md, protected:.devin/canon/BOOT_PROTOCOL.md, protected:.devin/canon/CORE_CANON.md

## 2b6b54b — fix: 移除 DISPATCH_TEMPLATES.md 舊引用 AI_Subagent_Templates v7.6
- **status**: skipped
- **applied**: none
- **skipped**: diverged:.devin/agents/DISPATCH_TEMPLATES.md

## 24374d0 — fix: state 檔案路徑不被工具替換
- **status**: skipped
- **applied**: none
- **skipped**: risky-new:.devin/adapters/base.py

## d3cd4de — fix: Glossary 移除舊檔案引用 + 部署 AHD 到自己
- **status**: skipped
- **applied**: none
- **skipped**: none

## f5be7da — fix: 區分共享 state 與 per-tool session state
- **status**: skipped
- **applied**: none
- **skipped**: risky-new:.devin/adapters/base.py

## 1b6e5ef — feat: BOOT_PROTOCOL 自動遷移 shared state（向後相容舊版 AHD）
- **status**: blocked
- **applied**: none
- **skipped**: protected:.devin/AGENTS.md, protected:.devin/canon/BOOT_PROTOCOL.md

## 408ee0a — fix: memory_audit.py 用共享 state 路徑 + 向後相容 fallback
- **status**: blocked
- **applied**: none
- **skipped**: protected:.devin/hooks/ahd_session.py

## 7045406 — feat: 蒸餾「驗證錨點分級」（強錨 vs 弱錨）至 VERIFICATION_PROTOCOL
- **status**: blocked
- **applied**: none
- **skipped**: protected:.devin/AGENTS.md, protected:.devin/canon/REDLINES.md
