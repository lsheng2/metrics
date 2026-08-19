# Dashboard Query Agent Handoff For AI Base

Date: 2026-08-19

Audience: Copilot or maintainers working in `D:\AIGC\Report_creater_agent\`.

## Purpose

This handoff proposes adding a new Dashboard Query Agent application profile to the existing AI base. The goal is to let users ask natural-language questions over the Metrics dashboard data, such as:

- "Show bugs newly opened in the last 10 days."
- "Which bugs are still open right now?"
- "List the top eight high-risk open defects."
- "Show a fixed versus new bug indicator chart for project 131600."

The Metrics dashboard repository remains the data authority. The AI base should provide an optional chat/model/tool orchestration shell and call the Metrics service through a small read-only query API.

This integration must be pluggable. Metrics must remain functionally complete without the AI base: source sync, fact normalization, indicator definitions, Grafana/dashboard rendering, deterministic drilldown, and ticket-list APIs should all work when Dashboard Query Agent is absent or disabled. The AI base adds natural-language access; it is not a required runtime dependency for the Metrics product.

## Current AI Base Facts Observed

The AI base already appears suitable for this integration:

- `config/app-profiles.json` registers multiple profiles: `sample_agent`, `report_creator`, and `soc_ai_driver`.
- `services/app-service/` is the shared FastAPI App Service.
- `template_runtime` provides `AgentRuntimeService`, backend registry, model gateway, and tool abstractions.
- Chat routes call `AgentRuntimeService.run_chat_turn(...)` with `runtime_tools`, `allowed_host_tools`, `approval_policy`, `mcp_servers`, and `skill_directories`.
- Host tools already use `RuntimeToolBinding`, Pydantic parameter models, permission modes, approval policy, and tool allowlists.

This means the Dashboard Query Agent can reuse the AI base instead of building a separate AI service inside the Metrics repository. Reuse is optional from the Metrics product perspective: Metrics exposes stable query APIs, and the AI base may plug into them as one client.

## Proposed Product Relationship

Use a split authority model:

| Concern | Owner |
| --- | --- |
| Chat UX, model routing, backend selection, runtime tools, approvals | AI base Dashboard Query Agent profile |
| Jira/GitHub/source sync, raw archive, normalized facts, deterministic query execution, authorization | Metrics dashboard service |
| Visual dashboard rendering | Grafana and/or Metrics UI |
| Source credentials | Metrics source modules only |

The AI base drives the conversation flow when the optional AI profile is installed. Metrics drives the data truth and authorization in all modes.

Two UX modes are valid:

1. AI-base-primary mode: users open the Dashboard Query Agent profile and ask questions directly.
2. Metrics-primary mode: users open the Metrics dashboard and use an embedded AI sidebar backed by the same AI base/query API.

Start with AI-base-primary mode for the AI add-on. It reuses the existing AI base profile system and avoids changing the Metrics UI first. This does not block the non-AI Metrics/Grafana path.

## Proposed New Profile

Add a fourth profile to `config/app-profiles.json`:

```json
"dashboard_query_agent": {
  "displayName": "Dashboard Query Agent",
  "shortName": "Dashboard AI",
  "tagline": "Natural-language analytics over delivery metrics",
  "description": "AI assistant for querying normalized Metrics dashboard facts and opening Grafana/dashboard views.",
  "iconGlyph": "D",
  "releaseChannel": "product",
  "serviceId": "dashboard-query-agent-app-service",
  "appServiceName": "Dashboard Query Agent App Service",
  "backendStartPort": 48300,
  "backendPortWindow": 20,
  "frontendPort": 48310,
  "frontendPortWindow": 5,
  "stackId": "dashboard-query-agent-dev-stack",
  "capabilities": {
    "ragEnabled": false,
    "dashboardQuery": true
  },
  "surfaces": {
    "defaultPage": "chat",
    "topNavPages": ["home", "chat", "settings"],
    "settingsTabs": ["appearance", "connections", "models", "advanced"],
    "deepLinkTargets": ["home", "chat", "settings"],
    "featureGates": ["dashboard-query"],
    "primaryWorkspaceMode": "context",
    "productSurfaceKey": null
  },
  "documentation": {
    "deltaDirectory": "docs/dashboard-query-agent",
    "commonManuals": ["docs/common/Multi-App-Profile-Architecture-Comparison-Manual.md"],
    "summary": "Dashboard Query Agent delta lives under docs/dashboard-query-agent."
  }
}
```

Exact ports and surface names can change to match AI-base conventions. The key requirement is that this profile is independent from `report_creator` and `soc_ai_driver` while reusing shared runtime infrastructure.

## Deferred AI Base Interface Extraction Candidates

These are candidate base-level improvements, not required first-spike work. The first Dashboard Query Agent implementation should use a narrow profile-specific read-only Metrics connector with the existing AI-base runtime tool conventions. Extract these abstractions into the base only after the dashboard connector proves the shape or after a second non-filesystem app needs the same pattern.

The candidates should still be reviewed because they may benefit Sample Agent, RCA, SoC-AI, and Dashboard Query Agent once proven.

### 1. Generalize Host Tools Into App Tool Catalog

Current host tools are filesystem-oriented (`read_file`, `view`, `edit_file`). Dashboard needs read-only business tools such as:

- `validate_metric_intent`
- `list_metric_tickets`
- `build_indicator_chart_spec`
- `build_grafana_link`
- `explain_bucket_membership`

Recommendation: introduce an App Tool Catalog abstraction where host filesystem tools are one family, not the whole model.

Suggested shape:

```text
AppToolCatalogEntry
  toolName
  appProfileId
  family
  sensitivity
  executionMode
  permissionMode
  authBoundary
  inputSchema
  outputSchema
  timeoutMs
  maxResultRows
  auditPolicy
