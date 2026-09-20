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
 *   --no-merge-main       Bỏ qua bước merge vào main (mặc định: tự merge).
 *   --main <name>         Tên branch main (mặc định: main).
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
  runGit,
  gitStatus,
  prompt,
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
let NO_MERGE_MAIN = args.includes('--no-merge-main');
let NO_CI = args.includes('--no-ci');
let REMOTE = 'origin';
let BRANCH = null;
let MAIN_BRANCH = 'main';

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
  } else if (args[i] === '--main' && args[i + 1]) {
    MAIN_BRANCH = args[i + 1];
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

async function ask(question) {
  if (YES) return true;
  return prompt(question);
}

// ---------------------------------------------------------------------------
// Merge branch hiện tại vào main + push main
// ---------------------------------------------------------------------------

async function mergeToMain(featureBranch) {
  if (featureBranch === MAIN_BRANCH) {
    log('info', `Đang ở branch ${MAIN_BRANCH} — không cần merge.`);
    return 0;
  }

  log('info', `Merge ${featureBranch} vào ${MAIN_BRANCH}...`);

  // Kiểm tra working tree sạch trước khi checkout
  const status = gitStatus(CWD);
  if (status.length > 0) {
    log('error', 'Working tree không sạch — không thể checkout main.');
    return 1;
  }

  // Checkout main
  const co = runGit(['checkout', MAIN_BRANCH], { cwd: CWD, stdio: 'inherit' });
  if (co.status !== 0) {
    log('error', `Checkout ${MAIN_BRANCH} thất bại.`);
    return co.status ?? 1;
  }

  // Pull main mới nhất
  const pull = runGit(['pull', '--rebase', REMOTE, MAIN_BRANCH], { cwd: CWD, stdio: 'inherit' });
  if (pull.status !== 0) {
    log('warn', `Pull ${MAIN_BRANCH} thất bại — tiếp tục merge với local.`);
  }

  // Merge feature branch vào main (--no-ff giữ history branch)
  const merge = runGit(['merge', '--no-ff', featureBranch, '-m', `Merge ${featureBranch} into ${MAIN_BRANCH}`], { cwd: CWD, stdio: 'inherit' });
  if (merge.status !== 0) {
    log('error', `Merge ${featureBranch} vào ${MAIN_BRANCH} thất bại.`);
    log('warn', 'Xử lý conflict thủ công, rồi quay lại branch cũ.');
    return merge.status ?? 1;
  }

  // Push main lên remote
  const push = runGit(['push', REMOTE, MAIN_BRANCH], { cwd: CWD, stdio: 'inherit' });
  if (push.status !== 0) {
    log('error', `Push ${MAIN_BRANCH} thất bại.`);
    return push.status ?? 1;
  }

  // Quay lại branch cũ
  const coBack = runGit(['checkout', featureBranch], { cwd: CWD, stdio: 'inherit' });
  if (coBack.status !== 0) {
    log('warn', `Quay lại ${featureBranch} thất bại — đang ở ${MAIN_BRANCH}.`);
  }

  log('success', `Merge ${featureBranch} → ${MAIN_BRANCH} + push thành công.`);
  return 0;
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

  // Bước 3b: CI Check — kiểm tra .githooks + .github + CI equivalents trước push
  if (NO_CI) {
    log('info', 'Bỏ qua CI check (--no-ci).');
  } else {
    log('info', 'Chạy hlk-git-ci-check.mjs...');
    const ciStatus = runScript('hlk-git-ci-check.mjs', []);
    if (ciStatus !== 0) {
      log('error', 'CI check thất bại. Push bị dừng để tránh GitHub Actions lỗi.');
      log('warn', 'Dùng --no-ci để bỏ qua bước này.');
      process.exit(1);
    }
    log('success', 'CI check OK.');
  }

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

  // Bước 5: Merge vào main + push main (mặc định ON)
  if (NO_MERGE_MAIN) {
    log('info', 'Bỏ qua merge vào main (--no-merge-main).');
  } else {
    const currentBranch = getBranch(CWD);
    if (currentBranch === MAIN_BRANCH) {
      log('info', `Đang ở ${MAIN_BRANCH} — không cần merge.`);
    } else if (!(await ask(`Merge ${currentBranch} vào ${MAIN_BRANCH} + push ${MAIN_BRANCH}?`))) {
      log('info', 'Bỏ qua merge vào main.');
    } else {
      const mergeStatus = await mergeToMain(currentBranch);
      if (mergeStatus !== 0) {
        log('error', 'Merge vào main thất bại. Dừng lại.');
        process.exit(1);
      }
    }
  }

  log('info', '');
  log('success', 'Safe sync hoàn thành: doctor → pull → commit → ci-check → push → merge-main.');
}

main();
