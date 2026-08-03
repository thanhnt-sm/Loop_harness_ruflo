# HLK (Harness & Logic Knowledge Layer) — v2.0.0

> **Mục tiêu**: Lớp bọc bảo vệ tri thức dự án, bảo mật dữ liệu nhạy cảm, tích hợp custom logic, có cơ chế **BẬT/TẮT** linh hoạt — **không xung đột khi ruflo cập nhật phiên bản mới**.

---

## Quick Start

```powershell
# Kiểm tra HLK đang hoạt động
node HLK/wrappers/hlk-verify-integrity.js

# Bật/Tắt HLK → sửa HLK/config/hlk.config.json → "hlk_enabled": true/false

# Cập nhật HLK
node HLK/bin/hlk-lifecycle.mjs --update --yes
```

---

## Setup MAX POWER (tự động, khuyến nghị)

> Cài đặt + cấu hình Ruflo + HLK + 3 CLI (Claude Code, Devin CLI, Antigravity CLI) + tinh chỉnh provider — tất cả trong một lệnh.

```bash
# Cài mới — hỏi tương tác, mỗi câu có đề xuất mặc định
node HLK/bin/hlk-setup-max-power.mjs

# Headless (không hỏi, dùng mặc định: local + claude + mọi tính năng bật)
node HLK/bin/hlk-setup-max-power.mjs --yes

# Cập nhật / re-patch / upgrade
node HLK/bin/hlk-update-max-power.mjs --yes
```

**Mặc định:** cài CỤC BỘ (không cần global), provider `claude`, mọi tính năng bật MAX POWER.

Chi tiết đầy đủ: xem [docs/10-setup-max-power.md](docs/10-setup-max-power.md).

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
│   └── hlk-verify-integrity.js ← Post-update HLK integrity checker
├── security/
│   ├── sanitizer.js           ← Redact API keys, tokens, passwords từ text
│   └── vault-bridge.js        ← Quản lý secrets qua env vars / local .env
├── prompts/                   ← 6 prompts phân tích & hardening
│   ├── 01_codebase_analysis.prompt.md
│   ├── 02_redteam_security.prompt.md
│   ├── 03_solution_architect.prompt.md
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

## Quy Trình Cập Nhật HLK

### Tự động (khuyến nghị):

```bash
node HLK/bin/hlk-lifecycle.mjs --update --yes
```

### Thủ công:

```bash
npm install -g /path/to/hlk-ruflo-x.y.z.tgz
npx hlk-update
node HLK/wrappers/hlk-verify-integrity.js
```

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
| 04 | `data_leak_hardening` | Khóa chặt chống rò rỉ dữ liệu |
| 05 | `harness_deepdive` | Hardening telemetry & AgentDB |
| 06 | `ruflo_hardening` | Tắt telemetry, config AIDefence |
