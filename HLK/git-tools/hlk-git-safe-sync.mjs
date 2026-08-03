#!/usr/bin/env node
/**
 * hlk-git-safe-sync.mjs
 * =====================
 * Chạy pipeline đầy đủ: git doctor → pull → commit (auto-add) → push.
 * Tự động xử lý các vấn đề an toàn, hỏi xác nhận với các thao tác nguy hiểm.
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-safe-sync.mjs [options]
 *
 * Options:
 *   -m, --message "msg"   Commit message.
 *   --yes                 Không hỏi xác nhận (vẫn không force).
 *   --no-push             Chỉ doctor + pull + commit, không push.
 *   --no-pull             Bỏ qua bước pull.
 *   --no-add              Không tự động git add (chỉ commit file đã staged).
 *   --remote <name>       Remote name (mặc định: origin).
 *   --branch <name>       Branch name (mặc định: branch hiện tại).
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
let NO_PULL = args.includes('--no-pull');
let NO_ADD = args.includes('--no-add');
let REMOTE = 'origin';
let BRANCH = null;

for (let i = 0; i < args.length; i++) {
  if ((args[i] === '-m' || args[i] === '--message') && args[i + 1]) {
    MESSAGE = args[i + 1];
    i++;
  } else if (args[i] === '--remote' && args[i + 1]) {
    REMOTE = args[i + 1];
    i++;
  } else if ((args[i] === '-b' || args[i] === '--branch') && args[i + 1]) {
    BRANCH = args[i + 1];
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

  // Bước 1: Doctor — kiểm tra sức khỏe repo
  const doctorStatus = runScript('hlk-git-doctor.mjs', ['--fix']);
  if (doctorStatus !== 0) {
    log('error', 'Git doctor phát hiện vấn đề nghiêm trọng. Dừng lại.');
    process.exit(1);
  }
  log('success', 'Git doctor OK.');

  // Bước 2: Pull — kéo source mới từ remote
  if (NO_PULL) {
    log('info', 'Bỏ qua pull (--no-pull).');
  } else {
    const pullArgs = ['--stash'];
    if (REMOTE !== 'origin') pullArgs.push('--remote', REMOTE);
    if (BRANCH) pullArgs.push('--branch', BRANCH);
    const pullStatus = runScript('hlk-git-pull.mjs', pullArgs);
    // Pull có thể fail nếu không có remote branch — không bắt buộc dừng
    if (pullStatus !== 0) {
      log('warn', 'Pull thất bại hoặc không có remote branch. Tiếp tục commit.');
    } else {
      log('success', 'Pull OK.');
    }
  }

  // Bước 3: Commit — thêm file mới + commit
  const commitArgs = [];
  if (MESSAGE) commitArgs.push('-m', MESSAGE);
  if (!NO_ADD) commitArgs.push('--add');
  const commitStatus = runScript('hlk-git-commit.mjs', commitArgs);

  // 0 = thành công hoặc không có gì commit, >0 = lỗi
  if (commitStatus !== 0) {
    log('error', 'Commit thất bại hoặc bị hủy. Dừng lại.');
    process.exit(1);
  }
  log('success', 'Commit OK.');

  // Bước 4: Push — đẩy lên remote
  if (NO_PUSH) {
    log('info', 'Bỏ qua push (--no-push).');
    process.exit(0);
  }

  const pushArgs = ['--pull'];
  if (BRANCH) pushArgs.push('--branch', BRANCH);
  const pushStatus = runScript('hlk-git-push.mjs', pushArgs);
  if (pushStatus !== 0) {
    log('error', 'Push thất bại. Dừng lại.');
    process.exit(1);
  }
  log('success', 'Push OK.');

  log('info', '');
  log('success', 'Safe sync hoàn thành: doctor → pull → commit → push.');
}

main();
