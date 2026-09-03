# Cindy 更新海报工作流

这条工作流每天检查 Cindy 的正式 GitHub Release，整理完整 Release 区间的 merged PR 数据，生成中英文社区文案、可编辑 HTML 海报和 Chrome 截图。它只把成品交付到本机会话和工作目录，不自动发 X、邮件或其它社区消息。

## 安装与更新

在目标 Cindy 工作目录执行：

```bash
node /path/to/cindy-workflows/install.mjs \
  --workflow cindy-update-poster \
  --target /path/to/cindy-project
```

安装器会写入：

```text
<target>/.agents/skills/cindy-update-poster/SKILL.md
<target>/.cindy/workflows/cindy-update-poster/
```

海报脚本、Skill、配置模板会在重复安装时同步到最新包版本；`config.local.json` 只在不存在时创建，因此不会覆盖本机配置。安装器不会创建线上 Scheduler。

## 本机配置

复制生成的 `config.local.json` 后，至少配置一个背景池目录：

```json
{
  "background_dir": "/absolute/path/to/cindy-backgrounds-resource-pack",
  "chrome": ""
}
```

也可以对单次运行设置环境变量：

```bash
export CINDY_POSTER_BACKGROUND_DIR=/absolute/path/to/cindy-backgrounds-resource-pack
export CINDY_POSTER_CHROME=/absolute/path/to/Google\ Chrome
```

背景池只读取以下两个目录中的 PNG/JPEG/WebP：

```text
<background_dir>/01-used-backgrounds/
<background_dir>/02-historical-variants/
```

`00-index/` 只用于预览索引，永远不会作为海报背景。每次正式发版运行随机选择一张，中英文 HTML 共用同一张；背景池为空时直接失败，不静默回退到固定图片。

## 定时任务怎么写

安装后，在 Cindy Scheduler 中手动创建一个 recurring Agent 任务。可直接参考或复制：

```text
任务名称：Cindy 每日更新海报与文案
任务类型：recurring cron
cron：30 18 * * *
时区：Asia/Shanghai
agentKind：codex
model：当前 Cindy 可用的网关 GPT（填写实际 model）
providerId：当前 Cindy 网关 provider（填写实际 providerId）
思考强度：medium
每次运行：新开独立会话（persistentSession=false）
工作目录：<target>/.cindy/workflows/cindy-update-poster
preRunHook：无；collect.py 无法确认正式 Release 时 fail-closed，不产出成品
silentWhenIdle：true
通知：仅成功成品、配置/采集失败或需要人工决策时通知；desktop=true，feishu=true
公开写入：无
```

完整可复制的 Scheduler prompt 在仓库的 [`templates/schedules/cindy-update-poster.txt`](../../templates/schedules/cindy-update-poster.txt)。核心约束是：

1. 先运行 `python3 collect.py <YYYY-MM-DD>`，只认正式公开 Release；Beta、canary、prerelease、draft 一律排除。
2. 以“前一个正式 Release → 当前 Release”的提交区间统计完整 merged PR，features、fixes、contributors 不得直接抄 Release notes 的精选数字。
3. Release notes 的功能主题按 Release 顺序精选；完整区间真实存在的修复必须进入独立 `FIXED / 问题修复` 模块，即使 Release notes 写 `fixes: 0`。
4. 中文文案以标题和用户场景开头；英文文案先参考 `@Cindy_Updates` 的近期帖子，保持“版本发布句 → 4–6 条短亮点 → 完整统计 → Release URL”的固定节奏。最终回复必须内联完整中英文文案。
5. 先生成 HTML，再用 Chrome full-page 截图；不要先调用 GPT ImageGen，也不要用 Pillow 拼图。

## 手动运行

从安装后的工作目录执行：

```bash
cd <target>/.cindy/workflows/cindy-update-poster
python3 collect.py 2026-09-03
python3 poster.py content/<day_id>.json --html-only
python3 poster.py content/<day_id>.json
```

通常由 Agent 根据采集结果编辑 `content/<day_id>.json` 后再运行后两条命令。输出为：

```text
out/html/<day_id>-cn.html
out/html/<day_id>-en.html
out/posters/cindy-daily-<day_id>-html-cn.png
out/posters/cindy-daily-<day_id>-html-en.png
```

HTML 是自包含文件：官方 `assets/brand/std-white.png` 会按固定 SHA-256 校验并内嵌，背景图也会内嵌。页面宽度为 1240px，高度随文字和模块内容自然增长；Chrome 使用 full-page 截图，背景从顶部锚定（`object-position: center top`），避免人物头部被居中裁掉。

## 交付前检查

```bash
python3 -m py_compile collect.py poster.py html_poster.py capture_poster.py pose_library.py
node /path/to/cindy-workflows/scripts/check-package.mjs
```

还要人工确认：Release URL 和版本正确、统计来自完整区间、中英文没有串语、没有空模块或文字溢出、文字不遮挡人物脸/眼睛/手/耳环/道具/黑猫、截图高度不是被强制固定为 1754px。
