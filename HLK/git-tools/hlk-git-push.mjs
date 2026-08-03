#!/usr/bin/env node
/**
 * hlk-git-push.mjs
 * =================
 * Push an toàn: kiểm tra divergence, set upstream, không force.
 *
 * Cách dùng:
 *   node HLK/git-tools/hlk-git-push.mjs [--branch main] [--yes]
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

  const branch = BRANCH || getBranch(CWD);
  if (!branch) {
    log('error', 'Không xác định được branch.');
    process.exit(1);
  }
  log('info', `Branch: ${branch}`);

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

  // Kiểm tra divergence
  const tracking = getTrackingBranch(CWD) || `origin/${branch}`;
  const r = runGit(['rev-list', '--left-right', '--count', `${tracking}...HEAD`], { cwd: CWD });
  if (r.status === 0) {
    const match = r.stdout.match(/(\d+)\s+(\d+)/);
    if (match) {
      const behind = parseInt(match[1], 10);
      const ahead = parseInt(match[2], 10);
      if (behind > 0 && ahead > 0) {
        log('error', `Branch diverged: ${behind} behind, ${ahead} ahead so với ${tracking}.`);
        log('warn', 'Cần pull/merge trước khi push.');
        if (await ask('Bạn có muốn pull --rebase trước khi push?')) {
          const pull = runGit(['pull', '--rebase', 'origin', branch], { cwd: CWD, stdio: 'inherit' });
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
        if (await ask('Pull trước khi push?')) {
          const pull = runGit(['pull', '--rebase', 'origin', branch], { cwd: CWD, stdio: 'inherit' });
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

  return { branch };
}

// ---------------------------------------------------------------------------
// Push
// ---------------------------------------------------------------------------

async function main() {
  log('info', '=== HLK Git Push ===');

  const { branch } = await prePushChecks();

  const tracking = getTrackingBranch(CWD);
  const expectedUpstream = `origin/${branch}`;
  let pushArgs = ['push', 'origin', branch];

  if (!tracking || tracking !== expectedUpstream) {
    pushArgs = ['push', '-u', 'origin', branch];
    log('info', `Sẽ set upstream ${expectedUpstream}.`);
  }

  if (!YES) {
    const ok = await ask(`Push branch ${branch} lên origin?`);
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

  log('success', `Push ${branch} thành công.`);
}

main();
