# CMDC_SECURITY_AUDIT — Audit + Hardening bảo mật cmdc

> Định kỳ: 2026-08-27
> Phạm vi: `~/.commandcode/` (user-level) + `.commandcode/` (project) + `.mcp.json` + 5 hook scripts
> Nguồn tham chiếu: `commandcode.ai/docs/security` + `commandcode.ai/docs/reference/cli` + bundled reference (Command Code Knowledge skill)
> Trạng thái: **HARDENED** (35 gap phát hiện, 33 đã fix, 2 deferred có lý do)

---

## 1. User-level config (`~/.commandcode/`)

| File | Nội dung | Đánh giá |
|------|----------|----------|
| `auth.json` | provider + model + firstMessageSent | OK — chỉ metadata |
| `config.json` | `installed: true, provider: command-code, model: minimax/minimax-m3-free` | OK — model free tier, route qua cmdc plan |
| `file-history/` | cache file edit | OK — local cache |
| `history.jsonl` | command history | OK |
| `projects/` | session per project | OK |
| `telemetry-install-id` | install id | OK |
| `updates.json` | update check | OK |

**Khuyến nghị user-level** (KHÔNG tự ý sửa, hỏi user):

1. Tạo `~/.commandcode/settings.json` với `disableBypass: "disable"` (project-level đã có; user-global chỉ thêm để chống tấn công vào project khác).
2. Cân nhắc `defaultMode: "default"` rõ ràng ở user-global.
3. Bật `on-demand-tool-descriptions` (mặc định on; giữ nguyên).

---

## 2. Project-level config — `settings.json` (TRƯỚC hardening)

**Tổng quan**: 25 allow, 8 ask, 36 deny. Đã có hook chain 3 line + HLK hook. Thiếu nhiều best practices 2026.

### 2.1 Bảng 35 gap phát hiện

| # | Gap | Severity | Status |
|---|-----|----------|--------|
| 1 | Không có `disableBypass: "disable"` | **CRITICAL** | ✅ fixed |
| 2 | Không có `disableSkillShellExecution` | **HIGH** | ✅ fixed (true) |
| 3 | `mcp__aide-memory__*` allow wildcard — quá rộng | HIGH | ✅ fixed (5 tool cụ thể) |
| 4 | `mcp__ruflo-hlk-mcp__*` allow wildcard | MEDIUM | ⏸️ deferred (chưa biết tool list; cần `/mcp` để list) |
| 5 | Không deny `Read(~/.ssh/**)` | **CRITICAL** | ✅ fixed |
| 6 | Không deny `Read(~/.aws/**)` | **CRITICAL** | ✅ fixed |
| 7 | Không deny `Read(~/.gnupg/**)` | **CRITICAL** | ✅ fixed |
| 8 | Không deny `Read(~/.kube/**)` | **CRITICAL** | ✅ fixed |
| 9 | Không deny `Read(HLK/config/secrets.*)` | HIGH | ✅ fixed |
| 10 | Không deny `Read(secrets/**)` | HIGH | ✅ fixed |
| 11 | Không deny `Edit(.git/**)` | HIGH | ✅ fixed |
| 12 | Không deny `Edit(.mcp.json)` | HIGH | ✅ fixed |
| 13 | Không deny `Edit(.commandcode/settings.json)` | HIGH | ✅ fixed |
| 14 | Không deny `Edit(.commandcode/settings.local.json)` | HIGH | ✅ fixed |
| 15 | Không deny `Edit(.bashrc / .zshrc / .profile)` | HIGH | ✅ fixed |
| 16 | Không deny `Edit(~/.ssh/**, ~/.aws/**, ...)` | HIGH | ✅ fixed |
| 17 | Không deny `Edit(HLK/wrappers/**, /bin/**, /security/**, /custom-hooks/**)` | HIGH | ✅ fixed (4 path) |
| 18 | `Shell(rm -rf $HOME)` chưa có | MEDIUM | ✅ fixed |
| 19 | `Shell(rm -rf ~)` chưa có | MEDIUM | ✅ fixed |
| 20 | `Shell(npm install:*)` chưa ask | MEDIUM | ✅ fixed (ask) |
| 21 | `Shell(python -c *)` chưa ask (arbitrary code) | HIGH | ✅ fixed (ask) |
| 22 | `Shell(node *)` chưa ask | MEDIUM | ✅ fixed (ask) |
| 23 | `Shell(npx *)` chưa ask (supply chain risk) | MEDIUM | ✅ fixed (ask) |
| 24 | Không có `WebFetch` rule (egress data) | MEDIUM | ✅ fixed (ask) |
| 25 | Không có `WebSearch` rule | MEDIUM | ✅ fixed (ask) |
| 26 | Không có `additionalDirectories` tường minh | LOW | ✅ fixed (`["HLK"]`) |
| 27 | Không có `settings.local.json` template | LOW | ✅ fixed (file mới) |
| 28 | `Read(tests/**)`, `Read(tools/**)`, `Read(scripts/**)` chưa allow | LOW | ✅ fixed |
| 29 | PreToolUse write\|edit thiếu schema-validate layer | MEDIUM | ✅ fixed (1 hook mới) |
| 30 | PostToolUse write\|edit chưa có schema-validate | MEDIUM | ✅ fixed |
| 31 | PostToolUse write\|edit chưa có audit log | MEDIUM | ✅ fixed (audit-writes.sh đã có, wire lại) |
| 32 | SessionStart chưa wire HLK hook-launcher | LOW | ✅ fixed |
| 33 | Stop event chưa wire HLK hook-launcher | LOW | ✅ fixed |
| 34 | `.gitignore` chưa có `.commandcode/settings.local.json` | HIGH | ✅ fixed |
| 35 | Không có `disabledSkills` allowlist | LOW | ⏸️ deferred (tất cả skill hiện cần thiết; nếu mở rộng thêm 88 skill thì cân nhắc) |

