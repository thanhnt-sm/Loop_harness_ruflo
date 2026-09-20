#!/usr/bin/env node
/**
 * hlk-upstream-pull.mjs
 * ======================
 * Script chuyên dụng: pull source code mới nhất từ upstream ruflo
 * (https://github.com/ruvnet/ruflo) vào workspace hiện tại, sau đó
 * cài lại HLK layer để đảm bảo các tùy chỉnh bảo vệ (PreToolUse hook,
 * MCP wrapper, .gitignore rules, .gitattributes merge=ours) không bị
 * upstream ghi đè mất.
 *
 * Luồng xử lý:
 *   1. Clone upstream ruflo về thư mục tạm (shallow clone --depth 1).
 *   2. Backup .claude/settings.json và .gitignore hiện tại (để rollback nếu cần).
 *   3. Copy đè source upstream vào workspace, BỎ QUA:
 *      - HLK/                (giữ nguyên HLK layer của user)
 *      - .git/               (giữ history local)
 *      - node_modules/       (tránh xóa dependencies đã cài)
 *      - .claude/settings.json (sẽ patch lại ở bước reinstall HLK)
 *   4. Patch trực tiếp HLK layer (không gọi install/update để tránh lỗi src=dest
 *      khi chạy từ chính HLK_ROOT):
 *      - Patch .claude/settings.json (PreToolUse hook, MCP wrapper)
 *      - Patch .gitattributes (merge=ours cho HLK files)
 *      - Patch .gitignore (bảo vệ secrets, *.rvf, .env)
 *      - Copy skills HLK sang .claude/skills/ và .devin/skills/
 *      - Cài .githooks/post-merge (tự verify HLK sau pull/merge)
 *   5. Run HLK integrity verify
 *   6. Báo cáo tóm tắt: file nào thay đổi, HLK check pass/fail.
 *
 * Cách dùng:
 *   node HLK/upstream/hlk-upstream-pull.mjs
 *   node HLK/upstream/hlk-upstream-pull.mjs --yes
 *   node HLK/upstream/hlk-upstream-pull.mjs --upstream https://github.com/ruvnet/ruflo.git
 *   node HLK/upstream/hlk-upstream-pull.mjs --branch main
 *   node HLK/upstream/hlk-upstream-pull.mjs --dry-run
 *
 * Options:
 *   --upstream <url>     URL git upstream (mặc định: https://github.com/ruvnet/ruflo.git)
 *   --branch <name>      Branch upstream cần pull (mặc định: main)
 *   --yes                Không hỏi xác nhận
 *   --dry-run            Chỉ clone + diff, không copy hay reinstall
 *   --keep-backup        Giữ backup trong HLK/backups/ (mặc định xóa sau khi xong)
 *   --skip-clone         Bỏ qua clone, dùng thư mục tạm đã có (debug)
 */

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HLK_ROOT = path.resolve(__dirname, '..');
const WORKSPACE_ROOT = process.cwd();

// ---------------------------------------------------------------------------
// Parse args
// ---------------------------------------------------------------------------

const args = process.argv.slice(2);
let UPSTREAM_URL = 'https://github.com/ruvnet/ruflo.git';
let UPSTREAM_BRANCH = 'main';
let YES = false;
let DRY_RUN = false;
let KEEP_BACKUP = false;
let SKIP_CLONE = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--upstream' && args[i + 1]) { UPSTREAM_URL = args[i + 1]; i++; }
  else if (args[i] === '--branch' && args[i + 1]) { UPSTREAM_BRANCH = args[i + 1]; i++; }
  else if (args[i] === '--yes') YES = true;
  else if (args[i] === '--dry-run') DRY_RUN = true;
  else if (args[i] === '--keep-backup') KEEP_BACKUP = true;
  else if (args[i] === '--skip-clone') SKIP_CLONE = true;
}

// ---------------------------------------------------------------------------
// Log helper
// ---------------------------------------------------------------------------

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

