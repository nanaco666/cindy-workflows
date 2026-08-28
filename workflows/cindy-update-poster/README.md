# Cindy 日报更新海报工作流

这是一个脱敏、可迁移的 Cindy 工作流包。它依赖：

- 本仓库中的 `skills/cindy-update-poster/SKILL.md`；
- 本仓库中的 `workflows/cindy-update-poster/` 脚本与资源；
- Cindy Scheduler 中由使用者创建的 schedule；
- 使用者本机已连接并可用的 GitHub CLI / GitHub 能力；
- 本机 Chrome headless，用于 HTML 截图。

安装器会把脚本和资源放入目标项目的 `.cindy/workflows/cindy-update-poster/`，并把 Skill 放入目标项目的
`.agents/skills/cindy-update-poster/`。运行数据、内容、截图、作者缓存和本地配置均不会进入本仓库。

配置模板不包含 Token、Cookie、OAuth、账号、Scheduler ID 或本机绝对路径。官方 Cindy 字标属于随包固定品牌资源，
其哈希只用于校验，不是凭证。

工作流只生成本地 HTML/PNG/JSON 和社区文案，不自动发布、不发消息、不创建邮件草稿。

安装后，请阅读仓库根目录 README，并在 Cindy Scheduler 中手动创建定时任务；安装器不会擅自创建任务或修改现有任务。
