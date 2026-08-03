#!/usr/bin/env node
/**
 * hlk-repack.mjs
 * ==============
 * Build lại package HLK khi có cập nhật.
 * Tự động: test, bump version (tùy chọn), pack, và cài vào workspace hiện tại.
 *
 * Cách dùng:
 *   node HLK/bin/hlk-repack.mjs [options]
 *
 * Options:
 *   --bump patch|minor|major   Tăng version (mặc định: patch).
 *   --no-bump                  Không tăng version.
 *   --install                  Cài package mới vào workspace hiện tại.
 *   --yes                      Không hỏi xác nhận.
 *   --publish                  In lệnh publish npm (không tự publish).
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const HLK_ROOT = path.resolve(__dirname, '..');
const WORKSPACE_ROOT = process.cwd();

const args = process.argv.slice(2);
const BUMP = args.includes('--bump') ? args[args.indexOf('--bump') + 1] || 'patch' : 'patch';
const NO_BUMP = args.includes('--no-bump');
const INSTALL = args.includes('--install');
const YES = args.includes('--yes');
const PUBLISH = args.includes('--publish');

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

function readJson(p) {
  return JSON.parse(fs.readFileSync(p, 'utf8'));
}

function writeJson(p, data) {
  fs.writeFileSync(p, JSON.stringify(data, null, 2) + '\n', 'utf8');
}

function run(cmd, args, opts = {}) {
  const result = spawnSync(cmd, args, {
    cwd: opts.cwd ?? WORKSPACE_ROOT,
    stdio: opts.stdio ?? 'inherit',
    ...opts,
  });
  return { status: result.status ?? 1 };
}

function bumpVersion(version, type) {
  const parts = version.split('.').map(Number);
  if (type === 'major') {
    parts[0]++;
    parts[1] = 0;
    parts[2] = 0;
  } else if (type === 'minor') {
    parts[1]++;
    parts[2] = 0;
  } else {
    parts[2]++;
  }
  return parts.join('.');
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

// ---------------------------------------------------------------------------
// Bước 1: Self-test
// ---------------------------------------------------------------------------

function selfTest() {
  log('info', '=== HLK Repack ===');
  log('info', 'Bước 1: Self-test package...');
  const r = run(process.execPath, [path.join(HLK_ROOT, 'bin', 'hlk-status.mjs'), '--self-test']);
  if (r.status !== 0) {
    log('error', 'Self-test thất bại. Không pack.');
    process.exit(1);
  }
  log('success', 'Self-test OK.');
}

// ---------------------------------------------------------------------------
// Bước 2: Bump version
// ---------------------------------------------------------------------------

async function bumpStep() {
  const pkgPath = path.join(HLK_ROOT, 'package.json');
  const configPath = path.join(HLK_ROOT, 'config', 'hlk.config.json');

  const pkg = readJson(pkgPath);
  const config = readJson(configPath);
  const oldVersion = pkg.version;

  if (NO_BUMP) {
    log('info', `Giữ nguyên version ${oldVersion} (--no-bump).`);
    return oldVersion;
  }

  const newVersion = bumpVersion(oldVersion, BUMP);
  log('info', `Version: ${oldVersion} → ${newVersion} (${BUMP})`);

  if (!YES) {
    const ok = await prompt(`Bump version lên ${newVersion}?`);
    if (!ok) {
      log('info', 'Hủy repack.');
      process.exit(0);
    }
  }

  pkg.version = newVersion;
  config.version = newVersion;

  writeJson(pkgPath, pkg);
  writeJson(configPath, config);

  log('success', `Đã bump version lên ${newVersion}.`);
  return newVersion;
}

// ---------------------------------------------------------------------------
// Bước 3: Pack
// ---------------------------------------------------------------------------

function packStep(version) {
  log('info', 'Bước 2: Pack HLK...');
  const r = run(process.execPath, [path.join(HLK_ROOT, 'bin', 'hlk-pack.mjs')]);
  if (r.status !== 0) {
    log('error', 'Pack thất bại.');
    process.exit(1);
  }
  log('success', `Pack thành công: HLK/dist/hlk-ruflo-${version}.tgz`);
}

// ---------------------------------------------------------------------------
// Bước 4: Install vào workspace hiện tại
// ---------------------------------------------------------------------------

async function installStep(version) {
  if (!INSTALL) return;

  const tarball = path.join(HLK_ROOT, 'dist', `hlk-ruflo-${version}.tgz`);
  if (!fs.existsSync(tarball)) {
    log('error', `Không tìm thấy tarball: ${tarball}`);
    process.exit(1);
  }

  log('info', 'Bước 3: Cài package mới vào workspace...');

  // Không thể cài package HLK vào chính package root
  if (WORKSPACE_ROOT === HLK_ROOT || WORKSPACE_ROOT === path.resolve(HLK_ROOT, '..')) {
    log('warn', 'Workspace hiện tại là source của package HLK. Không thể cài HLK vào chính nó.');
    log('info', 'Bỏ qua bước cài. Hãy chạy --install trong một workspace Ruflo riêng.');
    return;
  }

  // Kiểm tra HLK đã cài chưa
  const hlkDir = path.join(WORKSPACE_ROOT, 'HLK');
  const isUpdate = fs.existsSync(hlkDir);

  const script = isUpdate ? 'hlk-update.mjs' : 'hlk-install.mjs';
  const verb = isUpdate ? 'Cập nhật' : 'Cài';

  log('info', `${verb} HLK vào workspace bằng ${script}...`);
  if (!YES && !(await prompt(`${verb} HLK trong workspace hiện tại?`))) {
    log('info', 'Bỏ qua install.');
    return;
  }

  // Chạy trực tiếp bằng node hiện tại, tránh npx dùng sai Node version
  const r = run(process.execPath, [path.join(HLK_ROOT, 'bin', script)]);
  if (r.status !== 0) {
    log('error', `${verb} HLK thất bại.`);
    process.exit(1);
  }

  log('success', 'Cài đặt/cập nhật HLK thành công.');
}

// ---------------------------------------------------------------------------
// Bước 5: In publish commands
// ---------------------------------------------------------------------------

function publishStep(version) {
  if (!PUBLISH) return;
  log('info', '');
  log('info', 'Lệnh để publish lên registry:');
  log('info', `  cd HLK`);
  log('info', `  npm publish --access private`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  selfTest();
  const version = await bumpStep();
  packStep(version);
  await installStep(version);
  publishStep(version);

  log('info', '');
  log('success', '=== Repack hoàn tất ===');
  log('info', `Version: ${version}`);
  log('info', `Tarball: HLK/dist/hlk-ruflo-${version}.tgz`);
  log('info', '');
  log('info', 'Cách dùng trên workspace khác:');
  log('info', `  npm install -g HLK/dist/hlk-ruflo-${version}.tgz`);
  log('info', '  npx hlk-install');
}

main();