function prompt(question) {
  process.stderr.write(`${question} [y/N]: `);
  return new Promise((resolve) => {
    let input = '';
    process.stdin.resume();
    process.stdin.on('data', (data) => {
      input += data.toString();
      if (input.includes('\n')) {
        process.stdin.pause();
        const answer = input.trim().toLowerCase();
        resolve(answer === 'y' || answer === 'yes');
      }
    });
  });
}

async function ask(question) {
  if (YES) return true;
  return prompt(question);
}

// ---------------------------------------------------------------------------
// Bước 1: Clone upstream ruflo về thư mục tạm
// ---------------------------------------------------------------------------

const TEMP_DIR = path.join(os.tmpdir(), `hlk-upstream-${Date.now()}`);

function cloneUpstream() {
  if (SKIP_CLONE) {
    if (!fs.existsSync(TEMP_DIR)) {
      log('error', `--skip-clone nhưng ${TEMP_DIR} không tồn tại.`);
      process.exit(1);
    }
    log('info', `--skip-clone: dùng lại ${TEMP_DIR}`);
    return;
  }

  log('info', `Bước 1: Clone upstream ruflo từ ${UPSTREAM_URL} (branch ${UPSTREAM_BRANCH})...`);
  log('info', `Thư mục tạm: ${TEMP_DIR}`);

  // Xóa thư mục tạm cũ nếu có
  if (fs.existsSync(TEMP_DIR)) {
    fs.rmSync(TEMP_DIR, { recursive: true, force: true });
  }

  const r = spawnSync('git', [
    'clone',
    '--depth', '1',
    '--branch', UPSTREAM_BRANCH,
    UPSTREAM_URL,
    TEMP_DIR,
  ], { stdio: 'inherit' });

  if (r.status !== 0) {
    log('error', 'Clone upstream thất bại.');
    log('warn', `Kiểm tra: URL đúng chưa? Branch "${UPSTREAM_BRANCH}" có tồn tại không?`);
    process.exit(1);
  }

  log('success', 'Clone upstream thành công.');
}

// ---------------------------------------------------------------------------
// Bước 2: Backup các file cấu hình quan trọng trước khi overwrite
// ---------------------------------------------------------------------------

const BACKUP_DIR = path.join(HLK_ROOT, 'backups', `upstream-pull-${Date.now()}`);
const FILES_TO_BACKUP = [
  '.claude/settings.json',
  '.gitignore',
  '.gitattributes',
];

function backupConfigFiles() {
  log('info', 'Bước 2: Backup cấu hình hiện tại...');

  fs.mkdirSync(BACKUP_DIR, { recursive: true });

  for (const rel of FILES_TO_BACKUP) {
    const src = path.join(WORKSPACE_ROOT, rel);
    const dst = path.join(BACKUP_DIR, rel.replace(/[\\/]+/g, '__'));

    if (fs.existsSync(src)) {
      fs.copyFileSync(src, dst);
      log('info', `  Đã backup: ${rel}`);
    }
  }

  log('success', `Backup lưu tại: ${BACKUP_DIR}`);
}

// ---------------------------------------------------------------------------
// Bước 3: Copy source upstream vào workspace (BỎ QUA HLK/, .git, node_modules)
// ---------------------------------------------------------------------------

// Danh sách thư mục/file KHÔNG được copy đè từ upstream
const EXCLUDE_DIRS = new Set([
  '.git',
  'HLK',
  'node_modules',
  '.claude-flow',
  '.swarm',
  '.hive-mind',
]);

const EXCLUDE_FILES = new Set([
  '.git',
  '.gitignore',           // sẽ patch lại qua hlk-install
  '.gitattributes',        // sẽ patch lại qua hlk-install
  'agentdb.rvf',
  'agentdb.rvf.lock',
]);

