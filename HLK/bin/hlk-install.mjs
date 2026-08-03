#!/usr/bin/env node
/**
 * hlk-install.mjs
 * ===============
 * Cài đặt HLK vào một workspace Ruflo / Claude Flow (từ npm package hlk-ruflo).
 *
 * VAI TRÒ: Cài HLK layer vào workspace đã có ruflo. Không cấu hình MAX POWER.
 *           Dùng hlk-setup-max-power.mjs nếu muốn cài đầy đủ Ruflo + HLK + 3 CLI.
 *
 * Cách dùng:
 *   npx hlk-install
 *   # hoặc
 *   node HLK/bin/hlk-install.mjs
 *
 * Yêu cầu:
 *   - Node >= 20
 *   - Thư mục hiện tại là workspace Ruflo (có .claude/settings.json hoặc package.json ruflo/claude-flow)
 */

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';
import { randomBytes } from 'node:crypto';

// Module dùng chung: hỏi human đang dùng CLI nào + trả paths cấu hình cho CLI đó.
// Trước đây installer hard-code cho Claude Code, nên Devin/agy không thấy MCP ruflo.
// Giờ hỏi thẳng human rồi chỉ cấu hình cho CLI đã chọn (hoặc cả 3 nếu chọn 'all').
import {
  promptCli, cliTargets, cliConfigDir, cliMcpConfigPath, cliHooksPath,
  cliSkillsDir, cliDisplayName, ensureCliDirs, hookCommand,
} from '../wrappers/hlk-cli-select.mjs';

// Kiểm tra Node version tối thiểu
const NODE_MAJOR = parseInt(process.versions.node.split('.')[0], 10);
if (NODE_MAJOR < 14) {
  process.stderr.write('❌ Node >= 14 yêu cầu để chạy HLK installer.\n');
  process.exit(1);
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// Đường dẫn gốc của package HLK (nơi chứa package.json)
const HLK_PACKAGE_ROOT = path.resolve(__dirname, '..');
const WORKSPACE_ROOT = process.cwd();
const HLK_TARGET_DIR = path.join(WORKSPACE_ROOT, 'HLK');

// Danh sách thư mục cần copy từ package sang workspace
const HLK_CONTENT_DIRS = [
  'config',
  'wrappers',
  'security',
  'custom-hooks',
  'docs',
  'prompts',
  'reports',
  'loop',
  'git-tools',
];

// File riêng lẻ cần copy
const HLK_CONTENT_FILES = ['README.md', 'INSTALL.md'];

// File cần tồn tại để xác định workspace Ruflo
const RUFLO_MARKERS = [
  '.claude',
  'package.json',
  'bin/cli.js',
  'v3/@claude-flow/cli/bin/cli.js',
];

// ---------------------------------------------------------------------------
// Tiện ích log
// ---------------------------------------------------------------------------

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

// ---------------------------------------------------------------------------
// Sao chép đệ quy — tương thích Node cũ hơn fs.cpSync
// ---------------------------------------------------------------------------

function copyRecursive(src, dst, options = {}) {
  if (typeof fs.cpSync === 'function') {
    fs.cpSync(src, dst, { recursive: true, force: true, ...options });
    return;
  }

  if (!fs.existsSync(dst)) {
    fs.mkdirSync(dst, { recursive: true });
  }

  const entries = fs.readdirSync(src, { withFileTypes: true });
  for (const entry of entries) {
    const srcPath = path.join(src, entry.name);
    const dstPath = path.join(dst, entry.name);

    if (entry.isDirectory()) {
      copyRecursive(srcPath, dstPath, options);
    } else {
      fs.copyFileSync(srcPath, dstPath);
    }
  }
}

// ---------------------------------------------------------------------------
// Bước 1: Xác định workspace
// ---------------------------------------------------------------------------

function detectRufloWorkspace() {
  const markers = RUFLO_MARKERS.filter((m) => {
    const p = path.join(WORKSPACE_ROOT, m);
    return fs.existsSync(p);
  });

  if (markers.length === 0) {
    log('error', `Thư mục hiện tại không giống workspace Ruflo: ${WORKSPACE_ROOT}`);
    log('error', 'Thiếu ít nhất một trong các dấu hiệu: .claude/, package.json, bin/cli.js');
    process.exit(1);
  }

  let packageName = null;
  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(WORKSPACE_ROOT, 'package.json'), 'utf8'));
    packageName = pkg.name;
  } catch { /* ignore */ }

  if (packageName && !['claude-flow', 'ruflo'].some((n) => packageName.includes(n))) {
    log('warn', `package.json name là "${packageName}" — không chắc là Ruflo, nhưng vẫn tiếp tục.`);
  }

  log('info', `Workspace Ruflo: ${WORKSPACE_ROOT}`);
}

