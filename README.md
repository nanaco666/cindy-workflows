# 可移植的 Cindy 多工作流

这个仓库集中保存可协作迁移的 Cindy 工作流。每条工作流都包含自己的 Skill、脚本、模板和测试；运行态配置、连接器凭证、审计日志、SQLite 数据库和报告只保留在安装目标的 `.cindy/` 中，不进入仓库。

当前包含五条工作流：

- `filo-support-replies`：扫描 Gmail（包括 Spam），检查同事是否已回复、产品能力、Issue/PR 和发布版本，在原线程创建标准 Gmail 富文本回复草稿，并按本地策略决定是否自动发送。
- `filoai-feedback-triage`：扫描 Gmail 与 Feishu，先诊断短反馈，再核对产品、代码、Issue、PR 和发布记录，创建或补充证据充分的 Bug/Feature 工单。
- `cindy-update-poster`：生成 Cindy 日报海报与中英文文案。
- `model-comparison-poster`：从官方模型资料和配置的目录地址核验模型能力/价格，生成中英文对比海报、HTML、PNG 和社媒文案。
- `xiaohongshu-feedback-monitor`：通过用户自己的 Chrome Profile 只读采集小红书评论、私信和群聊，生成增量反馈报告。

## 一键安装全部工作流

在目标 Cindy 工作目录执行：

```bash
git clone https://github.com/nanaco666/cindy-workflows.git
cd cindy-workflows
node install.mjs --workflow all --target /path/to/cindy-project
```

不传 `--workflow` 时默认也是 `all`。默认是模板模式：只复制 Skill、脚本、配置模板和定时任务模板，不创建或修改线上 Scheduler，不写入 Gmail、Feishu、GitHub 或浏览器凭证。需要在安装过程中交互填写本机配置时，显式加 `--interactive`。

如果只需要一条工作流，可使用以下名称或别名：

```bash
node install.mjs --workflow filo-support-replies --target /path/to/cindy-project
node install.mjs --workflow filoai-feedback-triage --target /path/to/cindy-project
node install.mjs --workflow cindy-update-poster --target /path/to/cindy-project
node install.mjs --workflow model-comparison-poster --target /path/to/cindy-project
node install.mjs --workflow xiaohongshu-feedback-monitor --target /path/to/cindy-project
```

也支持别名：`support`、`triage`、`poster`、`model`、`xiaohongshu`。`--non-interactive` 会保留脱敏占位配置，方便在 CI 或批量安装中先落盘，之后再在本机补齐连接器账号、仓库和水位信息。

安装后：

1. Skill 位于目标目录的 `.agents/skills/`；
2. 回复与开单工作流的本地配置、状态、审计和 SQLite 索引位于 `.cindy/filo-support-automation/`；
3. 海报与小红书工作流的本地目录位于 `.cindy/workflows/<workflow>/`；
4. 使用对应目录里的 `*.txt`（以及小红书的 `*.yaml`）创建独立、默认暂停的 recurring Scheduler 任务；
5. 在 Cindy 中连接该工作流需要的 Gmail、XD Feishu、GitHub 或浏览器连接器后，再运行 preflight 和 Skill 自带检查。

模型对比海报工作流的资源和地址都由安装者配置：`source_urls` 填官方文档/定价页，`catalog_url` 可选，`hero_image`/`asset_dir` 只填当前机器上有授权的资源路径；留空即可生成无外部图片依赖的表格海报。

## 安全与数据边界

公开包内不包含真实账号、OAuth、Token、Cookie、飞书群 ID、Scheduler ID、客户正文、审计 JSONL、SQLite 数据库或本机绝对路径。`.cindy/` 已加入目标项目的 `.gitignore`。公开模板只描述字段和流程，真实身份与运行态数据由安装者在本机配置。

## 校验

```bash
node scripts/check-redaction.mjs
node scripts/check-template-sync.mjs
node scripts/check-package.mjs
python3 /path/to/skill-creator/scripts/quick_validate.py skills/filo-support-replies
python3 /path/to/skill-creator/scripts/quick_validate.py skills/filoai-feedback-triage
python3 /path/to/skill-creator/scripts/quick_validate.py skills/cindy-update-poster
python3 /path/to/skill-creator/scripts/quick_validate.py skills/model-comparison-poster
python3 /path/to/skill-creator/scripts/quick_validate.py skills/xiaohongshu-feedback-monitor
```

各工作流的纯逻辑测试都不需要连接真实服务；请按对应 Skill 目录中的测试说明运行。

## License

MIT；随包品牌和第三方资源仍以其各自授权为准。
