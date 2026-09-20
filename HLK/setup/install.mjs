// ============================================================================
// HLK Installer — Node.js cross-platform
// ============================================================================
//
// Cách dùng (từ source đã clone):
//   node HLK/setup/install.mjs
//   # Script sẽ hỏi path cần cài HLK vào, user nhập, mọi việc tự động tiếp
//
// Hoặc truyền path trực tiếp:
//   node HLK/setup/install.mjs /path/to/workspace
//   node HLK/setup/install.mjs --path /path/to/workspace
//
// Options (biến môi trường):
//   HLK_REPO, HLK_BRANCH, RUFLO_VERSION, SKIP_RUFLO, SKIP_CLONE
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import os from 'node:os';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

// Module dùng chung: hỏi human đang dùng CLI nào + trả paths cấu hình cho CLI đó.
// Trước đây installer hard-code cho Claude Code, nên Devin/agy không thấy MCP ruflo.
// Giờ hỏi thẳng human rồi chỉ cấu hình cho CLI đã chọn (hoặc cả 3 nếu chọn 'all').
import {
  promptCli, cliTargets, cliConfigDir, cliMcpConfigPath, cliHooksPath,
  cliSkillsDir, cliDisplayName, ensureCliDirs, hookCommand,
} from '../wrappers/hlk-cli-select.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Cấu hình ---
const HLK_REPO = process.env.HLK_REPO || 'https://github.com/thanhnt-sm/Loop_harness_ruflo.git';
const HLK_BRANCH = process.env.HLK_BRANCH || 'main';
const RUFLO_VERSION = process.env.RUFLO_VERSION || 'latest';
const SKIP_RUFLO = process.env.SKIP_RUFLO === '1';
const SKIP_CLONE = process.env.SKIP_CLONE === '1';

// --- Log ---
function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

// --- Hỏi path cài từ user ---
function askInstallPath() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    const defaultPath = process.cwd();
    rl.question(`Nhập path cần cài HLK vào [mặc định: ${defaultPath}]: `, (answer) => {
      rl.close();
      const trimmed = (answer || '').trim();
      resolve(trimmed || defaultPath);
    });
  });
}

// --- Hỏi human đang dùng CLI nào (để cấu hình đúng CLI đó) ---
function askCliChoice() {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    promptCli(rl).then((choice) => {
      rl.close();
      resolve(choice);
    });
  });
}

// --- Parse args: node install.mjs [path] hoặc node install.mjs --path <path> ---
let USER_PATH = null;
let CLI_CHOICE = null; // 'claude' | 'devin' | 'agy' | 'all' | null (chưa set → hỏi)
const rawArgs = process.argv.slice(2);
for (let i = 0; i < rawArgs.length; i++) {
  if (rawArgs[i] === '--path' && rawArgs[i + 1]) { USER_PATH = rawArgs[i + 1]; i++; }
  else if (rawArgs[i] === '--cli' && rawArgs[i + 1]) { CLI_CHOICE = rawArgs[i + 1]; i++; }
  else if (rawArgs[i] === '--yes') { /* skip confirm */ }
  else if (!rawArgs[i].startsWith('--')) { USER_PATH = rawArgs[i]; }
}

// --- Kiểm tra node version ---
const NODE_MAJOR = parseInt(process.versions.node.split('.')[0], 10);
if (NODE_MAJOR < 14) {
  log('error', `Node >= 14 yêu cầu. Hiện tại: ${process.version}`);
  process.exit(1);
}

// --- copyRecursive ---
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

// ============================================================================
// Main — async để hỏi path
// ============================================================================

