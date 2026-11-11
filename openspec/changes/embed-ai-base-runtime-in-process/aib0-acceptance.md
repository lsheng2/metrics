# AIB-0 Metrics launcher 验收回执

日期：2026-11-11。结论：AIB-0 第五项验收"现有 launcher 端到端"**通过**。

同时发现 AI Base 侧问题 AIB-F1、AIB-F2（见第 6 节），不影响本项结论。owner 已决定两项在 AIB-0 合入 main 前同轮修复（见第 8 节）。

本回执是 `tasks.md` 0.3 中 Metrics 部分的证据。0.3 要等两项修复完成、Metrics 在新的 HEAD 上重新验收通过、owner 把 AIB-0 合入 main 之后才勾选。

## 1. 被验收的代码

- AI Base worktree：`C:/Users/lsheng2/orca/workspaces/Report_creater_agent/harden-standalone-app-service`
  - 分支 `codex/harden-standalone-app-service`；
  - 实际 HEAD `c13418ff85e69f7df0c5e377f437c138e5559eda`，为回执提交；
  - 实现提交 `3b9b0c7b6f62d166a3ea5828629df955d0cd2d2d`；
  - 归档与 Linux 排序提交 `d695ae4d201cf0ffba66e58c42750d9e2970ee5d`；
  - 运行前后 `git status --porcelain` 都为空。
- Metrics：分支 `lsheng2/redesign-modern-dashboard-ui`，HEAD `d86c97bd76da5381ee9d78c3a0daa1af43dc8e6d`，launcher 未作修改。

## 2. 命令

```powershell
$env:METRICS_JIRA_SERVER_URL = 'https://tracker.example.test'
$env:METRICS_JIRA_AUTH_MODE = 'server_pat'
$env:METRICS_JIRA_API_TOKEN = 'synthetic-only-token'
pwsh -NoProfile -File .\scripts\e2e_dashboard_ai_stack.ps1 -AiBaseWorkspace "C:\Users\lsheng2\orca\workspaces\Report_creater_agent\harden-standalone-app-service" -SkipJiraSync
```

- 停止命令：同一脚本加 `-Action stop -AiBaseWorkspace <同上>`。
- 采用 `pwsh -NoProfile -File` 方式调用，原因是 launcher 的过期进程规则按命令行文本匹配；内联调用时，调用方 shell 自己就会被匹配并停止。
- 时间线：
  - 10:46:38 启动；
  - 10:49:03 输出 ready，用时约 145 s，其中 AI Base 启动 13.9 s；
  - 10:53:55 停止。

## 3. 与回执命令的偏离

