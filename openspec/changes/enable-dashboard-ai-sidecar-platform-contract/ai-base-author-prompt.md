# Prompt For AI Base Author

请你在 `D:\AIGC\Report_creater_agent\` 中评估并规划 AI Base 作为通用 AI platform 的下一步增强。Dashboard app 将成为 Sample、Report Creator、SoC AI Driver 之后的第 4 个 app profile，目标是让 Dashboard 通过 AI sidecar 调用 AI Base，而不是在 Dashboard repo 里重新实现 AI runtime。

请重点分析并设计以下 shared platform capabilities，不要只为 Dashboard 写一次性代码：

1. **新增 `dashboard_query_agent` profile**
   - 在 `config/app-profiles.json` 中新增 Dashboard profile。
   - 使用 profile-scoped feature gates，例如 `dashboardQuery`、`grafanaOperations`、`metricsConnector`。
   - 不影响现有 `sample_agent`、`report_creator`、`soc_ai_driver` 默认行为。

2. **Generic connector lane**
   - 在现有 extension bundle 机制中新增/完善 `connectors` lane。
   - Connector 定义应支持 `connectorId`、base URL、health path、auth ref、request/response schemas、timeout、redaction policy、allowed operations、diagnostics。
   - Dashboard 的 Metrics connector 是第一个应用：catalog lookup、intent validation、draft render config validation、provider evidence/context、gcx precondition。
   - 这个 connector 模型也要能服务未来 RCA、SoC 或其他 app 的外部服务集成。

3. **Shared app tool result envelope**
   - 为 host tools、CLI tools、connectors、workflow adapters 统一输出 envelope：
     - `status`
     - `data`
     - `warnings`
     - `audit`
     - `artifactRefs`
     - `correlationId`
     - `displayHints`
   - 不要把 tool result 只作为字符串返回给模型/UI。

4. **StandardCliRunner production hardening**
   - 当前已有 `services/app-service/app/services/cli_runner/`、`.agent-skills/shared/dashboard-gcx/cli-bundle.json` 和 tests。
   - 请检查并补齐：activation-time durable dry-run proof store、precondition executor、post-success callback executor。
   - `StandardCliRunner` 应在 successful `write_preview` dry-run 后记录 proof；mutation command 必须匹配 proof 的 command id、artifact path、profile/workspace/session/correlation/approval scope、executable fingerprint、env policy 和 expiry。
   - gcx mutation 前必须能调用 Dashboard/Metrics-owned precondition validator；失败时不得启动 gcx mutation。

5. **Run API / headless execution**
   - 如果 `/api/runs` / `ai-base run` 仍是 docs-only，请将它提升为 platform priority。
   - Dashboard 的 chart generation、artifact validation、gcx dry-run/publish/snapshot 更适合 durable Run lifecycle，而不是只挂在 chat turn 上。
   - Run result 应支持 events、approval、artifact refs、cancellation、idempotency 和 safe error envelope。

6. **Profile-scoped extension diagnostics**
   - Diagnostics 应显示每个 extension/capability 的状态：
     - registered
     - available
     - activated
     - executable
     - blocked reason
     - trusted executable configured or missing
     - model visible or operator/debug only
   - Dashboard 需要这套诊断来解释“为什么 AI sidecar/gcx 不可用”。

7. **Security boundaries**
   - AI Base 不应保存或读取 Jira/HSD-ES/source credentials。
   - AI Base 不应允许 raw shell、raw SQL、raw `gcx api` passthrough 或 model-selected executable paths。
   - `gcx` bundle 默认 disabled/modelVisible=false；只有 Dashboard profile/operator/session 激活后才可见。
   - Approval hooks are useful UX, but not sufficient authorization; enforcement must happen inside AI Base tool/connector handlers.

8. **Cross-repo contract tests**
   - Dashboard repo 应发布 Metrics-side schema fixtures/snapshots。
   - AI Base 应用 mocked Metrics API tests 验证 connector request/response shape。
   - 两边都应测试 contract version mismatch、unsupported operation、validation failure、redaction 和 fallback。

Dashboard-side current facts:

- Metrics owns provider profiles、chart recipes、canonical facts、aggregate artifacts、Grafana render config generation、artifact validator、AI intent validation 和 gcx precondition。
- Metrics currently supports HSD-ES profile `nvu-ttl-hsdes` and Jira profile `chiplet-2a-jira` through provider profile registry.
- Important semantic guardrail: if user asks for `new_critical` and current recipe only has `new_critical_high`, AI Base must return `needs_metric_recipe`; it must not relabel or synthesize unsupported metrics.
- Dashboard repo now publishes AI Base-facing contract fixtures:
  - `openspec/changes/enable-dashboard-ai-sidecar-platform-contract/contracts/ai-base-dashboard-profile-suggestion.json`
  - `openspec/changes/enable-dashboard-ai-sidecar-platform-contract/contracts/metrics-connector-operations.json`
- Metrics connector routes exposed by dashboard:
  - `GET /api/ai-dashboard/catalog/`
  - `POST /api/ai-dashboard/intent/validate/`
  - `POST /api/ai-dashboard/render-config/validate/`
  - `POST /api/ai-dashboard/gcx/precondition/`
  - `GET /api/ai-dashboard/context/`

Expected AI Base output:

- A concrete implementation plan for shared platform changes.
- A `dashboard_query_agent` profile plan.
- Connector lane DTO/API schema proposal.
- `StandardCliRunner` dry-run/precondition/callback hardening plan.
- Tests required before Dashboard can rely on AI Base for sidecar + gcx operations.
