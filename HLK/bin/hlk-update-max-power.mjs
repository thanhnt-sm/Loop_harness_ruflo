#!/usr/bin/env node
// ============================================================================
// HLK/bin/hlk-update-max-power.mjs
// ----------------------------------------------------------------------------
// Script UPDATE workspace đã setup MAX POWER.
// Khác với setup (cài mới), update:
//   - Không cài lại ruflo (giữ nguyên version đã cài).
//   - Upgrade ruflo lên version mới (nếu --upgrade).
//   - Re-patch tất cả config lên MAX POWER (đảm bảo không bị drift).
//   - Update HLK layer (pull upstream + reinstall).
//   - Update providers config.
//   - Verify lại.
//
// Cách dùng:
//   node HLK/bin/hlk-update-max-power.mjs                          # hỏi path
//   node HLK/bin/hlk-update-max-power.mjs --path D:/projects/my-ws --yes
//   node HLK/bin/hlk-update-max-power.mjs --path <ws> --upgrade    # upgrade ruflo version
//   node HLK/bin/hlk-update-max-power.mjs --path <ws> --local      # update ruflo cục bộ
//
// Options:
//   --path <dir>   Đường dẫn workspace (bỏ qua bước hỏi).
//   --yes          Không hỏi xác nhận.
//   --upgrade      Upgrade ruflo lên version mới (npm update hoặc npx -y ruflo@latest).
//   --local        Update ruflo cục bộ (npm update trong workspace).
//   --skip-hlk     Bỏ qua update HLK layer.
//   --skip-devin   Bỏ qua re-patch Devin CLI.
//   --skip-agy     Bỏ qua re-patch Antigravity CLI.
//   --skip-providers  Bỏ qua update providers.
//   --provider <name>  Đổi provider mặc định: claude|codex|gemini|openai.
//   --ruflo-version <ver>  Version ruflo khi upgrade (mặc định: latest).
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import readline from 'node:readline';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

// --- Parse args (mặc định LOCAL=true, mọi flag có mặc định) ---
let USER_PATH = null;
let YES = false;
let UPGRADE = false;
let LOCAL = true;          // Mặc định: update CỤC BỘ
let SKIP_HLK = false;
let SKIP_DEVIN = false;
let SKIP_AGY = false;
let SKIP_PROVIDERS = false;
let PROVIDER = null;  // null = giữ nguyên provider hiện có
let RUFLO_VERSION = 'latest';

const CLI_SET = new Set();

const rawArgs = process.argv.slice(2);
for (let i = 0; i < rawArgs.length; i++) {
  const a = rawArgs[i];
  if (a === '--path' && rawArgs[i + 1]) { USER_PATH = rawArgs[i + 1]; CLI_SET.add('path'); i++; }
  else if (a === '--yes' || a === '-y') { YES = true; CLI_SET.add('yes'); }
  else if (a === '--upgrade') { UPGRADE = true; CLI_SET.add('upgrade'); }
  else if (a === '--local') { LOCAL = true; CLI_SET.add('local'); }
  else if (a === '--global') { LOCAL = false; CLI_SET.add('local'); }
  else if (a === '--skip-hlk') { SKIP_HLK = true; CLI_SET.add('skip-hlk'); }
  else if (a === '--skip-devin') { SKIP_DEVIN = true; CLI_SET.add('skip-devin'); }
  else if (a === '--skip-agy') { SKIP_AGY = true; CLI_SET.add('skip-agy'); }
  else if (a === '--skip-providers') { SKIP_PROVIDERS = true; CLI_SET.add('skip-providers'); }
  else if (a === '--provider' && rawArgs[i + 1]) { PROVIDER = rawArgs[i + 1]; CLI_SET.add('provider'); i++; }
  else if (a === '--ruflo-version' && rawArgs[i + 1]) { RUFLO_VERSION = rawArgs[i + 1]; CLI_SET.add('ruflo-version'); i++; }
  else if (a === '--help' || a === '-h') {
    process.stderr.write([
      'hlk-update-max-power.mjs — UPDATE workspace đã setup MAX POWER',
      '',
      'Mặc định: update CỤC BỘ (--local), hỏi tất cả tham số có đề xuất mặc định.',
      'Dùng --yes để chạy headless (không hỏi, dùng mặc định).',
      '',
      'Cách dùng:',
      '  node HLK/bin/hlk-update-max-power.mjs                    # hỏi tương tác đầy đủ',
      '  node HLK/bin/hlk-update-max-power.mjs --yes              # headless, dùng mặc định',
      '  node HLK/bin/hlk-update-max-power.mjs --path D:/ws --upgrade --yes',
      '',
      'Options (ghi đè mặc định, bỏ qua câu hỏi tương ứng):',
      '  --path <dir>           Đường dẫn workspace',
      '  --yes                  Không hỏi, dùng mặc định',
      '  --upgrade              Upgrade ruflo lên version mới',
      '  --local                Update ruflo CỤC BỘ (MẶC ĐỊNH)',
      '  --global               Update ruflo global/npx',
      '  --skip-hlk             Bỏ qua update HLK layer',
      '  --skip-devin           Bỏ qua re-patch Devin CLI',
      '  --skip-agy             Bỏ qua re-patch Antigravity CLI',
      '  --skip-providers       Bỏ qua update providers',
      '  --provider <name>      Đổi provider: claude|codex|gemini|openai',
      '  --ruflo-version <ver>  Version ruflo khi upgrade (mặc định: latest)',
    ].join('\n') + '\n');
    process.exit(0);
  }
}

