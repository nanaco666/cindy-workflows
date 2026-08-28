#!/usr/bin/env node
import crypto from 'node:crypto';
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

function usage() {
  return [
    'usage:',
    '  save-state.mjs --current-sha256 <target-state.json>',
    '  save-state.mjs <target-state.json> <input-state.json> <expected-current-sha256>'
  ].join('\n');
}

function sha256(value) {
  return crypto.createHash('sha256').update(value).digest('hex');
}

function requireIso(value, label, nullable = false) {
  if (nullable && value === null) return;
  if (typeof value !== 'string' || value === '' || Number.isNaN(Date.parse(value))) {
    throw new Error(`${label} must be an ISO-8601 string${nullable ? ' or null' : ''}`);
  }
}

function requireString(value, label) {
  if (typeof value !== 'string' || value === '') throw new Error(`${label} must be a non-empty string`);
}

function requireArray(value, label) {
  if (!Array.isArray(value)) throw new Error(`${label} must be an array`);
}

function requireUniqueStrings(value, label) {
  requireArray(value, label);
  if (value.some((item) => typeof item !== 'string' || item === '')) {
    throw new Error(`${label} must contain only non-empty strings`);
  }
  if (new Set(value).size !== value.length) throw new Error(`${label} must not contain duplicates`);
}

