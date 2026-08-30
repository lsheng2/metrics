## Purpose
Provider Scope Wizard 定义从 provider metadata 创建 dashboard scope 的用户流程。第一版以 Jira 为 provider adapter，并把 Intel HSD-ES 作为第二 provider 的对齐目标；交互、DTO 和保存语义必须保持 provider-neutral，使未来 HSD-ES、GitHub、Azure DevOps 或其他 work item provider 可以复用同一模式。

## Requirements

### Requirement: Guided scope creation flow
Scope Wizard SHALL 提供 guided flow，让用户通过 source mode、space、item type、fields、filters、review 和 save 步骤创建 semantic scope config，而不是直接填写 raw provider config。

#### Scenario: User creates Jira bug trend scope
- **WHEN** 用户选择 guided mode 并选择 Jira provider
- **THEN** wizard SHALL 引导用户选择 Jira project、issue type、semantic fields、filter values，并生成可预览的 provider query

#### Scenario: User creates HSD-ES defect scope
- **WHEN** 用户选择 guided mode 并选择 HSD-ES provider
- **THEN** wizard SHALL 引导用户选择 HSD-ES tenant/space、subject/item type、semantic fields、filter values，并生成可预览的 EQL provider query；HSD-ES 原生 field names SHALL 来自 adapter metadata 或 lookup APIs 而不是硬编码

#### Scenario: Provider lacks a wizard capability
- **WHEN** provider manifest 声明某个 wizard step 依赖的 metadata capability 不可用
- **THEN** wizard SHALL 隐藏或禁用对应步骤，并显示 manifest 中的 unsupported reason

### Requirement: Source modes
Scope Wizard SHALL 支持 Guided、Saved provider filter 和 Advanced query 三类 source mode，并明确区分 generated query 与 user-authored provider query。

#### Scenario: Guided mode query preview
- **WHEN** 用户在 guided mode 中选择 space、item type、fields 和 filters
- **THEN** 系统 SHALL 生成 provider query preview，但 SHALL NOT 要求用户手写 JQL 或 GitHub search query

#### Scenario: Advanced query mode
- **WHEN** 用户选择 advanced query mode
- **THEN** wizard SHALL 允许输入 provider-specific query，并通过 adapter validator 返回 syntax、permission 或 empty-result feedback

### Requirement: Contextual metadata discovery
Wizard SHALL 通过 provider、space、item type 和 field context 发现 field metadata、allowed values、users、statuses、areas 和 release targets。

#### Scenario: Field options depend on issue type
- **WHEN** 用户选择 Jira project 和 issue type
- **THEN** wizard SHALL 从 Jira adapter 获取该上下文下可用 fields 和 allowed values，而不是使用全局硬编码列表

#### Scenario: HSD-ES field options depend on record context
- **WHEN** 用户选择 HSD-ES tenant 和 subject
- **THEN** wizard SHALL 从 HSD-ES adapter 获取该上下文下可用 fields、lookup values、owners、states、components、families 或 releases；static lookup MAY use `schema/lookupvalue?lookup_group=...` and dynamic lookup MAY use EQL or HSD-ES lookup endpoints such as families/releases/components

#### Scenario: Filter control selection
- **WHEN** 一个 field metadata 表示枚举、用户、日期、文本或多选值
- **THEN** wizard SHALL 使用适合该 field shape 的 control，例如 checkbox、searchable multi-select、user picker、date range 或 text input

### Requirement: Semantic scope config is the source of truth
Wizard SHALL 保存 semantic scope config，而不是保存 UI 临时 tag 或仅保存生成出来的 provider query。

#### Scenario: Scope saved from guided mode
- **WHEN** 用户保存 guided scope
- **THEN** 系统 SHALL 保存 provider、space、item type、semantic field mappings、filter selections、generated query、timezone、bucket granularity、correlation keys when selected 和 config version hash

#### Scenario: Dashboard renders a saved scope
- **WHEN** Bug Trend dashboard 使用 saved scope
- **THEN** dashboard SHALL 从 saved semantic config 和 durable calculation artifacts 读取 truth，而不是重新解释 UI tag 或 live-query provider

### Requirement: Review step before save
Wizard SHALL 在保存前展示 human-readable summary、generated provider query、expected issue count 或 validation feedback，以及 semantic mapping summary。

#### Scenario: User reviews generated query
- **WHEN** 用户进入 review step
- **THEN** wizard SHALL 显示自然语言摘要和 provider query preview，使用户能在保存前发现 scope 过宽、过窄或 field mapping 错误

### Requirement: Phase 1 Jira implementation
Phase 1 SHALL 实现 Jira-backed provider metadata 和 Scope Wizard MVP，并保持 public API/DTO provider-neutral。

#### Scenario: First implementation wave
- **WHEN** Phase 1 开始执行
- **THEN** deliverables SHALL include `ProviderCapabilityManifest`、space search、item type listing、field listing、field option listing、Jira JQL query builder、Jira query validator、Scope Wizard pages/partials 和 UI smoke test

### Requirement: HSD-ES alignment before hardening the wizard
Scope Wizard SHALL reserve provider-neutral contracts for HSD-ES before Jira-only implementation hardens public DTOs, so Jira and HSD-ES can be configured and correlated as peers later.

#### Scenario: HSD-ES API details are not yet verified
- **WHEN** target HSD-ES tenant/subject rules have not been imported into the repo
- **THEN** implementation SHALL only define provider-neutral extension points and HSD-ES manifest placeholders, and SHALL NOT hardcode tenant-specific fields、subject names、required field rules、production write behavior or permission semantics that have not been confirmed for the target tenant
