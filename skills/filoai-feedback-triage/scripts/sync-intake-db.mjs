#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const usage = 'usage: sync-intake-db.mjs <config.local.json> [state.json]';

function expandHome(value) {
  if (value === '~') return os.homedir();
  if (value.startsWith('~/')) return path.join(os.homedir(), value.slice(2));
  return path.resolve(value);
}

function fail(error) {
  console.error(`ERROR: ${error?.message ?? String(error)}`);
  process.exit(1);
}

try {
  const [configArg, stateArg] = process.argv.slice(2);
  if (!configArg) throw new Error(usage);
  const config = JSON.parse(fs.readFileSync(path.resolve(configArg), 'utf8'));
  const database = config.insights?.databasePath;
  if (typeof database !== 'string' || database === '') {
    throw new Error('config.insights.databasePath is required');
  }
  const selectedState = stateArg ?? (
    config.mode === 'SHADOW' ? config.state.shadowFile : config.state.liveFile
  );
  if (typeof selectedState !== 'string' || selectedState === '') throw new Error('selected state path is missing');

  const skillDir = process.env.CINDY_SUPPORT_SKILL_DIR
    ? path.resolve(process.env.CINDY_SUPPORT_SKILL_DIR)
    : path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'filo-support-replies');
  const helper = path.join(skillDir, 'scripts', 'intake_db.py');
  fs.accessSync(helper, fs.constants.R_OK);
  const output = execFileSync('python3', [
    helper,
    path.resolve(expandHome(database)),
    'import-feedback-state',
    path.resolve(expandHome(selectedState)),
  ], { encoding: 'utf8', timeout: 30_000, maxBuffer: 1024 * 1024 });
  process.stdout.write(output);
} catch (error) {
  fail(error);
}
