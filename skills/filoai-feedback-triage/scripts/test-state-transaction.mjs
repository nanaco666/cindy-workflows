#!/usr/bin/env node
import assert from 'node:assert/strict';
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { spawnSync } from 'node:child_process';

const skillDir = path.resolve(path.dirname(new URL(import.meta.url).pathname), '..');
const saver = path.join(skillDir, 'scripts', 'save-state.mjs');
const source = process.argv[2];

if (!source) {
  console.error('usage: test-state-transaction.mjs <valid-state.json>');
  process.exit(1);
}

function run(args) {
  return spawnSync(process.execPath, [saver, ...args], { encoding: 'utf8' });
}

function requireSuccess(result, label) {
  assert.equal(result.status, 0, `${label}: ${result.stderr}`);
}

function requireFailure(result, pattern, label) {
  assert.notEqual(result.status, 0, `${label}: unexpectedly succeeded`);
  assert.match(result.stderr, pattern, `${label}: ${result.stderr}`);
}

const fixture = JSON.parse(fs.readFileSync(source, 'utf8'));
const testRoot = fs.mkdtempSync(path.join(os.tmpdir(), 'filoai-state-transaction-'));
const target = path.join(testRoot, 'state.json');
const nextFile = path.join(testRoot, 'next.json');
fs.writeFileSync(target, `${JSON.stringify(fixture, null, 2)}\n`, { mode: 0o600 });

const hashResult = run(['--current-sha256', target]);
requireSuccess(hashResult, 'current hash');
const originalHash = hashResult.stdout.trim();
assert.match(originalHash, /^[a-f0-9]{64}$/);

const normal = structuredClone(fixture);
normal.gmailWatermarkTime = new Date(Date.parse(fixture.gmailWatermarkTime) + 1000).toISOString();
normal.lastSuccessfulScanAt = new Date(Math.max(Date.parse(fixture.lastSuccessfulScanAt ?? 0) + 1000, Date.parse(normal.gmailWatermarkTime))).toISOString();
normal.lastRun = structuredClone(fixture.lastRun) ?? {
  mode: fixture.mode,
  startedAt: normal.gmailWatermarkTime,
  finishedAt: normal.lastSuccessfulScanAt,
  scanWindows: { gmail: {} },
  counts: {},
  actions: [],
  limits: {},
  failures: [],
};
normal.lastRun.scanWindows ??= {};
normal.lastRun.scanWindows.gmail ??= {};
normal.lastRun.engineeringCandidateFingerprints = [];
normal.lastRun.startedAt = normal.gmailWatermarkTime;
normal.lastRun.finishedAt = normal.lastSuccessfulScanAt;
normal.lastRun.scanWindows.gmail.to = normal.gmailWatermarkTime;
normal.lastRun.scanWindows.gmail.watermarkAdvancedTo = normal.gmailWatermarkTime;
fs.writeFileSync(nextFile, `${JSON.stringify(normal, null, 2)}\n`);
const normalResult = run([target, nextFile, originalHash]);
requireSuccess(normalResult, 'normal save');
assert.equal(fs.readFileSync(target).at(-1), 10, 'saved state must end with a real newline');
JSON.parse(fs.readFileSync(target, 'utf8'));

const invalidFile = path.join(testRoot, 'invalid.json');
fs.writeFileSync(invalidFile, `${JSON.stringify(normal)}\\n`);
const currentHashResult = run(['--current-sha256', target]);
requireSuccess(currentHashResult, 'hash after normal save');
const currentHash = currentHashResult.stdout.trim();
requireFailure(run([target, invalidFile, currentHash]), /not valid JSON/, 'invalid JSON');

const rollback = structuredClone(normal);
rollback.gmailWatermarkTime = fixture.gmailWatermarkTime;
rollback.lastRun.scanWindows.gmail.watermarkAdvancedTo = rollback.gmailWatermarkTime;
const rollbackFile = path.join(testRoot, 'rollback.json');
fs.writeFileSync(rollbackFile, `${JSON.stringify(rollback, null, 2)}\n`);
requireFailure(run([target, rollbackFile, currentHash]), /must not move backward/, 'watermark rollback');

requireFailure(run([target, nextFile, originalHash]), /changed concurrently/, 'stale hash');

fs.writeFileSync(`${target}.lock`, '{}\n', { flag: 'wx', mode: 0o600 });
requireFailure(run([target, nextFile, currentHash]), /EEXIST/, 'existing lock');
fs.unlinkSync(`${target}.lock`);

console.log(JSON.stringify({ ok: true, cases: ['normal', 'invalid-json', 'watermark-rollback', 'stale-hash', 'existing-lock'], testRoot }));
