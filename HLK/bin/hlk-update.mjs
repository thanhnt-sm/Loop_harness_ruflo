#!/usr/bin/env node
/**
 * hlk-update.mjs
 * ==============
 * Cập nhật HLK trong một workspace đã cài.
 *
 * VAI TRÒ: Update HLK layer (backup + copy code mới + giữ config user + re-patch).
 *           Không re-patch MAX POWER — dùng hlk-update-max-power.mjs cho việc đó.
 *
 * Cách dùng:
 *   npx hlk-update
 *   # hoặc
 *   node HLK/bin/hlk-update.mjs
 *
 * Logic:
 *   - Backup HLK cũ.
 *   - Copy code mới từ package HLK vào workspace/HLK.
 *   - Giữ nguyên HLK/config/hlk.config.json và HLK/config/secrets.env của user.
 *   - Merge các trường mới từ package default vào user config.
 *   - Re-apply patch .claude/settings.json và .gitattributes.
 *   - Run verify.
 */

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

// Module dùng chung: hỏi human đang dùng CLI nào + trả paths cấu hình cho CLI đó.
// Khi update HLK, re-patch cấu hình cho đúng CLI đã chọn (giống lúc install).
import {
  promptCli, cliTargets, cliConfigDir, cliMcpConfigPath, cliHooksPath,
  cliSkillsDir, cliDisplayName, ensureCliDirs, hookCommand,
} from '../wrappers/hlk-cli-select.mjs';

// Kiểm tra Node version tối thiểu
const NODE_MAJOR = parseInt(process.versions.node.split('.')[0], 10);
if (NODE_MAJOR < 14) {
  process.stderr.write('❌ Node >= 14 yêu cầu để chạy HLK updater.\n');
  process.exit(1);
}

// Polyfill structuredClone nếu chạy trên Node < 17
if (typeof globalThis.structuredClone !== 'function') {
  globalThis.structuredClone = (v) => JSON.parse(JSON.stringify(v));
}

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const HLK_PACKAGE_ROOT = path.resolve(__dirname, '..');
const WORKSPACE_ROOT = process.cwd();
const HLK_TARGET_DIR = path.join(WORKSPACE_ROOT, 'HLK');

const HLK_CONTENT_DIRS = ['wrappers', 'security', 'custom-hooks', 'docs', 'prompts', 'reports', 'loop', 'git-tools'];
const CONFIG_DIRS = ['config']; // xử lý riêng
const HLK_CONTENT_FILES = ['README.md', 'INSTALL.md'];

// ---------------------------------------------------------------------------
// Tiện ích
// ---------------------------------------------------------------------------

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

function readJsonSafe(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch {
    return null;
  }
}