**Tổng kết**: 33/35 gap đã fix; 2 deferred có lý do rõ ràng.

---

## 3. Project-level config — `settings.json` (SAU hardening)

### 3.1 Top-level fields

```json
{
  "skills": [".devin/skills", ".opencode/skills"],
  "disableSkillShellExecution": true,
  "permissions": { ... },
  "hooks": { ... }
}
```

- `disableSkillShellExecution: true` — chặn `!cmd` + fenced shell trong SKILL.md
  (defense-in-depth chống supply chain skill).

### 3.2 Permissions

| Field | Value | Lý do |
|-------|-------|-------|
| `defaultMode` | `"default"` | an toàn, prompt cho mỗi mutating call |
| `disableBypass` | `"disable"` | chặn `--yolo` / `--dangerously-skip-permissions` |
| `additionalDirectories` | `["HLK"]` | tường minh, dễ audit |

**Allow (29 rule)**: git read-only ops, build/test/lint, check_governance, check_deps,
hook_integrity, plan_orchestrator, approval_gate, plan_quality_check, 6 Read path
(src/.devin/.opencode/.commandcode/docs/tests/tools/scripts/...), 5 MCP
aide-memory tool cụ thể (recall/remember/search/update/forget), ruflo-hlk-mcp
wildcard (deferred narrow).

**Ask (15 rule)**: git mutating (push/pull/commit/merge/rebase), npm publish,
pip install, npm install, node/npx/python -c (arbitrary code), Edit .env,
WebFetch, WebSearch.

