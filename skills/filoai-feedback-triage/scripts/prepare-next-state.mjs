#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const [currentArg, updateArg, outputArg] = process.argv.slice(2);

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

if (!currentArg || !updateArg || !outputArg) {
  fail('usage: prepare-next-state.mjs <current-state.json> <run-update.json> <next-state.json>');
}

function readJson(file, label) {
  try {
    return JSON.parse(fs.readFileSync(path.resolve(file), 'utf8'));
  } catch (error) {
    fail(`${label} is not valid JSON: ${error.message}`);
  }
}

function requireObject(value, label) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    fail(`${label} must be an object`);
  }
}

function appendUnique(current, additions, label) {
  if (!Array.isArray(current) || !Array.isArray(additions)) fail(`${label} must be arrays`);
  return [...new Set([...current, ...additions])];
}

const current = readJson(currentArg, 'current state');
const update = readJson(updateArg, 'run update');
requireObject(current, 'current state');
requireObject(update, 'run update');

const allowedUpdateKeys = new Set([
  'append',
  'reportedDecisionFingerprints',
  'gmailWatermarkTime',
  'feishuWatermarkPosition',
  'feishuWatermarkMessageId',
  'feishuWatermarkTime',
  'lastSuccessfulScanAt',
  'lastEffectiveAdditionAt',
  'lastRun',
]);
for (const key of Object.keys(update)) {
  if (!allowedUpdateKeys.has(key)) fail(`unsupported run-update field: ${key}`);
}

const append = update.append ?? {};
requireObject(append, 'run update.append');
const appendableFields = [
  'processedGmailMessageIds',
  'gmailContentFingerprints',
  'processedFeishuMessageIds',
  'processedFeishuThreadIds',
  'feishuContentFingerprints',
  'proposedActions',
];
for (const key of Object.keys(append)) {
  if (!appendableFields.includes(key)) fail(`unsupported append field: ${key}`);
}

const next = structuredClone(current);
for (const key of appendableFields) {
  if (key in append) next[key] = appendUnique(current[key], append[key], key);
}

if (update.reportedDecisionFingerprints !== undefined) {
  requireObject(update.reportedDecisionFingerprints, 'run update.reportedDecisionFingerprints');
  for (const [fingerprint, decision] of Object.entries(update.reportedDecisionFingerprints)) {
    if (fingerprint in current.reportedDecisionFingerprints) continue;
    requireObject(decision, `run update.reportedDecisionFingerprints.${fingerprint}`);
    if (!['create', 'supplement', 'no-register', 'await-release', 'human-review'].includes(decision.decision)) {
      fail(`新增决策 ${fingerprint} 的 decision 非法`);
    }
    if (typeof decision.reason !== 'string' || decision.reason.trim() === '') {
      fail(`新增决策 ${fingerprint} 缺少可查询的问题摘要 reason`);
    }
    if (typeof decision.observedAt !== 'string' || Number.isNaN(Date.parse(decision.observedAt))) {
      fail(`新增决策 ${fingerprint} 缺少有效 observedAt`);
    }
    const hasMessageId = typeof decision.sourceMessageId === 'string' && decision.sourceMessageId !== ''
      || Array.isArray(decision.sourceMessageIds) && decision.sourceMessageIds.length > 0;
    if (!hasMessageId) fail(`新增决策 ${fingerprint} 缺少 sourceMessageId/sourceMessageIds`);
  }
  next.reportedDecisionFingerprints = {
    ...current.reportedDecisionFingerprints,
    ...update.reportedDecisionFingerprints,
  };
}

for (const key of [
  'gmailWatermarkTime',
  'feishuWatermarkPosition',
  'feishuWatermarkMessageId',
  'feishuWatermarkTime',
  'lastSuccessfulScanAt',
  'lastEffectiveAdditionAt',
  'lastRun',
]) {
  if (key in update) next[key] = update[key];
}

const output = path.resolve(outputArg);
const serialized = `${JSON.stringify(next, null, 2)}\n`;
JSON.parse(serialized);
fs.writeFileSync(output, serialized, { flag: 'wx', mode: 0o600 });
console.log(`PREPARED: ${output}`);
