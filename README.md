# 可移植的 Cindy 工作流

这个仓库提供可脱敏安装的 Cindy 工作流：

- `cindy-update-poster`：生成 Cindy 日报海报与中英文文案。
- `xiaohongshu-feedback-monitor`：通过用户真实 Chrome Profile 的只读浏览器连接，采集多账号评论、私信和群聊，生成增量反馈报告。

包内 Skill、脚本和示例配置均为脱敏模板，不包含真实账号、Cookie、Token、报告、Scheduler ID 或机器状态。

## 一键安装

在 Cindy 工作目录执行：

```bash
git clone https://github.com/nanaco666/cindy-workflows.git
cd cindy-workflows
node install.mjs --workflow cindy-update-poster --target /path/to/project
```

安装器不会创建或修改线上 Scheduler，也不会写入凭证；它只复制 Skill、工作流脚本、本地配置模板并执行包校验。

只安装小红书巡检：

```bash
node install.mjs --workflow xiaohongshu --target /path/to/project --non-interactive
```

安装器会：

1. 将 Skill 安装到目标项目的 `.agents/skills/`；
2. 创建 `.cindy/workflows/xiaohongshu-feedback-monitor/`；
3. 初始化三个禁用的账号槽位、增量状态和报告目录；
4. 写入定时任务 prompt、YAML spec 和本地 preflight 模板；
5. 运行脱敏检查和模板同步检查。

然后在 Cindy 中连接浏览器 MCP，使用独立 Chrome Profile 手工登录每个账号，再按 Skill 的 `set-account` 命令完成映射。登录态只保存在用户自己的 Chrome Profile 中。

## 小红书定时任务

安装器不会自动创建 Scheduler 记录。使用以下文件创建一条暂停的 recurring agent schedule：

- `templates/schedules/xiaohongshu-feedback-monitor.txt`
- `templates/schedules/xiaohongshu-feedback-monitor.yaml`

默认建议每天 `10:00`、时区 `Asia/Shanghai`，空闲静默、异常或有新反馈时通知。需要前置检查时，把安装后的 `preflight.py` 内容交给 Cindy Scheduler 的 `schedule_set_pre_run_hook`，不要手工修改 Scheduler 数据库。

小红书工作流的边界：

- 评论、私信和群聊采集：依赖 Cindy 浏览器 MCP / Chrome DevTools 附着。
- 登录态：由真实 Chrome Profile 持有，不由 MCP 保存。
- 时间解析、去重、增量状态和报告：由本地 Python 脚本完成，不依赖 MCP。
- 默认只读：不回复、点赞、删除、标记已处理、发布或修改账号设置。

## Cindy 日报海报

```bash
node install.mjs --workflow cindy-update-poster --target /path/to/project
```

默认配置和定时任务模板见 `templates/config/cindy-update-poster.example.json` 与 `templates/schedules/cindy-update-poster.txt`。

## 校验

```bash
node scripts/check-redaction.mjs
node scripts/check-template-sync.mjs
node scripts/check-package.mjs
python3 '/path/to/skill-creator/scripts/quick_validate.py' skills/xiaohongshu-feedback-monitor
```

## License

MIT；随包品牌和第三方资源仍以其各自授权为准。