// ---------------------------------------------------------------------------
// Bước 2: Sao lưu HLK cũ nếu có
// ---------------------------------------------------------------------------

function backupExistingHlk() {
  if (!fs.existsSync(HLK_TARGET_DIR)) return;

  const ts = Date.now();
  const backupDir = path.join(WORKSPACE_ROOT, `HLK.backup.${ts}`);
  copyRecursive(HLK_TARGET_DIR, backupDir);
  log('info', `Đã sao lưu HLK cũ sang: ${backupDir}`);
}

// ---------------------------------------------------------------------------
// Bước 3: Copy nội dung HLK
// ---------------------------------------------------------------------------

function copyContent() {
  fs.mkdirSync(HLK_TARGET_DIR, { recursive: true });

  for (const dir of HLK_CONTENT_DIRS) {
    const src = path.join(HLK_PACKAGE_ROOT, dir);
    const dst = path.join(HLK_TARGET_DIR, dir);
    if (!fs.existsSync(src)) continue;

    copyRecursive(src, dst);
    log('success', `Đã copy ${dir}/`);
  }

  for (const file of HLK_CONTENT_FILES) {
    const src = path.join(HLK_PACKAGE_ROOT, file);
    const dst = path.join(HLK_TARGET_DIR, file);
    if (!fs.existsSync(src)) continue;

    fs.copyFileSync(src, dst);
    log('success', `Đã copy ${file}`);
  }
}

// ---------------------------------------------------------------------------
// Hỏi human đang dùng CLI nào (nếu chưa truyền qua biến môi trường HLK_CLI)
// ---------------------------------------------------------------------------

let CLI_CHOICE = process.env.HLK_CLI || null; // 'claude' | 'devin' | 'agy' | 'all'

async function askCliChoice() {
  if (CLI_CHOICE) {
    log('info', `CLI (từ HLK_CLI): ${CLI_CHOICE}`);
    return CLI_CHOICE;
  }
  const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
  const choice = await promptCli(rl);
  rl.close();
  return choice;
}

// ---------------------------------------------------------------------------
// Bước 4: Patch cấu hình MCP + hooks cho từng CLI đã chọn
// ---------------------------------------------------------------------------
// Trước đây chỉ patch .claude/settings.json → Devin/agy không thấy MCP ruflo.
// Giờ lặp qua danh sách CLI đã chọn, với mỗi CLI ghi đúng file cấu hình của nó:
//   - claude: .claude/settings.json (mcpServers + hooks.PreToolUse cùng file)
//   - devin:  .devin/mcp_config.json (mcpServers) + .devin/hooks.v1.json (hooks)
//   - agy:    .agents/mcp_config.json (mcpServers) — agy không có hooks file
// Hook command dùng hlk-hook-launcher.mjs (trung tính, không phụ thuộc $CLAUDE_PROJECT_DIR).

const HLK_PRETOOLUSE = {
  hooks: [hookCommand(5000)],
};

function writeMcpEntry() {
  return {
    command: 'node',
    args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start'],
  };
}