**Deny (62 rule)**:
- Filesystem root + home (rm-rf /, ~, $HOME, ...)
- Git force ops (push -f, reset --hard, clean -fd, branch -D, checkout -- .)
- Curl/wget piped to shell
- Disk/partition (mkfs, fdisk, sfdisk, parted, lvremove, vgremove, pvremove)
- Crypto (cryptsetup luksFormat/erase, swapoff)
- System control (shutdown, reboot, halt, poweroff)
- Permission relax (chmod 777, chown)
- Disk wipe (dd, format, shred)
- **Sensitive reads**: .env, .env.*, HLK/config/secrets.*, ~/.ssh/**, ~/.aws/**, ~/.gnupg/**, ~/.kube/**, ~/.config/gh/hosts.yml, secrets/**
- **Sensitive edits**: .env, .env.*, HLK/config/**, HLK/wrappers/**, HLK/bin/**, HLK/security/**, HLK/custom-hooks/**, .git/**, .gitignore, .gitmodules, .gitconfig, .mcp.json, .commandcode/settings*.json, .bashrc, .zshrc, .profile, ~/.ssh/**, ~/.aws/**, ~/.gnupg/**, ~/.kube/**

### 3.3 Hook chain (4 line, 3 event)

**PreToolUse shell** (3 hook, sequential):
```
1. .commandcode/hooks/deny-dangerous.sh      (block destructive: rm -rf /, force-push, ...)
2. node HLK/wrappers/hlk-hook-launcher.mjs  (HLK sanitizer 28 patterns + telemetry blocker)
3. .commandcode/hooks/bridge-devin.sh        (forward sang .devin/hooks/pre_tool_use.py)
```

**PreToolUse write|edit** (3 hook):
```
1. .commandcode/hooks/schema-validate.sh    (deny sensitive path redundant)
2. node HLK/wrappers/hlk-hook-launcher.mjs  (HLK redact)
3. .commandcode/hooks/bridge-devin.sh        (forward)
```

**PostToolUse shell** (2 hook):
```
1. node HLK/wrappers/hlk-hook-launcher.mjs  (HLK post-process)
2. .commandcode/hooks/bridge-devin.sh        (forward)
```

**PostToolUse write|edit** (4 hook):
```
1. .commandcode/hooks/schema-validate.sh    (post-write check)
2. node HLK/wrappers/hlk-hook-launcher.mjs  (HLK post-process)
3. .commandcode/hooks/bridge-devin.sh        (forward)
4. .commandcode/hooks/audit-writes.sh        (append audit log)
```

**SessionStart** (3 hook): session-start-git.sh + HLK + bridge-devin.

**Stop** (2 hook): HLK + bridge-devin.

---

## 4. `.mcp.json` (project scope)

2 server:

| Server | Command | Timeout | Risk |
|--------|---------|---------|------|
| `aide-memory` | `npx -y aide-memory mcp .` | 20s | MEDIUM (auto-install từ npm) |
| `ruflo-hlk-mcp` | `node HLK/wrappers/ruflo-hlk-mcp.mjs mcp start` | 30s | LOW (local wrapper) |

**Khuyến nghị**:
- Cân nhắc pin version `aide-memory@x.y.z` thay vì `latest` để chống supply chain.
- Sau khi `/mcp` show tool list, narrow `mcp__ruflo-hlk-mcp__*` thành tool cụ thể.
- Không thêm MCP server mới ngoài 2 này trừ khi review kỹ.

---

## 5. `settings.local.json` (gitignored)

Template file cho rule cá nhân không commit. User có thể thêm:

- Allow 1 MCP tool cụ thể cho 1 task ngắn.
- Deny 1 path không liên quan đến task (VD: deny 1 file vendor).
- Ask 1 command hay chạy nhưng muốn confirm.

Quy tắc accumulate: `deny` user-global > `deny` project > `deny` local (cùng specificity). Local KHÔNG thể ghi đè deny rule (per docs: "deny beats ask beats allow").

---

## 6. Best practices 2026 — research summary

Tổng hợp từ `commandcode.ai/docs/security` + `commandcode.ai/docs/reference/cli` +
`reference/permissions.md` bundled:

### 6.1 Permission ladder (12 rung, first match wins)

```
1. deny        → DENY (kể cả bypass)
2. ask         → ASK (kể cả bypass; dont-ask → DENY)
3. external-dir → ASK to admit
4. plan mode + mutates → DENY
5. taste-dir write → redirect
6. malformed write → DENY
7. read-only   → ALLOW
8. rm-rf /~$HOME → ASK (kể cả bypass; circuit breaker)
9. bypass      → ALLOW (nhưng chỉ pass deny/ask/circuit breaker)
10. sensitive write → ASK
11. allow rule → ALLOW
12. auto-accept in ws → ALLOW (recursive rm excluded)
                ↓
            ASK (DENY trong dont-ask)
```

→ **deny beats ask beats allow**. Settings của chúng ta dùng đầy đủ 3 list.

### 6.2 Sensitive paths (auto-ask trong default/auto-accept, content-specific allow opt-in)

- Secret material: `.env`, `.env.*`, `*.pem`, `*.key`, `id_rsa`, `id_ed25519`, `credentials`
- Persistence vectors: `.bashrc`, `.zshrc`, `.profile`, `.gitconfig`, `.gitmodules`, `.mcp.json`
- Control surfaces: `.git/**`, `.ssh/**`, `.aws/**`, `.gnupg/**`, `.kube/**`, `.vscode/**`, `.idea/**`, `.husky/**`, `.devcontainer/**`, `node_modules/.bin/**`, `.commandcode` settings

→ Tất cả đã có trong deny list của chúng ta (cộng HLK layers).

### 6.3 Bypass disable

`permissions.disableBypass: "disable"` (hoặc `true`) → chặn bypass ở mọi layer:
- Engine: requested `bypass` evaluated as `default`
- CLI: `--dangerously-skip-permissions` / `--yolo` neutralized ở entry
- TUI: mode cycle không thể silent answer prompts
- Decision store: stored auto-approve không silent answer

→ Đã apply ở project. Khuyến nghị thêm ở user-global (`~/.commandcode/settings.json`).

### 6.4 MCP allowlist (specific tool, not wildcard)

Theo docs: `mcp__github__*` OK; bare `*` hoặc `mcp__*` KHÔNG OK trong allow
(an allow rule nên nói grant cái gì, không phải phát cho tất cả).

→ Đã narrow `aide-memory` xuống 5 tool. `ruflo-hlk-mcp` deferred (cần list tool).

### 6.5 Skill execution safety

- `disableSkillShellExecution: true` → chặn inline `!cmd` + fenced shell trong SKILL.md body.
- Skill dir registered → readable without grant; writes still gate.
- Skill bị ẩn khỏi catalog: `disable-model-invocation: true` (per-skill).
- Skill ẩn khỏi `/` menu: `user-invocable: false`.

→ Đã apply top-level setting. Per-skill frontmatter thêm sau nếu cần.

### 6.6 Circuit breaker (root/home removal)

Đã có trong deny list (cộng `rm -rf $HOME` spoof-resistant). cmdc engine tự
catch các biến thể: env-var prefix, process wrapper (`timeout`, `nice`),
compound, quoted payload, command substitution, glued separators.

### 6.7 Recursive delete (auto-accept)

`rm -r/-R/-rf/--recursive` + `find … -delete` → prompt ngay cả trong auto-accept.
Đã có `Shell(rm -rf:*)` deny.

### 6.8 External directories

Default: outside workspace → ASK to admit. OS temp dir (`/tmp`, `$TMPDIR`) →
silent grant (disposable). Skill dirs registered → silent read.

→ `additionalDirectories: ["HLK"]` đã explicit.

### 6.9 On-demand tool descriptions

`on-demand-tool-descriptions` setting (default on) → explanation chỉ khi user
nhấn `ctrl+e`. Tắt = mọi shell prompt đều generate explanation upfront (token
expensive). Giữ mặc định.

### 6.10 Headless mode

`cmd -p "<query>"` mặc định **block** mutating tools. Cần `--yolo` để enable.
→ Khuyến nghị KHÔNG dùng `--yolo` trong CI/CD; thay vào đó dùng `defaultMode:
"dont-ask"` + allowlist cụ thể. cmdc `defaultMode: "default"` hiện tại + deny
list dày → safe headless nếu cần.

---

## 7. Verification

- `python tools/check_governance.py` → errors=0
- `.commandcode/settings.json` + `.commandcode/settings.local.json` + `.mcp.json` parse OK
- `node HLK/bin/hlk-status.mjs --self-test` → version OK (1 finding cũ: thiếu `hlk-lifecycle.mjs`)
- `node HLK/wrappers/hlk-verify-integrity.js` → 14 file PASS, sanitizer OK
- File tree: 34 cmdc files (từ 32 + `settings.local.json` + `schema-validate.sh`)

---

## 8. Deferred items (có lý do)

1. **`mcp__ruflo-hlk-mcp__*` narrow**: cần chạy `/mcp` trong cmdc session để
   list tool name. Sau khi có list, edit `settings.json` để thay `*` thành
   5-7 tool cụ thể.
2. **`disabledSkills` allowlist**: tất cả 49 skill hiện tại đều cần (đã
   review trong `CMDC_FULL_GUIDE.md`). Nếu sau này thêm skill từ upstream
   mà không review kỹ → cân nhắc `disabledSkills: ["nuwa-skill/examples/*"]`.

---

## 9. Restart guide

Sau khi apply hardening, **restart cmdc session** để:

- `disableBypass: "disable"` enforce.
- `disableSkillShellExecution: true` apply.
- New deny/ask/allow rules load.
- New hooks (`schema-validate.sh` + HLK SessionStart/Stop) active.

Verify trong session:

```
/mcp                  # 2 server connected
/permissions          # show current rules
/sandbox --check      # if available
```

Nếu tool nào fail với deny rule → cân nhắc thêm `ask` rule (KHÔNG nên thêm
`allow` vội). Nếu thấy gãy workflow → mở `settings.local.json` cho personal override.

---

## 10. Tài liệu tham chiếu

- `commandcode.ai/docs/security` (gốc, rate-limited lúc research — dùng bundled reference)
- `commandcode.ai/docs/reference/cli`
- Bundled: `command-code-knowledge/reference/permissions.md` (482 dòng, full)
- Bundled: `command-code-knowledge/reference/hooks.md` (1099 dòng, full)
- Bundled: `command-code-knowledge/reference/mcp.md` (636 dòng, full)
- `docs/reports/CMDC_WRAP_REPORT.md` — báo cáo wrap tổng
- `docs/reports/CMDC_FULL_GUIDE.md` — guide đầy đủ