```

Reason: RCA and SoC-AI will also need profile-specific tools that are not filesystem tools. A general App Tool Catalog avoids one-off tool registration paths per app.

### 2. Add App Tool Result Envelope

Tools should return structured results rather than only stringified JSON for the LLM.

Suggested shape:

```text
AppToolResultEnvelope
  status: ok | denied | validation_error | execution_error
  resultKind
  data
  warnings
  audit
  displayHints
  correlationId
```

Reason: Dashboard tools need to return ticket lists, chart specs, Grafana links, applied filters, warnings, and audit metadata. RCA and SoC-AI can reuse the same envelope for draft sections, report outlines, property completions, and patch reviews.

### 3. Add External Service Connector Contract

Dashboard Query Agent calls the Metrics service. This should be a general AI-base connector pattern.

Suggested shape:

```text
ExternalServiceConnector
  serviceId
  baseUrl
  authMode
  healthPath
  capabilitiesPath
  requestTimeoutMs
  retryPolicy
  redactionPolicy
```

Dashboard connector example:

```text
serviceId = metrics-dashboard
baseUrl = http://127.0.0.1:8002
authMode = service_token | mtls | loopback_trust_dev_only
capabilitiesPath = /api/ai-query/capabilities
```

Reason: RCA may later connect to Outlook, SharePoint, or a document store. SoC-AI may connect to spec services, code search, or validation pipelines. The connector abstraction should be shared.

### 4. Add App Tool Execution Context

Tool calls need profile/session/user context and correlation metadata.

Suggested shape:

```text
AppToolExecutionContext
  appProfileId
  sessionId
  userId
  workspaceId
  activeBackendId
  correlationId
  permissionMode
  operatorRoles
  serviceIdentity
```

When calling the Metrics service, send only the safe subset as headers or request metadata:

```text
X-App-Profile-Id
X-Session-Id
X-User-Id or pseudonymous user id
X-Correlation-Id
X-Service-Client-Id
```

Reason: Metrics must enforce scope authorization and audit every AI query. The same context propagation is useful for RCA and SoC-AI external tools.

### 5. Add Intent Execution Pattern

The dashboard-specific intent is `MetricQueryIntent`, but the pattern is generic.

Suggested base-level pattern:

```text
IntentExecutionPattern
  intentSchema
  validator
  executor
  renderer
  safetyPolicy
```

Profile-specific examples:

```text
Dashboard: MetricQueryIntent
RCA: ReportGenerationIntent
SoC-AI: IpCompletionIntent, PatchReviewIntent
```

Reason: The safe architecture is "LLM produces bounded intent JSON, deterministic code executes it." This is broadly reusable across apps.

### 6. Add Cross-Repo Contract Harness

The Dashboard Query Agent and Metrics service will live in separate repositories. They need shared contract checks.

Suggested convention:

```text
contracts/external-services/metrics-dashboard.ai-query.schema.json
```

Recommended tests:

- AI-base tool tests with mocked Metrics API responses.
- Metrics-side API tests for `MetricQueryIntent` validation and response shape.
- Schema snapshot compatibility checks in both repos.

Reason: Cross-repo DTO drift is the main integration risk.

## Metrics API Expected By AI Base

The Metrics repository should expose these read-only endpoints for optional AI clients and deterministic non-AI callers. They must not require the AI base to be installed:

```text
GET /api/ai-query/capabilities
  response: allowed sources, scopes, lifecycle states, result kinds, max limits

POST /api/ai-query/intent/validate
  request: MetricQueryIntent
  response: validated intent, normalized filters, warnings

POST /api/ai-query/tickets
  request: MetricQueryIntent where resultKind = ticket_list
  response: bounded ticket rows, applied filters, source links