function patchClaudeSettings(ws) {
  const settingsPath = path.join(ws, '.claude', 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    log('warn', 'Không tìm thấy .claude/settings.json — bỏ qua patch Claude.');
    return;
  }

  const raw = fs.readFileSync(settingsPath, 'utf8');
  let settings;
  try {
    settings = JSON.parse(raw);
  } catch (err) {
    log('error', `.claude/settings.json lỗi parse: ${err.message}`);
    process.exit(1);
  }

  if (!settings.hooks) settings.hooks = {};
  if (!Array.isArray(settings.hooks.PreToolUse)) settings.hooks.PreToolUse = [];

  const hasHlkHook = settings.hooks.PreToolUse.some((entry) =>
    entry.hooks?.some((h) => h.command?.includes('hlk-hook-launcher.mjs') || h.command?.includes('hlk-hook-bridge.mjs'))
  );

  if (!hasHlkHook) {
    settings.hooks.PreToolUse.unshift(HLK_PRETOOLUSE);
    log('success', 'Đã thêm HLK PreToolUse hook (launcher trung tính).');
  } else {
    // Nâng cấp hook cũ dùng $CLAUDE_PROJECT_DIR sang launcher trung tính
    settings.hooks.PreToolUse = settings.hooks.PreToolUse.map((entry) => {
      if (!entry.hooks) return entry;
      return {
        ...entry,
        hooks: entry.hooks.map((h) => {
          if (h.command?.includes('hlk-hook-bridge.mjs') && h.command.includes('$CLAUDE_PROJECT_DIR')) {
            return hookCommand(h.timeout ?? 5000);
          }
          return h;
        }),
      };
    });
    log('info', 'HLK PreToolUse hook đã có (đã nâng cấp sang launcher trung tính).');
  }

  if (!settings.mcpServers) settings.mcpServers = {};
  const cur = settings.mcpServers['claude-flow'];
  const usesHlk = cur?.args?.some((a) => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));
  if (!usesHlk) {
    settings.mcpServers['claude-flow'] = writeMcpEntry();
    log('success', 'Đã cập nhật mcpServers.claude-flow dùng HLK MCP wrapper.');
  } else {
    log('info', 'mcpServers.claude-flow đã dùng HLK wrapper.');
  }

  try {
    const pkg = JSON.parse(fs.readFileSync(path.join(ws, 'package.json'), 'utf8'));
    if (pkg?.version && settings.claudeFlow) {
      settings.claudeFlow.version = pkg.version;
      log('success', `Đồng bộ claudeFlow.version = ${pkg.version}`);
    }
  } catch { /* ignore */ }

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + '\n', 'utf8');
  log('success', 'Đã ghi .claude/settings.json');
}

function patchDevinSettings(ws) {
  ensureCliDirs(ws, 'devin');

  // .devin/mcp_config.json — MCP servers
  const mcpPath = cliMcpConfigPath(ws, 'devin');
  const devinMcp = { mcpServers: { 'claude-flow': writeMcpEntry() } };
  fs.writeFileSync(mcpPath, JSON.stringify(devinMcp, null, 2) + '\n', 'utf8');
  log('success', 'Đã ghi .devin/mcp_config.json');

  // .devin/hooks.v1.json — lifecycle hooks (dùng launcher trung tính)
  const hooksPath = cliHooksPath(ws, 'devin');
  const devinHooks = {
    PreToolUse: [
      {
        matcher: 'exec',
        hooks: [hookCommand(5)],
      },
    ],
  };
  fs.writeFileSync(hooksPath, JSON.stringify(devinHooks, null, 2) + '\n', 'utf8');
  log('success', 'Đã ghi .devin/hooks.v1.json (PreToolUse launcher trung tính)');
}

function patchAgySettings(ws) {
  ensureCliDirs(ws, 'agy');

  // .agents/mcp_config.json — MCP servers (agy đọc file này)
  const mcpPath = cliMcpConfigPath(ws, 'agy');
  const agyMcp = { mcpServers: { 'claude-flow': writeMcpEntry() } };
  fs.writeFileSync(mcpPath, JSON.stringify(agyMcp, null, 2) + '\n', 'utf8');
  log('success', 'Đã ghi .agents/mcp_config.json');
}