// --- Tiện ích log ---
const USE_COLOR = process.stderr.isTTY && process.platform !== 'win32';
const c = (code, s) => USE_COLOR ? `\x1b[${code}m${s}\x1b[0m` : s;
const log = {
  info: (m) => process.stderr.write(`${c('36', 'ℹ')} ${m}\n`),
  step: (m) => process.stderr.write(`${c('32', '▸')} ${m}\n`),
  ok:   (m) => process.stderr.write(`${c('32', '✓')} ${m}\n`),
  warn: (m) => process.stderr.write(`${c('33', '⚠')} ${m}\n`),
  err:  (m) => process.stderr.write(`${c('31', '✗')} ${m}\n`),
  head: (m) => process.stderr.write(`\n${c('1;36', '═══ ' + m + ' ═══')}\n`),
};

// ============================================================================
// HỆ THỐNG HỎI TƯƠNG TÁC
// ============================================================================

function askText(question, defaultVal) {
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question} [mặc định: ${c('33', defaultVal)}]: `, (ans) => {
      rl.close();
      const t = (ans || '').trim().replace(/^["']|["']$/g, '');
      resolve(t || defaultVal);
    });
  });
}

function askBool(question, defaultVal) {
  const hint = defaultVal ? 'Y/n' : 'y/N';
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question} [${hint}]: `, (ans) => {
      rl.close();
      const t = (ans || '').trim().toLowerCase();
      if (t === '') return resolve(defaultVal);
      resolve(/^y(es)?$/i.test(t));
    });
  });
}

function askChoice(question, choices, defaultIdx) {
  const lines = choices.map((ch, i) => {
    const marker = i === defaultIdx ? c('33', ` → ${i + 1}. ${ch}`) : `    ${i + 1}. ${ch}`;
    return marker;
  });
  return new Promise((resolve) => {
    const rl = readline.createInterface({ input: process.stdin, output: process.stderr });
    rl.question(`${question}\n${lines.join('\n')}\nChọn [mặc định: ${defaultIdx + 1}]: `, (ans) => {
      rl.close();
      const t = (ans || '').trim();
      if (t === '') return resolve(defaultIdx);
      const n = parseInt(t, 10);
      if (n >= 1 && n <= choices.length) return resolve(n - 1);
      const lower = t.toLowerCase();
      const idx = choices.findIndex((ch) => ch.toLowerCase().includes(lower));
      if (idx >= 0) return resolve(idx);
      log.warn(`Giá trị không hợp lệ, dùng mặc định: ${choices[defaultIdx]}`);
      resolve(defaultIdx);
    });
  });
}

// ============================================================================
// HỎI TẤT CẢ THAM SỐ
// ============================================================================

