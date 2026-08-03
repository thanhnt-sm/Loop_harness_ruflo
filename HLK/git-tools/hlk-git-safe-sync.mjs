#!/usr/bin/env node
/**
 * hlk-git-safe-sync.mjs
 * =====================
 * Chạy pipeline: git doctor → commit → push.
 * Tự động xử lý các vấn đề an toàn, hỏi xác nhận với các thao tác nguy hiểm.
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-safe-sync.mjs [options]
 *
 * Options:
 *   -m, --message "msg"   Commit message.
 *   --yes                 Không hỏi xác nhận (vẫn không force).
 *   --no-push             Chỉ doctor + commit, không push.
 */

import { fileURLToPath } from 'node:url';
import path from 'node:path';
import { spawnSync } from 'node:child_process';
import {
  log,
  getRepoRoot,
  getBranch,
} from './lib/hlk-git-lib.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CWD = process.cwd();
const HLK_GIT_TOOLS = path.resolve(__dirname);

const args = process.argv.slice(2);
let MESSAGE = null;
let YES = args.includes('--yes');
let NO_PUSH = args.includes('--no-push');

for (let i = 0; i < args.length; i++) {
  if ((args[i] === '-m' || args[i] === '--message') && args[i + 1]) {
    MESSAGE = args[i + 1];
    i++;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

function runScript(name, extraArgs = []) {
  const script = path.join(HLK_GIT_TOOLS, name);
  const allArgs = [script, ...extraArgs];
  if (YES) allArgs.push('--yes');

  log('info', `Chạy ${name}...`);
  const r = spawnSync(process.execPath, allArgs, { cwd: CWD, stdio: 'inherit' });
  return r.status ?? 1;
}

// ---------------------------------------------------------------------------
// Main
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git Safe Sync ===');
  log('info', `Workspace: ${CWD}`);
  log('info', `Branch: ${getBranch(CWD) ?? '?'}`);

  // Bước 1: Doctor
  const doctorStatus = runScript('hlk-git-doctor.mjs', ['--fix']);
  if (doctorStatus !== 0) {
    log('error', 'Git doctor phát hiện vấn đề nghiêm trọng. Dừng lại.');
    process.exit(1);
  }
  log('success', 'Git doctor OK.');

  // Bước 2: Commit
  const commitArgs = [];
  if (MESSAGE) commitArgs.push('-m', MESSAGE);
  const commitStatus = runScript('hlk-git-commit.mjs', commitArgs);

  // 0 = thành công, >0 = lỗi hoặc hủy. Không phân biệt "không có gì commit" với lỗi.
  // Nếu không có gì để commit, hlk-git-commit exit 0.
  if (commitStatus !== 0) {
    log('error', 'Commit thất bại hoặc bị hủy. Dừng lại.');
    process.exit(1);
  }
  log('success', 'Commit OK.');

  // Bước 3: Push
  if (NO_PUSH) {
    log('info', 'Bỏ qua push (--no-push).');
    process.exit(0);
  }

  const pushStatus = runScript('hlk-git-push.mjs');
  if (pushStatus !== 0) {
    log('error', 'Push thất bại. Dừng lại.');
    process.exit(1);
  }
  log('success', 'Push OK.');

  log('info', '');
  log('success', 'Safe sync hoàn thành.');
}

main();