| # | 偏离 | 理由 | 影响 |
| --- | --- | --- | --- |
| 1 | 加 `-SkipJiraSync` | 本机没有 Jira 凭据，Jira 同步也不属于 AIB-0 范围 | 使用快照中已有的 durable 数据 |
| 2 | 设置 3 个合成 Jira 环境变量（`.test` 域名无法解析，值不是 secret） | 绕过 Metrics 问题 F-a | 不产生网络访问 |
| 3 | 从主 checkout 只读复制 Grafana Infinity 4.0.0 插件到本 worktree 的 `state\grafana\data\plugins\` | 绕过 Metrics 问题 F-b | 插件副本已在 teardown 中删除 |
| 4 | 启动前用 SQLite backup API 从主 checkout 只读生成数据库快照，迁移和种子数据只写入副本 | 不改动主 checkout 的数据 | 无 |
| 5 | 本 worktree 的 `.venv` 临时 junction 到已有的 app-venv（CPython 3.13.7） | 沿用既有安排 | junction 已在 teardown 中删除 |

## 4. 隔离与进程来源

- **启动前预检**：
  - 过期进程规则命中 0 个；
  - AI Base 端口段 48300–48319、48130–48149、1530–1534 都没有监听；
  - AI Base profile 状态文件不存在。
- **端口与实例**：Metrics 实例 `default-f3fd9d9ad3`，Django 8002、Grafana 3051；AI Base backend 48300、frontend 48310，`portMode=fixed`。
- **AI Base 状态文件**：`repoRoot` 是被验收的 worktree，`startup=ready`。
- **进程树**：从状态文件记录的根 PID 展开，每个监听端口的进程都在对应的树内。
  - AI Base backend：被验收 worktree 的 `.venv\Scripts\python.exe -m uvicorn app.main:app`，端口 48300。
  - AI Base frontend：被验收 worktree 中 `apps\desktop` 的 vite，端口 48310。
  - Django：本仓库 `.venv` 启动的开发服务器，端口 8002。
  - Grafana：使用本仓库 `state` 下的配置；Infinity 插件进程来自第 3 节第 3 项的副本。
- **launcher 进程清点审计**：`dashboard_django=2`、`dashboard_grafana=1`、`grafana_plugins=2`、`ai_base=11`，没有发现过期进程。

## 5. 结果

- launcher 以 0 退出。
- **boot log 审计**：dashboard-start、ai-base-start、final 三个阶段各有 8 条 warning，都是 Grafana migrator 的 "Skipping migration: Already executed, but not recorded in migration log"，与 AIB-0 无关。
- **模型网关**：AI Base 启动时报告 "Gateway probe failed (gateway_connection_error)"，原因是没有配置模型网关。这与 AIB 回执中"未执行真实模型"一致，也不影响 smoke。
- **launcher smoke**：5 项全部通过：
  - Dashboard workbench；
  - Dashboard AI workflow；
  - Dashboard workflow API；
  - AI Base diagnostics；
  - Workspace context and artifact validation。
- **未执行**：`-FullAiChatSmoke`，它需要真实模型。

### 附加探针

以下探针在栈运行期间执行，输出只包含键名和布尔值，不包含凭据值。

| 探针 | 结果 |
| --- | --- |
| Django `/workbench/` | 200 |
| AI Base `/health` | 200；键为 `name,status,version,profile,serviceId,handshakePath`；没有 `instanceToken` 字段，响应体不含凭据值 |
| AI Base `/health/handshake` | 结果与 `/health` 相同 |
| AI Base `/api/runtime/diagnostics/summary` | 200；`handshake` 的键为 `ok,matchesServiceId,matchesInstanceToken,serviceId`；没有 `instanceToken` 字段，响应体不含凭据值 |
| AI Base `/api/runtime/info` | 仍返回 `app.instanceToken`。这是 AIB-0 spec "AIB-0 preserves the active Metrics integration" 的规定，属于延后到 AIB-2 的风险 |
| 以伪造的 Host 访问 `/health` | 400 |
| 已删除的未认证 `POST /api/metrics/workspace-context/sync` | 404 |

### 停止与清理

- launcher stop 以 0 退出。
- 运行中记录的 18 个自有 PID 全部退出。
- 停止前，过期进程规则对外部进程命中 0 个，sample_agent 端口上也没有外部进程监听，所以没有停止任何不属于本次运行的进程。
- junction、运行时 state 和插件副本已全部删除。
- AI Base worktree 中 git 跟踪的文件保持干净，profile 状态文件没有残留。
- AI Base 栈按设计在 worktree 中被 git 忽略的目录下写入了运行数据，这属于"launcher 按回执写入运行时状态"，未删除：
  - `.tmp-validation\runtime\logs\`：4 个文件；
  - `services\app-service\.local\app-data\dashboard_query_agent\`：新建或更新 21 个文件。
- 对上述 25 个文件做了凭据扫描：没有 GUID 形态的值，也不含任何合成 Jira 环境变量的值（token、地址、认证模式）。这说明 Metrics 推送的 workspace context 不携带 provider 凭据。

## 6. 发现

### AI Base 侧

- **AIB-F1**：`scripts/start-minimal-chat-dev.ps1:250` 把 instance credential 原样输出到控制台（`Instance    : <token>`），Metrics launcher 又把这段输出写进了运行日志。
  - 这个值正是 `_validate_sidecar_token` 校验的凭据。
  - 本次的 token 是一次性 GUID，实例已经停止，本地日志副本也已脱敏。
  - 建议改为输出 `serviceId` 或不可逆指纹（例如 SHA-256 的前 8 位），并补一条回归测试：启动脚本的输出不得包含凭据。
  - 这与 AIB-0 的要求"health/diagnostics 不含凭据"属于同一类问题。
  - 控制台输出中的泄露只有这一处：`scripts` 下其他脚本都不输出该凭据，AI Base 运行产物中也没有（见第 5 节）。
- **AIB-F2**：同一凭据还出现在 backend 子进程的命令行上。
  - `scripts/dev-stack.common.ps1:995` 把 `$env:RCA_APP_INSTANCE_TOKEN = '<token>'` 写进 backend 启动脚本；`:1079` 把整段脚本经 Base64 编码后作为 `-EncodedCommand` 的命令行参数交给子进程。Base64 可以直接还原。
  - 因此，同一用户的任何进程都能从进程列表读到它；开启命令行审计（4688、Sysmon、EDR）时，它还会被采集进安全日志并长期保存。
  - 该 `-EncodedCommand` 中的其余内容都不是凭据，包括：
    - 窗口标题、工作目录、profile、日志级别；
    - 网关地址、端口、`serviceId`、CORS、CLI tool 配置；
    - 客户端环境命令（`dev-stack.config.ps1:105`），只设置 CA 证书路径和 `NO_PROXY`。
  - frontend 的 `-EncodedCommand` 不含凭据。`task-minimal-chat-dev.ps1` 的 backend 角色从状态文件把 token 读入本进程环境，再启动 uvicorn，不经过命令行。
  - 本次的本地证据只保存了截断后的命令行，不含 Base64 串。
  - 现阶段的增量风险很低：token 是一次性的，只在回环端口有效，而且 `/api/runtime/info` 本来就会向本机进程返回它。但当 runtime/info 不再返回 token 后，这条路径就会成为真实泄露。修复成本也低：改为经子进程的环境块传递，命令行中不放任何凭据。

### Metrics 侧（不属于 AIB-0）

- **F-a**：`ui_web` 在构造 bug trend facade 时立即创建 Jira client，调用链为 `ui_web/container.py` → `jira_sync/container.py` → `bug_metrics/provider_connections/resolver.py`。
  - 没有 Jira 配置时，读本地 durable 数据的 `/api/charts/data/` 返回 500：缺少地址时报 `PROVIDER_ENDPOINT_INVALID`，token 为空时报 `PROVIDER_CREDENTIAL_INVALID`。
  - run1 因此失败。
- **F-b**：`scripts/e2e_grafana_runtime.py` 中的 `resolve_grafana_plugins_path` 只识别 `<repo>\.worktrees\<name>` 布局下的共享插件缓存。
  - 在 Orca worktree 布局下，Grafana 拿不到 Infinity 插件，`/api/plugins/yesoreyeram-infinity-datasource/settings` 返回 404。
  - run2 因此失败。
- **F-c**（低）：调用方重定向 launcher 输出时，launcher 本身退出后，调用方仍要等到 AI Base 进程停止才收到 EOF，推测是 AI Base 进程继承了输出句柄。
  - 判断是否就绪，应以日志中的 "stack is ready" 为准。
  - MDB-2 删除 sidecar launcher 后，这个问题自然消失。

## 7. 运行记录

| 运行 | 开始时间 | 结果 | 原因 |
| --- | --- | --- | --- |
| run1 | 10:34 | exit 1 | F-a；AI Base 未启动 |
| run2 | 10:41 | exit 1 | F-b；AI Base 未启动 |
| run3 | 10:46 | 通过 | 本回执 |

每次运行之后都执行了 teardown，下一次运行前都重新预检并生成新的快照。

本地证据位于 `.tmp\aib0-accept\`（gitignored，不入库），包括 preflight、provenance、security-probe、teardown 的输出和日志。

## 8. owner 决定（2026-11-11）

- **AIB-F1、AIB-F2**：同一轮修复，在 AIB-0 合入 main 之前完成。
  - AI Base 修复后，Metrics 在新的 HEAD 上重跑本验收，命令、偏离和探针与本次相同。
  - 额外检查两项，都只输出计数：
    - launcher 日志、AI Base 运行日志中不出现 token 值；token 值在运行中从状态文件读入内存，不落盘；
    - 所有 AI Base 进程的命令行中不出现 token 值，`-EncodedCommand` 先解码再检查。
  - 重跑结果追加到本回执。
- **F-a、F-b**：并入 MDB-2，作为 `tasks.md` 中的独立任务。
