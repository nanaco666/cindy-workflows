# 可移植的反馈自动化工作流

这个目录打包了三条可协作迁移的 Cindy 工作流：

- `filo-support-replies`：扫描 Gmail（包括 Spam），核验同事回复、产品能力、Issue/PR 和发布状态，在原线程生成标准 Gmail 富文本回复；可在明确授权的策略下自动发送。
- `filoai-feedback-triage`：扫描 Gmail 与 Feishu，先自行诊断短反馈，再查代码、Issue、PR 和发布记录，创建或补充证据充分的 Issue。
- `xiaohongshu-feedback-monitor`：通过用户真实 Chrome Profile 的只读浏览器连接，采集多账号评论、私信和群聊，生成带时间标准化、去重和增量游标的 Markdown 反馈报告。

包内的 Skill、脚本和示例配置均为脱敏模板。不会包含真实账号、OAuth、token、cookie、邮件正文、飞书群 ID、任务 ID、审计 JSONL 或 SQLite 数据库。

## 一键安装

在仓库根目录执行：

```bash
node install.mjs
```

安装器会：

1. 将已选 Skill 安装到目标项目的 `.agents/skills/`；
2. 将脱敏配置复制到 `.cindy/filo-support-automation/`（已存在文件不会覆盖）；
3. 准备本地审计、状态和 SQLite 路径（首次运行时才写入运行数据）；
4. 运行两份配置校验和脱敏检查；
5. 写入定时任务的短 prompt 模板，并输出下一步需要在 Cindy Scheduler 中完成的连接器检查。

默认模式是 `SHADOW` / `draft`。SHADOW 不写 GitHub，draft 不发送邮件。只有完成两轮手工验证并由操作者明确切换，才可改为 LIVE 或 `guarded-auto`。

仅安装小红书工作流（不需要填写 Gmail/Feishu 配置）：

```bash
node install.mjs --workflow xiaohongshu --target /path/to/project --non-interactive
```

安装器会复制 Skill、脱敏配置、账号/状态初始化脚本、定时任务 prompt/spec 和只做结构检查的 preflight 模板。账号槽位默认是禁用的；用户必须在各自的真实 Chrome Profile 中手工登录，再用 Skill 的 `set-account` 完成映射。

指定其他项目目录：

```bash
node install.mjs --target /path/to/project
```

自动化环境可使用 `--non-interactive`，此时必须通过环境变量提供所有必填值；缺失值会直接失败，不会猜测身份或来源。

## 连接器与定时任务

安装器不会伪造或写入 Gmail、Feishu、GitHub 或浏览器凭证，也不会直接修改 Scheduler。请在 Cindy 中连接对应来源，然后用 `templates/schedules/` 下的短 prompt 创建任务：

- `support-replies.txt`
- `feedback-triage.txt`
- `xiaohongshu-feedback-monitor.txt`

创建时使用独立任务、对应工作目录、桌面通知、空闲静默；先暂停新任务，运行两轮 SHADOW，再由维护者确认是否进入 LIVE。不要把配置文件、状态目录或日志提交到仓库。

如果需要安装前置检查，将对应 Skill 的 `scripts/preflight.py` 或 `preflight.mjs` 完整内容交给 Cindy Scheduler 的 `schedule_set_pre_run_hook`；不要在 prompt 里硬编码本机路径，也不要手工伪造 hook 命令。小红书 preflight 只检查本地配置；真实登录态检查必须在 Agent 运行时通过浏览器 MCP 完成。

## 本地文件边界

运行时文件只放在目标项目的 `.cindy/filo-support-automation/` 或 Cindy userData；`.cindy/` 已被仓库忽略。SQLite 只是高效查询索引，JSONL/CAS 状态才是各工作流的事实记录。日志只保留时间、来源、摘要指纹、Issue/PR ID、状态和连接器返回的消息 ID，不保存正文。

## 校验

```bash
node scripts/check-redaction.mjs
node scripts/check-template-sync.mjs
python3 skills/filo-support-replies/scripts/validate_policy.py .cindy/filo-support-automation/support-policy.local.json
node skills/filoai-feedback-triage/scripts/validate-config.mjs .cindy/filo-support-automation/feedback-triage.local.json
```

两份 Skill 的测试位于各自 `tests/`；不需要连接真实服务即可运行纯逻辑测试。