function patchCliSettingsAll(ws, targets) {
  log('info', `Bước 4: Patch cấu hình cho ${targets.length} CLI: ${targets.map(cliDisplayName).join(', ')}`);
  for (const cli of targets) {
    log('info', `  → ${cliDisplayName(cli)}`);
    if (cli === 'claude') patchClaudeSettings(ws);
    else if (cli === 'devin') patchDevinSettings(ws);
    else if (cli === 'agy') patchAgySettings(ws);
  }
}

// ---------------------------------------------------------------------------
// Bước 5: Patch .gitattributes
// ---------------------------------------------------------------------------

const HLK_GITATTRIBUTES_LINES = [
  '# HLK docs — keep ours',
  'HLK/docs/** merge=ours',
  '',
  '# .claude settings — keep ours to prevent upstream ruflo from',
  '# overwriting HLK PreToolUse/MCP wrapper customizations.',
  '# Review upstream changes manually if needed.',
  '.claude/settings.json merge=ours',
];

function patchGitAttributes() {
  const gitattributesPath = path.join(WORKSPACE_ROOT, '.gitattributes');
  let content = '';
  if (fs.existsSync(gitattributesPath)) {
    content = fs.readFileSync(gitattributesPath, 'utf8');
  }

  // Kiểm tra từng dòng, thêm nếu thiếu
  let modified = false;
  for (const line of HLK_GITATTRIBUTES_LINES) {
    if (line.startsWith('#')) {
      // vẫn thêm comment nếu chưa có
      if (!content.includes(line)) {
        content += (content.endsWith('\n') ? '' : '\n') + line + '\n';
        modified = true;
      }
    } else {
      const pattern = line.split(' ')[0];
      if (!content.includes(pattern)) {
        content += (content.endsWith('\n') ? '' : '\n') + line + '\n';
        modified = true;
      }
    }
  }

  if (modified) {
    fs.writeFileSync(gitattributesPath, content, 'utf8');
    log('success', 'Đã cập nhật .gitattributes với HLK merge=ours.');
  } else {
    log('info', '.gitattributes đã chứa HLK merge rules.');
  }
}

// ---------------------------------------------------------------------------
// Bước 6: Đảm bảo .gitignore bảo vệ secrets
// ---------------------------------------------------------------------------

const REQUIRED_IGNORE_PATTERNS = [
  'HLK/config/secrets.*',
  'HLK/config/*.local.json',
  'HLK/logs/',
  '*.rvf',
  '*.rvf.lock',
  'agentdb.rvf',
  'agentdb.rvf.lock',
  '.env',
  '.env.*',
  '.claude-flow/data/',
  '.swarm/',
  '.hive-mind/',
];

function ensureGitIgnore() {
  const gitignorePath = path.join(WORKSPACE_ROOT, '.gitignore');
  let content = '';
  if (fs.existsSync(gitignorePath)) {
    content = fs.readFileSync(gitignorePath, 'utf8');
  }

  let modified = false;
  for (const pattern of REQUIRED_IGNORE_PATTERNS) {
    const exists = content.split('\n').some((line) => line.trim() === pattern);
    if (!exists) {
      content += (content.endsWith('\n') ? '' : '\n') + pattern + '\n';
      modified = true;
    }
  }

  if (modified) {
    fs.writeFileSync(gitignorePath, content, 'utf8');
    log('success', 'Đã cập nhật .gitignore bảo vệ secrets.');
  } else {
    log('info', '.gitignore đã bảo vệ secrets.');
  }
}

// ---------------------------------------------------------------------------
// Bước 7: Tạo secrets.env nếu chưa có
// ---------------------------------------------------------------------------

