## Overview

本变更把 Workbench 的 scope/profile/provider 状态从“UI 参数 + 兼容推断”升级为“后端 binding authority”。核心对象是 `ScopeProviderBinding`，核心服务是 `ScopeProviderBindingResolver`。

## Architecture

### Authority Layers

1. `ProjectProviderProfileRegistry`
   - 继续作为 provider profile authority。
   - 负责 profile -> provider、source population、field bindings、chart support、readiness。

2. `ScopeProviderBinding`
   - 作为 Dashboard saved scope 到 provider profile 的显式绑定。
   - 存储 `scope_id`、`profile_id`、`provider_id`、`status`、`provenance`、`blockers`。
   - 允许 legacy scopes 在 backfill 后获得显式 binding。

3. `ScopeProviderBindingResolver`
   - 输入 `scope_id` 和可选 legacy query hints。
   - 输出 canonical binding。
   - 优先级：explicit binding > safe compatibility match > configuration_required。
   - 不允许 URL/localStorage/AI host action 覆盖 explicit binding。

4. `WorkbenchPageQueryState`
   - 保留 canonical UI query：`scope_id`、range、chart、run/snapshot、bucket/series、list filters。
   - `profile_id/provider_id/workspace_key` 为 resolver projection，不是 primary toolbar authority。

## Data Model

建议新增 `BugTrendScopeProviderBinding` model，而不是直接把 profile fields 混入 `JiraScopeConfig`：

- `scope`: one-to-one to `JiraScopeConfig`
- `profile_id`: provider profile key
- `provider_id`: resolved provider id
- `status`: `explicit`, `compatibility`, `configuration_required`, `ambiguous`, `disabled`
- `provenance`: JSON, records source such as `manual`, `seed`, `registry_profile_id`, `source_query_hash`, `legacy_jira_scope`
- `blockers`: JSON list
- `created_at`, `updated_at`

原因：scope config 仍是 bug trend semantic authority，binding 是 provider platform boundary，不应把两者混成一个可变表单字段。

## Runtime Flow

1. Workbench request arrives with URL query.
2. `WorkbenchPageQueryState.from_query()` parses raw query for canonical UI fields.
3. `WorkbenchView._state()` resolves selected/default `scope_id`.
4. `ScopeProviderBindingResolver.resolve(scope_id)` returns canonical binding.
5. View projects binding into state/context.
6. Workbench toolbar renders `profile/provider` as readonly derived fields.
7. Scope change submits only `scope_id/range/chart` fields; pushed URL omits derived profile/provider.

## Compatibility

- Existing URLs containing `profile_id/provider_id` remain loadable.
- If `scope_id` exists, stale profile/provider values are ignored.
- If `scope_id` is missing, legacy default behavior can still choose the scope matching `profile_id`, then binding resolution owns the final provider/profile.
- Compatibility matching is allowed only as a migration bridge and must mark provenance.

## Validation

- Model/service tests:
  - explicit binding wins over stale URL hints.
  - display-name changes do not change binding.
  - ambiguous compatibility match returns configuration_required/ambiguous.
  - legacy Jira scope can be backfilled to explicit binding.
- View/browser tests:
  - toolbar profile/provider have no `name`.
  - scope change pushes canonical URL without derived profile/provider.
  - AI context and evidence hidden fields use resolver output.
- E2E UI:
  - Start full stack.
  - Select Demo STDEL scope.
  - Confirm Profile/Provider, evidence scope, AI context and URL are canonical.

## Alternatives Considered

- Add `profile_id/provider_id` directly to `JiraScopeConfig`.
  - Rejected as the long-term default because it mixes bug trend semantic config with provider profile authority.
- Keep compatibility resolver only.
  - Rejected because mutable scope names and JQL text changes can reintroduce stale or ambiguous binding bugs.
- Let UI own binding state.
  - Rejected because browser state is not authoritative and has repeatedly produced stale profile/provider values.