function copyRecursive(src, dst) {
  if (typeof fs.cpSync === 'function') {
    fs.cpSync(src, dst, { recursive: true, force: true });
    return;
  }

  if (!fs.existsSync(dst)) fs.mkdirSync(dst, { recursive: true });
  for (const entry of fs.readdirSync(src, { withFileTypes: true })) {
    const s = path.join(src, entry.name);
    const d = path.join(dst, entry.name);
    if (entry.isDirectory()) copyRecursive(s, d);
    else fs.copyFileSync(s, d);
  }
}

function copyUpstreamToWorkspace() {
  log('info', 'Bước 3: Copy source upstream vào workspace...');

  if (DRY_RUN) {
    log('warn', '--dry-run: Bỏ qua copy. Chỉ liệt kê thư mục upstream:');
    for (const entry of fs.readdirSync(TEMP_DIR, { withFileTypes: true })) {
      const tag = entry.isDirectory() ? '[D]' : '[F]';
      log('info', `  ${tag} ${entry.name}`);
    }
    return;
  }

  const entries = fs.readdirSync(TEMP_DIR, { withFileTypes: true });
  let copied = 0;

  for (const entry of entries) {
    if (EXCLUDE_DIRS.has(entry.name)) continue;
    if (EXCLUDE_FILES.has(entry.name)) continue;

    const src = path.join(TEMP_DIR, entry.name);
    const dst = path.join(WORKSPACE_ROOT, entry.name);

    try {
      if (entry.isDirectory()) {
        copyRecursive(src, dst);
      } else {
        fs.copyFileSync(src, dst);
      }
      copied++;
    } catch (err) {
      log('warn', `Không copy được ${entry.name}: ${err.message}`);
    }
  }

  log('success', `Đã copy ${copied} mục từ upstream vào workspace.`);
  log('info', 'Đã BỎ QUA: HLK/, .git/, node_modules/, .gitignore, .gitattributes, agentdb.rvf');
}

// ---------------------------------------------------------------------------
// Bước 4: Patch lại HLK layer (settings.json, .gitattributes, .gitignore)
// ---------------------------------------------------------------------------
// Patch trực tiếp thay vì gọi hlk-install/hlk-update để tránh lỗi src=dest
// khi script chạy từ chính HLK_ROOT (source package = target dir).

const HLK_PRETOOLUSE_HOOK = {
  hooks: [
    {
      type: 'command',
      command: 'node "$CLAUDE_PROJECT_DIR/HLK/wrappers/hlk-hook-bridge.mjs"',
      timeout: 5000,
    },
  ],
};

const HLK_MCP_WRAPPER = 'HLK/wrappers/ruflo-hlk-mcp.mjs';

const HLK_GITATTRIBUTES_LINES = [
  '# HLK config — always keep our version on merge conflicts',
  'HLK/config/hlk.config.json merge=ours',
  '',
  '# HLK wrappers — keep ours',
  'HLK/wrappers/** merge=ours',
  '',
  '# HLK security — keep ours',
  'HLK/security/** merge=ours',
  '',
  '# HLK prompts — keep ours',
  'HLK/prompts/** merge=ours',
  '',
  '# HLK docs — keep ours',
  'HLK/docs/** merge=ours',
  '',
  '# HLK loop — keep ours',
  'HLK/loop/** merge=ours',
  '',
  '# HLK reports — keep ours',
  'HLK/reports/** merge=ours',
  '',
  '# .claude settings — keep ours to prevent upstream ruflo from',
  '# overwriting HLK PreToolUse/MCP wrapper customizations.',
  '.claude/settings.json merge=ours',
];

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
  '!.env.example',
  '!.env.*.example',
  'example.env',
  'HLK/dist/*.tgz',
  'HLK/dist/',
];

