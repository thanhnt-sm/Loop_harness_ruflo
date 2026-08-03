#!/usr/bin/env node
/**
 * hlk-git-push.mjs
 * =================
 * Push an toàn: kiểm tra divergence, set upstream, không force.
 * Hỗ trợ --pull tự động pull --rebase khi behind.
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-push.mjs [--branch main] [--yes] [--pull]
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
  gitStatus,
  prompt,
} from './lib/hlk-git-lib.mjs';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);
const CWD = process.cwd();

const args = process.argv.slice(2);
let YES = args.includes('--yes');
let BRANCH = null;
let AUTO_PULL = args.includes('--pull');

for (let i = 0; i < args.length; i++) {
  if ((args[i] === '-b' || args[i] === '--branch') && args[i + 1]) {
    BRANCH = args[i + 1];
    i++;
  }
}

// ---------------------------------------------------------------------------
// Helpers
// ---------------------------------------------------------------------------

async function ask(question) {
  if (YES) return true;
  return prompt(question);
}

// ---------------------------------------------------------------------------
// Kiểm tra trước push
// ---------------------------------------------------------------------------

async function prePushChecks() {
  if (!isGitRepo(CWD)) {
    log('error', 'Không phải git repo.');
    process.exit(1);
  }

  const localBranch = getBranch(CWD);
  const remoteBranch = BRANCH || localBranch;
  if (!localBranch) {
    log('error', 'Không xác định được branch.');
    process.exit(1);
  }
  log('info', `Local branch: ${localBranch}`);
  if (remoteBranch !== localBranch) {
    log('info', `Remote branch: ${remoteBranch}`);
  }

  const remotes = getRemotes(CWD);
  if (remotes.length === 0) {
    log('error', 'Không có remote. Không thể push.');
    process.exit(1);
  }
  log('info', `Remotes: ${remotes.join(', ')}`);

  // Không push khi có uncommitted
  const status = gitStatus(CWD);
  if (status.length > 0) {
    log('warn', 'Có thay đổi chưa commit:');
    for (const s of status) {
      log('info', `  [${s.status}] ${s.filePath}`);
    }
    if (!(await ask('Bạn có muốn push mặc dù có thay đổi chưa commit?'))) {
      log('info', 'Hủy push.');
      process.exit(0);
    }
  }

  // Kiểm tra divergence với remote branch mục tiêu
  const expectedUpstream = `origin/${remoteBranch}`;
  const r = runGit(['rev-list', '--left-right', '--count', `${expectedUpstream}...HEAD`], { cwd: CWD });
  if (r.status === 0) {
    const match = r.stdout.match(/(\d+)\s+(\d+)/);
    if (match) {
      const behind = parseInt(match[1], 10);
      const ahead = parseInt(match[2], 10);
      if (behind > 0 && ahead > 0) {
        log('error', `Branch diverged: ${behind} behind, ${ahead} ahead so với ${expectedUpstream}.`);
        log('warn', 'Cần pull/merge trước khi push.');
        if (AUTO_PULL || await ask('Pull --rebase trước khi push?')) {
          const pull = runGit(['pull', '--rebase', 'origin', remoteBranch], { cwd: CWD, stdio: 'inherit' });
          if (pull.status !== 0) {
            log('error', 'Pull --rebase thất bại.');
            process.exit(1);
          }
          log('success', 'Pull --rebase thành công.');
        } else {
          process.exit(1);
        }
      } else if (behind > 0) {
        log('warn', `${behind} commit behind. Nên pull trước khi push.`);
        if (AUTO_PULL || await ask('Pull trước khi push?')) {
          const pull = runGit(['pull', '--rebase', 'origin', remoteBranch], { cwd: CWD, stdio: 'inherit' });
          if (pull.status !== 0) {
            log('error', 'Pull thất bại.');
            process.exit(1);
          }
          log('success', 'Pull thành công.');
        }
      } else if (ahead === 0) {
        log('info', 'Không có gì để push.');
        process.exit(0);
      }
    }
  }

  return { localBranch, remoteBranch };
}

// ---------------------------------------------------------------------------
// Push
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git Push ===');

  const { localBranch, remoteBranch } = await prePushChecks();

  const tracking = getTrackingBranch(CWD);
  const expectedUpstream = `origin/${remoteBranch}`;
  const refspec = localBranch === remoteBranch ? remoteBranch : `${localBranch}:${remoteBranch}`;
  let pushArgs = ['push', 'origin', refspec];

  if (!tracking || tracking !== expectedUpstream) {
    pushArgs = ['push', '-u', 'origin', refspec];
    log('info', `Sẽ set upstream ${expectedUpstream}.`);
  }

  if (!YES) {
    const ok = await ask(`Push ${localBranch} lên origin/${remoteBranch}?`);
    if (!ok) {
      log('info', 'Hủy push.');
      process.exit(0);
    }
  }

  // Đảm bảo không force
  if (args.includes('--force') || args.includes('-f')) {
    log('error', 'HLK Git Push không hỗ trợ --force để tránh rewrite history.');
    process.exit(1);
  }

  const r = runGit(pushArgs, { cwd: CWD, stdio: 'inherit' });
  if (r.status !== 0) {
    log('error', 'Push thất bại.');
    process.exit(r.status ?? 1);
  }

  log('success', `Push lên origin/${remoteBranch} thành công.`);
}

main();
