## Why

当前 Metrics dashboard 已经具备 provider profile、chart recipe、Grafana render config、AI draft validator 和 gcx publication precondition 的基础能力。下一步要把 `D:\AIGC\Report_creater_agent\` 作为通用 AI platform 接入 dashboard，必须先定义 Dashboard app 与 AI Base 之间的 northbound/sidecar contract，避免 AI Base、gcx、Grafana 或 dashboard backend 之间出现重复语义、重复审批或绕过 Metrics validator 的路径。

## What Changes

- 新增 Dashboard AI Sidecar Integration capability，定义 dashboard app 如何启动、发现、调用和降级 AI Base。
- 定义 AI Base 作为第 4 个 app profile：`dashboard_query_agent`，复用现有 profile manifest、chat runtime、tool governance、approval、StandardCliRunner 和 extension bundle 机制。
- 定义 Dashboard-to-AI-Base northbound contract：Run API/Chat API、context envelope、tool activation、artifact/result envelope、error/approval/event stream。
- 定义 AI-Base-to-Metrics southbound contract：Metrics catalog、intent validation、draft render config validation、provider evidence、gcx precondition 和 publication/audit callback。
- 明确 AI Base platform-level enhancement 建议：generic connector registry、app tool result envelope、profile-scoped extension bundles、tool precondition/callback proof store、run lifecycle、cross-repo contract tests。
- 不在本 change 中直接修改 `D:\AIGC\Report_creater_agent\`；本 change 在 dashboard repo 中产出可 review 的集成规格、实施任务和可转发给 AI Base owner/author 的 prompt。

## Capabilities

### New Capabilities

- `dashboard-ai-sidecar-integration`: 定义 Metrics dashboard 与 AI Base / `dashboard_query_agent` / `gcx` 的 sidecar integration、ownership boundary、contract、fallback 和 validation workflow。

### Modified Capabilities

无。本 change 先新增 sidecar integration capability；它依赖前序 change 中的 Metrics-side AI composition 与 Grafana render config contract，但不要求在本 change 中修改尚未 archive 的 main spec。

## Impact

- Affected future code: Metrics AI endpoints/views, `bug_metrics/app/api/ai_dashboard_composition.py`, Grafana artifact validation scripts, optional AI sidecar launch/config, future UI sidebar/App/Scenes integration.
- Affected external system: AI Base repo `D:\AIGC\Report_creater_agent\` as reusable platform; especially app profile manifest, Run API, extension bundle loader, `StandardCliRunner`, tool governance, approval service, result envelope and diagnostics.
- Security impact: no Jira/HSD-ES/source credentials are sent to AI Base; AI Base receives only Metrics-approved catalog/facts/drafts and invokes gcx only after Metrics precondition.
- Compatibility impact: non-AI dashboard remains fully functional when AI Base is absent, disabled, unhealthy or not configured.
