#!/usr/bin/env node
// ============================================================================
// HLK/bin/hlk-agy-autopilot.mjs
// ----------------------------------------------------------------------------
// Script thiết lập Antigravity CLI (agy) + Ruflo autopilot cho workspace.
//
// VAI TRÒ: Cấu hình Antigravity CLI để dùng ruflo MCP tools tự động.
//           Sau khi chạy, user chỉ cần gửi mô tả công việc vào agy chat,
//           ruflo tự động chạy full pipeline:
//             swarm_init → agent_spawn → task execute → memory_store → report
//
// Cách dùng:
//   node HLK/bin/hlk-agy-autopilot.mjs --path <workspace> --yes
//
// Yêu cầu:
//   - Antigravity CLI đã cài (agy --version)
//   - Ruflo đã cài trong workspace (npx ruflo)
//   - Node 22 portable (script tự cài nếu chưa có)
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// ---------------------------------------------------------------------------
// Parse CLI args
// ---------------------------------------------------------------------------
const CLI_ARGS = process.argv.slice(2);
const CLI_SET = new Set(CLI_ARGS);
function getArg(name) {
  const idx = CLI_ARGS.indexOf(`--${name}`);
  if (idx >= 0 && idx + 1 < CLI_ARGS.length) return CLI_ARGS[idx + 1];
  return null;
}

const WS_PATH = getArg('path') || process.cwd();
const YES = CLI_SET.has('--yes') || CLI_SET.has('yes');

function log(msg) { console.log(`[hlk-agy-autopilot] ${msg}`); }
function ok(msg) { console.log(`  ✓ ${msg}`); }
function warn(msg) { console.log(`  ⚠ ${msg}`); }
function err(msg) { console.error(`  ✗ ${msg}`); }
log.info = (msg) => console.log(`[hlk-agy-autopilot] ℹ ${msg}`);

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