function patchClaudeSettings() {
  const settingsPath = path.join(WORKSPACE_ROOT, '.claude', 'settings.json');
  if (!fs.existsSync(settingsPath)) {
    log('warn', 'Không tìm thấy .claude/settings.json — bỏ qua patch.');
    return;
  }

  let settings;
  try {
    settings = JSON.parse(fs.readFileSync(settingsPath, 'utf8'));
  } catch (err) {
    log('error', `.claude/settings.json lỗi parse: ${err.message}`);
    process.exit(1);
  }

  // 1. Đảm bảo PreToolUse có HLK hook ở vị trí đầu tiên
  if (!settings.hooks) settings.hooks = {};
  if (!Array.isArray(settings.hooks.PreToolUse)) settings.hooks.PreToolUse = [];

  const hasHlkHook = settings.hooks.PreToolUse.some((entry) =>
    entry.hooks?.some((h) => h.command?.includes('hlk-hook-bridge.mjs'))
  );

  if (!hasHlkHook) {
    settings.hooks.PreToolUse.unshift(HLK_PRETOOLUSE_HOOK);
    log('success', 'Đã thêm lại HLK PreToolUse hook.');
  } else {
    log('info', 'HLK PreToolUse hook đã có.');
  }

  // 2. Cập nhật MCP server dùng HLK wrapper
  if (!settings.mcpServers) settings.mcpServers = {};
  const current = settings.mcpServers['claude-flow'];
  const usesHlkWrapper = current?.args?.some((a) => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));

  if (!usesHlkWrapper) {
    settings.mcpServers['claude-flow'] = {
      command: 'node',
      args: [HLK_MCP_WRAPPER, 'mcp', 'start'],
    };
    log('success', 'Đã cập nhật mcpServers.claude-flow dùng HLK MCP wrapper.');
  } else {
    log('info', 'MCP server đã dùng HLK wrapper.');
  }

  fs.writeFileSync(settingsPath, JSON.stringify(settings, null, 2) + '\n', 'utf8');
  log('success', 'Đã ghi .claude/settings.json.');
}