async function askAllParams() {
  log.head('Cấu hình update MAX POWER');

  // 1. Workspace path
  if (!CLI_SET.has('path')) {
    USER_PATH = await askText('1. Đường dẫn workspace cần UPDATE?', process.cwd());
  }

  // 2. Local vs Global
  if (!CLI_SET.has('local')) {
    const idx = await askChoice(
      '2. Chế độ update Ruflo?',
      ['Local (npm update trong workspace — khuyến nghị)', 'Global (npx -y ruflo@latest)'],
      0,
    );
    LOCAL = idx === 0;
  }

  // 3. Upgrade
  if (!CLI_SET.has('upgrade')) {
    UPGRADE = await askBool('3. Upgrade ruflo lên version mới?', false);
  }

  // 4. Ruflo version (chỉ hỏi nếu upgrade)
  if (UPGRADE && !CLI_SET.has('ruflo-version')) {
    RUFLO_VERSION = await askText('4. Version Ruflo để upgrade?', 'latest');
  }

  // 5. Provider (đề xuất = provider hiện có)
  if (!CLI_SET.has('provider')) {
    const currentProv = readCurrentProvider(path.resolve(USER_PATH));
    const idx = await askChoice(
      '5. AI Provider mặc định?',
      [
        `claude — Anthropic (reasoning, architecture, security)${currentProv === 'claude' ? ' [hiện tại]' : ''}`,
        `codex — OpenAI Codex (implementation, optimization)${currentProv === 'codex' ? ' [hiện tại]' : ''}`,
        `gemini — Google (multimodal, research, long-context)${currentProv === 'gemini' ? ' [hiện tại]' : ''}`,
        `openai — OpenAI GPT-4.1 (reasoning, general)${currentProv === 'openai' ? ' [hiện tại]' : ''}`,
        `giữ nguyên provider hiện tại (${currentProv})`,
      ],
      4,  // mặc định: giữ nguyên
    );
    if (idx < 4) PROVIDER = ['claude', 'codex', 'gemini', 'openai'][idx];
  }

  // 6. Các tính năng re-patch
  log.info('6. Các tính năng re-patch (bật/tắt):');

  if (!CLI_SET.has('skip-hlk')) {
    SKIP_HLK = !(await askBool('   Update HLK layer (upstream pull + reinstall)?', true));
  }
  if (!CLI_SET.has('skip-devin')) {
    SKIP_DEVIN = !(await askBool('   Re-patch Devin CLI (.devin/)?', true));
  }
  if (!CLI_SET.has('skip-agy')) {
    SKIP_AGY = !(await askBool('   Re-patch Antigravity CLI (agy)?', true));
  }
  if (!CLI_SET.has('skip-providers')) {
    SKIP_PROVIDERS = !(await askBool('   Update Provider config?', true));
  }

  // 7. Xác nhận
  if (!CLI_SET.has('yes')) {
    const prov = PROVIDER || readCurrentProvider(path.resolve(USER_PATH));
    log.info('');
    log.info('Tóm tắt cấu hình update:');
    log.info(`  Workspace:     ${USER_PATH}`);
    log.info(`  Chế độ:        ${LOCAL ? 'LOCAL (cục bộ)' : 'GLOBAL/npx'}`);
    log.info(`  Upgrade ruflo: ${UPGRADE ? `CÓ (${RUFLO_VERSION})` : 'KHÔNG'}`);
    log.info(`  Provider:      ${PROVIDER ? PROVIDER + ' (đổi)' : prov + ' (giữ nguyên)'}`);
    log.info(`  HLK layer:     ${SKIP_HLK ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  Devin CLI:     ${SKIP_DEVIN ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  Antigravity:   ${SKIP_AGY ? 'KHÔNG' : 'CÓ'}`);
    log.info(`  Providers:     ${SKIP_PROVIDERS ? 'KHÔNG' : 'CÓ'}`);
    log.info('');
    const ok = await askBool('Xác nhận bắt đầu update?', true);
    if (!ok) { log.info('Đã hủy.'); process.exit(0); }
  }
}