// Tự cài Node 22 portable nếu chưa có
function ensureNodePortable(ws) {
  const portableNode = path.join(ws, '.tools', 'node', 'node.exe');
  if (fs.existsSync(portableNode)) return portableNode;

  log.info('Chưa có Node portable — cài Node 22.22.3 vào .tools/node/...');
  const toolsDir = path.join(ws, '.tools');
  const nodeDir = path.join(toolsDir, 'node');
  if (!fs.existsSync(toolsDir)) fs.mkdirSync(toolsDir, { recursive: true });

  const zipPath = path.join(toolsDir, 'node-v22.22.3-win-x64.zip');
  const url = 'https://nodejs.org/dist/v22.22.3/node-v22.22.3-win-x64.zip';

  const dl = spawnSync('curl', ['-L', '-o', zipPath, url], { stdio: 'pipe' });
  if (dl.status !== 0) throw new Error('curl thất bại');

  const ex = spawnSync('powershell', ['-NoProfile', '-Command',
    `Expand-Archive -Path '${zipPath}' -DestinationPath '${toolsDir}' -Force`], { stdio: 'pipe' });
  if (ex.status !== 0) throw new Error('Expand-Archive thất bại');

  const extracted = path.join(toolsDir, 'node-v22.22.3-win-x64');
  if (!fs.existsSync(extracted)) throw new Error('Giải nén thất bại');
  if (fs.existsSync(nodeDir)) fs.rmSync(nodeDir, { recursive: true, force: true });
  fs.mkdirSync(nodeDir, { recursive: true });
  for (const item of fs.readdirSync(extracted)) {
    fs.renameSync(path.join(extracted, item), path.join(nodeDir, item));
  }
  fs.rmSync(extracted, { recursive: true, force: true });
  fs.unlinkSync(zipPath);

  // Tạo activate scripts
  fs.writeFileSync(path.join(ws, 'activate.ps1'),
    '# activate.ps1\n$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path\n$nodeDir = Join-Path $wsRoot ".tools\\node"\nif (-not (Test-Path "$nodeDir\\node.exe")) { return }\n$global:_OldPath = $env:PATH\n$env:PATH = "$nodeDir;$env:PATH"\nfunction global:deactivate { if ($global:_OldPath) { $env:PATH = $global:_OldPath } }\nWrite-Host "Node portable: $(& "$nodeDir\\node.exe" --version)"\n');
  fs.writeFileSync(path.join(ws, 'activate.cmd'),
    '@echo off\nset "WS=%~dp0"\nif "%WS:~-1%"=="\\" set "WS=%WS:~0,-1%"\nset "PATH=%WS%\\.tools\\node;%PATH%"\necho Node portable activated\n');

  // .gitignore
  const gi = path.join(ws, '.gitignore');
  if (fs.existsSync(gi)) {
    const c = fs.readFileSync(gi, 'utf8');
    if (!c.includes('.tools/node/')) fs.appendFileSync(gi, '\n.tools/node/\n.tools/*.zip\n');
  }

  ok(`Đã cài Node portable: ${spawnSync(portableNode, ['--version'], { encoding: 'utf8' }).stdout?.trim()}`);
  return portableNode;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  log('=== Antigravity CLI + Ruflo Autopilot Setup ===');
  log(`Workspace: ${WS_PATH}`);

  // 1. Node portable — tự cài nếu chưa có
  let nodeExe;
  try {
    nodeExe = ensureNodePortable(WS_PATH);
  } catch (e) {
    warn(`Không cài được Node portable: ${e.message}`);
    nodeExe = 'node';
  }
  const nodeVer = spawnSync(nodeExe, ['--version'], { encoding: 'utf8' }).stdout?.trim();
  ok(`Node: ${nodeVer} (${nodeExe})`);

  // 2. Kiểm tra Antigravity CLI
  const agyCheck = spawnSync('agy', ['--version'], { encoding: 'utf8', shell: true });
  if (agyCheck.status !== 0) {
    warn('Antigravity CLI (agy) chưa cài. Tải từ https://antigravity.dev/');
  } else {
    ok(`Antigravity CLI: ${agyCheck.stdout.trim()}`);
  }

  // 3. Kiểm tra ruflo
  const rufloCheck = spawnSync(nodeExe, ['node_modules/ruflo/bin/ruflo.js', '--version'], {
    cwd: WS_PATH, encoding: 'utf8'
  });
  if (rufloCheck.status === 0) ok(`Ruflo: ${rufloCheck.stdout.trim()}`);
  else warn('Ruflo chưa cài — chạy hlk-setup-max-power.mjs trước');

  // 4. Kiểm tra HLK wrapper
  const mcpWrapper = path.join(WS_PATH, 'HLK', 'wrappers', 'ruflo-hlk-mcp.mjs');
  if (fs.existsSync(mcpWrapper)) ok('HLK MCP wrapper: có');
  else warn('HLK MCP wrapper không tìm thấy — HLK chưa cài?');

  // 5. Cập nhật .agents/mcp_config.json — dùng Node 22 portable tuyệt đối
  const agentsDir = path.join(WS_PATH, '.agents');
  if (!fs.existsSync(agentsDir)) fs.mkdirSync(agentsDir, { recursive: true });

  const mcpConfigPath = path.join(agentsDir, 'mcp_config.json');
  const mcpConfig = {
    mcpServers: {
      'claude-flow': {
        command: nodeExe,
        args: [mcpWrapper, 'mcp', 'start'],
        env: {
          PATH: path.dirname(nodeExe) + ';C:\\Windows\\System32;C:\\Windows',
        },
      },
    },
  };
  fs.writeFileSync(mcpConfigPath, JSON.stringify(mcpConfig, null, 2));
  ok(`Đã ghi .agents/mcp_config.json (Node: ${path.basename(nodeExe)})`);

  // 6. Cập nhật .agents/config.toml — MCP server dùng Node 22 portable
  const configTomlPath = path.join(agentsDir, 'config.toml');
  let configToml = '';
  if (fs.existsSync(configTomlPath)) {
    configToml = fs.readFileSync(configTomlPath, 'utf8');
  }
  // Thay thế section [mcp_servers.claude-flow] nếu có
  const mcpTomlSection = `[mcp_servers.claude-flow]
command = "${nodeExe.replace(/\\/g, '\\\\')}"
args = ["${mcpWrapper.replace(/\\/g, '\\\\')}", "mcp", "start"]
enabled = true
tool_timeout_sec = 120`;

  if (configToml.includes('[mcp_servers.claude-flow]')) {
    // Thay thế section cũ
    configToml = configToml.replace(
      /\[mcp_servers\.claude-flow\][\s\S]*?(?=\n\[|\n$|$)/,
      mcpTomlSection
    );
  } else {
    configToml += '\n' + mcpTomlSection + '\n';
  }
  fs.writeFileSync(configTomlPath, configToml);
  ok('Đã cập nhật .agents/config.toml (MCP server → Node 22 portable)');

  // 7. Tạo .agents/skills/ruflo-autopilot/SKILL.md
  const skillDir = path.join(agentsDir, 'skills', 'ruflo-autopilot');
  if (!fs.existsSync(skillDir)) fs.mkdirSync(skillDir, { recursive: true });
  const skillMd = path.join(skillDir, 'SKILL.md');
  fs.writeFileSync(skillMd, `---
name: ruflo-autopilot
description: Auto-invoke ruflo MCP tools for any coding task. Use when user asks to build, test, review, refactor, or document code. Automatically runs swarm_init, agent_spawn, memory_search, agent_execute, memory_store.
---

# Ruflo Autopilot Skill (Antigravity CLI)

## Khi nào dùng
Dùng skill này MỌI khi user yêu cầu:
- Viết code / tạo feature mới
- Viết test
- Review code
- Refactor
- Tạo documentation
- Fix bug
- Bất kỳ task coding nào

## Quy trình tự động

1. **memory_search** — Tìm pattern tương tự:
   \`\`\`
   memory_search(query="<task keywords>", namespace="patterns")
   \`\`\`
   Nếu tìm thấy (score > 0.7), dùng pattern đó.

2. **swarm_init** — Khởi tạo swarm:
   \`\`\`
   swarm_init(topology="hierarchical-mesh", maxAgents=15)
   \`\`\`

3. **agent_spawn** — Spawn agents theo task:
   - coder (viết code)
   - tester (viết test)
   - reviewer (review)
   - architect (thiết kế)

4. **hooks_route** — Chọn model:
   \`\`\`
   hooks_route(task="<task description>")
   \`\`\`

5. **agent_execute** — Chạy task trên agent

6. **memory_store** — Lưu pattern:
   \`\`\`
   memory_store(key="<pattern-name>", value="<what worked>", namespace="patterns")
   \`\`\`

7. **swarm_status** — Báo cáo

## Lưu ý
- LUÔN gọi memory_search TRƯỚC khi bắt đầu
- LUÔN gọi memory_store SAU khi hoàn thành
- KHÔNG dừng sau swarm_init — tiếp tục spawn + execute ngay
- Agent spawn là record, KHÔNG phải agent chạy code — BẠN (agy) chạy code
`);
  ok('Đã ghi .agents/skills/ruflo-autopilot/SKILL.md');

  // 8. Tạo AGENTS.md cho agy — hướng dẫn autopilot
  const agentsMd = path.join(WS_PATH, 'AGENTS.md');
  if (!fs.existsSync(agentsMd) || YES) {
    fs.writeFileSync(agentsMd, `# Antigravity CLI + Ruflo Autopilot

## Cách hoạt động

Khi bạn gửi mô tả công việc vào Antigravity CLI, ruflo tự động:

1. **swarm_init** — Khởi tạo swarm (topology hierarchical-mesh, 15 agents)
2. **agent_spawn** — Tạo các agent chuyên biệt (coder, tester, reviewer, architect)
3. **hooks_route** — Chọn model AI phù hợp cho từng task
4. **memory_search** — Tìm pattern tương tự từ memory (học từ quá khứ)
5. **agent_execute** — Chạy task trên agent đã spawn
6. **memory_store** — Lưu kết quả + pattern vào memory để học cho lần sau
7. **swarm_status** — Báo cáo trạng thái

## Lệnh dùng trong Antigravity CLI

\`\`\`bash
# Mở agy tại workspace
cd ${WS_PATH}
agy

# Hoặc non-interactive:
agy -p --dangerously-skip-permissions -- "mô tả công việc"
\`\`\`

## Ví dụ mô tả công việc

- "Tạo API REST cho quản lý user với JWT auth"
- "Viết test cho src/api.ts, coverage > 80%"
- "Review code trong src/ và báo cáo security issues"
- "Refactor src/utils.js thành TypeScript"
- "Tạo documentation cho tất cả public functions"

Ruflo sẽ tự động:
- Khởi tạo swarm với 15 agents
- Spawn coder + tester + reviewer + architect
- Chia task, chạy song song
- Lưu pattern vào memory
- Báo cáo kết quả
`);
    ok('Đã ghi AGENTS.md (autopilot guide)');
  } else {
    warn('AGENTS.md đã tồn tại — dùng --yes để ghi đè');
  }

  // 9. Tạo wrapper agy-run.ps1 + agy-run.cmd
  const agyRunPs1 = path.join(WS_PATH, 'agy-run.ps1');
  fs.writeFileSync(agyRunPs1, `# agy-run.ps1 — Chạy Antigravity CLI với Node 22 portable + ruflo MCP
$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $wsRoot '.tools\\node'
if (Test-Path $nodeDir) { $env:PATH = "$nodeDir;$env:PATH" }
$env:NODE_PATH = Join-Path $wsRoot 'node_modules'
Write-Host "Antigravity CLI + Ruflo Autopilot" -ForegroundColor Cyan
Write-Host "Node: $(node --version)" -ForegroundColor DarkGray
agy @args
`);
  ok('Đã ghi agy-run.ps1');

  const agyRunCmd = path.join(WS_PATH, 'agy-run.cmd');
  fs.writeFileSync(agyRunCmd, `@echo off
set "WS_ROOT=%~dp0"
if "%WS_ROOT:~-1%"=="\\" set "WS_ROOT=%WS_ROOT:~0,-1%"
set "NODE_DIR=%WS_ROOT%\\.tools\\node"
if exist "%NODE_DIR%\\node.exe" set "PATH=%NODE_DIR%;%PATH%"
set "NODE_PATH=%WS_ROOT%\\node_modules"
echo Antigravity CLI + Ruflo Autopilot
agy %*
`);
  ok('Đã ghi agy-run.cmd');

  // 10. Tóm tắt
  log('');
  log('=== Tóm tắt ===');
  ok('MCP config (JSON): .agents/mcp_config.json (Node 22 portable)');
  ok('MCP config (TOML): .agents/config.toml (Node 22 portable)');
  ok('Autopilot guide: AGENTS.md');
  ok('Autopilot skill: .agents/skills/ruflo-autopilot/SKILL.md');
  ok('Wrapper: agy-run.ps1 / agy-run.cmd');
  log('');
  log('Cách dùng:');
  log('  1. Mở terminal tại workspace');
  log('  2. Chạy: .\\agy-run.ps1         (PowerShell)');
  log('     Hoặc: agy-run.cmd            (CMD)');
  log('  3. Gửi mô tả công việc vào chat');
  log('  4. Ruflo tự động chạy full pipeline');
  log('');
  log('Hoặc non-interactive:');
  log('  .\\agy-run.ps1 -p --dangerously-skip-permissions -- "mô tả công việc"');
}

main();
