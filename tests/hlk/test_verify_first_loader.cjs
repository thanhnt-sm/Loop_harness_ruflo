// Tests cho HLK/loaders/verify-first-loader.js
// Node test — chạy với `node --test tests/hlk/test_verify_first_loader.cjs`
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');

// Mirror loader logic: backslash allowed (Windows path)
// Loader đã revise để cho phép \\ (Windows path separator)
const SHELL_METACHARS = /[|&;()<>$`"\'*?{}\n\r\t]/;

function sanitizeArgv(argv) {
  const sanitized = [];
  const warnings = [];
  for (let i = 0; i < argv.length; i++) {
    const arg = argv[i];
    if (typeof arg !== 'string') {
      sanitized.push(String(arg));
      continue;
    }
    if (SHELL_METACHARS.test(arg)) {
      warnings.push(`argv[${i}] chứa shell metachar: ${arg.substring(0, 50)}`);
      sanitized.push(arg.replace(/[|&;()<>$`"\'*?{}\n\r\t]/g, '_'));
    } else {
      sanitized.push(arg);
    }
  }
  return { sanitized, warnings };
}

test('sanitizeArgv — normal args pass through', () => {
  const { sanitized, warnings } = sanitizeArgv(['--live', '--force', 'docs/BRD.md']);
  assert.deepStrictEqual(sanitized, ['--live', '--force', 'docs/BRD.md']);
  assert.strictEqual(warnings.length, 0);
});

test('sanitizeArgv — shell metachars flagged', () => {
  const { warnings } = sanitizeArgv(['--title', 'foo; rm -rf /']);
  assert.strictEqual(warnings.length, 1);
  assert.match(warnings[0], /shell metachar/);
});

test('sanitizeArgv — metachars replaced with underscore', () => {
  const { sanitized } = sanitizeArgv(['title; rm']);
  assert.strictEqual(sanitized[0], 'title_ rm');
});

test('sanitizeArgv — Windows path allowed', () => {
  const { sanitized, warnings } = sanitizeArgv(['C:\\Users\\foo\\BRD.md']);
  assert.strictEqual(warnings.length, 0);
  assert.strictEqual(sanitized[0], 'C:\\Users\\foo\\BRD.md');
});

test('sanitizeArgv — non-string coerced', () => {
  const { sanitized } = sanitizeArgv([123, null, true]);
  assert.strictEqual(sanitized[0], '123');
  assert.strictEqual(sanitized[1], 'null');
  assert.strictEqual(sanitized[2], 'true');
});

test('isVerifyFirstCall — detect via cmd', () => {
  function isVerifyFirstCall(cmd, args) {
    if (typeof cmd !== 'string') return false;
    if (cmd.endsWith('verify_first_cli.py')) return true;
    if (cmd === 'python' || cmd === 'python3' || cmd === 'py') {
      return args && args.some(a => typeof a === 'string' && a.endsWith('verify_first_cli.py'));
    }
    return false;
  }
  assert.strictEqual(isVerifyFirstCall('python', ['scripts/verify_first_cli.py']), true);
  assert.strictEqual(isVerifyFirstCall('python3', ['verify_first_cli.py']), true);
  assert.strictEqual(isVerifyFirstCall('py', ['verify_first_cli.py']), true);
  assert.strictEqual(isVerifyFirstCall('python', ['other.py']), false);
  assert.strictEqual(isVerifyFirstCall('node', ['script.js']), false);
});

test('isVerifyFirstCall — direct path', () => {
  function isVerifyFirstCall(cmd, args) {
    if (typeof cmd !== 'string') return false;
    if (cmd.endsWith('verify_first_cli.py')) return true;
    return false;
  }
  assert.strictEqual(isVerifyFirstCall('scripts/verify_first_cli.py', []), true);
  assert.strictEqual(isVerifyFirstCall('/abs/path/verify_first_cli.py', []), true);
});

test('loader file exists', () => {
  const loaderPath = path.resolve(__dirname, '../../HLK/loaders/verify-first-loader.js');
  assert.strictEqual(fs.existsSync(loaderPath), true);
});

test('wrapper file exists (in safe zone)', () => {
  const wrapperPath = path.resolve(__dirname, '../../.devin/scripts/hlk_wrappers/verify-first-wrapper.mjs');
  assert.strictEqual(fs.existsSync(wrapperPath), true);
});

test('wrapper has usage doc', () => {
  const wrapperPath = path.resolve(__dirname, '../../.devin/scripts/hlk_wrappers/verify-first-wrapper.mjs');
  const content = fs.readFileSync(wrapperPath, 'utf-8');
  assert.match(content, /Usage:/);
  assert.match(content, /process\.platform/);
});
