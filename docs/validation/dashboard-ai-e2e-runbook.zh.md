# Dashboard AI 发布联调 Runbook

## 状态与边界

本 runbook 描述 MDB-2 当前发布链路：Dashboard 进程内 runtime tools、runtime approval、Grafana import、`AiChartPublication` 历史，以及 Workbench 只读历史查看。

旧外部伴随服务、旧 HTTP business API、旧 Grafana CLI precondition、旧 proof id、旧 demo approval prefix、旧 demo publish endpoint 和旧 host-action 消息协议都不是当前操作说明。历史案例若提到这些术语，只能作为旧证据阅读。

Windows 入口已统一到进程内 `serve` 和 SLE 所有权管理。当前候选为 dev11，
解释器与安装身份以 [当前验证指南](../development/reporting-delivery.md) 为准。
[功能回执](../../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-functional-acceptance-dev10.json)
记录 3332 项、114/114 证据键通过；
[有界 pilot](../../openspec/docs/validation/performance-reports/2026-11-27-2024-dev10-pilot-r2.md)
记录完整采集、零错误、零超限。这些 dev10 证据不自动成为 dev11 验收，也不是整个项目发布。
真实 provider/model、人工验收、C5 正确性、R4/R7、完整性能及 Linux 资格仍未关闭。

## Windows 入口

安装和解释器选择以 `docs/development/reporting-delivery.md` 为准。普通本地后端入口只启动
Dashboard，不附带迁移、示例数据或 Grafana 导入；E2E 入口显式管理 Dashboard 与本地
Grafana。两者都拒绝旧启动选项，不回退到另一套 Python。停止按已登记实例及进程身份进行，
记录服务真实退出码；强制、失败和未知退出不算正常停止。完整 stack smoke 读取当前
Workbench 和服务端 workflow form，不再要求已退役的业务 API。

自动回归使用新的 D 盘隔离数据和 synthetic provider/model，不接触现有 8017 或生产数据。
最终功能交付还必须完成经授权的真实 provider/model 端到端验收；合成回归不能替代它。
2026-11-28 已授权按[真实链路验收计划](../../openspec/changes/embed-ai-base-runtime-in-process/windows-live-acceptance.md)
执行限定只读 Jira、已配置的真实模型和新的本地隔离实例。
真实凭据只在进程内使用，业务证据不进入 Git；不做 provider 写入、force refresh、调度或
外部发布。涉及 Grafana 时仅使用明确隔离的本地目标。授权不等于验收通过。

## 真实链路必验项

1. 从真实 provider 只读采集限定范围，核对身份、字段、成员集合、完整性和当前来源。
2. 从实际页面调用已安装 AIB 和真实模型，取得有效的摘要与编辑候选；不能以模型连通性或固定回复代替。
3. 人工检查事实和业务结果，完成编辑、Save、Finalize 和重开；图表流程须由模型实际调用工具，经显式审批发布到隔离目标。
4. 验证上下文切换、会话保持、重复请求、失败恢复、正常停止及无本次进程残留。
5. 分别记录外部调用耗时和用户端总等待；既有本机性能 PASS 不代表真实模型总耗时合格。

每项结果绑定双方源码、wheel、模型和实际数据范围。自动化浏览器验收与用户亲自试用
分别记录，不互相冒充；未运行或受阻项不标记 PASS。

## 当前契约

| Surface | 当前职责 | 可观察结果 |
| --- | --- | --- |
| `metrics.catalog` | 读取 profile 与 chart recipe catalog | 不泄漏 provider secret/native query |
| `metrics.chart_workflow` | 校验 chart intent、render config、数据和发布目标 readiness | 返回 `draft_validated` 或 typed blocker，例如 `needs_metric_recipe` |
| `metrics.publish_chart` preview | 生成 Dashboard-owned preview bytes，并绑定 `preview_digest` | readiness 不满足时不创建 approval |
| `metrics.publish_chart` handler | 只消费 runtime approval 绑定的 preview bytes | 写入 `AiChartPublication`，保存 runtime `approval_id` 与 `tool_call_id` |
| `/api/ai-publish-history/` | JSON-only read API | 只读 `AiChartPublication`，不列旧 audit 推导记录 |
| Workbench publication history | 只读 UI 历史 | `details[data-workbench-publication-history]` 内显示发布记录 |

Workbench 稳定选择器：

