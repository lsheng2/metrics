## Close Review

### Scope

本 close review 覆盖 `define-grafana-jira-first-ai-dashboard-target` 的最终证据：Jira-first Grafana parity、HSD-ES second-provider readiness、AI support coverage、remaining risks，以及 stock Grafana 到 Grafana App/Scenes 的升级触发条件。

### Runtime Evidence

- `scripts/e2e_provider_parity.py restart --force-by-port` 已完成 live runtime validation。
- Runtime 启动 Django `127.0.0.1:8002` 与 Grafana `127.0.0.1:3001`。
- Runtime 执行并通过：
  - Django migrations。
  - `manage.py seed_bug_trend_sample`，生成 canonical Jira profile `chiplet-2a-jira`。
  - `scripts/validate_grafana_artifacts.py --artifact-root ops/grafana --allowlist openspec/docs/current-baseline/grafana-approved-data-surfaces.json`，结果为 `PASS grafana artifacts checked=2`。
  - `manage.py check`，结果为 `System check identified no issues`。
  - Grafana datasource setup for `metrics-bug-trend-api`。
  - `ops/grafana/provider_parity_dashboard.json` import，dashboard uid 为 `metrics-provider-parity-dashboard`。
  - Direct Metrics API 与 Grafana datasource proxy API runtime checks。
  - Playwright visible dashboard validation：`QUALITY`、`EXECUTION`、`EFFICIENCY` section 与 representative parity panels 可见，且 Grafana chart canvas 非空。
- Screenshot evidence: `state/e2e/provider_parity_dashboard.png`。

### Jira-First Parity

第一版 Jira provider 已通过 `Project Provider Profile` 风格的 canonical profile `chiplet-2a-jira` 驱动 supported quality panels。Runtime dashboard 中以下 Jira-backed chart targets 通过 Metrics-owned `/api/provider-charts/data/` surface 返回 `supported`，并输出 nonblank `grafana_rows`：

- `component_bug`
- `rolling_valid_bug`
- `open_bug_trend`
- `total_bug_trend`
- `daily_new_standard_bug_count`
- `open_bug_aging`

这些 panels 使用 provider-neutral query state：`provider_id`、`profile_id`、`begin_ww`、`end_ww`、`space_id`、`release_target`、`milestone`，并保留 `calculation_run_id`、`fact_snapshot_id`、`mapping_version` 与 source query provenance。Grafana 未直接持有 Jira JQL、Jira custom field mapping 或 bug classification logic。

### HSD-ES Second-Provider Readiness

HSD-ES 已作为 second provider 被纳入同一 provider-neutral contract。第一版 profile 使用 `nvu-ttl-hsdes`，source seed 记录为 provider-owned saved query `NVU All Bugs` / `queryId=15017652869`，并记录 `ip_fw_sw_sensing.tenant`、`ip_fw_sw_sensing.bug`、criteria snapshot、exclusion snapshot、permission assumptions 与 observed result contract。

Runtime dashboard 对 HSD-ES quality binding panels 返回 `configuration_required`，而不是 fake zero data。该状态符合当前 field-binding readiness：HSD-ES 已有 seed/profile/projection/provenance contract，但除已验证的 quality aggregate artifact path 外，live provider read/search/detail/API contract 与更多 chart-level native field bindings 仍需后续实现和确认。

### Deferred Panels

Execution、automation、shift-left、escaped bug 相关 panels 第一版仍保持 deferred/configuration-required contract。Runtime validation 证明这些 panels 通过同一 `/api/provider-charts/data/` surface 返回 `provider_series_state`，状态为 `deferred` 并带 reason，而不是输出未经确认的事实或零值 aggregates。

### AI Support Coverage

AI 能力已覆盖当前 Jira-first 与 HSD-ES-ready contract：

- Chart catalog 与 provider facts context 可供 AI explanation 读取。
- AI explanation 必须基于 chart data、evidence rows、aggregate artifacts、provider facts 或 deferred reasons。
- AI chart draft 必须经过 approved datasource、series、evidence capability 与 publication policy validation。
- Jira action suggestion 只产生 `ProviderActionPlan` preview/audit-ready proposal，不直接写 Jira。
- HSD-ES write 继续 disabled；AI 只能输出 non-executable suggestion 或 explanation。
- Cross-provider risk explanation 可区分 `candidate`、`confirmed`、`rejected`、`stale` correlation state，并保留 provider-native truth。

### Residual Risks

- HSD-ES live API details 仍需基于 Intel HSD-ES authoritative wiki/API 做实现前确认，不能从已观察 dashboard 或 saved query 反推未验证 endpoint 行为。
- HSD-ES execution、automation、shift-left、escaped bug field mappings 仍为 post-first-wave TBD。
- Jira production profile 的真实 data volume、permission、custom field drift 与 saved-query/JQL governance 仍需在接入真实 Jira instance 时重新运行 sync/profile validation。
- Stock Grafana 的 table virtualization 可能隐藏部分 state/reason columns；runtime validation 已把 exact state assertion 放在 live API/proxy payload，browser validation 负责可见 dashboard shell、panel titles 与 nonblank chart rendering。

### C-Plugin / App/Scenes Trigger

当前 C-stock Grafana 通过了 dashboard import、approved datasource、provider-neutral query state、visible nonblank charts 与 state-panel runtime validation，因此本 change 不触发立即升级到 Grafana App/Scenes。

后续如果出现以下情况 SHOULD 触发 Grafana App/Scenes 或独立 AI surface 评估：

- 同页 evidence click、state synchronization 或 AI sidebar 无法被 stock dashboard 稳定承载。
- 需要更强的 guided workflow、multi-step AI interaction、cross-panel selection context 或 review/approval UX。
- Table/panel virtualization 导致必须把 state/reason/evidence workflow 做成更确定的 custom scene，而不是依赖 stock panel layout。

### Close Decision

本 change 的 implementation gates 已满足：Jira-first quality parity 可 runtime render，HSD-ES second-provider readiness 以 explicit configuration-required/provenance contract 表达，deferred categories 没有 fake data，AI governance 未绕过 Metrics contracts。剩余问题属于后续 provider implementation 与 UX upgrade decision，不阻塞本 change closure。
