# 02 — Thành phần và luồng hoạt động

> Liệt kê chi tiết các thành phần của Ruflo + HLK và mô tả luồng dữ liệu, luồng điều khiển.

---

## 1. Cấu trúc thư mục cấp cao

```
Loop_harness_ruflo/
├── .agents/              # Skills & config cho OpenAI Codex
├── .claude/              # Claude Code settings, hooks, helpers
│   ├── settings.json     # Cấu hình hooks, MCP, claudeFlow
│   ├── helpers/          # hook-handler.cjs, router.js, memory.js, v.v.
│   └── commands/         # Custom slash commands
├── .claude-flow/         # Runtime data (gitignored)
├── .github/              # GitHub Actions, issue templates
├── bin/                  # CLI entry points
│   └── cli.js            # Wrapper import v3/@claude-flow/cli/bin/cli.js
├── data/                 # Clone data, ledger, proof files
├── docs/                 # Tài liệu, ADRs
├── HLK/                  # HLK layer
│   ├── config/
│   ├── wrappers/
│   ├── security/
│   ├── custom-hooks/
│   ├── loop/
│   ├── reports/
│   └── docs/             # Tài liệu bạn đang đọc
├── plugins/              # 35 Claude Code plugins
├── ruflo/                # Docker stack, MCP bridge, chat UI
├── scripts/              # Utility scripts
├── tests/                # Test files
├── v3/                   # V3 monorepo packages
└── verification/         # Verification manifests
```

---

## 2. HLK Layer — thành phần chi tiết

```
HLK/
├── config/
│   ├── hlk.config.json         # Cấu hình bật/tắt, security rules, telemetry
│   ├── secrets.env.example     # Template secrets
│   └── secrets.env             # [GITIGNORED] Secrets thực tế
├── wrappers/
│   ├── hlk-loader.js           # Process preload (argv, telemetry, vault)
│   ├── hlk-hook-bridge.mjs     # Agent runtime PreToolUse hook
│   ├── hlk-verify-integrity.js # Kiểm tra toàn vẹn HLK sau merge
│   ├── ruflo-hlk.mjs           # Launcher local CLI với HLK
│   ├── ruflo-hlk-mcp.mjs       # Launcher MCP server với HLK
│   ├── ruflo-hlk.ps1           # PowerShell launcher
│   └── ruflo-hlk.cmd           # CMD launcher
├── security/
│   ├── sanitizer.js            # Redact sensitive strings
│   └── vault-bridge.js         # Quản lý secrets
├── custom-hooks/
│   ├── pre-argv/               # Hooks chạy trước argv sanitize
│   ├── post-sanitize/          # Hooks chạy sau argv sanitize
│   └── agent-tool/             # Hooks chạy trong hlk-hook-bridge
├── loop/
│   ├── hlk-loop.mjs            # Pipeline logic
│   └── hlk-loop.config.json    # Loop config
├── prompts/                    # Prompt templates phân tích
├── reports/                    # Báo cáo phân tích
└── docs/                       # Tài liệu vận hành
```

### 2.1 `hlk.config.json`

File cấu hình trung tâm. Các nhóm:

- `hlk_enabled`: bật/tắt tổng thể.
- `version`: phiên bản HLK.
- `ruflo_version_tested`: phiên bản Ruflo đã test với HLK.
- `features`: bật/tắt từng tính năng.
- `upgrade_policy`: chính sách merge/verify/backup.
- `security_rules`: regex patterns redact.
- `telemetry_overrides`: env vars để tắt telemetry.

### 2.2 `hlk-loader.js`

Được load qua `NODE_OPTIONS="--import=file://.../hlk-loader.js"`.

Các bước thực hiện:

1. Đọc `hlk.config.json`.
2. Nếu `hlk_enabled === false` → no-op.
3. Set telemetry env vars (nếu `telemetry_blocker`).
4. Load sanitizer (nếu `data_sanitization`).
5. Load vault bridge (nếu `secret_vault_override`).
6. Load custom hooks `pre-argv` / `post-sanitize` (nếu `custom_hooks_injection`).
7. Sanitize `process.argv` cho các flag nhạy cảm: `-v`, `--value`, `--data`, `--content`.

### 2.3 `hlk-hook-bridge.mjs`

Được gọi từ `PreToolUse` trong `.claude/settings.json`.

Các bước:

1. Đọc JSON từ `stdin`.
2. Load agent-tool custom hooks.
3. Trích xuất `tool_name` và `tool_input`.
4. Chạy agent-tool custom hooks.
5. Với `Bash` / `ApplyPatch`: nếu chứa secret chưa redact → exit `2` (block).
6. Với `Write` / `Edit`: redact các chuỗi nhạy cảm trong `tool_input`.
7. Trả lại JSON qua `stdout`, exit `0`.

