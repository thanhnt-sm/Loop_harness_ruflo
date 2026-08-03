# 03 — Cấu hình best practice

> Hướng dẫn cấu hình `.claude/settings.json`, `hlk.config.json`, secrets, Docker, môi trường, và các tính năng bảo mật theo best practice.

---

## 1. Nguyên tắc cấu hình

1. **Không commit secrets**: API key, token, password, private key chỉ tồn tại trong `HLK/config/secrets.env` (gitignored) hoặc env var.
2. **Tách biệt HLK và Ruflo core**: Mọi tùy chỉnh local đặt trong `HLK/`, không sửa trực tiếp `v3/` nếu không cần.
3. **Pin version khi cần**: Tránh `ruflo@latest` cho môi trường production; dùng version cụ thể.
4. **MCP bridge local-only**: Không bind `0.0.0.0` nếu chưa set `MCP_AUTH_TOKEN`.
5. **Telemetry tắt mặc định**: Nếu không cần, HLK sẽ set các env tắt telemetry.

---

## 2. `hlk.config.json` — best practice

Vị trí: `HLK/config/hlk.config.json`

```json
{
  "hlk_enabled": true,
  "version": "3.0.0",
  "ruflo_version_tested": "3.34.0",
  "description": "Harness & Logic Knowledge Layer config for Ruflo Workspace",
  "features": {
    "knowledge_protection": true,
    "data_sanitization": true,
    "secret_vault_override": true,
    "telemetry_blocker": true,
    "custom_hooks_injection": true,
    "post_merge_verify": true
  },
  "upgrade_policy": {
    "auto_merge": false,
    "verify_hlk_after_merge": true,
    "backup_config_before_merge": true,
    "log_upgrades": true
  },
  "security_rules": {
    "redact_patterns": [
      "sk-[a-zA-Z0-9]{32,}",
      "ghp_[a-zA-Z0-9]{36}",
      "\\b(sk-|pk-|api[_-]?key[_-]?)[a-zA-Z0-9]{20,}\\b",
      "\\beyJ[a-zA-Z0-9_-]*\\.eyJ[a-zA-Z0-9_-]*\\.[a-zA-Z0-9_-]*\\b",
      "(?i)password\\s*=\\s*['\"]?[^'\"\\s]+",
      "(?i)api[_-]?key\\s*=\\s*['\"]?[^'\"\\s]+",
      "(?i)secret\\s*[:=]\\s*['\"]?[^'\"\\s]+",
      "(?i)token\\s*[:=]\\s*['\"]?[^'\"\\s]+",
      "(?i)(mongodb\\+srv|postgresql|mysql)://[^\\s]+",
      "(?i)-----BEGIN (RSA |EC |OPENSSH )?PRIVATE KEY-----[\\s\\S]*?-----END (RSA |EC |OPENSSH )?PRIVATE KEY-----"
    ],
    "redact_replacement": "[REDACTED]",
    "scan_paths": ["src/**", "config/**", ".env*"],
    "exclude_paths": ["node_modules/**", "dist/**", "HLK/logs/**"]
  },
  "telemetry_overrides": {
    "CLAUDE_CODE_ENABLE_TELEMETRY": "0",
    "DISABLE_TELEMETRY": "1",
    "OTEL_TRACES_EXPORTER": "none",
    "OTEL_METRICS_EXPORTER": "file",
    "OTEL_LOGS_EXPORTER": "file",
    "LANGSMITH_TRACING": "false",
    "LANGFUSE_TRACING": "false"
  }
}
```

### Giải thích các feature

| Feature | Khi bật | Khi tắt |
|---------|---------|---------|
| `knowledge_protection` | Bảo vệ tri thức nội bộ | Không can thiệp |
| `data_sanitization` | Redact secret trong argv, tool input | Không redact |
| `secret_vault_override` | Dùng `vault-bridge.js` | Dùng `process.env` trực tiếp |
| `telemetry_blocker` | Set env tắt telemetry | Không set env |
| `custom_hooks_injection` | Load custom hooks | Bỏ qua thư mục custom-hooks |
| `post_merge_verify` | Kiểm tra HLK sau merge | Bỏ qua verify |

---

## 3. Quản lý secrets

### 3.1 Không bao giờ commit secret

Các file đã bị `.gitignore` chặn:

- `HLK/config/secrets.env`
- `HLK/config/*.local.json`
- `.env`, `.env.*`
- `*.pem`, `*.key`
- `agentdb.rvf`, `*.rvf`

### 3.2 `HLK/config/secrets.env.example`

```env
# Copy file này thành HLK/config/secrets.env và điền giá trị thật
# KHÔNG commit secrets.env

OPENAI_API_KEY=sk-your-openai-key
ANTHROPIC_API_KEY=sk-ant-your-anthropic-key
GOOGLE_API_KEY=your-google-key
MCP_AUTH_TOKEN=your-random-token
MONGO_INITDB_ROOT_PASSWORD=your-random-mongo-password
OPENROUTER_API_KEY=your-openrouter-key
```

Tạo file thực:

```bash
# Linux/macOS
cp HLK/config/secrets.env.example HLK/config/secrets.env

# Windows PowerShell
Copy-Item HLK\config\secrets.env.example HLK\config\secrets.env
```

### 3.3 Ưu tiên secret

Thứ tự `vault-bridge.js`:

1. `process.env[key]`
2. `HLK/config/secrets.env`
3. `defaultValue`

> **Best practice**: môi trường production dùng `process.env`; local dev dùng `secrets.env`.

---

## 4. `.claude/settings.json` — best practice

### 4.1 Các thay đổi đã áp dụng

- `claudeFlow.version` = `3.34.0` (đồng bộ package).
- `PreToolUse` đã thêm `hlk-hook-bridge.mjs` chạy đầu tiên.
- `mcpServers.claude-flow` dùng `HLK/wrappers/ruflo-hlk-mcp.mjs` thay vì `npx ruflo@latest`.

### 4.2 Cấu hình PreToolUse

```json
"PreToolUse": [
  {
    "hooks": [
      {
        "type": "command",
        "command": "node \"$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs\"",
        "timeout": 5000
      }
    ]
  },
  {
    "matcher": "Bash",
    "hooks": [
      {
        "type": "command",
        "command": "node \"$CLAUDE_PROJECT_DIR/.claude/helpers/hook-handler.cjs\" pre-bash",
        "timeout": 5000
      }
    ]
  }
]
```

> Lý do HLK chạy trước: ruflo `pre-bash` không thấy secret gốc, chỉ thấy `[REDACTED]`.

### 4.3 Cấu hình MCP server

```json
"mcpServers": {
  "claude-flow": {
    "command": "node",
    "args": [
      "HLK/wrappers/ruflo-hlk-mcp.mjs",
      "mcp",
      "start"
    ]
  }
},
"enabledMcpjsonServers": ["claude-flow"]
```

Wrapper `ruflo-hlk-mcp.mjs` sẽ:

1. Set `NODE_OPTIONS` trỏ đến `hlk-loader.js`.
2. Spawn `npx -y ruflo@latest mcp start`.
3. Đảm bảo MCP server chạy với HLK process preload.

### 4.4 Swarm / anti-drift

Best practice cho swarm trong `.claude/settings.json`:

```json
"swarm": {
  "topology": "hierarchical-mesh",
  "maxAgents": 15
}
```

Nhưng theo `CLAUDE.md`, để chống drift tốt nhất:

```json
"swarm": {
  "topology": "hierarchical",
  "maxAgents": 8,
  "strategy": "specialized"
}
```

> **Khuyến nghị**: với task phức tạp, dùng `hierarchical` hoặc `hierarchical-mesh`, `maxAgents <= 8-15`, `strategy: specialized`.

### 4.5 Memory

```json
"memory": {
  "backend": "hybrid",
  "enableHNSW": true,
  "learningBridge": { "enabled": true },
  "memoryGraph": { "enabled": true },
  "agentScopes": { "enabled": true }
}
```

### 4.6 Security

```json
"security": {
  "autoScan": true,
  "scanOnEdit": true,
  "cveCheck": true,
  "threatModel": true
}
```

---

## 5. Docker / MCP bridge hardening

### 5.1 `ruflo/docker-compose.yml` — mặc định an toàn

Sau ADR-166 (CVE-2026-59726 / GHSA-c4hm-4h84-2cf3), cấu hình mặc định đã an toàn:

```yaml
services:
  mongodb:
    image: mongo:7
    ports:
      - "127.0.0.1:27017:27017"
    environment:
      MONGO_INITDB_ROOT_USERNAME: ruflo
      MONGO_INITDB_ROOT_PASSWORD: ${MONGO_INITDB_ROOT_PASSWORD:?FATAL: set MONGO_INITDB_ROOT_PASSWORD in .env}
    command: ["--auth"]

  mcp-bridge:
    build: ./src/mcp-bridge
    ports:
      - "127.0.0.1:3001:3001"
    environment:
      MCP_BIND_HOST: 127.0.0.1
      MCP_AUTH_TOKEN: ${MCP_AUTH_TOKEN:-}
      MCP_ENABLE_TERMINAL: "false"
    read_only: true
    tmpfs:
      - /tmp
```

### 5.2 Tạo `.env` trước khi `docker compose up`

```bash
# Linux/macOS
{
  echo "MONGO_INITDB_ROOT_PASSWORD=$(openssl rand -base64 32)"
  echo "MCP_AUTH_TOKEN=$(openssl rand -base64 32)"
} > ruflo/.env

# Windows PowerShell
"MONGO_INITDB_ROOT_PASSWORD=$([Convert]::ToBase64String([byte[]](1..32 | % { Get-Random -Max 256 })))" | Out-File -FilePath ruflo\.env -Encoding utf8
"MCP_AUTH_TOKEN=$([Convert]::ToBase64String([byte[]](1..32 | % { Get-Random -Max 256 })))" | Out-File -FilePath ruflo\.env -Encoding utf8 -Append
```

> **Tuyệt đối không commit `ruflo/.env`**. Đảm bảo `.gitignore` bao gồm `.env`.

### 5.3 Public bind — chỉ khi thực sự cần

Nếu muốn expose MCP bridge ra ngoài, **bắt buộc** phải có `MCP_AUTH_TOKEN`:

```bash
# .env cho public
echo "MCP_BIND_HOST=0.0.0.0" >> ruflo/.env
echo "MCP_AUTH_TOKEN=$(openssl rand -base64 32)" >> ruflo/.env
docker compose -f ruflo/docker-compose.yml -f ruflo/docker-compose.public.yml up -d
```

> Nếu `MCP_AUTH_TOKEN` không có, bridge sẽ FATAL và exit khác 0.

### 5.4 Không expose port 3001/27017 lên internet

- Dùng firewall/Security Group chặn `0.0.0.0/0`.
- Nếu cần remote, dùng VPN/tunnel, không expose trực tiếp.
- Kiểm tra: `netstat -an | findstr 3001` (Windows) hoặc `ss -ltn | grep 3001` (Linux).

---

## 6. Launcher HLK

### 6.1 `ruflo-hlk.mjs` — local CLI

Dùng khi bạn đã build local CLI (`v3/@claude-flow/cli/dist/` tồn tại).

```bash
node HLK/wrappers/ruflo-hlk.mjs memory store -k demo -v "sk-abc..."
```

Tự động set `NODE_OPTIONS` trỏ đến `hlk-loader.js` rồi chạy `bin/cli.js`.

### 6.2 `ruflo-hlk-mcp.mjs` — MCP server

Dùng trong `.claude/settings.json` như ở mục 4.3.

```bash
node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start
```

### 6.3 `ruflo-hlk.ps1` / `.cmd`

PowerShell:

```powershell
.\HLK\wrappers\ruflo-hlk.ps1 memory store -k demo -v "sk-abc..."
```

CMD:

```cmd
HLK\wrappers\ruflo-hlk.cmd memory store -k demo -v "sk-abc..."
```

---

## 7. Custom hooks

### 7.1 Cấu trúc thư mục

```
HLK/custom-hooks/
├── pre-argv/          # Chạy trước khi loader sanitize argv
├── post-sanitize/     # Chạy sau khi loader sanitize argv
└── agent-tool/        # Chạy trong hlk-hook-bridge.mjs
```

### 7.2 Hợp đồng hook

```js
export default async function run(context) {
  return {
    value: context.value,  // giá trị đã biến đổi (tuỳ phase)
    block: false,          // true để chặn
    reason: ''             // lý do chặn
  };
}
```

### 7.3 Ví dụ: agent-tool hook chặn Bash chứa raw secret

`HLK/custom-hooks/agent-tool/10-block-raw-secrets.hook.mjs`:

