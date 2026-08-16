#!/usr/bin/env node
/**
 * hlk-git-pull.mjs
 * =================
 * Pull source từ remote an toàn: kiểm tra working tree sạch, stash nếu cần,
 * pull --rebase, xử lý conflict.
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-pull.mjs [options]
 *
 * Options:
 *   --remote <name>       Remote name (mặc định: origin).
 *   --branch <name>       Branch name (mặc định: branch hiện tại).
 *   --rebase              Dùng pull --rebase (mặc định).
 *   --merge               Dùng pull --no-rebase (merge thường).
 *   --stash               Stash thay đổi trước khi pull, pop sau.
 *   --yes                 Không hỏi xác nhận.
 */

import { fileURLToPath } from 'node:url';
import path from 'node:path';
import {
  log,
  runGit,
  isGitRepo,
  getBranch,
  getRemotes,
  getTrackingBranch,
  hasUncommittedChanges,
  gitStatus,
  prompt,
} from './lib/hlk-git-lib.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CWD = process.cwd();

const args = process.argv.slice(2);
let YES = args.includes('--yes');
let REMOTE = 'origin';
let BRANCH = null;
let USE_REBASE = !args.includes('--merge');
let USE_STASH = args.includes('--stash');

for (let i = 0; i < args.length; i++) {
  if (args[i] === '--remote' && args[i + 1]) { REMOTE = args[i + 1]; i++; }
  else if ((args[i] === '-b' || args[i] === '--branch') && args[i + 1]) { BRANCH = args[i + 1]; i++; }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function ask(question) {
  if (YES) return true;
  return prompt(question);
}

// ---------------------------------------------------------------------------
// Kiểm tra trước pull
// ---------------------------------------------------------------------------

async function prePullChecks() {
  if (!isGitRepo(CWD)) {
    log('error', 'Không phải git repo.');
    process.exit(1);
  }

  const localBranch = getBranch(CWD);
  if (!localBranch) {
    log('error', 'Không xác định được branch.');
    process.exit(1);
  }
  const remoteBranch = BRANCH || localBranch;
  log('info', `Branch: ${localBranch}`);
  log('info', `Remote: ${REMOTE}`);
  if (remoteBranch !== localBranch) {
    log('info', `Remote branch: ${remoteBranch}`);
  }

  const remotes = getRemotes(CWD);
  if (!remotes.includes(REMOTE)) {
    log('error', `Remote "${REMOTE}" không tồn tại. Remotes: ${remotes.join(', ') || '(không có)'}`);
    process.exit(1);
  }

  // Kiểm tra working tree có thay đổi không
  const dirty = hasUncommittedChanges(CWD);
  let stashed = false;

  if (dirty) {
    const status = gitStatus(CWD);
    log('warn', `Có ${status.length} thay đổi chưa commit:`);
    for (const s of status.slice(0, 10)) {
      log('info', `  [${s.status}] ${s.filePath}`);
    }
    if (status.length > 10) log('info', `  ... và ${status.length - 10} file nữa.`);

    if (USE_STASH || (await ask('Stash thay đổi trước khi pull? (khuyến nghị)'))) {
      log('info', 'Stash thay đổi...');
      const r = runGit(['stash', 'push', '-u', '-m', 'hlk-git-pull auto-stash'], { cwd: CWD, stdio: 'inherit' });
      if (r.status !== 0) {
        log('error', 'Stash thất bại.');
        process.exit(1);
      }
      stashed = true;
      log('success', 'Đã stash thay đổi.');
    } else if (!(await ask('Pull mặc dù có thay đổi chưa commit? (có thể gây conflict)'))) {
      log('info', 'Hủy pull.');
      process.exit(2);
    }
  }

  return { localBranch, remoteBranch, stashed };
}

// ---------------------------------------------------------------------------
// Pull
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git Pull ===');

  const { localBranch, remoteBranch, stashed } = await prePullChecks();

  // Kiểm tra xem có remote branch không
  const checkRemote = runGit(['ls-remote', '--heads', REMOTE, remoteBranch], { cwd: CWD });
  if (checkRemote.status !== 0 || !checkRemote.stdout.trim()) {
    log('error', `Remote branch "${REMOTE}/${remoteBranch}" không tồn tại.`);
    if (stashed) {
      log('info', 'Pop stash để khôi phục thay đổi...');
      runGit(['stash', 'pop'], { cwd: CWD, stdio: 'inherit' });
    }
    process.exit(1);
  }

  // Pull
  const pullArgs = ['pull'];
  if (USE_REBASE) pullArgs.push('--rebase');
  pullArgs.push(REMOTE, remoteBranch);

  log('info', `Chạy: git ${pullArgs.join(' ')}`);
  const r = runGit(pullArgs, { cwd: CWD, stdio: 'inherit' });

  if (r.status !== 0) {
    log('error', 'Pull thất bại.');
    if (stashed) {
      log('warn', 'Có stash đang chờ. Kiểm tra conflict rồi chạy: git stash pop');
    }
    process.exit(r.status ?? 1);
  }

  log('success', `Pull từ ${REMOTE}/${remoteBranch} thành công.`);

  // Pop stash nếu đã stash
  if (stashed) {
    log('info', 'Pop stash để khôi phục thay đổi...');
    const pop = runGit(['stash', 'pop'], { cwd: CWD, stdio: 'inherit' });
    if (pop.status !== 0) {
      log('warn', 'Stash pop có conflict. Xử lý thủ công: git stash pop');
    } else {
      log('success', 'Đã khôi phục thay đổi từ stash.');
    }
  }
}

main();