function requireObject(value, label) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} must be an object`);
  }
}

function requireNonNegativeInteger(value, label) {
  if (!Number.isInteger(value) || value < 0) throw new Error(`${label} must be a non-negative integer`);
}

function validateState(state, label) {
  requireObject(state, label);
  if (state.version !== 2) throw new Error(`${label}.version must be 2`);
  if (!['SHADOW', 'LIVE'].includes(state.mode)) throw new Error(`${label}.mode is invalid`);
  requireIso(state.initializedAt, `${label}.initializedAt`);
  requireIso(state.gmailWatermarkTime, `${label}.gmailWatermarkTime`);
  requireUniqueStrings(state.processedGmailMessageIds, `${label}.processedGmailMessageIds`);
  requireUniqueStrings(state.gmailContentFingerprints, `${label}.gmailContentFingerprints`);
  requireString(state.feishuChatId, `${label}.feishuChatId`);
  requireString(state.feishuWatermarkPosition, `${label}.feishuWatermarkPosition`);
  if (!/^\d+$/.test(state.feishuWatermarkPosition)) {
    throw new Error(`${label}.feishuWatermarkPosition must be a non-negative integer string`);
  }
  requireString(state.feishuWatermarkMessageId, `${label}.feishuWatermarkMessageId`);
  requireIso(state.feishuWatermarkTime, `${label}.feishuWatermarkTime`);
  requireUniqueStrings(state.processedFeishuMessageIds, `${label}.processedFeishuMessageIds`);
  requireUniqueStrings(state.processedFeishuThreadIds, `${label}.processedFeishuThreadIds`);
  requireUniqueStrings(state.feishuContentFingerprints, `${label}.feishuContentFingerprints`);
  requireObject(state.reportedDecisionFingerprints, `${label}.reportedDecisionFingerprints`);
  requireArray(state.proposedActions, `${label}.proposedActions`);
  requireIso(state.lastSuccessfulScanAt, `${label}.lastSuccessfulScanAt`, true);
  requireIso(state.lastEffectiveAdditionAt, `${label}.lastEffectiveAdditionAt`, true);

  if (state.lastRun !== null) {
    requireObject(state.lastRun, `${label}.lastRun`);
    requireIso(state.lastRun.startedAt, `${label}.lastRun.startedAt`);
    requireIso(state.lastRun.finishedAt, `${label}.lastRun.finishedAt`);
    if (state.lastRun.mode !== state.mode) throw new Error(`${label}.lastRun.mode must match state mode`);
    requireObject(state.lastRun.scanWindows, `${label}.lastRun.scanWindows`);
    requireObject(state.lastRun.counts, `${label}.lastRun.counts`);
    requireArray(state.lastRun.actions, `${label}.lastRun.actions`);
    requireObject(state.lastRun.limits, `${label}.lastRun.limits`);
    requireArray(state.lastRun.failures, `${label}.lastRun.failures`);
    for (const [key, value] of Object.entries(state.lastRun.counts)) {
      requireNonNegativeInteger(value, `${label}.lastRun.counts.${key}`);
    }
    for (const [key, value] of Object.entries(state.lastRun.limits)) {
      requireNonNegativeInteger(value, `${label}.lastRun.limits.${key}`);
    }
  }
}

function assertNonDecreasingIso(current, next, label) {
  if (Date.parse(next) < Date.parse(current)) throw new Error(`${label} must not move backward`);
}

function assertNullableIsoTransition(current, next, label) {
  if (current !== null && next === null) throw new Error(`${label} must not be cleared`);
  if (current !== null && next !== null) assertNonDecreasingIso(current, next, label);
}

function validateTransition(current, next) {
  if (next.version !== current.version) throw new Error('state version must not change');
  if (next.mode !== current.mode) throw new Error('state mode must not change during persistence');
  if (next.initializedAt !== current.initializedAt) throw new Error('initializedAt must not change');
  if (next.feishuChatId !== current.feishuChatId) throw new Error('Feishu chat ID must not change');
  assertNonDecreasingIso(current.gmailWatermarkTime, next.gmailWatermarkTime, 'Gmail watermark');

  const currentPosition = BigInt(current.feishuWatermarkPosition);
  const nextPosition = BigInt(next.feishuWatermarkPosition);
  if (nextPosition < currentPosition) throw new Error('Feishu watermark position must not move backward');
  assertNonDecreasingIso(current.feishuWatermarkTime, next.feishuWatermarkTime, 'Feishu watermark time');
  if (nextPosition === currentPosition) {
    if (next.feishuWatermarkMessageId !== current.feishuWatermarkMessageId) {
      throw new Error('Feishu watermark message ID must stay unchanged when position does not advance');
    }
    if (next.feishuWatermarkTime !== current.feishuWatermarkTime) {
      throw new Error('Feishu watermark time must stay unchanged when position does not advance');
    }
  }

  assertNullableIsoTransition(current.lastSuccessfulScanAt, next.lastSuccessfulScanAt, 'lastSuccessfulScanAt');
  assertNullableIsoTransition(current.lastEffectiveAdditionAt, next.lastEffectiveAdditionAt, 'lastEffectiveAdditionAt');

  for (const fingerprint of Object.keys(current.reportedDecisionFingerprints)) {
    if (!(fingerprint in next.reportedDecisionFingerprints)) {
      throw new Error(`reported decision fingerprint must not be removed: ${fingerprint}`);
    }
  }

  requireUniqueStrings(
    next.lastRun?.engineeringCandidateFingerprints,
    'next state.lastRun.engineeringCandidateFingerprints',
  );
  for (const fingerprint of next.lastRun.engineeringCandidateFingerprints) {
    if (!(fingerprint in next.reportedDecisionFingerprints)) {
      throw new Error(`engineering candidate has no persisted decision: ${fingerprint}`);
    }
  }

  if (next.lastRun?.scanWindows?.gmail?.complete === true) {
    if (next.lastRun.scanWindows.gmail.watermarkAdvancedTo !== next.gmailWatermarkTime) {
      throw new Error('complete Gmail scan watermark must match top-level Gmail watermark');
    }
  }
  if (next.lastRun?.scanWindows?.feishu?.complete === true) {
    if (String(next.lastRun.scanWindows.feishu.watermarkAdvancedTo) !== next.feishuWatermarkPosition) {
      throw new Error('complete Feishu scan watermark must match top-level Feishu position');
    }
  }
}

function readStateFile(file, label) {
  const bytes = fs.readFileSync(file);
  let state;
  try {
    state = JSON.parse(bytes.toString('utf8'));
  } catch (error) {
    throw new Error(`${label} is not valid JSON: ${error.message}`);
  }
  validateState(state, label);
  return { bytes, state, hash: sha256(bytes) };
}

function currentHash(targetArg) {
  const target = path.resolve(targetArg);
  const { hash } = readStateFile(target, 'current state');
  process.stdout.write(`${hash}\n`);
}

function saveState(targetArg, inputArg, expectedHash) {
  if (!/^[a-f0-9]{64}$/.test(expectedHash ?? '')) {
    throw new Error('expected current SHA-256 must be 64 lowercase hexadecimal characters');
  }

  const target = path.resolve(targetArg);
  const input = path.resolve(inputArg);
  const lock = `${target}.lock`;
  const temp = `${target}.tmp-${process.pid}-${Date.now()}`;
  let lockDescriptor;
  let tempDescriptor;

  fs.mkdirSync(path.dirname(target), { recursive: true });

  try {
    lockDescriptor = fs.openSync(lock, 'wx', 0o600);
    fs.writeFileSync(lockDescriptor, `${JSON.stringify({ pid: process.pid, startedAt: new Date().toISOString(), target })}\n`);
    fs.fsyncSync(lockDescriptor);

    const current = readStateFile(target, 'current state');
    if (current.hash !== expectedHash) {
      throw new Error(`current state changed concurrently: expected ${expectedHash}, found ${current.hash}`);
    }
    const next = readStateFile(input, 'next state');
    validateTransition(current.state, next.state);

    const serialized = `${JSON.stringify(next.state, null, 2)}\n`;
    JSON.parse(serialized);
    if (!serialized.endsWith('\n') || serialized.endsWith('\\n')) {
      throw new Error('serialized state must end with one real newline');
    }

    tempDescriptor = fs.openSync(temp, 'wx', 0o600);
    fs.writeFileSync(tempDescriptor, serialized, 'utf8');
    fs.fsyncSync(tempDescriptor);
    fs.closeSync(tempDescriptor);
    tempDescriptor = undefined;

    const staged = readStateFile(temp, 'staged state');
    validateTransition(current.state, staged.state);
    const latest = readStateFile(target, 'current state before rename');
    if (latest.hash !== expectedHash) {
      throw new Error(`current state changed before rename: expected ${expectedHash}, found ${latest.hash}`);
    }

    fs.renameSync(temp, target);
    const directoryDescriptor = fs.openSync(path.dirname(target), 'r');
    try {
      fs.fsyncSync(directoryDescriptor);
    } finally {
      fs.closeSync(directoryDescriptor);
    }

    const saved = readStateFile(target, 'saved state');
    validateTransition(current.state, saved.state);
    process.stdout.write(`${JSON.stringify({ ok: true, target, previousSha256: current.hash, savedSha256: saved.hash })}\n`);
  } finally {
    if (tempDescriptor !== undefined) {
      try { fs.closeSync(tempDescriptor); } catch {}
    }
    try { fs.unlinkSync(temp); } catch {}
    if (lockDescriptor !== undefined) {
      try { fs.closeSync(lockDescriptor); } catch {}
      try { fs.unlinkSync(lock); } catch {}
    }
  }
}

try {
  const args = process.argv.slice(2);
  if (args[0] === '--current-sha256' && args.length === 2) {
    currentHash(args[1]);
  } else if (args.length === 3) {
    saveState(args[0], args[1], args[2]);
  } else {
    throw new Error(usage());
  }
} catch (error) {
  console.error(`ERROR: ${error?.message ?? String(error)}`);
  process.exit(1);
}
