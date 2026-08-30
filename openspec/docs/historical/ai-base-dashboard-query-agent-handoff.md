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

## Current AI Base CLI And Tool Interface Findings

Follow-up exploration on 2026-08-24 checked `D:\AIGC\Report_creater_agent\` for a standard interface that could host an external CLI such as Grafana `gcx`.

Observed implementation facts:

- `services/app-service/template_runtime/tools.py` defines the backend-neutral tool abstraction: `ToolDeclaration`, `RuntimeToolBinding`, `ToolCallContext`, `ChatApprovalPolicy`, `RuntimeApprovalRequest`, and adapters for PydanticAI and Copilot SDK tool registration.
- `services/app-service/app/services/agent_runtime.py` already passes `runtime_tools`, `allowed_host_tools`, `approval_policy`, `mcp_servers`, and `skill_directories` into `AgentRuntimeService.run_chat_turn(...)` and `stream_chat_turn(...)`.
- `services/app-service/app/services/tool_governance.py` defines the current host tool catalog and governance preset model.
- `services/app-service/app/services/host_tool_binding.py` builds app-owned executable host tools from the activation summary.
- `services/app-service/app/services/host_tool_handlers.py` currently registers only filesystem tools: `read_file`, `view`, and `edit_file`.
- `services/app-service/app/services/host_tool_permission.py` provides per-tool permission checks and interactive approval hooks for framework-led approval where the backend supports it.
- `services/app-service/app/schemas.py` exposes `HostToolPolicy`, `HostToolCatalogEntry`, `HostToolPolicySummary`, `SandboxPolicyRef`, and `SessionActivationSummary` through the northbound API.
- `services/app-service/app/services/session_activation_governance.py` resolves active host tools and records sandbox status, but sandbox enforcement is still recorded-only for the current build.
- A later local AI-base review found `services/app-service/app/services/cli_runner/` with `StandardCliRunner`, registry bundle loading, typed argv templates, permission/dry-run proof checks, precondition hooks, tool binding, and a `.agent-skills/shared/dashboard-gcx/cli-bundle.json` package.
- `docs/common/Standard-CLI-Tool-Runner-Spec.md` in the AI-base checkout now describes the accepted direction: generic `StandardCliRunner` foundation first, `gcx` as the first disabled-by-default CLI instance, and Dashboard profile binding later.

Superseded finding: the initial exploration concluded that the AI base lacked a reusable external CLI runner. That is no longer the correct local baseline. The AI-base side now has a generic CLI runner foundation and a `dashboard-gcx` registry bundle; the remaining integration work is to bind those existing CLI tools into the Dashboard Query Agent profile, add Metrics-owned precondition/publication callbacks, and keep the tools disabled unless the Dashboard profile explicitly enables them.

Therefore the current state is:

| Capability | Status | Meaning for `gcx` |
| --- | --- | --- |
| Backend-neutral tool binding | Exists | `gcx` can be exposed as one or more `RuntimeToolBinding` tools. |
| Pydantic parameter schemas | Exists | `gcx` commands should use typed request models, not raw shell strings. |
| Host tool visibility and permission modes | Exists | Read-only and mutation commands can be separated by policy. |
| Approval policy | Exists, backend-dependent | Mutating `gcx` commands should require approval, with non-interactive fallback to blocked. |
| MCP projection | Exists | Future `gcx` MCP bridge is possible, but not needed for first spike. |
| Generic external CLI runner | Exists as `StandardCliRunner` foundation | Reuse it; do not add a parallel Dashboard-specific runner. |
| Effective OS sandbox | Not enforced in current build | Do not treat `SandboxPolicyRef` as sufficient protection for `gcx push/delete`. Use command allowlists and approval. |

The important distinction is now that AI base already has a standard tool-binding interface plus a generic CLI runner foundation. `gcx` should be integrated by reusing the existing `StandardCliRunner` and `dashboard-gcx` bundle, with Dashboard-specific profile enablement and Metrics-owned governance hooks layered on top.

## Grafana `gcx` Integration Decision

Grafana `gcx` should be treated as one CLI-backed tool family inside the AI base, not as a replacement for the Metrics API or Metrics chart governance. The target relationship is:

```text
User
  -> AI Base Dashboard Query Agent profile
      -> Metrics connector tools
          -> Metrics-owned AI query, chart catalog, chart data, and evidence APIs
      -> Grafana gcx connector tools
          -> gcx CLI
              -> Grafana dashboards, resources, datasources, snapshots, and observability APIs