function run(cmd, args, opts = {}) {
  return spawnSync(cmd, args, {
    cwd: opts.cwd,
    stdio: opts.stdio ?? 'inherit',
    shell: process.platform === 'win32',
    env: { ...process.env, ...(opts.env || {}) },
  });
}

// --- Đọc provider hiện tại từ providers.json ---
function readCurrentProvider(ws) {
  try {
    const p = path.join(ws, '.claude-flow', 'providers.json');
    if (fs.existsSync(p)) {
      const data = JSON.parse(fs.readFileSync(p, 'utf8'));
      return data.default || 'claude';
    }
  } catch { /* ignore */ }
  return 'claude';
}

// --- Gọi setup-max-power.mjs với --skip-ruflo (re-patch tất cả) ---
function rePatchViaSetup(ws) {
  log.head('Re-patch tất cả config qua hlk-setup-max-power.mjs');

  const setupScript = path.join(__dirname, 'hlk-setup-max-power.mjs');
  if (!fs.existsSync(setupScript)) {
    log.err(`Không tìm thấy ${setupScript}`);
    process.exit(1);
  }

  // Xây args cho setup script (--skip-ruflo vì update không cài lại)
  const setupArgs = ['--path', ws, '--yes', '--skip-ruflo'];
  // Truyền chế độ local/global
  setupArgs.push(LOCAL ? '--local' : '--global');
  if (SKIP_HLK) setupArgs.push('--skip-hlk');
  if (SKIP_DEVIN) setupArgs.push('--skip-devin');
  if (SKIP_AGY) setupArgs.push('--skip-agy');
  if (SKIP_PROVIDERS) setupArgs.push('--skip-providers');

  // Provider: dùng --provider nếu chỉ định, иначе giữ nguyên hiện có
  const prov = PROVIDER || readCurrentProvider(ws);
  setupArgs.push('--provider', prov);

  log.info(`Chạy: node setup-max-power.mjs ${setupArgs.join(' ')}`);
  const r = run(process.execPath, [setupScript, ...setupArgs], { cwd: ws });
  if (r.status !== 0) {
    log.err('hlk-setup-max-power.mjs thất bại trong quá trình re-patch.');
    process.exit(r.status ?? 1);
  }
  log.ok('Re-patch xong.');
}

// --- Upgrade ruflo version ---
function upgradeRuflo(ws) {
  if (!UPGRADE) return;
  log.head('Upgrade Ruflo version');

  const pkg = RUFLO_VERSION === 'latest' ? 'ruflo@latest' : `ruflo@${RUFLO_VERSION}`;

  if (LOCAL) {
    log.info(`--local: npm update ${pkg} trong workspace`);
    const r = run('npm', ['update', pkg], { cwd: ws });
    if (r.status !== 0) log.warn('npm update ruflo gặp lỗi.');
    else log.ok(`Đã update ${pkg} cục bộ.`);
  } else {
    log.info(`Upgrade: npx -y ${pkg} init upgrade --add-missing`);
    const r = run('npx', ['-y', pkg, 'init', 'upgrade', '--add-missing'], { cwd: ws });
    if (r.status !== 0) log.warn('Ruflo upgrade gặp lỗi — tiếp tục.');
    else log.ok('Ruflo upgrade xong.');
  }
}

// --- Update HLK layer (pull upstream + reinstall) ---
function updateHlkLayer(ws) {
  if (SKIP_HLK) return;
  log.head('Update HLK layer');

  // Thử chạy HLK upstream pull nếu có
  const upstreamScript = path.join(ws, 'HLK', 'upstream', 'hlk-upstream-pull.mjs');
  if (fs.existsSync(upstreamScript)) {
    log.info('Chạy HLK upstream pull...');
    const r = run(process.execPath, [upstreamScript, '--yes'], { cwd: ws });
    if (r.status !== 0) log.warn('HLK upstream pull gặp lỗi — tiếp tục.');
    else log.ok('HLK upstream pull xong.');
  } else {
    log.info('Không tìm thấy HLK/upstream/hlk-upstream-pull.mjs — bỏ qua upstream pull.');
  }

  // Re-install HLK qua setup script (đã handle ở rePatchViaSetup với --skip-ruflo)
  // HLK install sẽ chạy trong hlk-setup-max-power.mjs
  log.ok('HLK layer sẽ được re-install qua hlk-setup-max-power.mjs.');
}