function writeJson(p, data) {
  fs.writeFileSync(p, JSON.stringify(data, null, 2) + '\n', 'utf8');
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
// Bước 1: Xác định workspace và HLK đã cài
// ---------------------------------------------------------------------------

function detectWorkspace() {
  if (!fs.existsSync(HLK_TARGET_DIR)) {
    log('error', `Không tìm thấy HLK/ trong workspace. Hãy chạy 'npx hlk-install' trước.`);
    process.exit(1);
  }
  if (!fs.existsSync(path.join(WORKSPACE_ROOT, 'package.json'))) {
    log('warn', 'Không tìm thấy package.json — tiếp tục update HLK.');
  }
  log('info', `Workspace: ${WORKSPACE_ROOT}`);
}

// ---------------------------------------------------------------------------
// Bước 2: Backup
// ---------------------------------------------------------------------------

function backupHlk() {
  const ts = Date.now();
  const backupDir = path.join(WORKSPACE_ROOT, `HLK.backup.${ts}`);
  copyRecursive(HLK_TARGET_DIR, backupDir);
  log('success', `Đã sao lưu HLK hiện tại sang: ${backupDir}`);
  return backupDir;
}

// ---------------------------------------------------------------------------
// Bước 3: Copy code mới
// ---------------------------------------------------------------------------

function copyCodeFiles() {
  for (const dir of HLK_CONTENT_DIRS) {
    const src = path.join(HLK_PACKAGE_ROOT, dir);
    const dst = path.join(HLK_TARGET_DIR, dir);
    if (!fs.existsSync(src)) {
      log('warn', `Thiếu ${dir}/ trong package — bỏ qua.`);
      continue;
    }
    copyRecursive(src, dst);
    log('success', `Đã cập nhật ${dir}/`);
  }

  for (const file of HLK_CONTENT_FILES) {
    const src = path.join(HLK_PACKAGE_ROOT, file);
    const dst = path.join(HLK_TARGET_DIR, file);
    if (!fs.existsSync(src)) continue;
    fs.copyFileSync(src, dst);
    log('success', `Đã cập nhật ${file}`);
  }
}

// ---------------------------------------------------------------------------
// Bước 4: Xử lý config/ (giữ user config, merge trường mới)
// ---------------------------------------------------------------------------

function isPlainObject(v) {
  return typeof v === 'object' && v !== null && !Array.isArray(v) && !(v instanceof Date);
}

function mergeConfig(defaults, user) {
  const out = structuredClone(defaults);

  for (const key of Object.keys(user)) {
    if (isPlainObject(out[key]) && isPlainObject(user[key])) {
      out[key] = mergeConfig(out[key], user[key]);
    } else if (Array.isArray(out[key]) && Array.isArray(user[key])) {
      // Giữ array của user, nhưng nếu defaults có phần tử mới thì append (cho redact_patterns)
      const userSet = new Set(user[key]);
      for (const item of out[key]) {
        if (!userSet.has(item)) {
          out[key].push(item);
        }
      }
      out[key] = user[key];
    } else {
      out[key] = user[key];
    }
  }

  return out;
}

function updateConfig() {
  const packageConfigPath = path.join(HLK_PACKAGE_ROOT, 'config', 'hlk.config.json');
  const userConfigPath = path.join(HLK_TARGET_DIR, 'config', 'hlk.config.json');

  const packageDefaults = readJsonSafe(packageConfigPath);
  const userConfig = readJsonSafe(userConfigPath);

  if (!packageDefaults) {
    log('warn', 'Không đọc được package hlk.config.json — bỏ qua merge.');
    return;
  }

  if (!userConfig) {
    log('warn', 'Không đọc được user hlk.config.json — copy defaults.');
    fs.mkdirSync(path.dirname(userConfigPath), { recursive: true });
    writeJson(userConfigPath, packageDefaults);
    return;
  }

  const merged = mergeConfig(packageDefaults, userConfig);

  // Đảm bảo version mới nhất
  if (packageDefaults.version) {
    merged.version = packageDefaults.version;
  }

  // Backup trước khi ghi
  const backupPath = path.join(HLK_TARGET_DIR, 'logs', `hlk.config.json.user-backup.${Date.now()}.json`);
  fs.mkdirSync(path.dirname(backupPath), { recursive: true });
  writeJson(backupPath, userConfig);
  log('info', `Đã backup user config sang: ${backupPath}`);

  writeJson(userConfigPath, merged);
  log('success', 'Đã cập nhật hlk.config.json (giữ user config, merge trường mới).');
}

function updateSecretsEnv(backupDir) {
  const userSecrets = path.join(HLK_TARGET_DIR, 'config', 'secrets.env');
  const backupSecrets = path.join(backupDir, 'config', 'secrets.env');

  if (fs.existsSync(backupSecrets)) {
    fs.copyFileSync(backupSecrets, userSecrets);
    log('success', 'Đã giữ nguyên HLK/config/secrets.env của user.');
  } else {
    log('info', 'Không tìm thấy secrets.env cũ để restore.');
  }
}

function ensureSecretsExample() {
  const examplePath = path.join(HLK_PACKAGE_ROOT, 'config', 'secrets.env.example');
  const targetExamplePath = path.join(HLK_TARGET_DIR, 'config', 'secrets.env.example');
  if (fs.existsSync(examplePath)) {
    fs.copyFileSync(examplePath, targetExamplePath);
    log('success', 'Đã cập nhật secrets.env.example');
  }
}

// ---------------------------------------------------------------------------
// Bước 5: Re-apply patch cấu hình MCP + hooks cho từng CLI đã chọn
// ---------------------------------------------------------------------------
// Trước đây chỉ re-patch .claude/settings.json → Devin/agy mất cấu hình sau update.
// Giờ hỏi CLI (hoặc đọc từ HLK_CLI env), rồi re-patch cho từng CLI đã chọn.
// Hook command nâng cấp sang hlk-hook-launcher.mjs (trung tính, không $CLAUDE_PROJECT_DIR).

let CLI_CHOICE = process.env.HLK_CLI || null;

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

const HLK_PRETOOLUSE = {
  hooks: [hookCommand(5000)],
};

function reapplyClaudeSettings() {
  const settingsPath = path.join(WORKSPACE_ROOT, '.claude', 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    log('info', 'Không tìm thấy .claude/settings.json — bỏ qua re-patch Claude.');
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

  // Tìm hook HLK cũ (dùng bridge hoặc launcher) và nâng cấp sang launcher trung tính
  const existingIdx = settings.hooks.PreToolUse.findIndex((entry) =>
    entry.hooks?.some((h) => h.command?.includes('hlk-hook-bridge.mjs') || h.command?.includes('hlk-hook-launcher.mjs'))
  );

  if (existingIdx >= 0) {
    settings.hooks.PreToolUse[existingIdx] = HLK_PRETOOLUSE;
    log('info', 'Đã cập nhật HLK PreToolUse hook (launcher trung tính).');
  } else {
    settings.hooks.PreToolUse.unshift(HLK_PRETOOLUSE);
    log('success', 'Đã thêm HLK PreToolUse hook (launcher trung tính).');
  }

  writeJson(settingsPath, settings);
  log('success', 'Đã ghi .claude/settings.json');
}

function reapplyDevinSettings() {
  ensureCliDirs(WORKSPACE_ROOT, 'devin');

  const hooksPath = cliHooksPath(WORKSPACE_ROOT, 'devin');
  const devinHooks = {
    PreToolUse: [
      { matcher: 'exec', hooks: [hookCommand(5)] },
    ],
  };
  writeJson(hooksPath, devinHooks);
  log('success', 'Đã ghi .devin/hooks.v1.json (PreToolUse launcher trung tính)');
}

function reapplyAgySettings() {
  ensureCliDirs(WORKSPACE_ROOT, 'agy');
  log('success', 'Đã đảm bảo thư mục .agents/ tồn tại');
}

async function reapplyCliSettingsAll() {
  const choice = await askCliChoice();
  const targets = cliTargets(choice);
  log('info', `Re-patch cấu hình cho: ${targets.map(cliDisplayName).join(', ')}`);
  for (const cli of targets) {
    log('info', `  → ${cliDisplayName(cli)}`);
    if (cli === 'claude') reapplyClaudeSettings();
    else if (cli === 'devin') reapplyDevinSettings();
    else if (cli === 'agy') reapplyAgySettings();
  }
}

function reapplyGitAttributes() {
  const gitattributesPath = path.join(WORKSPACE_ROOT, '.gitattributes');
  let content = fs.existsSync(gitattributesPath) ? fs.readFileSync(gitattributesPath, 'utf8') : '';

  const lines = [
    'HLK/docs/** merge=ours',
    '.claude/settings.json merge=ours',
  ];

  let modified = false;
  for (const line of lines) {
    const pattern = line.split(' ')[0];
    if (!content.includes(pattern)) {
      content += (content.endsWith('\n') ? '' : '\n') + line + '\n';
      modified = true;
    }
  }

  if (modified) {
    fs.writeFileSync(gitattributesPath, content, 'utf8');
    log('success', 'Đã cập nhật .gitattributes.');
  }
}

function reapplyGitIgnore() {
  const gitignorePath = path.join(WORKSPACE_ROOT, '.gitignore');
  let content = fs.existsSync(gitignorePath) ? fs.readFileSync(gitignorePath, 'utf8') : '';

  const patterns = ['HLK/config/secrets.*', 'HLK/logs/', '*.rvf', 'agentdb.rvf', '.env'];
  let modified = false;
  for (const pattern of patterns) {
    const exists = content.split('\n').some((l) => l.trim() === pattern);
    if (!exists) {
      content += (content.endsWith('\n') ? '' : '\n') + pattern + '\n';
      modified = true;
    }
  }

  if (modified) {
    fs.writeFileSync(gitignorePath, content, 'utf8');
    log('success', 'Đã cập nhật .gitignore.');
  }
}

// ---------------------------------------------------------------------------
// Bước 6: Verify
// ---------------------------------------------------------------------------

function runVerify() {
  const script = path.join(HLK_TARGET_DIR, 'wrappers', 'hlk-verify-integrity.js');
  if (!fs.existsSync(script)) {
    log('warn', 'Không tìm thấy hlk-verify-integrity.js');
    return;
  }

  log('info', 'Đang chạy HLK verify...');
  const r = spawnSync(process.execPath, [script], { cwd: WORKSPACE_ROOT, stdio: 'inherit' });
  if (r.status !== 0) {
    log('error', 'HLK verify thất bại.');
    process.exit(r.status ?? 1);
  }
  log('success', 'HLK verify PASSED.');
}

function runLoopStatus() {
  const script = path.join(HLK_TARGET_DIR, 'loop', 'hlk-loop.mjs');
  if (!fs.existsSync(script)) return;

  log('info', 'Đang chạy HLK loop status...');
  const r = spawnSync(process.execPath, [script, '--status'], { cwd: WORKSPACE_ROOT, stdio: 'inherit' });
  if (r.status === 0) {
    log('success', 'HLK loop status OK.');
  } else {
    log('warn', 'HLK loop status chưa hoàn thành.');
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Updater ===');

  detectWorkspace();
  const backupDir = backupHlk();
  copyCodeFiles();
  updateConfig();
  ensureSecretsExample();
  updateSecretsEnv(backupDir);
  await reapplyCliSettingsAll();
  reapplyGitAttributes();
  reapplyGitIgnore();
  runVerify();
  runLoopStatus();

  log('info', '');
  log('success', 'HLK đã cập nhật xong.');
  log('info', '');
  log('info', 'Lưu ý:');
  log('info', '  - User config đã được merge, secrets.env được giữ nguyên.');
  log('info', `  - Backup cũ nằm tại: ${backupDir}`);
  log('info', '  - Kiểm tra hlk.config.json nếu có tính năng mới cần bật.');
}

main().catch((e) => {
  log('error', `Lỗi không xử lý được: ${e.message}`);
  process.exit(1);
});