```

In this model:

| Layer | Owner | Responsibility |
| --- | --- | --- |
| Metrics Django app | Metrics | Jira sync, durable history, scope semantics, calculation runs, chart definitions, evidence rows, audit, AI chart validation. |
| AI base Dashboard Query Agent | AI base | Chat UX, model routing, intent construction, tool selection, approval workflow, connector orchestration. |
| `gcx` connector | AI base tool adapter | Grafana resource operations, dashboard search, datasource discovery, validation, dry-run push, snapshot/render checks. |
| Grafana | Grafana | Rendering, layout, dashboard variables, datasource proxying, observability product UI. |

`gcx` is CLI-first from the integration perspective. It also has machine-readable outputs, command discovery, agent mode, resource files, raw API passthrough, and agent skills, but the stable integration boundary for the AI base should be subprocess execution of approved `gcx` commands with JSON/YAML output parsing.

### Proposed `gcx` Tool Family

Add a Dashboard Query Agent owned `gcx` tool family rather than exposing a raw shell. Each tool should map to one approved command shape:

| Tool | Backing command | Permission | Purpose |
| --- | --- | --- | --- |
| `grafana_gcx_check` | `gcx config check`, `gcx --version` | allow | Verify the configured `gcx` binary and Grafana context. |
| `grafana_gcx_command_catalog` | `gcx commands --flat -o json` | allow | Let the agent inspect supported `gcx` commands without web access. |
| `grafana_list_dashboards` | `gcx dashboards search ... -o json` or resources equivalent | allow | Find existing Grafana dashboards. |
| `grafana_list_datasources` | `gcx datasources list -o json` | allow | Discover Grafana datasources available to the configured context. |
| `grafana_validate_resources` | `gcx resources validate -p <path>` | allow | Validate Grafana resource files after Metrics artifact validation. |
| `grafana_dry_run_push_resources` | `gcx resources push -p <path> --dry-run` | ask | Preview Grafana resource mutations. |
| `grafana_push_resources` | `gcx resources push -p <path> --on-error abort` | ask | Apply approved Grafana resource mutations. |
| `grafana_snapshot_dashboard` | `gcx dashboards snapshot ...` | allow or ask by target | Produce visual evidence for dashboard rendering. |
| `grafana_query_signal` | `gcx metrics/logs/traces/profiles query ... -o json` | allow with bounded inputs | Query observability signals when debugging the dashboard runtime. |

The first implementation should not expose `gcx api` as an open-ended tool. If raw passthrough is needed, define a constrained wrapper with allowlisted paths, methods, and output limits.

### Required Guardrails For `gcx`

`gcx` commands must not bypass Metrics-owned governance. The connector should enforce these rules before any `gcx` process starts:

1. Set `GCX_TELEMETRY=disabled` or `DO_NOT_TRACK=1` in the subprocess environment by default.
2. Resolve the `gcx` executable path explicitly from profile settings, not from an untrusted prompt.
3. Reject raw shell strings. Use typed params that materialize a fixed argv list.
4. Restrict resource paths to approved workspace roots such as `ops/grafana/` or a dedicated generated artifact directory.
5. Run `scripts/validate_grafana_artifacts.py` before `gcx resources validate` or `gcx resources push` for Metrics-owned dashboard artifacts.
6. Require `gcx resources push --dry-run` before any real push.
7. Require interactive approval for mutation commands: `resources push`, `resources delete`, raw `api` with mutating HTTP methods, and any command that changes Cloud products.
8. Capture command, argv shape, target context, artifact path, exit code, stdout/stderr summary, correlation id, and approval id in AI base activity/audit.
9. Never pass Jira, GitHub, Intel PATs, or Metrics source credentials to `gcx`.
10. Keep `gcx` configured with Grafana service-account or operator-scoped Grafana credentials only.

### Correct AI Chart Flow With `gcx`

The safe flow is Metrics-first, `gcx`-second:

```text
User request
  -> AI Base asks Metrics for capabilities and chart catalog
  -> AI Base builds bounded MetricQueryIntent or AiChartDraftRequest
  -> Metrics validates semantic intent and chart spec
  -> Metrics materializes or exports a Grafana resource artifact
  -> Metrics artifact validator checks allowlist, metricsContract, evidence links, SQL/secret bans
  -> AI Base invokes gcx resources validate
  -> AI Base invokes gcx resources push --dry-run
  -> User or approver approves mutation
  -> AI Base invokes gcx resources push --on-error abort
  -> AI Base invokes snapshot/render check
  -> Metrics records chart publication/audit state