// --- Verify ---
function verifyUpdate(ws) {
  log.head('Verify update');
  const rufloCmd = LOCAL ? 'ruflo' : 'ruflo@latest';

  log.info('Chạy: ruflo doctor');
  const d = run('npx', [rufloCmd, 'doctor'], { cwd: ws });
  if (d.status !== 0) log.warn('ruflo doctor có cảnh báo.');

  // HLK integrity
  const verify = path.join(ws, 'HLK', 'wrappers', 'hlk-verify-integrity.js');
  if (fs.existsSync(verify)) {
    log.info('Chạy: HLK integrity verify');
    const v = run(process.execPath, [verify], { cwd: ws });
    if (v.status !== 0) log.warn('HLK integrity verify FAILED.');
    else log.ok('HLK integrity verify PASSED');
  }

  log.ok('Update verify xong.');
}

// ============================================================================
// MAIN
// ============================================================================

async function main() {
  process.stderr.write('\n');
  process.stderr.write('╔═══════════════════════════════════════════════════════════╗\n');
  process.stderr.write('║  Ruflo MAX POWER Update — Re-patch + Upgrade + Verify      ║\n');
  process.stderr.write('╚═══════════════════════════════════════════════════════════╝\n\n');

  // Kiểm tra Node
  const nodeMajor = parseInt(process.versions.node.split('.')[0], 10);
  if (nodeMajor < 20) { log.err(`Node >= 20 yêu cầu. Hiện tại: ${process.version}`); process.exit(1); }

  // Hỏi tất cả tham số (workspace, local/global, upgrade, provider, tính năng, xác nhận)
  // Nếu --yes: bỏ qua hỏi, dùng mặc định
  await askAllParams();

  const ws = path.resolve(USER_PATH);

  if (!fs.existsSync(ws)) {
    log.err(`Workspace không tồn tại: ${ws}`);
    log.info('Dùng hlk-setup-max-power.mjs để tạo mới trước.');
    process.exit(1);
  }

  // Kiểm tra đã setup MAX POWER chưa (chỉ cảnh báo, không block)
  const settingsPath = path.join(ws, '.claude', 'settings.json');
  const runtimePath = path.join(ws, '.claude-flow', 'runtime.json');
  if (!fs.existsSync(settingsPath) && !fs.existsSync(runtimePath)) {
    log.warn('Workspace có vẻ chưa setup MAX POWER (thiếu .claude/settings.json + .claude-flow/runtime.json).');
    log.info('Khuyến nghị: chạy hlk-setup-max-power.mjs trước. Tiếp tục update (sẽ tạo config mới)...');
  } else {
    log.ok('Workspace đã có cấu hình MAX POWER — tiến hành update.');
  }

  // 1. Upgrade ruflo (nếu --upgrade)
  upgradeRuflo(ws);

  // 2. Update HLK layer (nếu không --skip-hlk)
  updateHlkLayer(ws);

  // 3. Re-patch tất cả config qua hlk-setup-max-power.mjs (--skip-ruflo)
  rePatchViaSetup(ws);

  // 4. Verify
  verifyUpdate(ws);

  // Tóm tắt
  log.head('Tóm tắt update');
  log.ok(`Workspace: ${ws}`);
  log.ok(`Provider: ${PROVIDER || readCurrentProvider(ws)}`);
  if (UPGRADE) log.ok('Ruflo: đã upgrade');
  if (!SKIP_HLK) log.ok('HLK: đã update (upstream pull + reinstall)');
  log.ok('Config: đã re-patch MAX POWER (Claude Code + Devin CLI + agy + providers)');
  log.ok('Verify: doctor + HLK integrity');

  process.stderr.write('\n');
  log.ok('Ruflo MAX POWER update hoàn tất.');
  process.exit(0);
}

main().catch((e) => {
  log.err(`Lỗi: ${e?.stack || e?.message || e}`);
  process.exit(1);
});