POST /api/ai-query/chart-spec
  request: MetricQueryIntent where resultKind = indicator_chart | dashboard_link
  response: chart spec or Grafana URL with variables
```

AI-base tools should call only these endpoints. They should not call Jira, GitHub, Grafana data sources, or arbitrary SQL directly.

## MetricQueryIntent Contract

Initial shape:

```text
MetricQueryIntent
  resultKind: ticket_list | indicator_chart | dashboard_link
  sourceSystem: jira | github | any
  scopeId or sourceProjectKey
  indicatorDefinitionId
  definitionVersion
  timeWindow
  limit
  sort
  groupBy
```

Rules:

- The LLM may use natural-language vocabulary such as "open bugs" or "critical/high", but it must resolve that vocabulary through Metrics capabilities into `indicatorDefinitionId` and `definitionVersion`.
- The LLM produces `MetricQueryIntent`, not raw SQL or global business predicates.
- The Metrics service validates and normalizes the intent against Metrics-owned indicator definitions.
- The Metrics service enforces source/scope authorization, time bounds, row limits, and operator overrides.
- The AI base may explain validation errors but must not silently broaden the query.

## Auth And Authorization Boundary

The Metrics API must authenticate the AI-base client and enforce data authorization.

Minimum requirements:

| Concern | Requirement |
| --- | --- |
| Service identity | AI base calls as registered client `dashboard_query_agent`. |
| Credential type | Use non-source API credential or mTLS in production. `loopback_trust` is local-development only and must require loopback binding plus explicit dev/local profile. Do not use Jira/GitHub tokens. |
| User context | Carry user/session identity or explicit service-account context. |
| Scope authorization | Metrics checks `scopeId`, `sourceProjectKey`, and `sourceSystem`. |
| Overrides | Row/time limit overrides require operator/admin role. |
| Audit | Metrics logs caller, intent, scope, time window, row limit, result count, and override use. |
| Failure | Unauthorized or over-broad requests fail closed. |

## Suggested AI Base Implementation Nodes

1. Add `dashboard_query_agent` profile manifest entry.
2. Add profile docs under `docs/dashboard-query-agent/`.
3. Add a narrow profile-specific read-only Metrics connector first, using current AI-base tool conventions.
4. Add dashboard query tool bindings with Pydantic request models.
5. Add intent parsing service that emits `MetricQueryIntent` only after consulting mocked Metrics capabilities/indicator definitions.
6. Add mocked Metrics API tests for tool behavior.
7. Add schema snapshot or OpenAPI contract tests.
8. Add profile smoke test that asks a bounded natural-language query and receives a mocked ticket list/chart spec.
9. Extract generic App Tool Catalog only after this profile-specific connector proves the shape or a second non-filesystem app needs the same abstraction.

## Acceptance Criteria

- Dashboard Query Agent profile starts without affecting existing `sample_agent`, `report_creator`, or `soc_ai_driver` profiles.
- Metrics dashboard source sync, facts, Grafana/dashboard rendering, deterministic drilldown, and ticket-list APIs work when Dashboard Query Agent is not installed and the AI base is not running.
- Existing AI base backend/model settings remain shared and reusable.
- Dashboard tools are read-only and non-filesystem by default.
- Dashboard tools call only Metrics AI-query endpoints.
- No Jira/GitHub/source credentials are added to AI base profile files, dashboard JSON, SQL, fixtures, or logs.
- `MetricQueryIntent` examples are covered by unit tests.
- Metrics API response DTOs are mocked in AI-base tests and covered by contract snapshots.
- Tool results return structured envelopes with applied filters, indicator definition id/version, warnings, result count, and correlation id.

## Open Questions For AI Base Review

1. Should App Tool Catalog be a direct replacement for Host Tool Catalog, or should Host Tool Catalog remain and App Tool Catalog wrap it?
2. Should `dashboard_query_agent` use the existing Chat page only, or does it need a profile-specific dashboard result page?
3. Should External Service Connector live in `template_runtime` or `app/services`?
4. Which service-to-service auth mode best fits the AI base: service token, local mTLS, loopback trust, or profile-managed secret?
5. Should schema snapshots be generated from Metrics OpenAPI, hand-maintained JSON schema, or shared package artifacts?

## Recommended First Decision

Implement Dashboard Query Agent first with a narrow profile-specific read-only Metrics connector using the existing AI-base runtime tool conventions. Treat the generic App Tool Catalog as an extraction trigger after the dashboard connector proves the result envelope, execution context, and external service connector shape, or after a second non-filesystem app needs the same abstraction.

Reason: this preserves existing ownership paths and avoids turning the first dashboard query spike into a broad AI-base platform refactor before the Metrics-owned query API and indicator-definition contract are proven.