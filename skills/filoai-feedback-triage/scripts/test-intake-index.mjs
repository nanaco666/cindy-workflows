#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';

const skillDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const prepare = path.join(skillDir, 'scripts', 'prepare-next-state.mjs');

function run(file, args) {
  return spawnSync(process.execPath, [file, ...args], { encoding: 'utf8' });
}

const root = fs.mkdtempSync(path.join(os.tmpdir(), 'filoai-intake-index-'));
const currentPath = path.join(root, 'current.json');
const updatePath = path.join(root, 'update.json');
const nextPath = path.join(root, 'next.json');
const fingerprint = 'a'.repeat(64);
const current = {
  version: 2,
  mode: 'LIVE',
  reportedDecisionFingerprints: {},
};

function write(file, value) {
  fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, { flag: 'wx', mode: 0o600 });
}

write(currentPath, current);

const valid = {
  reportedDecisionFingerprints: {
    [fingerprint]: {
      decision: 'create',
      reason: 'Windows 桌面端收不到新邮件提醒',
      observedAt: '2026-08-19T01:00:00Z',
      sourceMessageId: 'gmail-1',
      issue: 'OWNER/FRONTEND_REPO#1009',
    },
  },
};
write(updatePath, valid);
const prepared = run(prepare, [currentPath, updatePath, nextPath]);
assert.equal(prepared.status, 0, prepared.stderr);
assert.ok(fs.existsSync(nextPath));
fs.rmSync(nextPath);

for (const [label, decision] of [
  ['missing reason', { ...valid.reportedDecisionFingerprints[fingerprint], reason: '' }],
  ['missing message ID', ({ ...valid.reportedDecisionFingerprints[fingerprint], sourceMessageId: undefined })],
]) {
  const invalidUpdate = path.join(root, `invalid-${label.replace(/\s+/g, '-')}.json`);
  const invalidNext = path.join(root, `invalid-next-${label.replace(/\s+/g, '-')}.json`);
  write(invalidUpdate, { reportedDecisionFingerprints: { [fingerprint]: decision } });
  const rejected = run(prepare, [currentPath, invalidUpdate, invalidNext]);
  assert.notEqual(rejected.status, 0, `${label} unexpectedly succeeded`);
  assert.match(rejected.stderr, /reason|sourceMessageId/, rejected.stderr);
  assert.ok(!fs.existsSync(invalidNext));
}

console.log(JSON.stringify({ ok: true, cases: ['valid-decision', 'missing-reason', 'missing-message-id'] }));
