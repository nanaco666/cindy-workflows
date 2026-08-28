#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';

const [configArg] = process.argv.slice(2);

function fail(message) {
  console.error(`INVALID: ${message}`);
  process.exit(1);
}

function isObject(value) {
  return value !== null && typeof value === 'object' && !Array.isArray(value);
}

function requireString(value, label) {
  if (typeof value !== 'string' || value.trim() === '') fail(`${label} must be a non-empty string`);
  if (value.includes('REPLACE_WITH_')) fail(`${label} still contains a placeholder`);
}

function requirePositiveInteger(value, label) {
  if (!Number.isInteger(value) || value <= 0) fail(`${label} must be a positive integer`);
}

if (!configArg) fail('usage: validate-config.mjs <config.json>');

const configPath = path.resolve(configArg);
let config;
try {
  config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
} catch (error) {
  fail(`cannot read valid JSON at ${configPath}: ${error.message}`);
}

if (!isObject(config)) fail('root must be an object');
if (config.version !== 2) fail('version must equal 2');
if (!['SHADOW', 'LIVE'].includes(config.mode)) fail('mode must be SHADOW or LIVE');

for (const key of ['schedule', 'sources', 'github', 'state', 'limits']) {
  if (!isObject(config[key])) fail(`${key} must be an object`);
}
if (!isObject(config.sources.gmail) || !isObject(config.sources.feishu)) fail('sources.gmail and sources.feishu must be objects');

requireString(config.schedule.name, 'schedule.name');
requireString(config.schedule.cronExpr, 'schedule.cronExpr');
if (config.schedule.cronExpr.trim().split(/\s+/).length !== 5) fail('schedule.cronExpr must have five fields');
requireString(config.schedule.timezone, 'schedule.timezone');
requireString(config.schedule.agentKind, 'schedule.agentKind');
requireString(config.schedule.model, 'schedule.model');
requireString(config.schedule.effort, 'schedule.effort');
if (config.schedule.silentWhenIdle !== true) fail('schedule.silentWhenIdle must be true');
if (!isObject(config.schedule.notify) || config.schedule.notify.desktop !== true || config.schedule.notify.feishu !== false) {
  fail('schedule.notify must be {desktop:true, feishu:false}');
}

requireString(config.sources.gmail.account, 'sources.gmail.account');
requireString(config.sources.gmail.initialWatermarkTime, 'sources.gmail.initialWatermarkTime');
if (Number.isNaN(Date.parse(config.sources.gmail.initialWatermarkTime))) fail('Gmail watermark must be ISO-8601');
requirePositiveInteger(config.sources.gmail.overlapMinutes, 'sources.gmail.overlapMinutes');
requirePositiveInteger(config.sources.gmail.maxDeepCandidatesPerRun, 'sources.gmail.maxDeepCandidatesPerRun');

requireString(config.sources.feishu.chatName, 'sources.feishu.chatName');
requireString(config.sources.feishu.chatId, 'sources.feishu.chatId');
requireString(config.sources.feishu.initialWatermarkPosition, 'sources.feishu.initialWatermarkPosition');
requireString(config.sources.feishu.initialWatermarkMessageId, 'sources.feishu.initialWatermarkMessageId');
requireString(config.sources.feishu.initialWatermarkTime, 'sources.feishu.initialWatermarkTime');
if (Number.isNaN(Date.parse(config.sources.feishu.initialWatermarkTime))) fail('Feishu watermark time must be ISO-8601');

requireString(config.github.canonicalRepo, 'github.canonicalRepo');
if (!/^[^/\s]+\/[^/\s]+$/.test(config.github.canonicalRepo)) fail('github.canonicalRepo must be owner/repo');
if (!Array.isArray(config.github.relatedRepos)) fail('github.relatedRepos must be an array');
for (const [index, repo] of config.github.relatedRepos.entries()) {
  requireString(repo, `github.relatedRepos[${index}]`);
  if (!/^[^/\s]+\/[^/\s]+$/.test(repo)) fail(`github.relatedRepos[${index}] must be owner/repo`);
}
if (config.github.branchPolicy !== 'remote-default') fail('github.branchPolicy must be remote-default');

requireString(config.state.shadowFile, 'state.shadowFile');
requireString(config.state.liveFile, 'state.liveFile');
if (config.state.shadowFile === config.state.liveFile) fail('shadow and live state files must differ');
requirePositiveInteger(config.state.maxRememberedIds, 'state.maxRememberedIds');
requirePositiveInteger(config.state.maxRememberedFingerprints, 'state.maxRememberedFingerprints');

if (!isObject(config.insights)) fail('insights must be an object');
requireString(config.insights.databasePath, 'insights.databasePath');
if (!config.insights.databasePath.endsWith('.sqlite')) {
  fail('insights.databasePath must end with .sqlite');
}

requirePositiveInteger(config.limits.maxRunMinutes, 'limits.maxRunMinutes');
requirePositiveInteger(config.limits.maxExternalReads, 'limits.maxExternalReads');
requirePositiveInteger(config.limits.maxGithubWrites, 'limits.maxGithubWrites');

const serialized = JSON.stringify(config).toLowerCase();
for (const forbidden of ['password', 'token', 'cookie', 'client_secret', 'refresh_token', 'access_token']) {
  if (serialized.includes(`"${forbidden}"`)) fail(`config must not contain secret field ${forbidden}`);
}

console.log(`VALID: ${configPath} (${config.mode})`);
