#!/usr/bin/env node
import fs from 'node:fs';
import path from 'node:path';
import process from 'node:process';
import { execFileSync } from 'node:child_process';

const packageRoot = path.resolve(import.meta.dirname);
const args = process.argv.slice(2);
const workflow = args[args.indexOf('--workflow') + 1] || 'cindy-update-poster';
const targetArg = args[args.indexOf('--target') + 1];
const target = path.resolve(targetArg || process.cwd());
const nonInteractive = args.includes('--non-interactive');

function fail(message) { console.error(`安装失败：${message}`); process.exit(1); }
function readJson(file) { return JSON.parse(fs.readFileSync(file, 'utf8')); }
function envOr(name, fallback = '') { return process.env[name] || fallback; }
function copyTree(source, destination) {
  if (!fs.existsSync(source)) fail(`安装包缺少目录：${path.relative(packageRoot, source)}`);
  fs.mkdirSync(destination, { recursive: true });
  for (const entry of fs.readdirSync(source, { withFileTypes: true })) {
    if (['.DS_Store', '__pycache__'].includes(entry.name)) continue;
    const from = path.join(source, entry.name);
    const to = path.join(destination, entry.name);
    if (entry.isDirectory()) copyTree(from, to);
    else if (!fs.existsSync(to)) fs.copyFileSync(from, to);
  }
}
function writeNew(file, value) {
  fs.mkdirSync(path.dirname(file), { recursive: true, mode: 0o700 });
  if (!fs.existsSync(file)) fs.writeFileSync(file, `${JSON.stringify(value, null, 2)}\n`, { mode: 0o600 });
}
function protectLocalData() {
  if (!fs.existsSync(path.join(target, '.git'))) return;
  const ignoreFile = path.join(target, '.gitignore');
  const entry = '.cindy/';
  const marker = '# Cindy workflow local data';
  const current = fs.existsSync(ignoreFile) ? fs.readFileSync(ignoreFile, 'utf8') : '';
  if (current.split(/\r?\n/).includes(entry)) return;
  const suffix = current === '' || current.endsWith('\n') ? '' : '\n';
  fs.writeFileSync(ignoreFile, `${current}${suffix}\n${marker}\n${entry}\n`, { mode: 0o644 });
}
function setPosterConfig(config) {
  config.client_repo = envOr('CINDY_POSTER_CLIENT_REPO', config.client_repo);
  config.server_repo = envOr('CINDY_POSTER_SERVER_REPO', config.server_repo);
  config.timezone = envOr('CINDY_POSTER_TIMEZONE', config.timezone);
  config.chrome = envOr('CINDY_POSTER_CHROME', config.chrome);
  return config;
}
function runPackageChecks() {
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-redaction.mjs')], { stdio: 'inherit' });
}

if (!fs.existsSync(target) || !fs.statSync(target).isDirectory()) fail(`目标目录不存在：${target}`);
protectLocalData();

if (workflow === 'xiaohongshu') {
  const skillSource = path.join(packageRoot, 'skills', workflow);
  const configTemplate = path.join(packageRoot, 'templates', 'config', `${workflow}-feedback.example.json`);
  const localRoot = path.join(target, '.cindy', 'workflows', workflow);
  if (!fs.existsSync(configTemplate)) fail(`安装包缺少配置模板：${configTemplate}`);
  copyTree(skillSource, path.join(target, '.agents', 'skills', workflow));
  const config = readJson(configTemplate);
  config.runtime.directory = '.cindy/workflows/xiaohongshu-feedback-monitor';
  config.browser.chromeLocalState = process.platform === 'darwin'
    ? path.join(process.env.HOME || '', 'Library/Application Support/Google/Chrome/Local State')
    : 'REPLACE_WITH_LOCAL_CHROME_STATE_PATH';
  writeNew(path.join(localRoot, 'config.local.json'), config);
  writeNew(path.join(localRoot, 'README.local.txt'), '本目录包含本机账号映射、增量状态和报告。不要提交或分享。\n');
  const manage = path.join(target, '.agents', 'skills', workflow, 'scripts', 'manage_config.py');
  execFileSync('python3', [manage, 'init', '--runtime', localRoot, '--slots', String(config.accountSlots), '--disabled'], { stdio: 'inherit' });
  for (const file of ['xiaohongshu-feedback-monitor.txt', 'xiaohongshu-feedback-monitor.yaml']) {
    fs.copyFileSync(path.join(packageRoot, 'templates', 'schedules', file), path.join(localRoot, file));
  }
  fs.copyFileSync(path.join(skillSource, 'scripts', 'preflight.py'), path.join(localRoot, 'preflight.py'));
  fs.chmodSync(path.join(localRoot, 'preflight.py'), 0o755);
  runPackageChecks();
  console.log(`安装完成：${target}`);
  console.log(`工作流目录：${localRoot}`);
  console.log(`本地配置：${path.join(localRoot, 'config.local.json')}`);
  console.log('下一步：在 Cindy 中连接浏览器 MCP，使用独立 Chrome Profile 登录账号，再按 xiaohongshu-feedback-monitor.txt 创建一个暂停的定时任务。');
  if (nonInteractive) console.log('非交互模式：未写入任何凭证、账号、Scheduler ID 或远程配置。');
  process.exit(0);
}

if (workflow !== 'cindy-update-poster') fail(`未知 workflow：${workflow}`);
const workflowSource = path.join(packageRoot, 'workflows', workflow);
const skillSource = path.join(packageRoot, 'skills', workflow);
const localRoot = path.join(target, '.cindy', 'workflows', workflow);
const configTemplate = path.join(packageRoot, 'templates', 'config', `${workflow}.example.json`);
if (!fs.existsSync(configTemplate)) fail(`安装包缺少配置模板：${configTemplate}`);
copyTree(skillSource, path.join(target, '.agents', 'skills', workflow));
copyTree(workflowSource, localRoot);
const config = setPosterConfig(readJson(configTemplate));
const configPath = path.join(localRoot, 'config.local.json');
writeNew(configPath, config);
fs.mkdirSync(path.join(localRoot, 'content'), { recursive: true, mode: 0o700 });
fs.mkdirSync(path.join(localRoot, 'out'), { recursive: true, mode: 0o700 });
try {
  runPackageChecks();
  execFileSync(process.execPath, [path.join(packageRoot, 'scripts', 'check-package.mjs')], { stdio: 'inherit' });
  execFileSync('python3', ['-m', 'py_compile', 'collect.py', 'poster.py', 'html_poster.py', 'capture_poster.py', 'pose_library.py'], { cwd: localRoot, stdio: 'inherit' });
} catch { fail('工作流包检查未通过'); }
console.log(`安装完成：${target}`);
console.log(`工作流目录：${localRoot}`);
console.log(`本地配置：${configPath}`);
console.log('下一步：在 Cindy 中连接 GitHub，并将 templates/schedules/cindy-update-poster.txt 创建为每天 18:30、Asia/Shanghai 的独立 recurring 任务。不要创建重复任务。');
if (nonInteractive) console.log('非交互模式：未写入任何凭证、账号、Scheduler ID 或远程配置。');
