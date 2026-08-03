#!/usr/bin/env node
// ============================================================================
// HLK/bin/hlk-devin-autopilot.mjs
// ----------------------------------------------------------------------------
// Script thiết lập Devin CLI + Ruflo autopilot cho workspace.
//
// VAI TRÒ: Cấu hình Devin CLI để dùng ruflo MCP tools tự động.
//           Sau khi chạy, user chỉ cần gửi mô tả công việc vào Devin CLI chat,
//           ruflo tự động chạy full pipeline:
//             swarm_init → agent_spawn → task execute → memory_store → report
//
// Cách dùng:
//   node HLK/bin/hlk-devin-autopilot.mjs --path <workspace> --yes
//
// Yêu cầu:
//   - Node >= 22 (hoặc .tools/node/ portable đã cài)
//   - Devin CLI đã cài (devin --version)
//   - Ruflo đã cài trong workspace (npx ruflo)
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

function log(msg) { console.log(`[hlk-devin-autopilot] ${msg}`); }
function ok(msg) { console.log(`  ✓ ${msg}`); }
function warn(msg) { console.log(`  ⚠ ${msg}`); }
function err(msg) { console.error(`  ✗ ${msg}`); }
log.info = (msg) => console.log(`[hlk-devin-autopilot] ℹ ${msg}`);

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------
function main() {
  log('=== Devin CLI + Ruflo Autopilot Setup ===');
  log(`Workspace: ${WS_PATH}`);

  // 1. Kiểm tra Node portable — tự cài nếu chưa có
  const portableNode = path.join(WS_PATH, '.tools', 'node', 'node.exe');
  let nodeExe = fs.existsSync(portableNode) ? portableNode : 'node';
  let nodeVer = spawnSync(nodeExe, ['--version'], { encoding: 'utf8' }).stdout?.trim();

  // Nếu không có portable, thử cài (delegates sang installNodePortable logic đơn giản)
  if (!fs.existsSync(portableNode) && YES) {
    log.info('Chưa có Node portable — cài Node 22.22.3 vào .tools/node/...');
    try {
      const toolsDir = path.join(WS_PATH, '.tools');
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
      fs.writeFileSync(path.join(WS_PATH, 'activate.ps1'),
        '# activate.ps1\n$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path\n$nodeDir = Join-Path $wsRoot ".tools\\node"\nif (-not (Test-Path "$nodeDir\\node.exe")) { return }\n$global:_OldPath = $env:PATH\n$env:PATH = "$nodeDir;$env:PATH"\nfunction global:deactivate { if ($global:_OldPath) { $env:PATH = $global:_OldPath } }\nWrite-Host "Node portable: $(& "$nodeDir\\node.exe" --version)"\n');
      fs.writeFileSync(path.join(WS_PATH, 'activate.cmd'),
        '@echo off\nset "WS=%~dp0"\nif "%WS:~-1%"=="\\" set "WS=%WS:~0,-1%"\nset "PATH=%WS%\\.tools\\node;%PATH%"\necho Node portable activated\n');
      // .gitignore
      const gi = path.join(WS_PATH, '.gitignore');
      if (fs.existsSync(gi)) {
        const c = fs.readFileSync(gi, 'utf8');
        if (!c.includes('.tools/node/')) fs.appendFileSync(gi, '\n.tools/node/\n.tools/*.zip\n');
      }
      nodeExe = portableNode;
      nodeVer = spawnSync(nodeExe, ['--version'], { encoding: 'utf8' }).stdout?.trim();
      ok(`Đã cài Node portable: ${nodeVer}`);
    } catch (e) {
      warn(`Không cài được Node portable: ${e.message}`);
      warn('  Chạy thủ công: node HLK/bin/hlk-setup-max-power.mjs --install-node-portable --path <ws>');
    }
  }

  if (nodeVer) ok(`Node: ${nodeVer} (${nodeExe})`);
  else { err('Node không tìm thấy'); process.exit(1); }

  // 2. Kiểm tra Devin CLI
  const devinCheck = spawnSync('devin', ['--version'], { encoding: 'utf8', shell: true });
  if (devinCheck.status !== 0) {
    warn('Devin CLI chưa cài. Cài: npm install -g @anthropic-ai/devin-cli');
    warn('  (hoặc tải từ https://devin.ai/downloads)');
  } else {
    ok(`Devin CLI: ${devinCheck.stdout.trim()}`);
  }

  // 3. Kiểm tra ruflo
  const rufloCheck = spawnSync(nodeExe, ['node_modules/ruflo/bin/ruflo.js', '--version'], {
    cwd: WS_PATH, encoding: 'utf8'
  });
  if (rufloCheck.status === 0) ok(`Ruflo: ${rufloCheck.stdout.trim()}`);
  else warn('Ruflo chưa cài trong workspace. Chạy: npm install ruflo');

  // 4. Kiểm tra HLK wrapper
  const mcpWrapper = path.join(WS_PATH, 'HLK', 'wrappers', 'ruflo-hlk-mcp.mjs');
  if (fs.existsSync(mcpWrapper)) ok('HLK MCP wrapper: có');
  else warn('HLK MCP wrapper không tìm thấy — HLK chưa cài?');

  // 5. Cập nhật .devin/mcp_config.json — dùng Node portable tuyệt đối
  const devinDir = path.join(WS_PATH, '.devin');
  if (!fs.existsSync(devinDir)) fs.mkdirSync(devinDir, { recursive: true });

  const mcpConfigPath = path.join(devinDir, 'mcp_config.json');
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
  ok(`Đã ghi .devin/mcp_config.json (Node: ${path.basename(nodeExe)})`);

  // 6. Tạo .devin/config.json — permissions cho ruflo
  const configPath = path.join(devinDir, 'config.json');
  const config = {
    permissions: {
      allow: [
        'Exec(npx ruflo:*)',
        'Exec(npx claude-flow:*)',
        'Exec(node:*)',
        'Exec(npm run:*)',
        'Exec(npm test:*)',
        'Exec(git status)',
        'Exec(git diff:*)',
        'Exec(git log:*)',
        'Exec(git add:*)',
        'Exec(git commit:*)',
        'Read(src/**)',
        'Read(tests/**)',
        'Read(docs/**)',
        'Read(HLK/**)',
        'Read(.devin/**)',
      ],
      deny: ['Exec(sudo)', 'Exec(rm -rf /)', 'Read(.env)', 'Read(.env.*)'],
    },
  };
  fs.writeFileSync(configPath, JSON.stringify(config, null, 2));
  ok('Đã ghi .devin/config.json (permissions)');

  // 7. Tạo AGENTS.md cho Devin — hướng dẫn autopilot
  const agentsMd = path.join(WS_PATH, 'AGENTS.md');
  const autopilotGuide = `# Devin CLI + Ruflo Autopilot

## Cách hoạt động

Khi bạn gửi mô tả công việc vào Devin CLI, ruflo tự động:

1. **swarm_init** — Khởi tạo swarm (topology hierarchical-mesh, 15 agents)
2. **agent_spawn** — Tạo các agent chuyên biệt (coder, tester, reviewer, architect)
3. **hooks_route** — Chọn model AI phù hợp cho từng task
4. **memory_search** — Tìm pattern tương tự từ memory (học từ quá khứ)
5. **agent_execute** — Chạy task trên agent đã spawn
6. **memory_store** — Lưu kết quả + pattern vào memory để học cho lần sau
7. **swarm_status** — Báo cáo trạng thái

## Lệnh dùng trong Devin CLI

\`\`\`bash
# Mở Devin CLI tại workspace
cd ${WS_PATH}
devin

# Hoặc non-interactive:
devin -p --permission-mode dangerous -- "mô tả công việc"
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
`;

  // Chỉ ghi nếu chưa có AGENTS.md hoặc ghi đè nếu có --yes
  if (!fs.existsSync(agentsMd) || YES) {
    fs.writeFileSync(agentsMd, autopilotGuide);
    ok('Đã ghi AGENTS.md (autopilot guide)');
  } else {
    warn('AGENTS.md đã tồn tại — dùng --yes để ghi đè');
  }

  // 8. Tạo .devin/skills/ruflo-autopilot/ — skill hướng Devin dùng ruflo
  const skillDir = path.join(devinDir, 'skills', 'ruflo-autopilot');
  if (!fs.existsSync(skillDir)) fs.mkdirSync(skillDir, { recursive: true });
  const skillMd = path.join(skillDir, 'SKILL.md');
  fs.writeFileSync(skillMd, `---
name: ruflo-autopilot
description: Auto-invoke ruflo MCP tools for any coding task. Use when user asks to build, test, review, refactor, or document code. Automatically runs swarm_init, agent_spawn, memory_search, agent_execute, memory_store.
---

# Ruflo Autopilot Skill

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
- Agent spawn là record, KHÔNG phải agent chạy code — BẠN (Devin) chạy code
`);
  ok('Đã ghi .devin/skills/ruflo-autopilot/SKILL.md');

  // 9. Tạo wrapper script để chạy Devin với Node 22 + ruflo
  const devinRunPs1 = path.join(WS_PATH, 'devin-run.ps1');
  fs.writeFileSync(devinRunPs1, `# devin-run.ps1 — Chạy Devin CLI với Node 22 portable + ruflo MCP
$wsRoot = Split-Path -Parent $MyInvocation.MyCommand.Path
$nodeDir = Join-Path $wsRoot '.tools\\node'
if (Test-Path $nodeDir) { $env:PATH = "$nodeDir;$env:PATH" }
$env:NODE_PATH = Join-Path $wsRoot 'node_modules'
Write-Host "Devin CLI + Ruflo Autopilot" -ForegroundColor Cyan
Write-Host "Node: $(node --version)" -ForegroundColor DarkGray
devin @args
`);
  ok('Đã ghi devin-run.ps1');

  const devinRunCmd = path.join(WS_PATH, 'devin-run.cmd');
  fs.writeFileSync(devinRunCmd, `@echo off
set "WS_ROOT=%~dp0"
if "%WS_ROOT:~-1%"=="\\" set "WS_ROOT=%WS_ROOT:~0,-1%"
set "NODE_DIR=%WS_ROOT%\\.tools\\node"
if exist "%NODE_DIR%\\node.exe" set "PATH=%NODE_DIR%;%PATH%"
set "NODE_PATH=%WS_ROOT%\\node_modules"
echo Devin CLI + Ruflo Autopilot
devin %*
`);
  ok('Đã ghi devin-run.cmd');

  // 10. Tóm tắt
  log('');
  log('=== Tóm tắt ===');
  ok('MCP config: .devin/mcp_config.json (Node 22 portable)');
  ok('Permissions: .devin/config.json');
  ok('Autopilot guide: AGENTS.md');
  ok('Autopilot skill: .devin/skills/ruflo-autopilot/SKILL.md');
  ok('Wrapper: devin-run.ps1 / devin-run.cmd');
  log('');
  log('Cách dùng:');
  log('  1. Mở terminal tại workspace');
  log('  2. Chạy: .\\devin-run.ps1    (PowerShell)');
  log('     Hoặc: devin-run.cmd       (CMD)');
  log('  3. Gửi mô tả công việc vào chat');
  log('  4. Ruflo tự động chạy full pipeline');
  log('');
  log('Hoặc non-interactive:');
  log('  .\\devin-run.ps1 -p --permission-mode dangerous -- "mô tả công việc"');
}

main();