```

The unsafe flow is explicitly forbidden:

```text
User prompt
  -> LLM writes arbitrary Grafana JSON or SQL
  -> gcx resources push
```

That flow would let Grafana JSON or prompt text become a second business truth system and bypass `ChartDefinition`, `EvidenceContract`, `metricsContract`, artifact allowlists, parity gates, and audit.

### Minimal AI Base Implementation Shape

The smallest useful AI base change is a profile-specific binding around the existing generic runner, not a second Dashboard-only subprocess connector:

```text
services/app-service/app/services/dashboard_query/
  metrics_connector.py
  dashboard_tool_handlers.py
  dashboard_tool_models.py
  metrics_grafana_preconditions.py
```

The existing AI-base CLI runner should continue to own subprocess execution details:

```text
StandardCliRunner
  trusted executable refs
  fixed argv templates
  working-directory and path policy
  environment policy
  timeout and output caps
  permission and dry-run proof checks
  precondition and post-success callback hooks
```

`dashboard_tool_handlers.py` should expose or select the existing `dashboard-gcx` typed CLI tools through `RuntimeToolBinding`, following the CLI runner binding path, with Dashboard-specific permissions, Metrics artifact preconditions, and output envelopes.

Do not add a generic shell-like tool. `gcx` mutation safety depends on command-level allowlists, dry-run ordering, trusted executable refs, Metrics artifact validation, and profile-scoped activation.

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

`gcx` strengthens this extraction case, but it should not invert the sequence or duplicate the AI-base runner. First bind the existing `dashboard-gcx` CLI bundle as a Dashboard Query Agent owned tool family. Extract only missing catalog/result-envelope pieces after the binding proves which fields are truly shared across app tools.

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

The local AI-base checkout already has a generic CLI runner foundation. Treat the shape below as the conceptual contract that `StandardCliRunner` and registry bundles should satisfy, not as a request to add a second connector class:

```text
StandardCliRunner / CLI registry bundle
  cliId
  executablePath
  workingDirectory
  allowedArgvTemplates
  environmentPolicy
  timeoutMs
  outputParsers
  mutationPolicy
  auditPolicy