```js
export default async function run({ toolName, toolInput }) {
  if (toolName !== 'Bash' || !toolInput?.command) {
    return { value: toolInput };
  }

  const raw = toolInput.command;
  const dangerous = /\b(sk-|ghp_|api[_-]?key\s*=|password\s*=|token\s*=)/i;

  if (dangerous.test(raw) && !raw.includes('[REDACTED]')) {
    return {
      block: true,
      reason: 'Bash command contains unredacted secret-like string'
    };
  }

  return { value: toolInput };
}
```

> Đã có `.gitkeep` trong các thư mục. Để hook hoạt động, đặt file `.hook.mjs` vào đúng phase.

---

## 8. Environment variables best practice

| Variable | Giá trị | Mục đích |
|----------|---------|----------|
| `OPENAI_API_KEY` | `sk-...` | OpenAI provider |
| `ANTHROPIC_API_KEY` | `sk-ant-...` | Anthropic provider |
| `GOOGLE_API_KEY` | `...` | Google/Gemini provider |
| `MCP_AUTH_TOKEN` | base64 random | Auth MCP bridge nếu public bind |
| `MONGO_INITDB_ROOT_PASSWORD` | random | MongoDB root password |
| `CLAUDE_CODE_ENABLE_TELEMETRY` | `0` | Tắt Claude Code telemetry |
| `DISABLE_TELEMETRY` | `1` | Tắt generic telemetry |
| `OTEL_TRACES_EXPORTER` | `none` | Tắt OpenTelemetry trace export |
| `OTEL_METRICS_EXPORTER` | `file` | Ghi metrics ra file, không gửi đi |
| `OTEL_LOGS_EXPORTER` | `file` | Ghi logs ra file, không gửi đi |
| `LANGSMITH_TRACING` | `false` | Tắt LangSmith |
| `LANGFUSE_TRACING` | `false` | Tắt Langfuse |
| `RUFLO_NO_AUTO_ENABLE` | `1` | Không auto-enable spinner/announcements |
| `RUFLO_MEMORY_SCAN_ON_WRITE` | `1` | Quét memory khi write (ADR-125) |

### 8.1 Đặt env cho Claude Code trên Windows

PowerShell:

```powershell
[Environment]::SetEnvironmentVariable("ANTHROPIC_API_KEY", "sk-ant-...", "User")
```

Hoặc trong `.claude/settings.json`:

```json
"env": {
  "CLAUDE_CODE_EXPERIMENTAL_AGENT_TEAMS": "1",
  "CLAUDE_FLOW_V3_ENABLED": "true",
  "CLAUDE_FLOW_HOOKS_ENABLED": "true",
  "ANTHROPIC_API_KEY": "${ANTHROPIC_API_KEY}"
}
```

> Lưu ý: `.claude/settings.json` không thể reference `${...}`; phải hardcode hoặc set ở OS level.

---

## 9. `.gitignore` và `.gitattributes`

### 9.1 Đảm bảo `.gitignore` bao phủ

Kiểm tra:

```text
HLK/config/secrets.*
HLK/config/*.local.json
HLK/logs/
.env
.env.*
*.rvf
*.rvf.lock
agentdb.rvf
agentdb.rvf.lock
.claude-flow/data/
.swarm/
.hive-mind/
```

### 9.2 `.gitattributes`

Đã có:

```text
HLK/** merge=ours
.claude/settings.json merge=ours
```

> `merge=ours` đảm bảo khi merge, file này giữ phiên bản local, không bị ghi đè.

---

## 10. Security hardening checklist

| # | Hạng mục | Trạng thái |
|---|----------|------------|
| 1 | `hlk_enabled: true` trong `hlk.config.json` | ☐ |
| 2 | `HLK/config/secrets.env` tồn tại, không commit | ☐ |
| 3 | API keys không xuất hiện trong code đã commit | ☐ |
| 4 | PreToolUse đã gọi `hlk-hook-bridge.mjs` | ☐ |
| 5 | MCP server dùng `ruflo-hlk-mcp.mjs` | ☐ |
| 6 | Docker `MCP_BIND_HOST=127.0.0.1` | ☐ |
| 7 | `MCP_ENABLE_TERMINAL=false` | ☐ |
| 8 | `MONGO_INITDB_ROOT_PASSWORD` set trong `.env` | ☐ |
| 9 | `.claude/settings.json` có `merge=ours` | ☐ |
| 10 | GitHub repo private + AI training opt-out | ☐ |

Hoàn thành checklist này trước khi chạy production.
