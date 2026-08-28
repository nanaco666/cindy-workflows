# Cindy 更新海报工作流

这个目录提供一个可移植、可脱敏安装的 Cindy 日报工作流：

- `skills/cindy-update-poster/`：完整依赖 Skill，包含事实口径、编辑规则、HTML/CSS 视觉契约和验收规则；
- `workflows/cindy-update-poster/`：采集脚本、内容编辑入口、HTML/CSS 生成器、Chrome 截图器和随包品牌/人物资源；
- `templates/config/cindy-update-poster.example.json`：可复制的本地配置；
- `templates/schedules/cindy-update-poster.txt`：可直接粘贴到 Cindy Scheduler 的定时任务 prompt；
- `scripts/check-redaction.mjs`：脱敏检查；
- `scripts/check-package.mjs`：资源、脚本和安装内容检查；
- `install.mjs`：交互式 / 非交互式一键安装器。

## 一键安装

在 Cindy 工作目录执行：

```bash
git clone https://github.com/nanaco666/cindy-workflows.git
cd cindy-workflows
node install.mjs --workflow cindy-update-poster
```

安装器会：

1. 把 Skill 安装到目标项目的 `.agents/skills/cindy-update-poster/`；
2. 把独立工作流脚本和随包资源复制到目标项目的 `.cindy/workflows/cindy-update-poster/`；
3. 生成本机配置模板，不覆盖已有配置；
4. 将目标项目 `.cindy/` 加入 `.gitignore`（仅 Git 仓库）；
5. 运行脱敏、资源和 Python 语法校验；
6. 输出 Scheduler 配置步骤。

指定目标项目：

```bash
node install.mjs --workflow cindy-update-poster --target /path/to/project
```

自动化安装：

```bash
node install.mjs --workflow cindy-update-poster --target /path/to/project --non-interactive
```

非交互模式只使用环境变量和安全默认值；未提供必要身份信息时直接失败，不猜测仓库或账号。

## 首次配置

安装器会创建：

```text
.cindy/workflows/cindy-update-poster/config.local.json
```

其中只放本机运行参数，不放 Token、Cookie、OAuth、API key 或 Scheduler ID。GitHub CLI 登录由使用者
在 Cindy / 本机环境自行完成；工作流只调用 `gh`，不会收集或保存凭证。

可选环境变量：

- `CINDY_POSTER_CLIENT_REPO`：默认 `makecindy/cindy`；
- `CINDY_POSTER_SERVER_REPO`：默认 `xindong/cindy-server`；
- `CINDY_POSTER_TIMEZONE`：默认 `Asia/Shanghai`；
- `CINDY_POSTER_CHROME`：本机 Chrome 可执行文件路径；不设置时使用 macOS 默认路径；
- `CINDY_POSTER_WORDMARK_SHA256`：固定官方字标校验值，安装器会拒绝修改。

## Scheduler

安装器不会创建或修改定时任务，避免重复任务和错误绑定。安装后在 Cindy Scheduler 创建一条新的
recurring agent schedule：

- 名称：`Cindy 每日更新海报与文案`；
- cron：`30 18 * * *`；
- timezone：`Asia/Shanghai`；
- 独立会话：开启；
- working directory：当前 Cindy 工作目录；
- prompt：复制 `templates/schedules/cindy-update-poster.txt`；
- 默认通知：desktop + Feishu；
- 不调用 GPT ImageGen。

如果已有同名任务，应先检查并更新它，不要创建第二条。定时任务必须先采集正式 Release：当天没有正式
Release 时只汇报无真实发版并结束；Beta、canary、prerelease、draft 和当天 merged PR 都不能替代正式发版。

## 默认输出

每次正式 Release 运行后，输出：

```text
.cindy/workflows/cindy-update-poster/content/<day_id>.json
.cindy/workflows/cindy-update-poster/out/html/<day_id>-cn.html
.cindy/workflows/cindy-update-poster/out/html/<day_id>-en.html
.cindy/workflows/cindy-update-poster/out/posters/cindy-daily-<day_id>-html-cn.png
.cindy/workflows/cindy-update-poster/out/posters/cindy-daily-<day_id>-html-en.png
```

HTML 海报是固定品牌网页结构：全幅 Cindy / 游戏 key-art 背景、约 40–50% 黑色透明层、参考海报位置的
长条文字模块，以及可复用的头部/底部品牌装饰。Chrome headless 截图固定为 `1240 × 1754`。

工作流只生成并落盘内容，不自动发社区、不发消息、不创建邮件草稿、不提交 PR。

## 本地检查

```bash
node scripts/check-redaction.mjs
node scripts/check-package.mjs
node install.mjs --workflow cindy-update-poster --target /tmp/cindy-poster-test --non-interactive
```

## License

MIT，工作流资源的第三方/品牌使用仍以其各自授权为准。
