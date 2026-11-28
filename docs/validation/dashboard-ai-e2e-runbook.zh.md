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
[dev11 真实链路回执](../../openspec/changes/embed-ai-base-runtime-in-process/evidence/windows-live-acceptance-dev11.json)
记录了限定只读 Jira 与实际 `gpt-5.5` 的执行通过。它只覆盖 1 个符合上限的真实工单；
原选定大工单仍因输入超限被拒绝。人工验收、大输入/真实多日增量、C5、R4/R7、
完整性能及 Linux 资格没有因此关闭。

## Windows 入口

安装和解释器选择以 `docs/development/reporting-delivery.md` 为准。普通本地后端入口只启动
Dashboard，不附带迁移、示例数据或 Grafana 导入；E2E 入口显式管理 Dashboard 与本地
Grafana。两者都拒绝旧启动选项，不回退到另一套 Python。停止按已登记实例及进程身份进行，
记录服务真实退出码；强制、失败和未知退出不算正常停止。完整 stack smoke 读取当前
Workbench 和服务端 workflow form，不再要求已退役的业务 API。

自动回归使用新的 D 盘隔离数据和 synthetic provider/model，不接触现有 8017 或生产数据。
真实 provider/model 端到端执行已有上述限定回执；合成回归仍不能替代它。
2026-11-28 已授权按[真实链路验收计划](../../openspec/changes/embed-ai-base-runtime-in-process/windows-live-acceptance.md)
执行限定只读 Jira、已配置的真实模型和新的本地隔离实例。
真实凭据只在进程内使用，业务证据不进入 Git；不做 provider 写入、force refresh、调度或
外部发布。涉及 Grafana 时仅使用明确隔离的本地目标；其他来源或部署不能继承本次 PASS。

## 本轮已验证

- 真实来源完整采集后，`metrics.project_summary@3` 输出通过 schema、证据和业务校验，页面为 `draft_ready`。
- 人工备注保存为修订 2；真实 `metrics.report_authoring@1` 候选经 Apply、Save 后成为修订 3，保留 `ai_assisted` 来源。
- 精确修订 3 本地定稿；原生浏览器下载与 Git 中的 HTML 原件逐字节一致。
- 真实模型调用 catalog、workflow、publish 工具；批准前无发布，按钮审批后导入隔离 Grafana。
- 待审批时切换当前范围，没有替换 session/iframe 或原预览；发布仍使用原批准范围。Grafana 返回时间字段及 `[0, 1]`，对应 1 条真实工单。
- 重复保存/聊天请求不产生新修订或新发布；宿主重启后会话、已消费审批、发布和报告 hash 一致，模型 run 数没有增加。
- 错误认证被拒绝后正确认证恢复。各次停止均为 exit 0、未强制；19 个主验收实例和 6 个恢复观察实例均无残留，端口释放。

首次采集到草稿就绪约 106 秒，编辑候选约 12 秒，两次 Save 约 2.8/2.9 秒，
Finalize 约 12.7 秒。这些是单次观察，不是 P95、可靠性统计或完整性能认证。
截图工具未取得 bitmap；DOM、非空画布像素、实际 Grafana 查询和原生下载分别留有证据。

## 人工试用顺序

1. 使用当前候选和明确隔离的数据库、archive、端口。完成模型 CA、来源 profile 与凭据配置后启动；新增 profile 后重启以重新加载 registry。
2. 执行阶段报告，先确认来源完整、摘要 `accepted`、页面 `draft_ready`。`partial` 或 `ANALYSIS_INPUT_LIMIT` 不能当作通过，也不能截断记录或伪造完整性。
3. 独立运行产生的初始草稿先添加备注并 Save 一次，再选择具体 Summary 等字段打开 AI assist。初始未保存版本可能没有 AI targets；这不是模型连通性失败。
4. 检查实际候选内容，明确 Apply，再 Save。Apply 只修改本地脏内容；Save 与 Finalize 是不同动作。
5. 勾选精确保存修订后 Finalize，重开并下载原文件，核对人工内容、AI 来源和未读正文的范围说明。
6. 图表必须先有覆盖当前范围的真实计算。在已确认的隔离 settings 下使用正常 `sync_jira_scope <scope_id> --coverage-start YYYY-MM-DD --coverage-end YYYY-MM-DD`；本次没有使用 `--full` 或 `--force-refresh`。
7. 在 Workbench 选定 profile/范围，让模型验证图表并调用 `metrics.publish_chart` 创建审批预览。模型仅口头请求确认时，可以明确要求它创建 runtime 审批；聊天文本本身不是批准。
8. 检查目标、系列和范围，再点 Approve。查看发布历史和实际 Grafana 数据，最后正常停止并检查残留。

自动化浏览器应按 origin 处理 HTTP 认证，不要把 Dashboard 的 Basic 头广播给
Grafana。真实 source/model 记录和凭据只保留在受控的本地证据区，不进入 Git。

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
