#!/usr/bin/env node
import fs from 'node:fs';
import os from 'node:os';
import path from 'node:path';
import process from 'node:process';
import { execFileSync } from 'node:child_process';
import readline from 'node:readline/promises';

const packageRoot = path.resolve(import.meta.dirname);
const args = process.argv.slice(2);
const targetArg = args[args.indexOf('--target') + 1];
const target = path.resolve(targetArg || process.cwd());
const nonInteractive = args.includes('--non-interactive');
const rl = nonInteractive ? null : readline.createInterface({ input: process.stdin, output: process.stdout });
const supportTemplate = path.join(packageRoot, 'templates', 'config', 'support-policy.example.json');
const triageTemplate = path.join(packageRoot, 'templates', 'config', 'feedback-triage.example.json');
const localRoot = path.join(target, '.cindy', 'filo-support-automation');

function fail(message) { console.error(`安装失败：${message}`); process.exit(1); }
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function writeNew(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  if (!fs.existsSync(file)) fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
}
function envOr(name, fallback = '') { return process.env[name] || fallback; }
async function ask(label, envName, fallback = '') {
  const value = envOr(envName, fallback);
  if (nonInteractive) return value;
  const input = (await rl.question(`${label}${fallback ? ` [${fallback}]` : ''}: `)).trim();
  return input || value || fallback;
}
function requireValue(value, label) { if (!value || value.startsWith('REPLACE_WITH_')) fail(`${label} 未配置`); return value; }
function protectLocalData() {
  const gitMarker = path.join(target, '.git');
  if (!fs.existsSync(gitMarker)) return;
  const ignoreFile = path.join(target, '.gitignore');
  const marker = '# Cindy Filo support automation local data';
  const entry = '.cindy/filo-support-automation/';
  const current = fs.existsSync(ignoreFile) ? fs.readFileSync(ignoreFile, 'utf8') : '';
  if (current.includes(entry)) return;
  const suffix = current.endsWith('\n') || current === '' ? '' : '\n';
  fs.writeFileSync(ignoreFile, `${current}${suffix}\n${marker}\n${entry}\n`, { mode: 0o644 });
}
function copyTree(source, destination) {
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    if (['.DS_Store', '__pycache__'].includes(entry.name)) continue;
    const from = path.join(source, entry.name); const to = path.join(destination, entry.name);
    if (entry.isDirectory()) copyTree(from, to);
    else if (!fs.existsSync(to)) fs.copyFileSync(from, to);
  }
}
if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) fail(`目标目录不存在：${target}`);
protectLocalData();

const support = readJson(supportTemplate);
support.product = await ask('产品名称', 'CINDY_SUPPORT_PRODUCT', 'Filo');
support.policy_review.reviewed_at = envOr('CINDY_SUPPORT_POLICY_REVIEWED_AT', new Date().toISOString().slice(0, 10));
support.policy_review.reviewed_by = await ask('策略审核人', 'CINDY_SUPPORT_POLICY_REVIEWER');
support.policy_review.source_of_truth = await ask('策略来源（内部路径或文档标识）', 'CINDY_SUPPORT_POLICY_SOURCE');
support.sender.mailbox_account = await ask('Gmail 连接账号', 'CINDY_SUPPORT_GMAIL_ACCOUNT');
support.sender.from_address = await ask('Gmail 发件别名', 'CINDY_SUPPORT_FROM_ADDRESS');
support.sender.cc_addresses = [await ask('必需 CC 地址', 'CINDY_SUPPORT_CC_ADDRESS')];
support.threading.staff_domains = [await ask('同事邮箱域名', 'CINDY_SUPPORT_STAFF_DOMAIN')];
support.bug_tracking.canonical_repo = await ask('默认 GitHub 仓库（owner/repo）', 'CINDY_SUPPORT_FRONTEND_REPOSITORY');
support.bug_tracking.repository_routes.frontend.repository = support.bug_tracking.canonical_repo;
support.bug_tracking.repository_routes.server.repository = await ask('服务端 GitHub 仓库（owner/repo）', 'CINDY_SUPPORT_SERVER_REPOSITORY');
support.automation.audit_log_path = path.join(localRoot, 'support-audit.jsonl');
support.automation.intake_database_path = path.join(localRoot, 'intake.sqlite');
for (const [value, label] of [[support.policy_review.reviewed_by, '策略审核人'], [support.policy_review.source_of_truth, '策略来源'], [support.sender.mailbox_account, 'Gmail 账号'], [support.sender.from_address, '发件别名'], [support.sender.cc_addresses[0], 'CC 地址'], [support.threading.staff_domains[0], '同事域名'], [support.bug_tracking.canonical_repo, '默认仓库'], [support.bug_tracking.repository_routes.server.repository, '服务端仓库']]) requireValue(value, label);

