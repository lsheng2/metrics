## Why

现有项目已经在 Jira-backed Bug Trend、Grafana 可行性、AI chart governance 和 provider-neutral platform 方向上分别开始探索，但最终产品目标还没有被一个统一 change freeze：最终界面要以 Grafana 为主，功能深度要对齐 Intel HSD-ES `In-fly Indicator v2.0` dashboard，同时第一落地数据 provider 必须是 Jira，而不是 HSD-ES。

现在需要把目标顺序说清楚：我们不是先复制 HSD-ES 接入，也不是只做一个 Jira bug chart；我们要先用 Jira provider 建出与参考 dashboard 同等级的 Grafana dashboard 能力，再把 HSD-ES 作为第二个平行 provider 加入，并让 AI 能力跨两个 provider 复用。

## What Changes

- 将项目最终 UI 目标明确为 Grafana-first：Grafana 承担主 dashboard 界面、变量、布局和图表渲染。
- 将 Django/Metrics 后端明确为业务语义 owner：provider sync、durable facts、indicator definitions、evidence contracts、correlation、audit、权限和 AI governance 都由 Metrics 拥有。
- 将参考 dashboard 的功能范围纳入项目目标：`QUALITY`、`EXECUTION`、`EFFICIENCY` 三个区，以及 component bug、open bug trend、execution statistics、milestone schedule/progress、automation、shift-left、escaped bugs、aging、total bug trend 等 panel 级能力。
- 明确 provider 顺序：第一 provider 是 Jira；第二 provider 是 Intel HSD-ES；两个 provider 都必须通过 provider-neutral contracts 被 dashboard 和 AI 消费。
- 明确第一阶段 Jira source query 默认方式：JQL SHALL 存在 Project Provider Profile/config 中并由 Metrics 管理、版本化和审计；第一版默认 JQL 为 `project = "131600" AND component = "team_int_qemu"`；Jira saved filter 只作为后续可选接入模式。
- 明确第一版 Grafana dashboard 目标：用户一次选择一个 Project Provider Profile，页面只渲染该 profile/provider 的数据；Jira 与 HSD-ES 使用同一套 chart contract，开发顺序仍是 Jira facts first、HSD-ES quality facts second。显式 Jira/HSD-ES 对比应作为后续 comparison/correlation mode，而不是默认 dashboard 页面。
- 明确首批 chart 范围：quality bug trends、component、valid bug、total bug 和 aging 优先；所有含有 execution、automation、shift-left 或 escaped bug 语义的 chart 第一阶段 SHALL 标记为 `deferred`、`configuration_required` 或 `unsupported`，不伪造数据。
- 明确 AI 能力边界：AI 可以查询、解释、生成 chart draft、建议 correlation 和提出 action plan；AI 不得直接绕过 Metrics 后端查询 provider，也不得直接写 Jira 或 HSD-ES。
- 明确 HSD-ES dashboard 观察结论：参考 Grafana 页面使用 Mongo 聚合数据源而不是前端直接调用 HSD-ES API；其变量映射可作为目标维度参考，但不能替代 HSD-ES `tenant/subject` contract review。
- 明确 HSD-ES saved query 观察结论：`NVU All Bugs` (`queryId=15017652869`) 使用 `ip_fw_sw_sensing.tenant` / `ip_fw_sw_sensing.bug` 和一组 NVU-FW bug criteria；这些 SHALL 作为 HSD-ES provider seed/configuration evidence，而不是 provider-neutral dashboard schema。
- 明确 HSD-ES 第一版 quality facts seed：`NVU All Bugs` (`queryId=15017652869`) SHALL 作为所有 HSD-ES quality facts 的 base seed，除非后续 profile 明确版本化地改为更窄 seed。
- 明确 dashboard scope label 可配置：Jira 第一版使用 `IP=chiplet_ip`、`Project=chiplet`、`Milestone=2a`；HSD-ES 第一版使用 `IP=NVU`、`Project=NVU1.0_TTL`、`Milestone=NVU_TTL_FWSW0.8`。这些 dashboard-level display/scope 值 MAY 先由用户在 profile config 中写入 raw/static text；这类值 SHALL 标记为 user-configured fixed dimensions，不能被误认为来自 provider article field。
- 明确 field layering：canonical fields 负责 dashboard/evidence/AI/correlation 共享语义，provider fields 保留 Jira/HSD-ES native payload，project fields 表达 NVU/Jira-project 等 per-project mapping。
- 明确 chart layering：每个 parity panel SHALL 由 Metrics-owned provider-neutral chart recipe 定义，再由 Jira/HSD-ES provider binding 生成 approved Grafana data surface。
- 明确 daily metric calculation layering：例如“每天新建的标准 bug 数量” SHALL 由 Metrics 后端基于 provider facts、Project Provider Profile 和 chart recipe 计算并版本化；Grafana 只保存 panel layout、variables、visualization 和 approved data-surface query，不保存 bug 定义、字段映射或聚合语义。
- 明确 Project Provider Profile：每个 provider/project combination SHALL 有一个 profile config 来声明 source query ownership、field bindings、value normalization、chart support、evidence rules 和 mapping version。
- 明确 Grafana profile selector UX：用户 SHALL 先选择 `profile_id`，`provider_id`、静态 scope labels、source query ownership 和 mapping version SHALL 从 profile 解析；Grafana 不应要求用户手动同步 provider 与 profile。用户 MAY 临时覆盖 scope/time 字段，但覆盖状态 SHALL 作为 runtime override 明确标记，并保留后续保存为新 profile 或更新 profile 的产品路径。
- 明确 query ownership 差异：HSD-ES 可以引用 provider-owned saved query；Jira 通常使用 Metrics-owned configured JQL，也 MAY 引用 Jira saved filter；两者都 SHALL 被 profile 包装为同一种 source population contract。
- 明确 Grafana 路线：先验证 C-stock dashboard parity；若 stock Grafana 无法满足同页 evidence、AI catalog 或状态同步，则升级到 Grafana App/Scenes，不退回长期 Django chart shell。
- 明确 AI 入口路线：优先尝试 Grafana App/Scenes 与 Metrics UI sidebar；若 dashboard layout 或交互承载不了，则可拆成独立 AI dashboard agent/surface，但后端 contract 保持不变。
- 不在本 change 中实现代码或迁移数据；本 change 只定义目标、行为 contract、架构路线和实施 DAG。