async function main() {
  // Xác định path cài
  let WORKSPACE_ROOT;
  if (USER_PATH) {
    WORKSPACE_ROOT = path.resolve(USER_PATH);
    log('info', `Path cài (từ args): ${WORKSPACE_ROOT}`);
  } else {
    WORKSPACE_ROOT = path.resolve(await askInstallPath());
    log('info', `Path cài: ${WORKSPACE_ROOT}`);
  }

  // Hỏi human đang dùng CLI nào (nếu chưa truyền qua --cli)
  if (!CLI_CHOICE) {
    CLI_CHOICE = await askCliChoice();
  } else {
    log('info', `CLI (từ --cli): ${CLI_CHOICE}`);
  }
  const targets = cliTargets(CLI_CHOICE);
  log('info', `Sẽ cấu hình cho: ${targets.map(cliDisplayName).join(', ')}`);

  // Tạo thư mục nếu chưa có
  if (!fs.existsSync(WORKSPACE_ROOT)) {
    fs.mkdirSync(WORKSPACE_ROOT, { recursive: true });
    log('success', `Đã tạo thư mục: ${WORKSPACE_ROOT}`);
  }

  const TEMP_DIR = path.join(os.tmpdir(), `hlk-install-${Date.now()}`);
  const HLK_TARGET_DIR = path.join(WORKSPACE_ROOT, 'HLK');

  log('info', '=== HLK Installer ===');
  log('success', `Node ${process.version}`);
  log('info', `Workspace: ${WORKSPACE_ROOT}`);
  log('info', `HLK target: ${HLK_TARGET_DIR}`);
  if (SKIP_RUFLO) log('warn', 'SKIP_RUFLO=1 — bỏ qua cài Ruflo');
  if (SKIP_CLONE) log('warn', 'SKIP_CLONE=1 — dùng HLK từ source local');

  // --- Kiểm tra git ---
  function checkCmd(cmd) {
    const r = spawnSync(cmd, ['--version'], { stdio: 'pipe', shell: process.platform === 'win32' });
    return r.status === 0;
  }
  if (!checkCmd('git')) {
    log('error', 'Không tìm thấy git. Cài git trước.');
    process.exit(1);
  }

  // ============================================================================
  // Bước 1: Xác định nguồn HLK
  // ============================================================================

  let hlkSourceDir;
  if (SKIP_CLONE) {
    // Dùng HLK/setup/ local — repo đã clone
    const repoRoot = path.resolve(__dirname, '..', '..');
    hlkSourceDir = repoRoot;
    log('info', `Bước 1: Dùng HLK từ source local: ${repoRoot}`);
  } else {
    log('info', 'Bước 1: Tải HLK từ GitHub...');
    hlkSourceDir = TEMP_DIR;

    // Thử tải tarball
    const tarballUrl = `https://codeload.github.com/thanhnt-sm/Loop_harness_ruflo/tar.gz/refs/heads/${HLK_BRANCH}`;
    const tarballPath = path.join(TEMP_DIR, 'hlk.tar.gz');
    fs.mkdirSync(TEMP_DIR, { recursive: true });

    const curlR = spawnSync('curl', ['-fsSL', '-o', tarballPath, tarballUrl], { stdio: 'inherit' });

    if (curlR.status === 0 && fs.existsSync(tarballPath)) {
      log('info', 'Đã tải tarball, giải nén...');
      const tarR = spawnSync('tar', ['-xzf', tarballPath, '-C', TEMP_DIR], { stdio: 'inherit' });

      if (tarR.status === 0) {
        const extracted = fs.readdirSync(TEMP_DIR)
          .filter((f) => f.startsWith('Loop_harness_ruflo-') && fs.statSync(path.join(TEMP_DIR, f)).isDirectory())[0];
        if (extracted) {
          hlkSourceDir = path.join(TEMP_DIR, extracted);
          log('success', `Đã giải nén HLK vào ${hlkSourceDir}`);
        } else {
          log('warn', 'Không tìm thấy thư mục sau giải nén, fallback git clone...');
          hlkSourceDir = null;
        }
      } else {
        log('warn', 'Giải nén tarball thất bại, fallback git clone...');
        hlkSourceDir = null;
      }
    } else {
      log('warn', 'Tải tarball thất bại, fallback git clone...');
      hlkSourceDir = null;
    }

    if (!hlkSourceDir) {
      const cloneDir = path.join(TEMP_DIR, 'hlk-clone');
      const r = spawnSync('git', ['clone', '--depth', '1', '--branch', HLK_BRANCH, HLK_REPO, cloneDir], { stdio: 'inherit' });
      if (r.status !== 0) {
        log('error', 'Git clone thất bại. Repo có thể private — cần auth.');
        log('info', 'Nếu repo private, hãy clone thủ công rồi chạy:');
        log('info', '  git clone https://github.com/thanhnt-sm/Loop_harness_ruflo.git');
        log('info', '  node Loop_harness_ruflo/HLK/setup/install.mjs --path /target');
        process.exit(1);
      }
      hlkSourceDir = cloneDir;
      log('success', `Đã clone HLK vào ${hlkSourceDir}`);
    }
  }

  // ============================================================================
  // Bước 2: Cài Ruflo nếu chưa có
  // ============================================================================

  function installRuflo() {
    if (SKIP_RUFLO) {
      log('info', 'Bước 2: Bỏ qua cài Ruflo (SKIP_RUFLO=1)');
      return;
    }

    const hasRuflo = fs.existsSync(path.join(WORKSPACE_ROOT, '.claude')) ||
                     fs.existsSync(path.join(WORKSPACE_ROOT, 'package.json'));

    if (hasRuflo) {
      log('info', 'Bước 2: Ruflo đã có trong workspace — bỏ qua init.');
      return;
    }

    log('info', `Bước 2: Cài Ruflo ${RUFLO_VERSION} qua npm...`);

    const pkg = RUFLO_VERSION === 'latest' ? 'ruflo@latest' : `ruflo@${RUFLO_VERSION}`;
    const commands = [['-y', pkg, 'init'], ['-y', pkg, 'setup'], ['-y', pkg]];

    let success = false;
    for (const cmd of commands) {
      log('info', `  Thử: npx ${cmd.join(' ')}`);
      const r = spawnSync('npx', cmd, { cwd: WORKSPACE_ROOT, stdio: 'inherit', shell: process.platform === 'win32' });
      if (r.status === 0) { success = true; break; }
      log('warn', `  Lệnh "${cmd.slice(2).join(' ') || '(default)'}" thất bại, thử cách khác...`);
    }

    if (!success) {
      log('warn', 'Ruflo init thất bại qua tất cả cách. Tiếp tục cài HLK độc lập.');
      log('warn', 'Bạn có thể cài Ruflo thủ công sau: https://github.com/ruvnet/ruflo');
      return;
    }
    log('success', 'Ruflo đã cài xong.');
  }

  // ============================================================================
  // Bước 3: Copy HLK vào workspace
  // ============================================================================

  function copyHlk() {
    log('info', `Bước 3: Copy HLK vào ${HLK_TARGET_DIR}...`);

    const hlkSrc = path.join(hlkSourceDir, 'HLK');
    if (!fs.existsSync(hlkSrc)) {
      log('error', `Không tìm thấy HLK/ trong source: ${hlkSrc}`);
      process.exit(1);
    }

    if (fs.existsSync(HLK_TARGET_DIR)) {
      const backupDir = path.join(WORKSPACE_ROOT, `HLK.backup.${Date.now()}`);
      copyRecursive(HLK_TARGET_DIR, backupDir);
      log('info', `Đã backup HLK cũ sang: ${backupDir}`);
    }

    fs.mkdirSync(HLK_TARGET_DIR, { recursive: true });

    const dirs = ['config', 'wrappers', 'security', 'custom-hooks', 'docs', 'prompts', 'reports', 'loop', 'git-tools', 'upstream', 'skills', 'bin', 'setup'];
    for (const dir of dirs) {
      const src = path.join(hlkSrc, dir);
      if (fs.existsSync(src)) {
        copyRecursive(src, path.join(HLK_TARGET_DIR, dir));
        log('info', `  Đã copy ${dir}/`);
      }
    }

    const files = ['README.md', 'INSTALL.md', 'package.json'];
    for (const file of files) {
      const src = path.join(hlkSrc, file);
      if (fs.existsSync(src)) {
        fs.copyFileSync(src, path.join(HLK_TARGET_DIR, file));
      }
    }

    log('success', `Đã copy HLK vào ${HLK_TARGET_DIR}`);
  }

  // ============================================================================
  // Bước 4: Patch cấu hình MCP + hooks cho từng CLI đã chọn
  // ----------------------------------------------------------------------------
  // Trước đây chỉ patch .claude/settings.json (Claude Code), nên Devin CLI và
  // Antigravity không thấy MCP server của ruflo → ruflo không nhận diện CLI.
  // Giờ lặp qua từng CLI trong targets và ghi đúng file cấu hình của CLI đó:
  //   - claude: .claude/settings.json  (mcpServers + hooks cùng file)
  //   - devin:  .devin/mcp_config.json (mcpServers) + .devin/hooks.v1.json (hooks)
  //   - agy:    .agents/mcp_config.json (mcpServers) — agy không có file hooks
  // Hook command dùng hookCommand() trung tính (không phụ thuộc $CLAUDE_PROJECT_DIR).
  // ============================================================================

  // Entry MCP server chung cho cả 3 CLI — gọi HLK wrapper ruflo-hlk-mcp.mjs
  const HLK_MCP_SERVER = { command: 'node', args: ['HLK/wrappers/ruflo-hlk-mcp.mjs', 'mcp', 'start'] };

  // Đọc file JSON an toàn; nếu chưa có hoặc lỗi parse thì trả object rỗng
  function readJsonSafe(filePath, fallback = {}) {
    if (!fs.existsSync(filePath)) return { ...fallback };
    try { return JSON.parse(fs.readFileSync(filePath, 'utf8')); }
    catch { log('warn', `Lỗi parse ${filePath} — ghi đè.`); return { ...fallback }; }
  }

  // Ghi JSON đẹp 2 space + newline cuối
  function writeJsonPretty(filePath, obj) {
    fs.writeFileSync(filePath, JSON.stringify(obj, null, 2) + '\n', 'utf8');
  }

  // Patch cho Claude Code: .claude/settings.json (mcpServers + hooks cùng file)
  function patchClaudeSettings() {
    log('info', `Bước 4: Patch ${cliDisplayName('claude')} (.claude/settings.json)...`);
    ensureCliDirs(WORKSPACE_ROOT, 'claude');
    const settingsPath = cliMcpConfigPath(WORKSPACE_ROOT, 'claude');
    const settings = readJsonSafe(settingsPath);

    // Hooks: PreToolUse dùng hookCommand() trung tính
    if (!settings.hooks) settings.hooks = {};
    if (!Array.isArray(settings.hooks.PreToolUse)) settings.hooks.PreToolUse = [];
    const hasHlk = settings.hooks.PreToolUse.some((e) => e.hooks?.some((h) => h.command?.includes('hlk-hook-launcher.mjs')));
    if (!hasHlk) {
      settings.hooks.PreToolUse.unshift({ hooks: [hookCommand()] });
      log('success', 'Đã thêm HLK PreToolUse hook (launcher trung tính)');
    } else {
      log('info', 'HLK PreToolUse hook đã có');
    }

    // MCP server
    if (!settings.mcpServers) settings.mcpServers = {};
    const usesHlk = settings.mcpServers['claude-flow']?.args?.some((a) => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));
    if (!usesHlk) {
      settings.mcpServers['claude-flow'] = { ...HLK_MCP_SERVER };
      log('success', 'Đã cập nhật MCP wrapper dùng HLK');
    } else {
      log('info', 'MCP server đã dùng HLK wrapper');
    }

    writeJsonPretty(settingsPath, settings);
    log('success', `Đã ghi ${settingsPath}`);
  }

  // Patch cho Devin CLI: .devin/mcp_config.json (chỉ mcpServers) + .devin/hooks.v1.json (PreToolUse)
  function patchDevinSettings() {
    log('info', `Bước 4: Patch ${cliDisplayName('devin')} (.devin/mcp_config.json + hooks.v1.json)...`);
    ensureCliDirs(WORKSPACE_ROOT, 'devin');

    // MCP config — chỉ chứa mcpServers, không hooks
    const mcpPath = cliMcpConfigPath(WORKSPACE_ROOT, 'devin');
    const mcpConfig = readJsonSafe(mcpPath);
    if (!mcpConfig.mcpServers) mcpConfig.mcpServers = {};
    const usesHlk = mcpConfig.mcpServers['claude-flow']?.args?.some((a) => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));
    if (!usesHlk) {
      mcpConfig.mcpServers['claude-flow'] = { ...HLK_MCP_SERVER };
      log('success', 'Đã cập nhật MCP wrapper dùng HLK');
    } else {
      log('info', 'MCP server đã dùng HLK wrapper');
    }
    writeJsonPretty(mcpPath, mcpConfig);
    log('success', `Đã ghi ${mcpPath}`);

    // Hooks config — PreToolUse dùng hookCommand() trung tính
    const hooksPath = cliHooksPath(WORKSPACE_ROOT, 'devin');
    const hooksConfig = readJsonSafe(hooksPath);
    if (!hooksConfig.hooks) hooksConfig.hooks = {};
    if (!Array.isArray(hooksConfig.hooks.PreToolUse)) hooksConfig.hooks.PreToolUse = [];
    const hasHlk = hooksConfig.hooks.PreToolUse.some((e) => e.hooks?.some((h) => h.command?.includes('hlk-hook-launcher.mjs')));
    if (!hasHlk) {
      hooksConfig.hooks.PreToolUse.unshift({ hooks: [hookCommand()] });
      log('success', 'Đã thêm HLK PreToolUse hook (launcher trung tính)');
    } else {
      log('info', 'HLK PreToolUse hook đã có');
    }
    writeJsonPretty(hooksPath, hooksConfig);
    log('success', `Đã ghi ${hooksPath}`);
  }

  // Patch cho Antigravity: .agents/mcp_config.json (chỉ mcpServers) — agy không có file hooks
  function patchAgySettings() {
    log('info', `Bước 4: Patch ${cliDisplayName('agy')} (.agents/mcp_config.json)...`);
    ensureCliDirs(WORKSPACE_ROOT, 'agy');

    const mcpPath = cliMcpConfigPath(WORKSPACE_ROOT, 'agy');
    const mcpConfig = readJsonSafe(mcpPath);
    if (!mcpConfig.mcpServers) mcpConfig.mcpServers = {};
    const usesHlk = mcpConfig.mcpServers['claude-flow']?.args?.some((a) => typeof a === 'string' && a.includes('ruflo-hlk-mcp'));
    if (!usesHlk) {
      mcpConfig.mcpServers['claude-flow'] = { ...HLK_MCP_SERVER };
      log('success', 'Đã cập nhật MCP wrapper dùng HLK');
    } else {
      log('info', 'MCP server đã dùng HLK wrapper');
    }
    writeJsonPretty(mcpPath, mcpConfig);
    log('success', `Đã ghi ${mcpPath}`);
  }

  // Lặp qua từng CLI trong targets và patch đúng file cấu hình cho CLI đó
  function patchCliSettingsAll(targets) {
    for (const cli of targets) {
      if (cli === 'claude') patchClaudeSettings();
      else if (cli === 'devin') patchDevinSettings();
      else if (cli === 'agy') patchAgySettings();
      else log('warn', `CLI không hỗ trợ: ${cli} — bỏ qua`);
    }
  }

  // ============================================================================
  // Bước 5-6: Patch .gitattributes + .gitignore
  // ============================================================================

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
    '# HLK docs — keep ours',
    'HLK/docs/** merge=ours',
    '',
    '# .claude settings — keep ours',
    '.claude/settings.json merge=ours',
  ];

  function patchGitAttributes() {
    log('info', 'Bước 5: Patch .gitattributes...');
    const p = path.join(WORKSPACE_ROOT, '.gitattributes');
    let content = fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
    let modified = false;
    for (const line of HLK_GITATTRIBUTES_LINES) {
      if (!content.includes(line)) {
        content += (content.endsWith('\n') ? '' : '\n') + line + '\n';
        modified = true;
      }
    }
    if (modified) { fs.writeFileSync(p, content, 'utf8'); log('success', 'Đã cập nhật .gitattributes'); }
    else { log('info', '.gitattributes đã chứa HLK merge rules'); }
    configureMergeOursDriver();
  }

  // CVE-2026-AHD-013: .gitattributes merge=ours chỉ có tác dụng nếu git driver
  // "ours" được khai báo. Nếu thiếu, HLK KHÔNG được bảo vệ khỏi upstream overwrite.
  function configureMergeOursDriver() {
    log('info', 'Bước 5b: Cấu hình git merge.ours driver...');
    try {
      // Driver ghi log khi giữ ours (không silent) — CVE-2026-AHD-017
      const driverPath = path.join(__dirname, '..', 'git-tools', 'hlk-merge-ours.mjs');
      const r = spawnSync('git', ['config', 'merge.ours.driver', `node ${JSON.stringify(driverPath)} %A %O %B`], { cwd: WORKSPACE_ROOT, stdio: ['ignore', 'pipe', 'pipe'] });
      if (r.status === 0) {
        log('success', 'Đã cấu hình git merge.ours.driver (log-aware, không còn silent).');
      } else {
        log('warn', `Không thể cấu hình merge.ours.driver: ${(r.stderr || '').toString().trim()}`);
      }
    } catch (err) {
      log('warn', `Không thể cấu hình merge.ours.driver: ${err.message}`);
    }
  }

  const REQUIRED_IGNORE_PATTERNS = [
    'HLK/config/secrets.*', 'HLK/config/*.local.json', 'HLK/logs/',
    '*.rvf', '*.rvf.lock', 'agentdb.rvf', 'agentdb.rvf.lock',
    '.env', '.env.*', '!.env.example', '!.env.*.example', 'example.env',
    'HLK/dist/*.tgz', 'HLK/dist/',
  ];

  function patchGitIgnore() {
    log('info', 'Bước 6: Patch .gitignore...');
    const p = path.join(WORKSPACE_ROOT, '.gitignore');
    let content = fs.existsSync(p) ? fs.readFileSync(p, 'utf8') : '';
    let modified = false;
    for (const pattern of REQUIRED_IGNORE_PATTERNS) {
      if (!content.split('\n').some((l) => l.trim() === pattern)) {
        content += (content.endsWith('\n') ? '' : '\n') + pattern + '\n';
        modified = true;
      }
    }
    if (modified) { fs.writeFileSync(p, content, 'utf8'); log('success', 'Đã cập nhật .gitignore'); }
    else { log('info', '.gitignore đã bảo vệ đầy đủ'); }
  }

  // ============================================================================
  // Bước 7: Copy skills HLK
  // ============================================================================

  // Copy skills HLK sang thư mục skills của từng CLI đã chọn.
  // Trước đây hard-code .claude/skills/ và .devin/skills/, nên Antigravity (.agents/skills/) bị bỏ sót.
  // Giờ dùng cliSkillsDir(ws, cli) cho mỗi CLI trong targets (bao gồm .agents/skills/ cho agy).
  function copySkillsAll(targets) {
    log('info', 'Bước 7: Copy skills HLK...');
    const skillsSrc = path.join(HLK_TARGET_DIR, 'skills');
    if (!fs.existsSync(skillsSrc)) { log('warn', 'Không tìm thấy HLK/skills/ — bỏ qua'); return; }

    // Đảm bảo thư mục skills của từng CLI tồn tại
    for (const cli of targets) {
      ensureCliDirs(WORKSPACE_ROOT, cli);
    }

    for (const entry of fs.readdirSync(skillsSrc, { withFileTypes: true })) {
      if (!entry.isDirectory() || !entry.name.startsWith('hlk-')) continue;
      const src = path.join(skillsSrc, entry.name);
      for (const cli of targets) {
        const dst = path.join(cliSkillsDir(WORKSPACE_ROOT, cli), entry.name);
        copyRecursive(src, dst);
      }
      log('info', `  Đã copy skill ${entry.name} → ${targets.map(cliDisplayName).join(', ')}`);
    }
    log('success', `Đã copy skills sang: ${targets.map((c) => cliSkillsDir(WORKSPACE_ROOT, c)).join(', ')}`);
  }

  // ============================================================================
  // Bước 8: Cài .githooks/post-merge
  // ============================================================================

  function installGitHooks() {
    log('info', 'Bước 8: Cài .githooks/post-merge...');
    const template = path.join(HLK_TARGET_DIR, 'skills', 'post-merge.template');
    if (!fs.existsSync(template)) { log('warn', 'Không tìm thấy post-merge.template — bỏ qua'); return; }

    const githooksDir = path.join(WORKSPACE_ROOT, '.githooks');
    fs.mkdirSync(githooksDir, { recursive: true });
    const dstPath = path.join(githooksDir, 'post-merge');
    fs.copyFileSync(template, dstPath);
    if (process.platform !== 'win32') { try { fs.chmodSync(dstPath, 0o755); } catch { /* ignore */ } }
    log('success', 'Đã cài .githooks/post-merge');

    // Kích hoạt core.hooksPath nếu workspace có .git
    if (fs.existsSync(path.join(WORKSPACE_ROOT, '.git'))) {
      const r = spawnSync('git', ['config', 'core.hooksPath'], { cwd: WORKSPACE_ROOT, encoding: 'utf8' });
      const current = r.stdout?.trim();
      if (r.status !== 0 || !current) {
        spawnSync('git', ['config', 'core.hooksPath', '.githooks'], { cwd: WORKSPACE_ROOT });
        log('success', 'Đã kích hoạt git config core.hooksPath .githooks');
      } else if (current !== '.githooks') {
        log('warn', `core.hooksPath hiện tại = "${current}" — chạy: git config core.hooksPath .githooks`);
      }
    } else {
      log('info', 'Workspace chưa có .git/ — bỏ qua git config. Chạy "git init" trước khi kích hoạt hooks.');
    }
  }

  // ============================================================================
  // Bước 9: Tạo secrets.env
  // ============================================================================

  function createSecrets() {
    const secretsPath = path.join(HLK_TARGET_DIR, 'config', 'secrets.env');
    if (fs.existsSync(secretsPath)) { log('info', 'HLK/config/secrets.env đã có — giữ nguyên'); return; }
    const examplePath = path.join(HLK_TARGET_DIR, 'config', 'secrets.env.example');
    if (fs.existsSync(examplePath)) {
      fs.copyFileSync(examplePath, secretsPath);
      log('success', 'Đã tạo HLK/config/secrets.env từ example');
    } else {
      log('warn', 'Không tìm thấy secrets.env.example — bỏ qua');
    }
  }

  // ============================================================================
  // Bước 10: Run HLK integrity verify
  // ============================================================================

  function runVerify() {
    log('info', 'Bước 9: HLK integrity verify...');
    const verify = path.join(HLK_TARGET_DIR, 'wrappers', 'hlk-verify-integrity.js');
    if (!fs.existsSync(verify)) { log('warn', 'Không tìm thấy hlk-verify-integrity.js — bỏ qua'); return; }
    const r = spawnSync(process.execPath, [verify], { cwd: WORKSPACE_ROOT, stdio: 'inherit' });
    if (r.status !== 0) { log('error', 'HLK integrity verify FAILED'); process.exit(1); }
    log('success', 'HLK integrity verify PASSED');
  }

  // ============================================================================
  // Cleanup
  // ============================================================================

  function cleanup() {
    if (SKIP_CLONE) return;
    if (TEMP_DIR && fs.existsSync(TEMP_DIR)) {
      try { fs.rmSync(TEMP_DIR, { recursive: true, force: true }); } catch { /* ignore */ }
    }
  }

  // ============================================================================
  // Chạy
  // ============================================================================

  try {
    installRuflo();
    copyHlk();
    patchCliSettingsAll(targets);
    patchGitAttributes();
    patchGitIgnore();
    copySkillsAll(targets);
    installGitHooks();
    createSecrets();
    runVerify();

    log('info', '');
    log('success', 'HLK đã cài đặt xong.');
    log('info', '');
    log('info', 'Các bước tiếp theo:');
    log('info', '  1. Mở HLK/config/secrets.env và điền API keys / tokens thật.');
    log('info', '  2. Khởi động lại Claude Code để MCP server dùng HLK wrapper.');
    log('info', '  3. Test: node HLK/wrappers/hlk-hook-bridge.mjs < test-secret.json');
    log('info', '  4. Đọc HLK/docs/01-tong-quan-va-kien-truc.md để tìm hiểu thêm.');
    log('info', '');
    log('info', 'Pull update từ upstream ruflo + reinstall HLK:');
    log('info', '  node HLK/upstream/hlk-upstream-pull.mjs --yes');
  } finally {
    cleanup();
  }
}

main();