function createSecretsEnv() {
  const examplePath = path.join(HLK_TARGET_DIR, 'config', 'secrets.env.example');
  const secretsPath = path.join(HLK_TARGET_DIR, 'config', 'secrets.env');

  if (fs.existsSync(secretsPath)) {
    log('info', 'HLK/config/secrets.env đã tồn tại — giữ nguyên.');
    return;
  }

  if (fs.existsSync(examplePath)) {
    fs.copyFileSync(examplePath, secretsPath);
    log('success', 'Đã tạo HLK/config/secrets.env từ example.');
  } else {
    // Tạo file cơ bản nếu example thiếu
    const basic = [
      '# HLK secrets — KHÔNG commit file này',
      'OPENAI_API_KEY=',
      'ANTHROPIC_API_KEY=',
      'GOOGLE_API_KEY=',
      'MCP_AUTH_TOKEN=' + randomBytes(24).toString('base64'),
      'MONGO_INITDB_ROOT_PASSWORD=' + randomBytes(24).toString('base64'),
      'OPENROUTER_API_KEY=',
      '',
    ].join('\n');
    fs.writeFileSync(secretsPath, basic, 'utf8');
    log('success', 'Đã tạo HLK/config/secrets.env cơ bản.');
  }

  // Đảm bảo file bị ignore
  ensureGitIgnore();
}

// ---------------------------------------------------------------------------
// Bước 8: Verify HLK
// ---------------------------------------------------------------------------

function runHlkVerify() {
  const verifyScript = path.join(HLK_TARGET_DIR, 'wrappers', 'hlk-verify-integrity.js');
  if (!fs.existsSync(verifyScript)) {
    log('warn', 'Không tìm thấy hlk-verify-integrity.js — bỏ qua.');
    return;
  }

  log('info', 'Đang chạy HLK integrity verify...');
  const result = spawnSync(process.execPath, [verifyScript], { cwd: WORKSPACE_ROOT, stdio: 'inherit' });

  if (result.status !== 0) {
    log('error', 'HLK integrity verify thất bại.');
    process.exit(result.status ?? 1);
  }

  log('success', 'HLK integrity verify PASSED.');
}

// ---------------------------------------------------------------------------
// Bước 9: Chạy hlk-loop status
// ---------------------------------------------------------------------------

function runHlkLoopStatus() {
  const loopScript = path.join(HLK_TARGET_DIR, 'loop', 'hlk-loop.mjs');
  if (!fs.existsSync(loopScript)) return;

  log('info', 'Đang chạy HLK loop status...');
  const result = spawnSync(process.execPath, [loopScript, '--status'], { cwd: WORKSPACE_ROOT, stdio: 'inherit' });

  if (result.status !== 0) {
    log('warn', 'HLK loop status gặp lỗi (có thể do chưa hoàn thành pipeline).');
  } else {
    log('success', 'HLK loop status OK.');
  }
}

// ---------------------------------------------------------------------------
// Bước 8: Copy skills vào đúng thư mục skills của từng CLI đã chọn
// ---------------------------------------------------------------------------
// Trước đây chỉ copy sang .claude/skills/ và .devin/skills/ → agy không thấy.
// Giờ copy sang cliSkillsDir(ws, cli) cho mỗi CLI trong targets (bao gồm .agents/skills/).
function copyHlkSkillsAll(ws, targets) {
  const srcSkillsDir = path.join(HLK_PACKAGE_ROOT, 'skills');
  if (!fs.existsSync(srcSkillsDir)) {
    log('warn', 'Không tìm thấy HLK/skills/ trong package — bỏ qua.');
    return;
  }

  const skillDirs = fs.readdirSync(srcSkillsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith('hlk-'))
    .map((e) => e.name);

  if (skillDirs.length === 0) {
    log('info', 'Không có skill template nào trong HLK/skills/.');
    return;
  }

  for (const cli of targets) {
    const dstSkillsDir = cliSkillsDir(ws, cli);
    fs.mkdirSync(dstSkillsDir, { recursive: true });

    for (const skillDir of skillDirs) {
      const src = path.join(srcSkillsDir, skillDir);
      const dst = path.join(dstSkillsDir, skillDir);
      if (typeof fs.cpSync === 'function') {
        fs.cpSync(src, dst, { recursive: true, force: true });
      } else {
        copyRecursive(src, dst);
      }
    }
    log('success', `Đã copy ${skillDirs.length} skill sang ${cliDisplayName(cli)} (${path.relative(ws, dstSkillsDir)}/)`);
  }
}

