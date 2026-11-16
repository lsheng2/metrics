# Metrics Dashboard 新用户 Onboarding：从 Scope 到 AI Grafana Chart

## 适用对象

这份手册面向第一次使用 Metrics Dashboard 的用户。目标是让用户从零开始理解并完成下面的路径：

1. 获取已配置的 Dashboard 和 Grafana 地址；AI runtime 由 Dashboard 进程托管。
2. 在 Provider Setup 中确认可用 provider profile，并在 Scope Library 中理解已有 scope。
3. 创建或导入一个 scope。
4. 完成 scope validation 和 deployment。
5. 确认 provider binding、sync/cache、calculation 和 evidence readiness。
6. 打开 Workbench 查看图表和 ticket evidence。
7. 使用 AI Workflow 检查就绪状态，并在 Workbench 的 AI pane 中申请审批发布。

示例会同时使用：

- Jira 示例：`chiplet-2a-jira`
- HSD-ES 示例：`nvu-ttl-hsdes`

## 0. 获取应用入口

从部署维护者获取当前 Dashboard 地址。Workbench、AI Workflow 和嵌入的 AI pane
使用同一个 Dashboard origin；不需要另开 AI 前端或后端地址。以下页面路径相对于
这个地址，Grafana 地址以发布记录或部署配置为准。

开发者需要验证安装与发布链路时，使用
[Dashboard AI 发布联调 Runbook](../validation/dashboard-ai-e2e-runbook.zh.md)
中的隔离命令。该流程使用合成数据，不会替用户同步真实 provider 或迁移用户数据库；
全局启动脚本和容器迁移的未完成项也在该 runbook 中说明。

## 1. 先确认 Provider Setup 和 Scope Library 的边界

Provider profile 的管理入口是：

```text
/provider-setup/
```

这里负责 profile 的创建、编辑、连接测试、导入导出、归档和删除。示例 profile 包括：

- Jira 示例：`chiplet-2a-jira`
- HSD-ES 示例：`nvu-ttl-hsdes`

Scope 的管理入口是：

打开：

```text
/bug-trend/scopes/
```

这里只列出 saved scopes。新用户先看三件事：

| 区域 | 作用 | 新用户应该看什么 |
| --- | --- | --- |
| 顶部 summary | 当前 scope 数量和 binding policy | 是否已有可用 scope |
| Scope lifecycle | 从 draft 到 AI/Grafana 的步骤 | 按 1 到 6 的顺序做，不要跳过 validation/sync/calculation |
| Readiness matrix | 每个能力需要哪些前置条件 | 缺什么字段会影响哪个后续流程 |

重要概念：

- **Scope**：Dashboard 本地保存的查询范围和语义配置。
- **Provider profile**：provider 连接/onboarding 配置，例如 `chiplet-2a-jira` 或 `nvu-ttl-hsdes`。它在 Provider Setup 中管理，在 Scope Library/Scope Config 中只被 scope 引用。
- **Binding**：把 scope 绑定到某个 provider profile，使 Workbench / AI / Grafana 知道应该使用哪个 provider context。
- **Archived**：从正常选择中移除，但保留历史数据。它不是 hard delete。

## 2. 新建 scope

在 Scope Library 点击 `New Scope`。

最小字段：

| 字段 | 必填级别 | 用途 | 示例 |
| --- | --- | --- | --- |
| Name | 保存 draft 必填 | 人能识别的 scope 名称 | `Chiplet bug trend` |
| IP | 可选但推荐 | 页面分组/搜索和人类识别 | `chiplet_ip` |
| Project label | 可选但推荐 | 页面分组/搜索和人类识别 | `chiplet` |
| JQL | 保存 draft 必填 | Jira 查询范围 | `project = STDEL AND issuetype = Bug` |
| Bug type values | 保存 draft 必填 | 识别哪些 issue 类型算 bug | `Bug` |
| Bucket granularity | 保存 draft 必填 | 计算按天还是按周聚合 | `Weekly` |
| Timezone | 保存 draft 必填 | bucket 时间边界 | `UTC` |

