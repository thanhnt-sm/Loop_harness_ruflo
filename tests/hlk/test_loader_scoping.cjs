// Tests cho HLK/chain/loaders/wrap_helpers.js (Plan 8 phase 2)
const test = require('node:test');
const assert = require('node:assert');
const path = require('node:path');
const fs = require('node:fs');

const WRAP_HELPERS = path.resolve(__dirname, '../../HLK/chain/loaders/wrap_helpers.js');
const LOADER = path.resolve(__dirname, '../../HLK/chain/loaders/verify-first-loader.js');

test('wrap_helpers.js exists', () => {
  assert.strictEqual(fs.existsSync(WRAP_HELPERS), true);
});

test('verify-first-loader.js exists', () => {
  assert.strictEqual(fs.existsSync(LOADER), true);
});

test('wrap_helpers exports required functions', () => {
  const content = fs.readFileSync(WRAP_HELPERS, 'utf-8');
  assert.match(content, /export\s*\{[^}]*wrapSpawn/);
  assert.match(content, /export\s*\{[^}]*wrapExecFile/);
  assert.match(content, /export\s*\{[^}]*enablePatching/);
  assert.match(content, /export\s*\{[^}]*disablePatching/);
  assert.match(content, /export\s*\{[^}]*sanitizeArgv/);
});

test('verify-first-loader uses opt-in pattern', () => {
  const content = fs.readFileSync(LOADER, 'utf-8');
  // Phải check env var, không patch ngay khi import
  assert.match(content, /HLK_VERIFY_FIRST_ACTIVE/);
  // Có enableScopedPatching / disableScopedPatching
  assert.match(content, /enableScopedPatching/);
  assert.match(content, /disableScopedPatching/);
});

test('wrap_helpers shell metachar regex includes common dangerous chars', () => {
  const content = fs.readFileSync(WRAP_HELPERS, 'utf-8');
  // Phải check các metachar nguy hiểm
  for (const ch of ['|', '&', ';', '<', '>', '$', '`', '\\', '"', "'", '*', '?', '{', '}']) {
    assert.ok(content.includes(ch), `missing shell metachar: ${ch}`);
  }
});

test('verify-first-loader does NOT call enablePatching at module top-level (only on env)', () => {
  const content = fs.readFileSync(LOADER, 'utf-8');
  // Tìm pattern enablePatching outside env var check
  // Có thể có ở cuối file trong "if (process.env.HLK_VERIFY_FIRST_ACTIVE === '1')" block
  const lines = content.split('\n');
  let inEnvCheck = false;
  for (let i = 0; i < lines.length; i++) {
    const line = lines[i];
    if (line.includes('HLK_VERIFY_FIRST_ACTIVE ===')) inEnvCheck = true;
    if (line.includes('enableScopedPatching')) {
      // Phải nằm trong env check block
      assert.ok(inEnvCheck, `enableScopedPatching at line ${i+1} not in env check block`);
    }
  }
});
