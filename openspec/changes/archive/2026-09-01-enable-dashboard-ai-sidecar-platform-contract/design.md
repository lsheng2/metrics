## Context

See `proposal.md` for motivation. The dashboard repo now owns provider profile registry, chart recipe compatibility, render config generation, AI intent validation, and gcx publication precondition. The AI Base repo at `D:\AIGC\Report_creater_agent\` already has shared foundations that are directly relevant:

- `config/app-profiles.json` currently defines `sample_agent`, `report_creator`, and `soc_ai_driver`; `dashboard_query_agent` is not yet registered.
- `services/app-service/app/profile_manifest.py` parses profile manifests and surfaces feature gates, navigation, service id, ports, documentation bindings and desktop identity.
- `services/app-service/app/config.py` already has `cli_tool_bundle_paths`, `cli_tool_visible_set`, and trusted executable refs for CLI tools.
- `services/app-service/app/services/cli_runner/` exists with `CliToolDefinition`, `CliCommandTemplate`, `StandardCliRunner`, bundle loading, registry, permission checks, preconditions, callbacks, redaction and RuntimeToolBinding projection.
- `.agent-skills/shared/dashboard-gcx/cli-bundle.json` already declares disabled-by-default `gcx` templates, including version/config check, datasource list, resource validate, dry-run push and push.
- `build_cli_tool_runtime()` currently constructs `StandardCliRunner` from visible settings and trusted executable refs, but does not wire a durable dry-run proof store, Metrics precondition executor, or publication callback executor.
- `docs/common/AI-Base-Run-Interface-Spec.md` defines the intended external Run API, but code search did not show `/api/runs` as an implemented generic runner route yet.

## Goals / Non-Goals

**Goals:**

- Make Dashboard the fourth AI Base app profile without changing Sample/RCA/SoC behavior.
- Define a clean Dashboard-to-AI-Base northbound contract for sidecar chat/run requests and AI UI state.
- Define the AI-Base-to-Metrics southbound contract for catalog, intent validation, render draft validation, evidence and gcx precondition.
- Reuse AI Base shared extension lanes, StandardCliRunner, RuntimeToolBinding, approval and diagnostics instead of creating Dashboard-only infrastructure.
- Identify generic AI Base platform enhancements that benefit Dashboard plus future apps.

**Non-Goals:**

- Do not move Jira/HSD-ES credentials, provider facts, chart semantics or Metrics validators into AI Base.
- Do not let AI Base patch Metrics backend code/API or author unvalidated Grafana JSON as production truth.
- Do not implement Dashboard-specific code in AI Base inside this dashboard-repo planning change.
- Do not expose raw shell, raw `gcx api`, arbitrary SQL or arbitrary provider queries.

## Decisions

### Decision 1: AI Base is the chat/orchestration platform, Metrics remains semantic authority

Dashboard sends bounded context and receives structured results. Metrics owns provider profiles, chart recipes, facts, aggregates, evidence, validators and publication audit.

Alternative considered: let AI Base own dashboard semantics and call Jira/HSD-ES/Grafana directly. Rejected because it would duplicate provider credentials, field mappings and chart semantics.

### Decision 2: Dashboard uses a `dashboard_query_agent` app profile

AI Base should add a fourth manifest entry rather than overloading `report_creator` or `sample_agent`. This keeps feature gates, ports, docs, desktop identity and extension bundles profile-scoped.

Alternative considered: run Dashboard inside Report Creator profile. Rejected because RCA workflow/tool defaults would leak into Dashboard and make policy debugging harder.

### Decision 3: Use two explicit integration directions

Northbound:

```text
Dashboard app -> AI Base
  sidecar handshake
  chat/run request
  events/result/artifacts
```

Southbound:

```text
AI Base -> Metrics app
  catalog/profile/readiness
  intent validation
  draft render config validation
  evidence/query context
  gcx publication precondition
  publication/audit callback