### 2.4 `sanitizer.js`

- Đọc `redact_patterns` từ `hlk.config.json`.
- Biên dịch thành `RegExp`.
- Hàm `sanitize(text)` thay thế bằng `[REDACTED]` (hoặc `redact_replacement`).
- `sanitizeObject(obj)` áp dụng lên tất cả string trong object nông (shallow).

Patterns mặc định:

| Pattern | Ví dụ khớp |
|---------|------------|
| `sk-[a-zA-Z0-9]{32,}` | `sk-abc123...` (OpenAI key) |
| `ghp_[a-zA-Z0-9]{36}` | `ghp_xxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxxx` (GitHub PAT) |
| `eyJ[a-zA-Z0-9_-]*\.eyJ[...` | JWT token |
| `mongodb+srv://...` | Connection string MongoDB |
| `-----BEGIN PRIVATE KEY-----` | SSH/EC/RSA private key |

### 2.5 `vault-bridge.js`

Thứ tự ưu tiên khi lấy secret:

1. `process.env[key]`
2. `HLK/config/secrets.env`
3. `defaultValue`

File `secrets.env` định dạng đơn giản:

```env
OPENAI_API_KEY=sk-...
ANTHROPIC_API_KEY=sk-ant-...
MCP_AUTH_TOKEN=...
MONGO_INITDB_ROOT_PASSWORD=...
```

### 2.6 `hlk-verify-integrity.js`

Kiểm tra sau khi cập nhật HLK:

- Các file HLK bắt buộc tồn tại.
- `hlk.config.json` hợp lệ.
- `.gitignore` có các pattern bảo vệ secrets.
- `.gitattributes` có `merge=ours` cho HLK.
- Các file `.rvf` / `.db` không bị track.

---

## 3. V3 packages — thành phần core

| Package | Vai trò |
|---------|---------|
| `@claude-flow/cli` | CLI 26 commands, 140+ subcommands, MCP server, daemon |
| `@claude-flow/cli-core` | Core CLI logic (dependency) |
| `@claude-flow/codex` | Dual-mode Claude + Codex collaboration |
| `@claude-flow/memory` | AgentDB unification, HNSW, hybrid SQLite+AgentDB |
| `@claude-flow/hooks` | 27 hooks + 12 background workers |
| `@claude-flow/security` | Input validation, path validation, CVE remediation |
| `@claude-flow/mcp` | Standalone MCP server: stdio/http/websocket |
| `@claude-flow/swarm` | Swarm coordination, topologies, consensus |
| `@claude-flow/neural` | SONA, RL algorithms, pattern training |
| `@claude-flow/embeddings` | Embedding service: OpenAI, ONNX, Transformers.js |
| `@claude-flow/guidance` | Governance control plane: compile, enforce, prove |
| `@claude-flow/plugin-agent-federation` | Cross-installation federation, PII-gated data flow |
| `@claude-flow/shared` | Types, events, utilities, plugin interfaces |

---

## 4. Ruflo Core — thành phần

### 4.1 `ruflo/docker-compose.yml`

| Service | Port | Mục đích | Security |
|---------|------|----------|----------|
| `mongodb` | `127.0.0.1:27017` | Lưu conversation, session | `--auth`, `MONGO_INITDB_ROOT_PASSWORD` |
| `mcp-bridge` | `127.0.0.1:3001` | MCP bridge HTTP server | `MCP_BIND_HOST=127.0.0.1`, `MCP_AUTH_TOKEN`, `MCP_ENABLE_TERMINAL=false`, `read_only`, `tmpfs` |
| `nginx` | `3000` | Reverse proxy, static assets | Healthcheck |
| `chat-ui` | `3000` (internal) | RuVocal SvelteKit chat UI | OIDC app-level |

### 4.2 MCP Bridge

- File: `ruflo/src/mcp-bridge/index.js` và `ruflo/src/ruvocal/mcp-bridge/index.js`.
- Nhận request JSON-RPC `tools/call`.
- Gọi `executeTool()`.
- Gate `terminal_execute`: chỉ cho phép nếu `MCP_ENABLE_TERMINAL=true`.
- Auth: `Authorization: Bearer <MCP_AUTH_TOKEN>` khi public bind.

### 4.3 RuVocal Chat UI

- Fork của HuggingFace Chat UI.
- SvelteKit, gọi MCP bridge qua internal network.
- Lưu conversation vào MongoDB.

---

## 5. Luồng hoạt động

### 5.1 Luồng tổng thể: user → Ruflo → tool

