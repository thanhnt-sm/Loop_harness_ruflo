#!/usr/bin/env node
// ============================================================================
// HLK/wrappers/ruflo-hlk.mjs
// ----------------------------------------------------------------------------
// Local CLI launcher cho ruflo với HLK preload.
// Cách dùng:
//   node HLK/wrappers/ruflo-hlk.mjs memory store -k demo -v "sk-abc..."
//
// Tự động set NODE_OPTIONS để import hlk-loader.js trước khi ruflo CLI parse
// process.argv, đảm bảo secret trong argv bị redact.
// ============================================================================

import fs from 'node:fs';
import path from 'node:path';
import { fileURLToPath, pathToFileURL } from 'node:url';
import { spawn } from 'node:child_process';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

function resolveHlkDir() {
  const candidates = [
    path.join(process.cwd(), 'HLK'),
    path.resolve(__dirname, '..'),
  ];
  for (const dir of candidates) {
    if (fs.existsSync(path.join(dir, 'wrappers', 'hlk-loader.js'))) {
      return dir;
    }
  }
  return candidates[0];
}

const HLK_DIR = resolveHlkDir();
const LOADER_PATH = path.join(HLK_DIR, 'wrappers', 'hlk-loader.js');

if (!fs.existsSync(LOADER_PATH)) {
  process.stderr.write(`[ruflo-hlk] Không tìm thấy hlk-loader.js tại ${LOADER_PATH}\n`);
  process.exit(1);
}

const importFlag = `--import=${pathToFileURL(LOADER_PATH).href}`;
const existing = process.env.NODE_OPTIONS || '';
const nodeOptions = existing ? `${existing} ${importFlag}` : importFlag;

const rufloVersion = process.env.RUFLO_VERSION || 'latest';
const rufloArgs = process.argv.slice(2);
const args = ['-y', `ruflo@${rufloVersion}`, ...rufloArgs];

process.stderr.write(`[ruflo-hlk] Spawn npx ruflo@${rufloVersion} ${rufloArgs.join(' ')} với HLK preload\n`);

const child = spawn('npx', args, {
  cwd: process.cwd(),
  stdio: 'inherit',
  shell: process.platform === 'win32',
  env: { ...process.env, NODE_OPTIONS: nodeOptions },
});

child.on('exit', (code, signal) => {
  if (signal) process.exit(1);
  process.exit(code ?? 1);
});

child.on('error', (err) => {
  process.stderr.write(`[ruflo-hlk] Lỗi spawn: ${err.message}\n`);
  process.exit(1);
});
