#!/usr/bin/env node
/**
 * Ruflo HLK Launcher
 * ==================
 * Mục đích tổng thể:
 *   Tự động set `NODE_OPTIONS` trỏ đến `hlk-loader.js`
 *   rồi chạy `node <repo>/bin/cli.js <args...>`.
 *
 * Điều này giúp người dùng không cần cấu hình `NODE_OPTIONS` toàn cục
 * mà vẫn đảm bảo HLK được preload.
 *
 * Cách dùng:
 *   node HLK/wrappers/ruflo-hlk.mjs memory store -k demo -v "sk-abc..."
 */

import { spawn } from 'node:child_process';
import { resolve, dirname } from 'node:path';
import { fileURLToPath } from 'node:url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = dirname(__filename);

// ---------------------------------------------------------------------------
// Bước 1: Xác định đường dẫn gốc repo và loader
// ---------------------------------------------------------------------------

const REPO_ROOT = resolve(__dirname, '..', '..');
const LOADER_URL = `file://${resolve(REPO_ROOT, 'HLK/wrappers/hlk-loader.js')}`;
const CLI_PATH = resolve(REPO_ROOT, 'bin/cli.js');

// ---------------------------------------------------------------------------
// Bước 2: Chuẩn bị môi trường
// ---------------------------------------------------------------------------

const env = { ...process.env };

// Chỉ thêm `--import` nếu chưa có
if (!env.NODE_OPTIONS) {
  env.NODE_OPTIONS = `--import=${LOADER_URL}`;
} else if (!env.NODE_OPTIONS.includes('--import=')) {
  env.NODE_OPTIONS += ` --import=${LOADER_URL}`;
}

// ---------------------------------------------------------------------------
// Bước 3: Spawn tiến trình Node với bin/cli.js
// ---------------------------------------------------------------------------

const cliArgs = process.argv.slice(2);

const child = spawn(process.execPath, [CLI_PATH, ...cliArgs], {
  cwd: REPO_ROOT,
  env,
  stdio: 'inherit',
  shell: false,
});

child.on('exit', (code) => {
  process.exit(code ?? 0);
});

child.on('error', (err) => {
  process.stderr.write(`[ruflo-hlk] Lỗi spawn: ${err.message}\n`);
  process.exit(1);
});