Deployment 还需要这些字段，否则不能 `Enable Scope`：

| 字段 | 为什么需要 |
| --- | --- |
| Open status values | 计算 open bug trend |
| Fixed status values 或 Closed status values | 计算 fixed/closed trend |
| Severity field | 识别 critical/high vs medium/low |
| Critical/high values | 计算 critical/high series |
| Medium/low values | 计算 medium/low series |

示例 Jira scope：

```text
Name: My Chiplet Bug Trend
IP: chiplet_ip
Project label: chiplet
JQL: project = STDEL AND issuetype = Bug
Bug type values: Bug
Open status values: New
Fixed status values: Fixed
Closed status values: Closed
Severity field: priority
Critical/high values: P1-Critical
Medium/low values: P3-Medium
Bucket granularity: Weekly
```

建议新用户先点 `Save Draft`。确认无误后再点 `Enable Scope`。

## 3. Validate 和 Deploy 的区别

Dashboard 把 scope 分成几层 readiness：

| 阶段 | 用户动作 | 系统检查 | 通过后能做什么 |
| --- | --- | --- | --- |
| Draft save | `Save Draft` | 基础字段和格式 | 保存配置，继续编辑 |
| Deploy | `Enable Scope` | 关键 metrics 字段完整 | 出现在 Dashboard / Workbench / AI scope selection |
| Provider binding | Scope Library inline binding | profile/provider 可解析 | AI 和 Workbench 有 provider context |
| Sync/cache | stack sync 或 provider sync | source facts 可用 | Data Health 不再报 sync/cache blocker |
| Calculation | sync 后 recalculate | bucket/run/evidence 可用 | chart 和 evidence list 可用 |
| AI/Grafana | AI Workflow / Chat | profile、chart recipe、series、range、发布就绪状态 | 生成可审批的发布预览或解释 blocker |

如果 `Enable Scope` 失败，不要直接改 AI 或 Grafana。先回到 Scope Config 补字段，再看 Data Health。

## 4. 连接 provider profile

回到 Scope Library。每个 scope 有 Binding 列：

| 状态 | 含义 | 用户动作 |
| --- | --- | --- |
| `explicit` | 已明确绑定 provider profile | 可以继续 sync / calculate / AI workflow |
| `inferred` | 系统根据旧逻辑推断绑定 | 建议点击 Confirm，转成 explicit |
| `configuration_required` | 缺少 profile/provider | 从下拉框选择 provider profile 并 Save |
| `ambiguous` | 多个 profile 可能匹配 | 选择正确 profile 并 Save |

示例：

- Jira 使用 `chiplet-2a-jira`
- HSD-ES 使用 `nvu-ttl-hsdes`

如果只想管理 profile 本身，不要在 Scope Library 中找 profile 行；请回到 Provider Setup。

## 5. Archive、Export、Import、Delete

### Archive

`More -> Archive` 是默认安全移除方式。

影响：

- 不再出现在 Dashboard、Workbench、AI Assistant 的正常 scope selection。
- 历史 calculation runs、bucket evidence、Jira history、sync cache、provider binding、audit records 仍保留。
- 可以进入 Edit 后 `Enable Scope` 恢复。

### Export JSON

`More -> Export JSON` 会下载 scope 配置包。

包含：

- semantic scope config
- provider binding metadata

不包含：

- calculation runs
- bucket evidence
- Jira issues/snapshots/transitions
- sync cursor
- audit history

### Import Scope File

顶部点击 `Import Scope File`，再选择 JSON 包并点击 `Import`。导入后默认是 archived/draft，不会自动进入 Dashboard 或 AI 流程。

导入后请按顺序：

1. Edit 检查字段。
2. Confirm 或保存 provider binding。
3. Enable Scope。
4. Sync/cache。
5. Calculate。
6. Workbench / AI Workflow。

### Delete archived

只有 archived scope 才能 hard delete。需要输入：

```text
DELETE <scope name>
```

这是不可逆清理，会级联删除相关历史数据。新用户不要删除重要 scope。建议只删除刚导入错或临时测试的 scope。