- 打开历史控件：`details[data-workbench-publication-history] > summary`
- 历史刷新区域：`[data-workbench-publication-history-region]`
- 单条 approval id：`[data-approval-id="<approval_id>"] code[title="<approval_id>"]`

`Refresh` 是局部 htmx 刷新，使用 `hx-swap="outerHTML ignoreTitle:true"`，不得替换 AI iframe/session，也不得改页面 title。

## 人工验证重点

1. 触发一个 synthetic chart workflow，确认 unsupported series 不被静默改写。
2. 进入 runtime approval 流程，确认 pending approval 期间切换 range 会更新当前 session binding 的新 `ContextRef`；但已经开始的 run/approval 保留其原始 preview/range，批准后发布的仍是该原始 preview。
3. 人工批准后，确认 Grafana import 使用已批准 preview bytes。
4. 打开 Grafana 查询结果，确认 timeseries 至少有一个 time field；当前生成器将 `bucket_start` 声明为 `type: "timestamp"`，`timestampFormat: "2006-01-02"`。
5. 打开 Workbench，展开 `Publication history`，点击 `Refresh`，确认同一 `approval_id` 可见且 AI iframe identity 未变化。
6. 重复同一 `tool_call_id` 且已存在 matching publication row 时读取既有结果；若 Grafana import 成功但数据库确认丢失，可以用同一 approved bytes/uid 和 `overwrite: True` 有界重试。历史中同 uid supersession 最新行标记 latest。

不要断言模型回复的固定英文句子、旧 demo UID、旧 proof id 或旧自动 host action。模型可以用不同措辞解释同一 runtime approval 结果。

## 隔离测试命令

按 `docs/development/reporting-delivery.md` 的 no-dotenv 入口运行显式测试路径。示例从 Dashboard repo root 运行 real browser join，并使用新的临时 basetemp：

```powershell
$reportingPython = 'D:\AIGC\d11-1128\venv\Scripts\python.exe'
$baseTemp = Join-Path 'D:\AIGC\d11-1128\temp' ('mdb2-publication-browser-' + [guid]::NewGuid().ToString('N'))
& $reportingPython -I -B scripts/validation/run_report_authoring_tests.py ai_host/tests/test_publication_browser_join.py -q --tb=short -p no:cacheprovider -o asyncio_default_fixture_loop_scope=function --basetemp $baseTemp
```

`pytest` 直接运行不是等价门禁，因为它会遗漏部分模块并加载开发设置。

原发布 packet 的历史证据记录在：

```text
openspec/changes/embed-ai-base-runtime-in-process/evidence/publication-packet-20261117.json
```

该文件记录当时 runtime approval + Grafana + Workbench history 的 synthetic 验证；
它不替代本页顶部的历史 dev10 回执或新的 dev11 真实链路验收，也不证明整个 Dashboard/AIB 项目已关闭。

## 当前安全边界

- 发布身份只来自 runtime `ToolApproval.approval_id`。
- `tool_call_id` 是幂等键；已有 matching publication row 时重复执行读取既有结果。若 import 成功但 App 记录未落库，恢复路径允许再次导入同一 approved bytes/uid，并以 `overwrite: True` 保持 Grafana 目标等价。
- handler 校验 `preview_digest`，digest mismatch 不得调用 Grafana。
- 数据变化导致 preview 失效时不得 import。
- denied/expired approval 不得调用 handler。
- publication history 只读 App-owned `AiChartPublication`。
- Chat 文本、模型输出、旧 audit event、旧 proof id、旧 demo approval prefix 都不是发布授权。

## 故障定位

| 现象 | 当前检查点 |
| --- | --- |
| Workflow not ready | 检查 `publish_readiness.status`、profile binding、provider facts 和 Grafana target |
| Grafana timeseries no data/time field | 检查 generated target columns；`bucket_start` 应是 `timestamp` |
| Workbench history看不到记录 | 检查 `/api/ai-publish-history/` JSON 与 `[data-workbench-publication-history-region]` |
| Refresh 后页面标题变化 | 检查 history refresh 是否保留 `ignoreTitle:true` |
| Stop 返回 `server_thread_alive` | 检查 Waitress active keepalive channels 是否被 drain/close |

## 非目标

- synthetic 自动回归不默认调用真实 provider/model；最终功能交付必须通过上面的真实链路验收。
- 不验证用户数据库或既有 Grafana 服务。
- 不以发布链路证明完整宿主资格或 Linux 部署通过。
- 不声明 9.4、10.2、10.3、10.4 完成。