```

For Dashboard Query Agent, `gcx` is the first expected implementation of this pattern.

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
6. Bind the existing `dashboard-gcx` registry bundle and `StandardCliRunner` into the Dashboard Query Agent profile for approved read-only commands.
7. Bind gated mutation tools for `gcx resources push --dry-run` and approved push, with approval required before mutation.
8. Add mocked Metrics API tests for tool behavior.
9. Add or reuse `StandardCliRunner` and `dashboard-gcx` tests that prove fixed argv construction, telemetry opt-out, path allowlisting, timeout handling, JSON parsing, and mutation blocking.
10. Add schema snapshot or OpenAPI contract tests.
11. Add profile smoke test that asks a bounded natural-language query and receives a mocked ticket list/chart spec.
12. Add profile smoke test that validates a Metrics-generated Grafana artifact through the `gcx` connector without publishing it.
13. Extract only missing generic App Tool Catalog pieces after this profile binding proves the shape or a second non-filesystem app needs the same abstraction.

## Acceptance Criteria

- Dashboard Query Agent profile starts without affecting existing `sample_agent`, `report_creator`, or `soc_ai_driver` profiles.
- Metrics dashboard source sync, facts, Grafana/dashboard rendering, deterministic drilldown, and ticket-list APIs work when Dashboard Query Agent is not installed and the AI base is not running.
- Existing AI base backend/model settings remain shared and reusable.
- Dashboard tools are read-only and non-filesystem by default.
- Dashboard tools call only Metrics AI-query endpoints.
- Grafana tools call only approved `gcx` argv templates and never expose a raw shell command interface.
- `gcx` subprocesses default to telemetry disabled through environment policy.
- `gcx` mutation tools require dry-run first and interactive approval before real push/delete.
- Metrics-owned Grafana artifacts pass `scripts/validate_grafana_artifacts.py` before any `gcx resources validate` or push command runs.
- No Jira/GitHub/source credentials are added to AI base profile files, dashboard JSON, SQL, fixtures, or logs.
- `MetricQueryIntent` examples are covered by unit tests.
- Metrics API response DTOs are mocked in AI-base tests and covered by contract snapshots.
- Tool results return structured envelopes with applied filters, indicator definition id/version, warnings, result count, and correlation id.
- `gcx` tool results return structured envelopes with command category, target context, artifact path, exit code, parsed output, redacted stderr summary, approval id, and correlation id.

## Open Questions For AI Base Review

1. Should App Tool Catalog be a direct replacement for Host Tool Catalog, or should Host Tool Catalog remain and App Tool Catalog wrap it?
2. Should `dashboard_query_agent` use the existing Chat page only, or does it need a profile-specific dashboard result page?
3. Should External Service Connector live in `template_runtime` or `app/services`?
4. Which service-to-service auth mode best fits the AI base: service token, local mTLS, loopback trust, or profile-managed secret?
5. Should schema snapshots be generated from Metrics OpenAPI, hand-maintained JSON schema, or shared package artifacts?
6. Which existing `dashboard-gcx` bundle commands should the Dashboard Query Agent profile expose to the model by default, and which should remain operator/debug-only?
7. Which `gcx` operations should be allowed in local-only mode but denied in shared/cloud mode?
8. Should Grafana service-account credentials be stored in AI base profile settings, OS credential storage, or supplied only through deployment environment variables?
9. Should `gcx api` be disallowed completely at first, or exposed through a separate allowlisted-path wrapper for health and diagnostics only?
10. Which activity/audit events belong in AI base only, and which chart publication events must be mirrored back to Metrics audit?

## Recommended First Decision

Implement Dashboard Query Agent first with narrow profile-specific bindings: a read-only Metrics connector for semantic data, and the existing AI-base `StandardCliRunner` plus `dashboard-gcx` CLI bundle for Grafana operations. Both should use the existing AI-base `RuntimeToolBinding` conventions. Treat generic App Tool Catalog work as an extraction trigger after the dashboard profile proves the result envelope, execution context, external service connector shape, CLI allowlist, approval model, and audit shape, or after a second non-filesystem app needs the same abstraction.

Reason: this preserves existing ownership paths and avoids turning the first dashboard query spike into a broad AI-base platform refactor before the Metrics-owned query API, indicator-definition contract, Grafana artifact validator, and `gcx` command safety model are proven.
