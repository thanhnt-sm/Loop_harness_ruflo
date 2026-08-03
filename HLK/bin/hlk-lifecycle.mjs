#!/usr/bin/env node
/**
 * hlk-lifecycle.mjs  (đổi tên từ hlk-ruflo-setup.mjs)
 * ===================
 * Script full lifecycle: cài đặt hoặc cập nhật Ruflo + HLK.
 *
 * VAI TRÒ: Orchestrator lifecycle đơn giản — init workspace mới hoặc update.
 *           Gọi hlk-install.mjs / hlk-update.mjs để làm việc thực.
 *           KHÔNG cấu hình MAX POWER — dùng hlk-setup-max-power.mjs cho việc đó.
 *
 * KHI NÀO DÙNG SCRIPT NÀO TRONG HLK/bin/:
 *   - Cài MAX POWER đầy đủ (Ruflo + HLK + 3 CLI + provider tuning):
 *       → hlk-setup-max-power.mjs
 *   - Update/re-patch/upgrade workspace đã có MAX POWER:
 *       → hlk-update-max-power.mjs
 *   - Lifecycle đơn giản (init + install HLK, không MAX POWER):
 *       → hlk-lifecycle.mjs (script này)
 *   - Chỉ cài HLK vào workspace đã có ruflo:
 *       → hlk-install.mjs
 *   - Chỉ update HLK trong workspace:
 *       → hlk-update.mjs
 *   - Kiểm tra trạng thái HLK:
 *       → hlk-status.mjs
 *   - Đóng gói HLK thành .tgz (chỉ trong repo HLK):
 *       → hlk-pack.mjs / hlk-repack.mjs
 *
 * Cách dùng:
 *   # Cài mới
 *   node HLK/bin/hlk-lifecycle.mjs --init my-project
 *
 *   # Cập nhật workspace hiện tại
 *   node HLK/bin/hlk-lifecycle.mjs --update
 *
 * Options:
 *   --init <dir>              Tạo workspace mới.
 *   --update                  Cập nhật workspace hiện tại.
 *   --ruflo-version <ver>     Version ruflo (mặc định: 3.34.0).
 *   --hlk-tgz <path>          Đường dẫn tarball HLK.
 *   --hlk-global              HLK đã global install, dùng npx hlk-install.
 *   --hlk-npm                 Dùng npm registry (npm install -g hlk-ruflo).
 *   --yes                     Không hỏi xác nhận.
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HLK_ROOT = path.resolve(__dirname, '..');

const args = process.argv.slice(2);

let INIT_DIR = null;
let UPDATE = false;
let RUFLO_VERSION = '3.34.0';
let HLK_TGZ = null;
let HLK_GLOBAL = false;
let HLK_NPM = false;
let SKIP_RUFLO = false;
let YES = false;

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--init' && args[i + 1]) { INIT_DIR = args[i + 1]; i++; }
  else if (args[i] === '--update') UPDATE = true;
  else if (args[i] === '--ruflo-version' && args[i + 1]) { RUFLO_VERSION = args[i + 1]; i++; }
  else if (args[i] === '--hlk-tgz' && args[i + 1]) { HLK_TGZ = args[i + 1]; i++; }
  else if (args[i] === '--hlk-global') HLK_GLOBAL = true;
  else if (args[i] === '--hlk-npm') HLK_NPM = true;
  else if (args[i] === '--skip-ruflo') SKIP_RUFLO = true;
  else if (args[i] === '--yes') YES = true;
}

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, {
    cwd: opts.cwd,
    stdio: opts.stdio ?? 'inherit',
    ...opts,
  });
  return { status: result.status ?? 1 };
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
// Tìm HLK tarball mặc định
// ---------------------------------------------------------------------------

function findDefaultHlkTgz() {
  const distDir = path.join(HLK_ROOT, 'dist');
  if (!fs.existsSync(distDir)) return null;

  const files = fs.readdirSync(distDir).filter((f) => f.startsWith('hlk-ruflo-') && f.endsWith('.tgz'));
  if (files.length === 0) return null;

  // Lấy file mới nhất theo tên (semantic version sẽ sort đúng)
  files.sort();
  return path.join(distDir, files[files.length - 1]);
}

// ---------------------------------------------------------------------------
// Cài HLK
// ---------------------------------------------------------------------------

async function installHlk(cwd, isUpdate) {
  log('info', '=== Cài đặt / Cập nhật HLK ===');

  let packageRoot = null;

  if (HLK_NPM) {
    // Cài từ npm registry vào workspace tạm thời (không save)
    const r = run('npm', ['install', '--no-save', 'hlk-ruflo'], { cwd });
    if (r.status !== 0) {
      log('error', 'Cài HLK package thất bại.');
      process.exit(1);
    }
    packageRoot = path.join(cwd, 'node_modules', 'hlk-ruflo');
  } else if (HLK_TGZ) {
    const tgz = path.resolve(HLK_TGZ);
    if (!fs.existsSync(tgz)) {
      log('error', `Không tìm thấy HLK tarball: ${tgz}`);
      process.exit(1);
    }
    log('info', `Cài HLK từ tarball: ${tgz}`);
    const r = run('npm', ['install', '--no-save', tgz], { cwd });
    if (r.status !== 0) {
      log('error', 'Cài HLK package thất bại.');
      process.exit(1);
    }
    packageRoot = path.join(cwd, 'node_modules', 'hlk-ruflo');
  } else if (HLK_GLOBAL) {
    // Tìm global package root
    const result = spawnSync('npm', ['root', '-g'], { encoding: 'utf8' });
    if (result.status !== 0 || !result.stdout) {
      log('error', 'Không xác định được npm global root.');
      process.exit(1);
    }
    packageRoot = path.join(result.stdout.trim(), 'hlk-ruflo');
    if (!fs.existsSync(packageRoot)) {
      log('error', 'HLK chưa được global install. Hãy chạy: npm install -g hlk-ruflo');
      process.exit(1);
    }
  } else {
    // Mặc định: tìm tarball gần nhất trong HLK/dist/
    const tgz = findDefaultHlkTgz();
    if (tgz) {
      log('info', `Cài HLK từ tarball mặc định: ${tgz}`);
      const r = run('npm', ['install', '--no-save', tgz], { cwd });
      if (r.status !== 0) {
        log('error', 'Cài HLK package thất bại.');
        process.exit(1);
      }
      packageRoot = path.join(cwd, 'node_modules', 'hlk-ruflo');
    } else {
      // Nếu script đang chạy từ package source (HLK_ROOT), dùng trực tiếp
      packageRoot = HLK_ROOT;
    }
  }

  if (!fs.existsSync(packageRoot)) {
    log('error', `Không tìm thấy HLK package tại: ${packageRoot}`);
    process.exit(1);
  }

  const script = isUpdate ? 'hlk-update.mjs' : 'hlk-install.mjs';
  const scriptPath = path.join(packageRoot, 'bin', script);
  log('info', `Chạy ${script} từ ${scriptPath} bằng Node ${process.version}`);

  const r = run(process.execPath, [scriptPath], { cwd });
  if (r.status !== 0) {
    log('error', `${script} thất bại.`);
    process.exit(1);
  }

  log('success', `HLK ${isUpdate ? 'cập nhật' : 'cài đặt'} thành công.`);
}

// ---------------------------------------------------------------------------
// Cài mới Ruflo + HLK
// ---------------------------------------------------------------------------

async function initWorkspace() {
  if (!INIT_DIR) {
    log('error', 'Thiếu --init <dir>');
    process.exit(1);
  }

  const target = path.resolve(INIT_DIR);
  if (!fs.existsSync(target)) {
    fs.mkdirSync(target, { recursive: true });
  }

  log('info', `=== Tạo workspace mới: ${target} ===`);

  if (!YES && !(await ask(`Tạo workspace Ruflo tại ${target}?`))) {
    log('info', 'Hủy.');
    process.exit(0);
  }

  // Kiểm tra ruflo đã cài trong thư mục chưa
  const hasRuflo = fs.existsSync(path.join(target, '.claude')) || fs.existsSync(path.join(target, 'package.json'));
  if (SKIP_RUFLO) {
    log('info', '--skip-ruflo: Bỏ qua cài đặt Ruflo.');
  } else if (!hasRuflo) {
    log('info', 'Bước 1: Cài Ruflo...');
    const r = run('npx', ['-y', `ruflo@${RUFLO_VERSION}`, 'init'], { cwd: target });
    if (r.status !== 0) {
      log('error', 'Ruflo init thất bại.');
      process.exit(1);
    }
    log('success', 'Ruflo init thành công.');
  } else {
    log('info', 'Ruflo đã tồn tại, bỏ qua init.');
  }

  await installHlk(target, false);

  // Nhắc cấu hình secrets
  log('info', '');
  log('info', 'Cấu hình secrets:');
  log('info', `  ${path.join(target, 'HLK/config/secrets.env')}`);

  log('info', '');
  log('success', 'Workspace mới sẵn sàng.');
}

// ---------------------------------------------------------------------------
// Cập nhật Ruflo + HLK
// ---------------------------------------------------------------------------

async function updateWorkspace() {
  const cwd = process.cwd();
  log('info', `=== Cập nhật workspace: ${cwd} ===`);

  if (!fs.existsSync(path.join(cwd, '.claude')) && !fs.existsSync(path.join(cwd, 'package.json'))) {
    log('error', 'Thư mục hiện tại không phải workspace Ruflo.');
    process.exit(1);
  }

  if (!YES && !(await ask('Cập nhật Ruflo + HLK trong workspace hiện tại?'))) {
    log('info', 'Hủy.');
    process.exit(0);
  }

  // Cập nhật Ruflo
  if (SKIP_RUFLO) {
    log('info', '--skip-ruflo: Bỏ qua cập nhật Ruflo.');
  } else {
    log('info', 'Bước 1: Cập nhật Ruflo...');
    const r = run('npx', ['-y', `ruflo@${RUFLO_VERSION}`, 'init', 'upgrade', '--add-missing'], { cwd });
    if (r.status !== 0) {
      log('error', 'Ruflo upgrade thất bại.');
      process.exit(1);
    }
    log('success', 'Ruflo cập nhật thành công.');
  }

  // Cập nhật HLK
  await installHlk(cwd, true);

  log('info', '');
  log('success', 'Workspace cập nhật thành công.');
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  if (UPDATE) {
    await updateWorkspace();
  } else if (INIT_DIR) {
    await initWorkspace();
  } else {
    log('error', 'Thiếu --init <dir> hoặc --update');
    log('info', '');
    log('info', 'Ví dụ:');
    log('info', '  node HLK/bin/hlk-lifecycle.mjs --init my-project');
    log('info', '  node HLK/bin/hlk-lifecycle.mjs --update --yes');
    process.exit(1);
  }
}

main();
