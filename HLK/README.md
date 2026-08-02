# HLK (Harness & Logic Knowledge Layer) — v2.0.0

> **Mục tiêu**: Lớp bọc bảo vệ tri thức dự án, bảo mật dữ liệu nhạy cảm, tích hợp custom logic, có cơ chế **BẬT/TẮT** linh hoạt — **không xung đột khi ruflo cập nhật phiên bản mới**.

---

## Quick Start

```powershell
# Kiểm tra HLK đang hoạt động
node HLK/wrappers/hlk-verify-integrity.js

# Bật/Tắt HLK → sửa HLK/config/hlk.config.json → "hlk_enabled": true/false

# Sync upstream ruflo (Windows)
powershell -File HLK/wrappers/git-upstream-sync.ps1

# Sync upstream ruflo (Linux/Mac)
bash HLK/wrappers/git-upstream-sync.sh

# Dry-run (xem trước thay đổi, không merge)
powershell -File HLK/wrappers/git-upstream-sync.ps1 -DryRun
```

---

## Cấu Trúc Thư Mục

```
HLK/
├── config/
│   ├── hlk.config.json        ← Cấu hình bật/tắt, security rules, telemetry overrides
│   ├── secrets.env.example    ← Template cho file secrets (gitignored)
│   └── secrets.env            ← [GITIGNORED] Secrets thực tế
├── wrappers/
│   ├── hlk-loader.js          ← Interceptor: bind sanitizer, telemetry blocker, vault
│   ├── hlk-verify-integrity.js ← Post-merge HLK integrity checker
│   ├── git-upstream-sync.sh   ← Upstream sync script (Bash)
│   └── git-upstream-sync.ps1  ← Upstream sync script (PowerShell)
├── security/
│   ├── sanitizer.js           ← Redact API keys, tokens, passwords từ text
│   └── vault-bridge.js        ← Quản lý secrets qua env vars / local .env
├── prompts/                   ← 7 prompts phân tích & hardening
│   ├── 01_codebase_analysis.prompt.md
│   ├── 02_redteam_security.prompt.md
│   ├── 03_solution_architect.prompt.md
│   ├── 04_upstream_update_plan.prompt.md
│   ├── 05_data_leak_hardening_guide.prompt.md
│   ├── 06_harness_deepdive_hardening.prompt.md
│   └── 07_ruflo_hardening_implementation.prompt.md
└── logs/                      ← [GITIGNORED] Upgrade logs, config backups
```

---

## Cơ Chế Bật / Tắt HLK

Tệp [`HLK/config/hlk.config.json`](config/hlk.config.json):

| Trạng thái | Hành vi |
|------------|---------|
| `hlk_enabled: true` | Loader bind middleware: sanitizer redact secrets, telemetry bị block, vault bridge kích hoạt |
| `hlk_enabled: false` | Bypass toàn bộ — ruflo chạy nguyên bản 100% |

### Features toggle riêng:

| Feature | Mô tả |
|---------|--------|
| `knowledge_protection` | Bảo vệ tri thức dự án |
| `data_sanitization` | Redact API keys, tokens trước khi gửi đi |
| `secret_vault_override` | Quản lý secrets qua vault-bridge thay vì .env trực tiếp |
| `telemetry_blocker` | Tắt OpenTelemetry, LangSmith, Langfuse |
| `custom_hooks_injection` | Chèn custom hooks vào runtime |
| `post_merge_verify` | Tự kiểm tra HLK sau mỗi merge |

---

## Quy Trình Cập Nhật Upstream Ruflo

### Tự động (khuyến nghị):

```powershell
# Windows
powershell -File HLK/wrappers/git-upstream-sync.ps1

# Script tự động:
# 1. Kiểm tra git remote, thêm upstream nếu chưa có
# 2. Fetch upstream
# 3. Backup hlk.config.json trước merge
# 4. Merge upstream/main --no-ff
# 5. Verify HLK integrity sau merge
# 6. Tự restore config nếu bị corrupt
```

### Thủ công:

```bash
git fetch upstream
git merge upstream/main --no-ff -m "chore: merge upstream ruflo updates"
node HLK/wrappers/hlk-verify-integrity.js
```

### Tại sao không xung đột?

1. **`HLK/`** hoàn toàn nằm ngoài ruflo source tree — upstream không có folder này
2. **`.gitattributes`** đặt merge strategy `ours` cho tất cả `HLK/**` files
3. **Config backup** được tạo trước mỗi merge trong `HLK/logs/`
4. **Auto-restore** nếu config bị corrupt sau merge

---

## Security Modules

### Sanitizer (`HLK/security/sanitizer.js`)

```javascript
import { sanitize } from './HLK/security/sanitizer.js';

const clean = sanitize("Connect with postgresql://admin:secret@db.example.com/prod");
// → "Connect with [REDACTED]"
```

Patterns được config trong `hlk.config.json → security_rules.redact_patterns`.

### Vault Bridge (`HLK/security/vault-bridge.js`)

```javascript
import { getSecret, hasSecret } from './HLK/security/vault-bridge.js';

const key = getSecret('OPENAI_API_KEY');
// Ưu tiên: process.env → HLK/config/secrets.env → undefined
```

---

## Prompts Tích Hợp

| # | File | Mục đích |
|---|------|----------|
| 01 | `codebase_analysis` | Quét & đánh giá kiến trúc ruflo |
| 02 | `redteam_security` | Kiểm tra rò rỉ dữ liệu & tri thức |
| 03 | `solution_architect` | Thiết kế HLK middleware |
| 04 | `upstream_update_plan` | Kế hoạch cập nhật ruflo an toàn |
| 05 | `data_leak_hardening` | Khóa chặt chống rò rỉ dữ liệu |
| 06 | `harness_deepdive` | Hardening telemetry & AgentDB |
| 07 | `ruflo_hardening` | Tắt telemetry, config AIDefence |