## Capabilities

### New Capabilities
- `grafana-dashboard-parity`: 定义 Grafana 主界面必须对齐参考 HSD-ES dashboard 的 dashboard、变量、section、panel、series、drilldown 和 parity 行为。

### Modified Capabilities
- `work-item-provider-platform`: 明确 Jira first、HSD-ES second 的 provider 顺序，以及 dashboard 功能 parity 不等于 HSD-ES first。
- `provider-facts-and-sync`: 增加 Jira-first durable facts 到 Grafana parity dashboard 的要求，并保留 HSD-ES second provider 的 durable facts 扩展路径。
- `provider-correlation`: 明确 Jira 与 HSD-ES 作为平行 provider 的 correlation 在 Grafana dashboard 和 AI 中的消费方式。
- `provider-ai-actions`: 明确 AI 能力必须同时支持 Jira 与 HSD-ES provider facts/action plans，但 HSD-ES write 仍保持禁用直到 tenant/subject 和治理规则确认。

## Impact

- Affected specs: `work-item-provider-platform`、`provider-facts-and-sync`、`provider-correlation`、`provider-ai-actions`，以及新增 `grafana-dashboard-parity`。
- Future affected modules: `bug_metrics/`、`jira_sync/`、`jira_history/`、future `hsdes_provider/` or `hsdes_sync/`、future `provider_ops/` or `work_items/`、`ui_web/`、`ops/grafana/`、`scripts/`。
- Affected external systems: Jira provider first, HSD-ES provider second, Grafana as primary dashboard UI, optional AI-base as AI orchestration shell.
- Affected governance: chart catalog validation、approved data surfaces、evidence contracts、provider action approval、cross-provider audit、Grafana artifact validation。
