#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';

const [configArg, modeArg] = process.argv.slice(2);

function fail(message) {
  console.error(`ERROR: ${message}`);
  process.exit(1);
}

function expandHome(value) {
  if (value === '~') return os.homedir();
  if (value.startsWith('~/')) return path.join(os.homedir(), value.slice(2));
  return path.resolve(value);
}

if (!configArg || !['shadow', 'live'].includes(modeArg)) {
  fail('usage: init-state.mjs <config.json> <shadow|live>');
}

let config;
try {
  config = JSON.parse(fs.readFileSync(path.resolve(configArg), 'utf8'));
} catch (error) {
  fail(`cannot read config: ${error.message}`);
}

const mode = modeArg.toUpperCase();
const target = expandHome(modeArg === 'shadow' ? config?.state?.shadowFile : config?.state?.liveFile);
if (!target) fail('state path is missing');
if (fs.existsSync(target)) fail(`refusing to overwrite existing state: ${target}`);

const now = new Date().toISOString();
const state = {
  version: 2,
  mode,
  initializedAt: now,
  gmailWatermarkTime: config?.sources?.gmail?.initialWatermarkTime,
  processedGmailMessageIds: [],
  gmailContentFingerprints: [],
  feishuChatId: config?.sources?.feishu?.chatId,
  feishuWatermarkPosition: String(config?.sources?.feishu?.initialWatermarkPosition ?? ''),
  feishuWatermarkMessageId: config?.sources?.feishu?.initialWatermarkMessageId,
  feishuWatermarkTime: config?.sources?.feishu?.initialWatermarkTime,
  processedFeishuMessageIds: [],
  processedFeishuThreadIds: [],
  feishuContentFingerprints: [],
  reportedDecisionFingerprints: {},
  proposedActions: [],
  lastSuccessfulScanAt: null,
  lastEffectiveAdditionAt: null,
  lastRun: null
};

for (const [key, value] of Object.entries({
  gmailWatermarkTime: state.gmailWatermarkTime,
  feishuChatId: state.feishuChatId,
  feishuWatermarkPosition: state.feishuWatermarkPosition,
  feishuWatermarkMessageId: state.feishuWatermarkMessageId,
  feishuWatermarkTime: state.feishuWatermarkTime
})) {
  if (typeof value !== 'string' || value === '' || value.includes('REPLACE_WITH_')) fail(`invalid ${key}`);
}

fs.mkdirSync(path.dirname(target), { recursive: true });
const temp = `${target}.tmp-${process.pid}-${Date.now()}`;
try {
  fs.writeFileSync(temp, `${JSON.stringify(state, null, 2)}\n`, { flag: 'wx', mode: 0o600 });
  fs.renameSync(temp, target);
} catch (error) {
  try { fs.unlinkSync(temp); } catch {}
  fail(`cannot initialize state: ${error.message}`);
}

console.log(`INITIALIZED: ${target} (${mode})`);
