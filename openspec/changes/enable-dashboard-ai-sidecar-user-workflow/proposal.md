## Why

Dashboard 与 AI Base 的后端 contract 已经完成，但用户还缺少一个可操作的端到端工作流来验证“自然语言请求 -> Metrics intent validation -> render config draft -> gcx precondition/dry-run gate”的路径。现在需要把这个能力从 API contract 推进到可见、可验证、可审计的用户流程，并证明它对 HSD-ES 与 Jira profile 都保持 provider/profile neutral。

## What Changes

- 增加一个 Dashboard 侧 AI sidecar workflow surface，用于展示 sidecar readiness、用户请求、profile/range/chart 输入、intent validation、render config preview、gcx precondition 和 publication callback guidance。
- 支持内置 try-run 场景：
  - HSD-ES `nvu-ttl-hsdes` 请求 `new_critical_high` 成功生成 draft。
  - HSD-ES `nvu-ttl-hsdes` 请求 `new_critical` 返回 `needs_metric_recipe`。
  - Jira `chiplet-2a-jira` 使用同一工作流验证 provider/profile abstraction。
- 保持 Dashboard/Metrics 拥有 metric semantics、provider facts、render validation、gcx precondition 与 audit；AI Base 仍然是 optional orchestrator，不获得 provider credentials 或 raw native queries。
- 增加 focused tests 覆盖页面、API workflow envelope、unsupported semantic、gcx precondition guidance 与 Jira/HSD-ES profile neutrality。

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `dashboard-ai-sidecar-integration`: 增加用户可见 sidecar workflow、readiness/validation/precondition 展示和 cross-profile try-run 要求。
- `provider-ai-dashboard-composition`: 增加 Dashboard-owned workflow envelope 与 provider-neutral AI draft/precondition UX 要求。

## Impact

- Affected code: `ui_web/views/ai_dashboard_view.py`, `ui_web/urls.py`, `ui_web/templates/`, `ui_web/facades/bug_trend_facade.py`, `bug_metrics/app/api/ai_dashboard_composition.py` or adjacent API helpers if a workflow envelope belongs in domain API.
- Affected tests: `ui_web/tests/test_ai_dashboard_api_surface.py`, new focused UI/view tests, existing AI chart governance tests.
- Affected docs/specs: OpenSpec delta specs and tasks under this change.
- External systems: no new dependency; AI Base remains optional at `METRICS_AI_BASE_URL`, gcx mutation remains blocked unless Metrics precondition passes and approval policy allows it.
