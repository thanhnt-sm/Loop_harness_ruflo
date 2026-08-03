#!/usr/bin/env node
/**
 * hlk-pack.mjs
 * ============
 * Đóng gói HLK thành file `.tgz` có thể cài đặt qua npm/npx.
 *
 * Cách dùng:
 *   npx hlk-pack
 *   # hoặc
 *   node HLK/bin/hlk-pack.mjs
 *
 * Output:
 *   HLK/dist/hlk-ruflo-<version>.tgz
 */

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath } from 'node:url';
import { spawnSync } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const HLK_ROOT = path.resolve(__dirname, '..');
const DIST_DIR = path.join(HLK_ROOT, 'dist');

function log(level, msg) {
  const prefix = level === 'error' ? '❌' : level === 'warn' ? '⚠️' : level === 'success' ? '✅' : 'ℹ️';
  process.stderr.write(`${prefix} ${msg}\n`);
}

function readJsonSafe(p) {
  try {
    return JSON.parse(fs.readFileSync(p, 'utf8'));
  } catch (err) {
    return null;
  }
}

// ---------------------------------------------------------------------------
// Bước 1: Kiểm tra package.json và version
// ---------------------------------------------------------------------------

function validatePackage() {
  const pkgPath = path.join(HLK_ROOT, 'package.json');
  const pkg = readJsonSafe(pkgPath);

  if (!pkg) {
    log('error', `Không đọc được ${pkgPath}`);
    process.exit(1);
  }

  if (!pkg.name || !pkg.version) {
    log('error', 'package.json thiếu name hoặc version');
    process.exit(1);
  }

  // Kiểm tra version đồng nhất với hlk.config.json
  const configPath = path.join(HLK_ROOT, 'config', 'hlk.config.json');
  const config = readJsonSafe(configPath);
  if (config && config.version !== pkg.version) {
    log('warn', `Version package.json (${pkg.version}) khác hlk.config.json (${config.version}).`);
    log('warn', 'Bạn nên đồng bộ trước khi pack.');
  }

  log('info', `Package: ${pkg.name}@${pkg.version}`);
  return pkg;
}

// ---------------------------------------------------------------------------
// Bước 2: Kiểm tra các file bắt buộc
// ---------------------------------------------------------------------------

const REQUIRED_FILES = [
  'bin/hlk-install.mjs',
  'bin/hlk-update.mjs',
  'bin/hlk-pack.mjs',
  'bin/hlk-status.mjs',
  'git-tools/hlk-git-doctor.mjs',
  'git-tools/hlk-git-commit.mjs',
  'git-tools/hlk-git-push.mjs',
  'git-tools/hlk-git-safe-sync.mjs',
  'git-tools/lib/hlk-git-lib.mjs',
  'config/hlk.config.json',
  'config/secrets.env.example',
  'wrappers/hlk-loader.js',
  'wrappers/hlk-hook-bridge.mjs',
  'wrappers/ruflo-hlk-mcp.mjs',
  'wrappers/hlk-verify-integrity.js',
  'security/sanitizer.js',
  'security/vault-bridge.js',
];

function validateContents() {
  for (const f of REQUIRED_FILES) {
    const p = path.join(HLK_ROOT, f);
    if (!fs.existsSync(p)) {
      log('error', `Thiếu file bắt buộc: ${f}`);
      process.exit(1);
    }
  }
  log('success', 'Tất cả file bắt buộc tồn tại.');
}

// ---------------------------------------------------------------------------
// Bước 3: Validate cú pháp scripts
// ---------------------------------------------------------------------------

function validateScripts() {
  const scripts = [
    'bin/hlk-install.mjs',
    'bin/hlk-update.mjs',
    'bin/hlk-pack.mjs',
    'bin/hlk-status.mjs',
  ];

  for (const s of scripts) {
    const p = path.join(HLK_ROOT, s);
    const result = spawnSync(process.execPath, ['--check', p], { stdio: 'pipe' });
    if (result.status !== 0) {
      log('error', `Lỗi cú pháp trong ${s}`);
      process.stderr.write(result.stderr);
      process.exit(1);
    }
  }
  log('success', 'Tất cả scripts pass cú pháp.');
}

// ---------------------------------------------------------------------------
// Bước 4: Chạy npm pack
// ---------------------------------------------------------------------------

function npmPack() {
  fs.mkdirSync(DIST_DIR, { recursive: true });

  // Xóa các tarball cũ trong dist
  for (const f of fs.readdirSync(DIST_DIR)) {
    if (f.endsWith('.tgz')) {
      fs.unlinkSync(path.join(DIST_DIR, f));
      log('info', `Đã xóa tarball cũ: ${f}`);
    }
  }

  const result = spawnSync('npm', ['pack'], { cwd: HLK_ROOT, stdio: 'inherit' });

  if (result.status !== 0) {
    log('error', 'npm pack thất bại.');
    process.exit(1);
  }

  // npm pack tạo file tại HLK_ROOT. Di chuyển vào dist.
  const tgzFiles = fs.readdirSync(HLK_ROOT).filter((f) => f.endsWith('.tgz'));
  if (tgzFiles.length === 0) {
    log('error', 'Không tìm thấy tarball sau npm pack.');
    process.exit(1);
  }

  for (const f of tgzFiles) {
    const src = path.join(HLK_ROOT, f);
    const dst = path.join(DIST_DIR, f);
    fs.renameSync(src, dst);
    log('success', `Đã tạo: ${dst}`);
  }

  return tgzFiles[0];
}

// ---------------------------------------------------------------------------
// Bước 5: Kiểm tra tarball
// ---------------------------------------------------------------------------

function inspectTarball(fileName) {
  const tarPath = path.join(DIST_DIR, fileName);
  const result = spawnSync('tar', ['-tzf', tarPath], { stdio: 'pipe' });

  if (result.status !== 0) {
    log('error', `Không thể đọc tarball: ${fileName}`);
    process.stderr.write(result.stderr);
    process.exit(1);
  }

  const listing = result.stdout.toString('utf8');
  const hasBin = listing.includes('package/bin/hlk-install.mjs');
  const hasConfig = listing.includes('package/config/');
  const hasWrappers = listing.includes('package/wrappers/');

  if (!hasBin || !hasConfig || !hasWrappers) {
    log('error', 'Tarball thiếu nội dung quan trọng.');
    process.exit(1);
  }

  log('success', `Tarball ${fileName} chứa đủ nội dung.`);
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

function main() {
  log('info', '=== HLK Packager ===');

  const pkg = validatePackage();
  validateContents();
  validateScripts();
  const tarball = npmPack();
  inspectTarball(tarball);

  log('info', '');
  log('success', 'Đóng gói HLK thành công.');
  log('info', `File: HLK/dist/${tarball}`);
  log('info', '');
  log('info', 'Cách dùng:');
  log('info', `  1. Global install: npm install -g HLK/dist/${tarball}`);
  log('info', `  2. Trong workspace Ruflo mới: npx hlk-install`);
  log('info', `  3. Cập nhật: npx hlk-update`);
}

main();