## 6. 检查 Data Health

打开：

```text
/data-health/
```

重点看：

| 区域 | 说明 |
| --- | --- |
| Scope Binding Health | provider binding 是否 explicit |
| Provider Sync Cache Health | provider profile 的 facts/cache 是否可用 |
| Jira Sync Health | Jira scope 的 sync cursor 是否成功 |
| Calculation Health | completed run 是否匹配当前 config hash |
| AI runtime status | 嵌入式 AI runtime 是否启动、模型设置是否齐全 |

如果这里显示 blocker，AI 可以解释 blocker，但不应该把 chart 当成 ready 发布。

## 7. 打开 Workbench 查看 chart 和 ticket evidence

打开启动输出里的 Workbench URL，例如：

```text
/workbench/
```

新用户确认：

1. 上方 chart pane 有图。
2. 选择 chart bar 后，下方 Evidence tickets 会刷新。
3. 右侧 AI Assistant pane 正常显示或显示明确的不可用原因。
4. 底部 service status bar 显示 Dashboard、Grafana、AI Base 状态。

如果某个 chart 没有 ticket evidence，页面应该提示 summary-only 或 unsupported，而不是显示错的 ticket list。

## 8. 用 AI Workflow 检查就绪状态

在当前 Dashboard 中打开 `/ai-dashboard/workflow/`，选择 scope 对应的 profile、
chart、series 和 range，再执行 `Run Metrics Validation`。支持且输入有效的草稿
可以达到 `draft_validated`；数据或目标未就绪时，先处理页面给出的 blocker。
不支持的 metric 保留 `needs_metric_recipe`，不能换成另一个 metric 冒充成功。

## 9. 在 Workbench 申请审批发布

从已绑定 scope 的 Workbench AI pane 发起图表请求。在 runtime 的审批界面核对
预览并批准后，查看 `Publication history` 中的记录及其 Grafana 链接。
Chat 中的文字表态不能代替这条审批记录。

发布步骤、范围变化、重复请求和失败恢复只维护在
[Dashboard AI 发布联调 Runbook](../validation/dashboard-ai-e2e-runbook.zh.md)。
验收依据是审批、发布历史和 Grafana 数据，不是模型回复的固定措辞。

## 10. 新用户故障排查

| 现象 | 常见原因 | 下一步 |
| --- | --- | --- |
| Scope 无法 Save Draft | name/JQL/bug type/timezone/bucket 格式缺失 | 回到 Scope Config 补基础字段 |
| Scope 无法 Enable Scope | open/fixed/closed/severity/critical/medium 字段缺失 | 看错误提示，补 deployment 必填字段 |
| Workbench scope 下拉里看不到 scope | scope 仍是 archived/draft | Edit 后 Enable Scope |
| AI Workflow profile 不 ready | provider binding 或 provider readiness blocker | 看 Scope Library Binding、Provider Setup 和 Data Health |
| Chart 无数据 | sync/cache 或 calculation run 缺失/过期 | 跑 stack sync 或 recalculate |
| Evidence tickets 不刷新 | chart 不支持 bucket/series evidence | 换支持 evidence 的 chart/series |
| AI Base 不可用 | runtime 未启动或模型设置缺失 | 看底部 status bar 和 Data Health AI runtime status |
| Grafana URL 打不开 | Grafana 未启动或端口变化 | 看启动输出中的 Grafana port |

## 11. 新用户完成标准

一个新用户完成 onboarding 后，应能证明：

- Provider Setup 中能看懂 provider profile；Scope Library 中能看懂 scope、binding、archive/export/import/delete archived。
- 至少一个 scope 已 `Enable Scope`。
- 该 scope 有 explicit provider binding。
- Data Health 没有阻塞该 profile/chart 的关键 blocker。
- Workbench 能打开 chart，并能看到或解释 evidence state。
- AI Workflow 能验证支持的草稿，并明确报告数据或配置 blocker。
- Workbench 能展示 runtime 审批；批准后的发布记录包含审批关联，并能打开对应 Grafana 图表。
