import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { fileURLToPath } from 'node:url';
import { execFileSync } from 'node:child_process';

const cwd = process.cwd();
const configPath = path.join(cwd, '.cindy', 'filo-support-automation', 'feedback-triage.local.json');

function expandHome(value) {
  if (value === '~') return os.homedir();
  if (value.startsWith('~/')) return path.join(os.homedir(), value.slice(2));
  return path.resolve(cwd, value);
}

function git(args, capture = false) {
  return execFileSync('git', args, {
    cwd,
    encoding: capture ? 'utf8' : undefined,
    stdio: capture ? ['ignore', 'pipe', 'pipe'] : 'ignore',
    timeout: 30_000,
    env: { ...process.env, GIT_TERMINAL_PROMPT: '0', GCM_INTERACTIVE: 'Never' }
  });
}

function isGitHubRemote(value) {
  const remote = value.trim();
  if (/^[^@\s]+@github\.com:[^/\s]+\/[^/\s]+\/?$/i.test(remote)) return true;
  try { return new URL(remote).hostname.toLowerCase() === 'github.com'; } catch { return false; }
}

function requireIso(value, label, nullable = false) {
  if (nullable && value === null) return;
  if (typeof value !== 'string' || value === '' || Number.isNaN(Date.parse(value))) {
    throw new Error(`${label} 不是有效 ISO-8601 时间`);
  }
}

function requireStringArray(value, label) {
  if (!Array.isArray(value) || value.some((item) => typeof item !== 'string' || item === '')) {
    throw new Error(`${label} 不是非空字符串数组`);
  }
  if (new Set(value).size !== value.length) throw new Error(`${label} 存在重复项`);
}

function requireObject(value, label) {
  if (value === null || typeof value !== 'object' || Array.isArray(value)) {
    throw new Error(`${label} 不是对象`);
  }
}

try {
  if (!fs.statSync(cwd).isDirectory()) throw new Error('工作目录不是目录');
  if (git(['rev-parse', '--is-inside-work-tree'], true).trim() !== 'true') throw new Error('工作目录不是 Git 工作树');
  const origin = git(['remote', 'get-url', 'origin'], true);
  if (!isGitHubRemote(origin)) throw new Error('origin 不是 GitHub 远端');
  git(['ls-remote', 'origin']);

  const config = JSON.parse(fs.readFileSync(configPath, 'utf8'));
  if (config.version !== 2) throw new Error('配置 version 不是 2');
  if (!['SHADOW', 'LIVE'].includes(config.mode)) throw new Error('配置 mode 非法');
  if (typeof config.sources?.feishu?.chatId !== 'string' || config.sources.feishu.chatId.startsWith('REPLACE_WITH_')) throw new Error('飞书 chat_id 未配置');
  const insightsDatabase = config.insights?.databasePath;
  if (typeof insightsDatabase !== 'string' || insightsDatabase === '') {
    throw new Error('config.insights.databasePath 缺少');
  }
  const databasePath = expandHome(insightsDatabase);
  fs.mkdirSync(path.dirname(databasePath), { recursive: true });
  fs.accessSync(path.dirname(databasePath), fs.constants.W_OK);
  const supportSkillDir = process.env.CINDY_SUPPORT_SKILL_DIR
    ? path.resolve(process.env.CINDY_SUPPORT_SKILL_DIR)
    : path.resolve(path.dirname(fileURLToPath(import.meta.url)), '..', '..', 'filo-support-replies');
  fs.accessSync(path.join(supportSkillDir, 'scripts', 'intake_db.py'), fs.constants.R_OK);

  const selected = config.mode === 'SHADOW' ? config.state?.shadowFile : config.state?.liveFile;
  if (typeof selected !== 'string' || selected === '') throw new Error('当前模式状态路径缺失');
  const statePath = expandHome(selected);
  const stateText = fs.readFileSync(statePath, 'utf8');
  if (!stateText.endsWith('\n') || stateText.endsWith('\\n')) throw new Error('状态文件结尾不是单个真实换行');
  const state = JSON.parse(stateText);
  if (state.version !== 2 || state.mode !== config.mode) throw new Error('状态 version/mode 与配置不匹配');
  if (state.feishuChatId !== config.sources.feishu.chatId) throw new Error('状态 chat_id 与配置不匹配');
  requireIso(state.initializedAt, '状态 initializedAt');
  requireIso(state.gmailWatermarkTime, '状态 gmailWatermarkTime');
  if (typeof state.feishuWatermarkPosition !== 'string' || !/^\d+$/.test(state.feishuWatermarkPosition)) {
    throw new Error('状态 feishuWatermarkPosition 不是非负整数字符串');
  }
  if (typeof state.feishuWatermarkMessageId !== 'string' || state.feishuWatermarkMessageId === '') {
    throw new Error('状态 feishuWatermarkMessageId 缺失');
  }
  requireIso(state.feishuWatermarkTime, '状态 feishuWatermarkTime');
  requireIso(state.lastSuccessfulScanAt, '状态 lastSuccessfulScanAt', true);
  requireIso(state.lastEffectiveAdditionAt, '状态 lastEffectiveAdditionAt', true);
  for (const key of ['processedGmailMessageIds', 'gmailContentFingerprints', 'processedFeishuMessageIds', 'processedFeishuThreadIds', 'feishuContentFingerprints']) {
    requireStringArray(state[key], `状态 ${key}`);
  }
  requireObject(state.reportedDecisionFingerprints, '状态 reportedDecisionFingerprints');
  if (!Array.isArray(state.proposedActions)) throw new Error('状态 proposedActions 不是数组');
  if (state.processedGmailMessageIds.length > config.state.maxRememberedIds) throw new Error('Gmail 已处理 ID 超过配置上限');
  if (state.processedFeishuMessageIds.length > config.state.maxRememberedIds) throw new Error('飞书已处理 ID 超过配置上限');
  if (state.gmailContentFingerprints.length > config.state.maxRememberedFingerprints) throw new Error('Gmail 指纹超过配置上限');
  if (state.feishuContentFingerprints.length > config.state.maxRememberedFingerprints) throw new Error('飞书指纹超过配置上限');

  const stateDir = path.dirname(statePath);
  const stateBase = path.basename(statePath);
  if (fs.existsSync(`${statePath}.lock`)) throw new Error('检测到状态写入锁；可能有并发运行或上次写入未正常结束');
  const residue = fs.readdirSync(stateDir).filter((name) => name.startsWith(`${stateBase}.tmp-`));
  if (residue.length > 0) throw new Error(`检测到状态临时文件残留：${residue.join(', ')}`);
  fs.mkdirSync(stateDir, { recursive: true });
  const probe = path.join(stateDir, `.write-test-${process.pid}-${Date.now()}`);
  fs.writeFileSync(probe, '', { flag: 'wx', mode: 0o600 });
  fs.unlinkSync(probe);
  process.exit(0);
} catch (error) {
  console.error(`运行前检查失败：${error?.message ?? String(error)}`);
  process.exit(1);
}