```

Alternative considered: Dashboard only embeds AI Base chat and lets the agent discover APIs from docs. Rejected because it is less deterministic and harder to validate.

### Decision 4: Prefer Run API for product workflows, Chat API for exploratory UX

For a dashboard sidecar embedded in Grafana/Metrics UI, interactive user Q&A can start with the existing Chat API. Repeatable operations such as “generate chart draft”, “validate draft”, “dry-run publish”, and “snapshot dashboard” should move to AI Base Run API when it is implemented, because Run gives durable lifecycle, events, artifacts, cancellation and idempotency.

Alternative considered: use Chat API for everything. Accepted only as a bridge because chat turns do not fully model long-running operations, resumable status, artifacts or CI/scheduler use.

### Decision 5: gcx remains a CLI tool lane behind Metrics preconditions

The existing `dashboard-gcx` bundle is directionally correct: disabled by default, typed argv templates, no raw shell, telemetry disabled, no open-ended API passthrough. Before production mutation, AI Base must wire Metrics precondition executor, durable dry-run proof recording, approval, and post-success callback.

Alternative considered: let Metrics shell out to `gcx`. Rejected for now because AI Base already has the generic CLI runner foundation and should own tool execution UX/governance.

### Decision 6: Add a generic connector lane, not a Dashboard-only HTTP client

Dashboard needs a Metrics connector, but the same pattern will help RCA, SoC and future apps. AI Base should model connector definitions as profile-scoped extension lane entries with auth refs, base URL, health, request schemas, response envelopes, redaction and policy.

Alternative considered: add hand-coded dashboard HTTP calls in a Dashboard profile service. Rejected because the owner wants AI Base to become a reusable platform.

## AI Base Platform Enhancement Recommendations

1. Implement `dashboard_query_agent` in `config/app-profiles.json` with Dashboard-specific ports, feature gates and docs.
2. Add a generic `connectors` lane parallel to `cliTools`, with typed request/response schemas and service identity.
3. Add a shared `AppToolResultEnvelope` for connectors, CLI tools and workflow adapters: status, data, warnings, audit, artifacts, correlation id and display hints.
4. Wire `StandardCliRunner` activation with durable dry-run proof store, precondition executor and callback executor; current activation creates the runner without those dependencies.
5. Teach `StandardCliRunner` to record dry-run proof after successful `write_preview` commands that satisfy a mutation’s `dryRunCommandId`.
6. Add `Run API` implementation for profile-scoped workflows if it is still docs-only; Dashboard publish/snapshot flows should not rely only on chat turns.
7. Add profile-scoped extension diagnostics: registered, available, activated, executable, blocked reason, trusted executable state and model visibility.
8. Add cross-repo contract-test convention so Dashboard can publish JSON schema/OpenAPI snapshots and AI Base can run mocked connector tests against them.
9. Keep `gcx` command catalog operator/debug only by default, because command discovery output is not the same as an approved executable registry.
10. Add a sidecar lifecycle/handshake helper in AI Base or launcher scripts so external apps can reliably probe service id, instance token, profile id and capability readiness.

## Risks / Trade-offs

- [Risk] AI Base connector lane may duplicate existing host tools if modeled too narrowly. → Mitigation: define connector as a distinct lane for external service contracts, not filesystem tools.
- [Risk] gcx mutation safety can be bypassed if approval and dry-run proof are not durable. → Mitigation: require proof store and precondition executor at activation, and test that mutation blocks without both.
- [Risk] Dashboard prompt requests may expect arbitrary new metrics. → Mitigation: Metrics returns `needs_metric_recipe`; AI explains that semantic work must be added to Metrics first.
- [Risk] Profile-specific code leaks into shared AI Base runtime. → Mitigation: use manifest/extension bundles and keep Dashboard-specific behavior in `dashboard_query_agent` profile bindings.
- [Risk] Cross-repo DTO drift. → Mitigation: add schema snapshots and contract tests in both repos.

## Migration Plan

1. Finish and archive `generalize-provider-profile-and-grafana-render-config` in the dashboard repo.
2. In AI Base, add `dashboard_query_agent` manifest entry and docs delta.
3. Add dashboard sidecar config in Metrics: AI base base URL, expected `serviceId`, optional `instanceToken`, and enable/disable knob.
4. Add Metrics connector endpoint/client contract for AI Base: catalog, intent validate, draft validate, evidence context and precondition.
5. Wire AI Base connector and `dashboard-gcx` extension bundle for Dashboard profile only.
6. Add a first HSD-ES try run: supported series draft, unsupported `new_critical`, gcx precondition pass/fail.
7. Add optional Grafana publish dry-run after precondition proof and approval.
8. Extend same workflow to Jira profile once the HSD-ES sidecar try run is validated.

Rollback strategy: turn off Dashboard AI sidecar config. Metrics dashboard remains non-AI functional; AI Base profile/bundle can remain registered but inactive.

## Dashboard-side Implemented Connector Surface

Dashboard repo exposes the Metrics-owned connector routes under `/api/ai-dashboard/`:

- `catalog/` 返回 provider profile、chart recipe、allowed series、range mode、limit、security policy，不暴露 provider credential 或 native query text。
- `intent/validate/` 接收 `DashboardCompositionIntent`，对已支持 series 返回 validated draft render config；对未定义 semantic（例如 `new_critical`）返回 `needs_metric_recipe`。
- `render-config/validate/` 使用与开发者提交 Grafana artifact 相同的 render config validator 和 generated dashboard validator，返回 preview metadata。
- `gcx/precondition/` 在 AI Base/gcx mutation 前执行 Metrics precondition，invalid draft 必须在 Metrics 侧 blocked。
- `gcx/publication-callback/` 在 AI Base/gcx mutation 后记录 Metrics audit metadata，保留 correlation id、artifact ref、proof id 和 mutation status。
- `context/` 返回 selected profile/range/chart 的安全 context，包含 profile mapping version、chart recipe version、fact snapshot/freshness 等 provenance，并在 HTTP AI-facing 层移除敏感 provider/native-query 字段。

Dashboard repo 同时发布 `contracts/metrics-connector-operations.json` 作为 AI Base mocked connector tests 的起点；AI Base 侧仍需把这些 operations 注册成 profile-scoped connector/tool declarations。

## Open Questions

- Should the first Dashboard sidecar UI live inside Grafana App/Scenes, Metrics UI sidebar, or AI Base primary chat page?
- Should Dashboard-to-AI Base use the existing Chat API first, or wait for the generic Run API implementation for all non-chat operations?
- What production auth mode should Dashboard use when calling AI Base: service token, mTLS, loopback dev trust, or enterprise SSO-bound user context?
- Should `gcx` publish be enabled in local development only at first, with shared Grafana publish requiring CI or admin approval?