// ---------------------------------------------------------------------------
// Bước 9: Cài .githooks/post-merge để tự verify HLK sau pull/merge
// ---------------------------------------------------------------------------

/**
 * Copy template post-merge từ HLK/skills/post-merge.template sang
 * .githooks/post-merge của workspace, rồi chmod +x (trên Unix).
 *
 * Git hook này tự chạy hlk-verify-integrity.js sau mỗi git pull/merge,
 * cảnh báo nếu upstream đã ghi đè cấu hình HLK.
 */
function installPostMergeHook() {
  const templatePath = path.join(HLK_PACKAGE_ROOT, 'skills', 'post-merge.template');
  if (!fs.existsSync(templatePath)) {
    log('warn', 'Không tìm thấy HLK/skills/post-merge.template — bỏ qua.');
    return;
  }

  const githooksDir = path.join(WORKSPACE_ROOT, '.githooks');
  fs.mkdirSync(githooksDir, { recursive: true });

  const dstPath = path.join(githooksDir, 'post-merge');
  fs.copyFileSync(templatePath, dstPath);

  // chmod +x trên Unix (Windows không cần)
  if (process.platform !== 'win32') {
    try {
      fs.chmodSync(dstPath, 0o755);
    } catch { /* ignore */ }
  }

  log('success', 'Đã cài .githooks/post-merge — HLK verify sẽ chạy sau mỗi pull/merge.');

  // Nhắc user kích hoạt core.hooksPath nếu chưa
  const r = spawnSync('git', ['config', 'core.hooksPath'], { cwd: WORKSPACE_ROOT, encoding: 'utf8' });
  const currentHooksPath = r.stdout?.trim();
  if (r.status !== 0 || !currentHooksPath) {
    log('info', 'Kích hoạt git hooks: git config core.hooksPath .githooks');
  } else if (currentHooksPath !== '.githooks') {
    log('warn', `core.hooksPath hiện tại = "${currentHooksPath}" (không phải .githooks).`);
    log('warn', 'Chạy: git config core.hooksPath .githooks');
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Installer for Ruflo ===');
  log('info', `HLK package root: ${HLK_PACKAGE_ROOT}`);
  log('info', `Workspace root: ${WORKSPACE_ROOT}`);

  detectRufloWorkspace();

  // Hỏi human đang dùng CLI nào (nếu chưa truyền qua HLK_CLI)
  const choice = await askCliChoice();
  const targets = cliTargets(choice);
  log('info', `Sẽ cấu hình cho: ${targets.map(cliDisplayName).join(', ')}`);

  backupExistingHlk();
  copyContent();
  patchCliSettingsAll(WORKSPACE_ROOT, targets);
  patchGitAttributes();
  ensureGitIgnore();
  createSecretsEnv();
  copyHlkSkillsAll(WORKSPACE_ROOT, targets);
  installPostMergeHook();
  runHlkVerify();
  runHlkLoopStatus();

  log('info', '');
  log('success', 'HLK đã cài đặt xong.');
  log('info', '');
  log('info', 'Các bước tiếp theo:');
  log('info', '  1. Mở HLK/config/secrets.env và điền API keys / tokens thật.');
  log('info', `  2. Khởi động lại ${targets.map(cliDisplayName).join(' / ')} để MCP server dùng HLK wrapper.`);
  log('info', '  3. Kích hoạt git hooks: git config core.hooksPath .githooks');
  log('info', '  4. Test: node HLK/wrappers/hlk-hook-launcher.mjs < test-secret.json');
  log('info', '  5. Đọc HLK/docs/01-tong-quan-va-kien-truc.md để tìm hiểu thêm.');
}

main().catch((e) => {
  log('error', `Lỗi không xử lý được: ${e.message}`);
  process.exit(1);
});