function patchGitAttributes() {
  const gitattributesPath = path.join(WORKSPACE_ROOT, '.gitattributes');
  let content = '';
  if (fs.existsSync(gitattributesPath)) {
    content = fs.readFileSync(gitattributesPath, 'utf8');
  }

  let modified = false;
  for (const line of HLK_GITATTRIBUTES_LINES) {
    if (line.startsWith('#')) {
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

  // CVE-2026-AHD-013: merge=ours chỉ hiệu lực nếu git driver "ours" được khai báo.
  ensureMergeOursDriver();
}

function ensureMergeOursDriver() {
  // Driver ghi log khi giữ ours (không silent) — CVE-2026-AHD-017
  const driverPath = path.resolve(__dirname, '..', 'git-tools', 'hlk-merge-ours.mjs');
  const res = spawnSync('git', ['config', 'merge.ours.driver', `node ${JSON.stringify(driverPath)} %A %O %B`], { cwd: WORKSPACE_ROOT, encoding: 'utf8' });
  if (res.status === 0) {
    log('success', 'Đã cấu hình git merge.ours.driver (log-aware, không còn silent).');
  } else {
    log('warn', `Không thể cấu hình merge.ours.driver: ${(res.stderr || '').trim()}`);
  }
}

function patchGitIgnore() {
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
    log('success', 'Đã cập nhật .gitignore bảo vệ secrets + *.rvf + .env.');
  } else {
    log('info', '.gitignore đã bảo vệ đầy đủ.');
  }
}

// ---------------------------------------------------------------------------
// Bước 4b: Copy skills HLK sang .claude/skills/ và .devin/skills/
// ---------------------------------------------------------------------------

function copyHlkSkills() {
  const srcSkillsDir = path.join(HLK_ROOT, 'skills');
  if (!fs.existsSync(srcSkillsDir)) {
    log('warn', 'Không tìm thấy HLK/skills/ — bỏ qua copy skills.');
    return;
  }

  const skillDirs = fs.readdirSync(srcSkillsDir, { withFileTypes: true })
    .filter((e) => e.isDirectory() && e.name.startsWith('hlk-'))
    .map((e) => e.name);

  if (skillDirs.length === 0) {
    log('info', 'Không có skill template nào trong HLK/skills/.');
    return;
  }

  const claudeSkillsDir = path.join(WORKSPACE_ROOT, '.claude', 'skills');
  fs.mkdirSync(claudeSkillsDir, { recursive: true });

  const devinSkillsDir = path.join(WORKSPACE_ROOT, '.devin', 'skills');
  fs.mkdirSync(devinSkillsDir, { recursive: true });

  for (const skillDir of skillDirs) {
    const src = path.join(srcSkillsDir, skillDir);

    // Copy sang .claude/skills/
    const dstClaude = path.join(claudeSkillsDir, skillDir);
    if (typeof fs.cpSync === 'function') {
      fs.cpSync(src, dstClaude, { recursive: true, force: true });
    } else {
      copyRecursive(src, dstClaude);
    }

    // Copy sang .devin/skills/
    const dstDevin = path.join(devinSkillsDir, skillDir);
    if (typeof fs.cpSync === 'function') {
      fs.cpSync(src, dstDevin, { recursive: true, force: true });
    } else {
      copyRecursive(src, dstDevin);
    }

    log('success', `Đã copy skill ${skillDir} sang .claude/skills/ và .devin/skills/`);
  }
}

// ---------------------------------------------------------------------------
// Bước 4c: Cài .githooks/post-merge
// ---------------------------------------------------------------------------

function installPostMergeHook() {
  const templatePath = path.join(HLK_ROOT, 'skills', 'post-merge.template');
  if (!fs.existsSync(templatePath)) {
    log('warn', 'Không tìm thấy HLK/skills/post-merge.template — bỏ qua.');
    return;
  }

  const githooksDir = path.join(WORKSPACE_ROOT, '.githooks');
  fs.mkdirSync(githooksDir, { recursive: true });

  const dstPath = path.join(githooksDir, 'post-merge');
  fs.copyFileSync(templatePath, dstPath);

  if (process.platform !== 'win32') {
    try {
      fs.chmodSync(dstPath, 0o755);
    } catch { /* ignore */ }
  }

  log('success', 'Đã cài .githooks/post-merge — HLK verify sẽ chạy sau mỗi pull/merge.');

  // CVE-2026-AHD-014: chủ động kích hoạt core.hooksPath thay vì chỉ nhắc — nếu
  // không set, post-merge hook không bao giờ chạy.
  const r = spawnSync('git', ['config', 'core.hooksPath'], { cwd: WORKSPACE_ROOT, encoding: 'utf8' });
  const currentHooksPath = r.stdout?.trim();
  if (r.status !== 0 || !currentHooksPath) {
    const set = spawnSync('git', ['config', 'core.hooksPath', '.githooks'], { cwd: WORKSPACE_ROOT, encoding: 'utf8' });
    if (set.status === 0) {
      log('success', 'Đã kích hoạt core.hooksPath = .githooks — post-merge verify sẽ chạy.');
    } else {
      log('warn', `Không thể set core.hooksPath: ${(set.stderr || '').trim()}`);
    }
  } else if (currentHooksPath !== '.githooks') {
    log('warn', `core.hooksPath hiện tại = "${currentHooksPath}" (không phải .githooks).`);
    log('warn', 'Chạy: git config core.hooksPath .githooks');
  }
}

function reinstallHlk() {
  if (DRY_RUN) {
    log('warn', '--dry-run: Bỏ qua reinstall HLK.');
    return;
  }

  log('info', 'Bước 4: Patch lại HLK layer (settings.json, .gitattributes, .gitignore, skills, githooks)...');
  patchClaudeSettings();
  patchGitAttributes();
  patchGitIgnore();
  copyHlkSkills();
  installPostMergeHook();
  log('success', 'HLK layer đã được patch lại.');
}

// ---------------------------------------------------------------------------
// Bước 5: Run HLK integrity verify
// ---------------------------------------------------------------------------

function runIntegrityCheck() {
  if (DRY_RUN) {
    log('warn', '--dry-run: Bỏ qua integrity check.');
    return;
  }

  log('info', 'Bước 5: HLK integrity verify...');
  const verifyScript = path.join(HLK_ROOT, 'wrappers', 'hlk-verify-integrity.js');

  if (!fs.existsSync(verifyScript)) {
    log('warn', 'Không tìm thấy hlk-verify-integrity.js — bỏ qua.');
    return;
  }

  const r = spawnSync(process.execPath, [verifyScript], {
    cwd: WORKSPACE_ROOT,
    stdio: 'inherit',
  });

  if (r.status !== 0) {
    log('error', 'HLK integrity verify FAILED.');
    log('warn', `Backup vẫn còn tại: ${BACKUP_DIR}`);
    process.exit(1);
  }

  log('success', 'HLK integrity verify PASSED.');
}

// ---------------------------------------------------------------------------
// Bước 6: Dọn dẹp thư mục tạm + backup (tùy chọn)
// ---------------------------------------------------------------------------

function cleanup() {
  // Xóa thư mục tạm clone
  if (fs.existsSync(TEMP_DIR) && !SKIP_CLONE) {
    try {
      fs.rmSync(TEMP_DIR, { recursive: true, force: true });
      log('info', `Đã xóa thư mục tạm: ${TEMP_DIR}`);
    } catch {
      log('warn', `Không xóa được thư mục tạm: ${TEMP_DIR}`);
    }
  }

  // Xóa backup nếu --keep-backup không được set
  if (!KEEP_BACKUP && fs.existsSync(BACKUP_DIR)) {
    try {
      fs.rmSync(BACKUP_DIR, { recursive: true, force: true });
      log('info', `Đã xóa backup: ${BACKUP_DIR}`);
    } catch {
      log('warn', `Không xóa được backup: ${BACKUP_DIR}`);
    }
  } else if (KEEP_BACKUP) {
    log('info', `Backup được giữ tại: ${BACKUP_DIR} (--keep-backup)`);
  }
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Upstream Pull ===');
  log('info', `Workspace: ${WORKSPACE_ROOT}`);
  log('info', `Upstream:  ${UPSTREAM_URL} (branch ${UPSTREAM_BRANCH})`);
  log('info', `HLK root:  ${HLK_ROOT}`);
  if (DRY_RUN) log('warn', 'DRY-RUN mode: chỉ clone + list, không copy/reinstall.');

  // Kiểm tra workspace có phải Ruflo không
  if (!fs.existsSync(path.join(WORKSPACE_ROOT, '.claude')) &&
      !fs.existsSync(path.join(WORKSPACE_ROOT, 'package.json'))) {
    log('error', 'Thư mục hiện tại không phải workspace Ruflo (thiếu .claude/ hoặc package.json).');
    process.exit(1);
  }

  // Xác nhận
  if (!YES && !(await ask('Pull upstream ruflo và reinstall HLK?'))) {
    log('info', 'Hủy.');
    process.exit(0);
  }

  cloneUpstream();
  backupConfigFiles();
  copyUpstreamToWorkspace();
  reinstallHlk();
  runIntegrityCheck();
  cleanup();

  log('info', '');
  log('success', 'Upstream pull + HLK reinstall hoàn tất.');
  log('info', '');
  log('info', 'Các bước tiếp theo:');
  log('info', '  1. Khởi động lại Claude Code để MCP server dùng HLK wrapper.');
  log('info', '  2. Review git status để xem file nào thay đổi.');
  log('info', '  3. Nếu cần rollback: dùng backup trong HLK/backups/ (nếu --keep-backup).');
}

main();