const triage = readJson(triageTemplate);
triage.schedule.model = requireValue(await ask('可用模型标识', 'CINDY_TRIAGE_MODEL'), '模型标识');
triage.schedule.providerId = requireValue(await ask('模型供应商标识', 'CINDY_TRIAGE_PROVIDER_ID'), '模型供应商标识');
triage.sources.gmail.account = support.sender.mailbox_account;
triage.sources.gmail.initialWatermarkTime = requireValue(await ask('Gmail 初始水位（ISO-8601）', 'CINDY_TRIAGE_GMAIL_WATERMARK'), 'Gmail 初始水位');
triage.sources.feishu.chatName = requireValue(await ask('Feishu 群名称', 'CINDY_TRIAGE_FEISHU_CHAT_NAME'), 'Feishu 群名称');
triage.sources.feishu.chatId = requireValue(await ask('Feishu 群 ID', 'CINDY_TRIAGE_FEISHU_CHAT_ID'), 'Feishu 群 ID');
triage.sources.feishu.initialWatermarkPosition = requireValue(await ask('Feishu 初始位置', 'CINDY_TRIAGE_FEISHU_POSITION'), 'Feishu 初始位置');
triage.sources.feishu.initialWatermarkMessageId = requireValue(await ask('Feishu 初始消息 ID', 'CINDY_TRIAGE_FEISHU_MESSAGE_ID'), 'Feishu 初始消息 ID');
triage.sources.feishu.initialWatermarkTime = requireValue(await ask('Feishu 初始水位（ISO-8601）', 'CINDY_TRIAGE_FEISHU_WATERMARK'), 'Feishu 初始水位');
triage.github.canonicalRepo = support.bug_tracking.canonical_repo;
triage.github.relatedRepos = [support.bug_tracking.repository_routes.server.repository];
triage.insights.databasePath = support.automation.intake_database_path;
triage.state.shadowFile = path.join(localRoot, 'state', 'feedback-triage-shadow.json');
triage.state.liveFile = path.join(localRoot, 'state', 'feedback-triage-live.json');
writeNew(path.join(localRoot, 'support-policy.local.json'), support);
writeNew(path.join(localRoot, 'feedback-triage.local.json'), triage);
writeNew(path.join(localRoot, 'README.local.txt'), '本目录包含本机配置、状态、审计和 SQLite 索引。不要提交或分享。\n');

copyTree(path.join(packageRoot, 'skills', 'filo-support-replies'), path.join(target, '.agents', 'skills', 'filo-support-replies'));
copyTree(path.join(packageRoot, 'skills', 'filoai-feedback-triage'), path.join(target, '.agents', 'skills', 'filoai-feedback-triage'));
fs.mkdirSync(path.join(localRoot, 'state'), { recursive: true, mode: 0o700 });
const validateSupport = path.join(target, '.agents', 'skills', 'filo-support-replies', 'scripts', 'validate_policy.py');
const validateTriage = path.join(target, '.agents', 'skills', 'filoai-feedback-triage', 'scripts', 'validate-config.mjs');
try {
  execFileSync('python3', [validateSupport, path.join(localRoot, 'support-policy.local.json')], { stdio: 'inherit' });
  execFileSync(process.execPath, [validateTriage, path.join(localRoot, 'feedback-triage.local.json')], { stdio: 'inherit' });
  const shadowState = path.resolve(triage.state.shadowFile);
  if (!fs.existsSync(shadowState)) {
    execFileSync(process.execPath, [
      path.join(target, '.agents', 'skills', 'filoai-feedback-triage', 'scripts', 'init-state.mjs'),
      path.join(localRoot, 'feedback-triage.local.json'), 'shadow'
    ], { stdio: 'inherit' });
  } else {
    console.log(`复用已有 SHADOW 状态：${shadowState}`);
  }
} catch { fail('配置校验未通过；请修正本地配置后重试'); }
try {
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-redaction.mjs')], { stdio: 'inherit' });
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-template-sync.mjs')], { stdio: 'inherit' });
} catch { fail('工作流包自身的脱敏或模板一致性检查未通过'); }
console.log(`安装完成：${target}`);
console.log('下一步：在 Cindy 中连接 Gmail、XD Feishu、GitHub；将 templates/schedules/*.txt 作为两个 Scheduler prompt，先以 SHADOW/draft 暂停运行两轮。');
rl?.close();
