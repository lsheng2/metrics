# Spec Delta

## ADDED Requirements

### Requirement: Session context boundary is provider and project scoped
`metrics.workbench` context provider 解析 `ContextRef` 时 SHALL 给出会话边界：允许的 provider id、profile id、project label、range mode 和 data-block id。每个 Metrics tool SHALL 按 `ctx.context_ref` 解析出的边界校验参数，越界的调用 SHALL 返回 `CONTEXT_BOUNDARY_VIOLATION`，且 SHALL NOT 读取或写入 Metrics 数据。

#### Scenario: Context boundary is included
- **WHEN** context provider 解析一个 `ContextRef`
- **THEN** 结果 SHALL 包含允许的 provider id、profile id、project label、range mode 和 data-block id

#### Scenario: Tool call crosses the session boundary
- **WHEN** tool 调用的参数引用会话边界之外的 provider、profile 或 project
- **THEN** tool SHALL 返回 `CONTEXT_BOUNDARY_VIOLATION`，SHALL NOT 读取或写入 Metrics 数据

#### Scenario: Session has no bound context
- **WHEN** 需要 scope 的 tool 在一个没有 `ContextRef` 的会话中被调用
- **THEN** tool SHALL 返回结构化错误，提示从 workbench 的 scope 打开聊天
- **AND** tool SHALL NOT 默认使用任何 profile

## MODIFIED Requirements

### Requirement: Metrics exposes workspace context bundles
Metrics SHALL expose a context bundle for a selected provider/project/profile. 该 bundle SHALL 由 `metrics.workbench` context provider 每次从会话的 `ContextRef` 解析，SHALL NOT 存入 AI 运行时的 workspace 或文件存储。

#### Scenario: HSD-ES workspace context is requested
- **WHEN** context provider 解析一个绑定 profile `nvu-ttl-hsdes` 的 `ContextRef`
- **THEN** Metrics SHALL return boundary metadata, provider profile metadata, canonical field mappings, data-block catalog, Grafana render constraints and Metrics help content
- **THEN** the bundle SHALL identify `provider_id=hsdes`, `profile_id=nvu-ttl-hsdes` and project labels for NVU
- **THEN** the bundle SHALL include fields `context_ref`, `bundle_version`, `boundary` and `files`

#### Scenario: Jira workspace context is requested
- **WHEN** context provider 解析一个绑定 profile `chiplet-2a-jira` 的 `ContextRef`
- **THEN** Metrics SHALL return the same bundle shape with `provider_id=jira` and Jira project labels
- **THEN** AI-facing fields SHALL use Metrics canonical names rather than Jira custom field ids

#### Scenario: Scope binding is unresolved
- **WHEN** `ContextRef` 中的 scope binding key 无法解析为当前可用的 profile，例如 binding 已删除或需要配置
- **THEN** context provider SHALL 返回 `binding_unresolved` 和 Scope Library 的修复入口
- **AND** context provider SHALL NOT 返回之前 scope 的数据

### Requirement: AI Base chat is grounded by Metrics workspace context
Metrics SHALL provide enough context through the `metrics.workbench` context provider for embedded chat sessions to answer project boundary、canonical field、data block 和 Grafana constraint questions without guessing provider-native details.

#### Scenario: User asks available data blocks
- **WHEN** a chat session is bound to a `metrics.workbench` `ContextRef`
- **THEN** the AI answer SHALL use the resolved context bundle data-block catalog to list available block ids, grain, canonical dimensions, measures, allowed transforms and evidence capability
- **THEN** the answer SHALL NOT introduce provider-native fields as chart-authoring fields unless the context bundle marks them as provenance examples only

#### Scenario: User asks workspace boundary
- **WHEN** a user asks what provider/project/profile the current chat context represents
- **THEN** the AI answer SHALL cite the resolved boundary context and identify allowed provider ids, profile ids, project labels, range modes and permitted data blocks
- **THEN** the answer SHALL not claim access outside that boundary

#### Scenario: Context is incomplete
- **WHEN** the resolved context does not include data-block catalog, canonical field map or boundary metadata
- **THEN** AI SHALL report the missing context and ask the user to select or repair the scope binding instead of inventing chart fields or provider semantics

## REMOVED Requirements

### Requirement: Workspace boundary is provider and project scoped
**Reason**: 原 scenario "Connector invocation crosses workspace boundary" 以 connector 和 AI Base workspace 为前提，二者都已删除。
**Migration**: 由 "Session context boundary is provider and project scoped" 承接；边界改为由 `ContextRef` 解析，越界检查由 Metrics tool 执行。