```mermaid
sequenceDiagram
    autonumber
    participant U as User
    participant CC as Claude Code
    participant H as HLK Hook Bridge
    participant R as Ruflo MCP Server
    participant T as Tool Executor
    participant M as AgentDB / Memory

    U->>CC: Nhập prompt / lệnh
    CC->>CC: PreToolUse hooks
    CC->>H: JSON {tool_name, tool_input}
    H->>H: Load sanitizer + custom hooks
    H->>H: Kiểm tra/redact secret
    H-->>CC: JSON đã xử lý
    CC->>R: tools/call
    R->>R: Route đến tool
    R->>T: Thực thi
    T->>M: Ghi/không ghi memory
    T-->>R: Kết quả
    R-->>CC: Kết quả
    CC->>CC: PostToolUse hooks
    CC-->>U: Phản hồi
```

### 5.2 Luồng CLI: `npx ruflo memory store -k demo -v "sk-abc..."`

```mermaid
flowchart LR
    A[User chạy lệnh] --> B{HLK enabled?}
    B -->|Yes| C[hlk-loader.js]
    C --> D[Sanitize argv:<br/>-v sk-abc... &rarr; -v [REDACTED]]
    C --> E[Set telemetry env]
    C --> F[Load vault]
    D --> G[bin/cli.js]
    E --> G
    F --> G
    B -->|No| G
    G --> H[v3/@claude-flow/cli/bin/cli.js]
    H --> I{MCP mode?}
    I -->|No| J[CLI parser]
    J --> K[memory store]
    K --> L[AgentDB]
    I -->|Yes| M[MCP stdio server]
```

### 5.3 Luồng MCP server

```mermaid
sequenceDiagram
    autonumber
    participant C as Claude Code
    participant L as hlk-loader.js
    participant M as Ruflo MCP Server
    participant Tr as Tool Registry
    participant E as Executor

    C->>M: Spawn MCP server process
    Note over M,L: NODE_OPTIONS preload hlk-loader.js
    L->>L: Sanitize argv, block telemetry
    M->>C: initialize response
    C->>M: tools/list
    M->>Tr: listMCPTools()
    Tr-->>M: tools
    M-->>C: schemas
    loop Mỗi tool call
        C->>M: tools/call
        M->>E: callMCPTool()
        E-->>M: result
        M-->>C: result
    end
```

### 5.4 Luồng swarm

```mermaid
flowchart TB
    A[User yêu cầu task phức tạp] --> B[swarm init]
    B --> C[Chọn topology: hierarchical-mesh]
    C --> D[Spawn agents song song]
    D --> E[Coordinator / Queen]
    E --> F[Researcher]
    E --> G[Architect]
    E --> H[Coder]
    E --> I[Tester]
    E --> J[Reviewer]
    F --> K[Memory store findings]
    G --> K
    H --> K
    I --> K
    J --> K
    K --> L[consensus / raft]
    L --> M[Return kết quả]
```

---

## 6. Luồng dữ liệu trong AgentDB

```mermaid
flowchart LR
    A[Input] --> B[Embedding model<br/>ONNX / OpenAI]
    B --> C[Vector 384/1536 dim]
    C --> D[HNSW index]
    D --> E[AgentDB .rvf]
    E --> F[Search query]
    F --> G[Top-K ANN]
    G --> H[Retrieve context]
```

Các namespace (không gian nhớ) chính:

| Namespace | Mục đích |
|-----------|----------|
| `patterns` | Lưu pattern thành công |
| `tasks` | Lưu task đã hoàn thành |
| `solutions` | Lưu giải pháp |
| `feedback` | Phản hồi từ user |
| `security` | Phát hiện bảo mật |
| `claude-memories` | Bridge từ Claude Code auto-memory |
| `collaboration` | Dual-mode Claude + Codex chia sẻ |

---

## 7. Cấu trúc hook trong `.claude/settings.json`

Các sự kiện hook:

| Sự kiện | Mô tả | Lệnh gọi |
|---------|-------|----------|
| `PreToolUse` | Trước khi tool chạy | `hlk-hook-bridge.mjs`, `hook-handler.cjs pre-bash` |
| `PostToolUse` | Sau khi tool chạy | `hook-handler.cjs post-edit` |
| `UserPromptSubmit` | Khi user gửi prompt | `hook-handler.cjs route` |
| `SessionStart` | Bắt đầu session | `hook-handler.cjs session-restore`, `auto-memory-hook.mjs import` |
| `SessionEnd` | Kết thúc session | `hook-handler.cjs session-end` |
| `Stop` | Dừng session | `auto-memory-hook.mjs sync` |
| `PreCompact` | Trước khi compact context | `hook-handler.cjs compact-manual/auto` |
| `SubagentStop` | Khi subagent kết thúc | `hook-handler.cjs post-task` |

Thứ tự PreToolUse hiện tại:

1. `hlk-hook-bridge.mjs` — redact/block secrets.
2. `hook-handler.cjs pre-bash` — ruflo command safety.

> HLK chạy trước để ruflo không thấy secret gốc.

---


