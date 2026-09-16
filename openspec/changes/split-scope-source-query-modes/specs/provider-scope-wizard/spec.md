## MODIFIED Requirements

### Requirement: Source modes
Scope Wizard SHALL support provider-specific source modes and clearly distinguish a generated query from a user-authored provider query. For Jira-backed Scope Config, the page SHALL present `Custom JQL` and `Query Builder` as mutually exclusive source authoring modes for the saved scope.

#### Scenario: Guided mode query preview
- **WHEN** 用户在 guided mode 中选择 space、item type、fields 和 filters
- **THEN** 系统 SHALL 生成 provider query preview，但 SHALL NOT 要求用户手写 JQL 或 GitHub search query

#### Scenario: Advanced query mode
- **WHEN** 用户选择 advanced query mode
- **THEN** wizard SHALL 允许输入 provider-specific query，并通过 adapter validator 返回 syntax、permission 或 empty-result feedback

#### Scenario: User chooses Custom JQL mode
- **WHEN** 用户在 Jira-backed Scope Config 中选择 `Custom JQL`
- **THEN** 页面 SHALL 允许用户输入 provider-specific JQL
- **AND** 保存时 SHALL treat 该 JQL as the only runtime source query for the saved scope
- **AND** Query Builder selections SHALL NOT be applied as an additional hidden filter

#### Scenario: User chooses Query Builder mode
- **WHEN** 用户在 Jira-backed Scope Config 中选择 `Query Builder`
- **THEN** 页面 SHALL 引导用户选择 Jira project、issue type 和 supported filter values
- **AND** 系统 SHALL 生成可预览的 JQL
- **AND** 保存时 SHALL use the generated JQL as the runtime source query for the saved scope
- **AND** raw custom JQL SHALL NOT be applied in parallel

#### Scenario: Saved provider filter is provider-profile owned
- **WHEN** source population is owned by a provider profile or saved provider reference instead of this Scope Config page
- **THEN** Scope Config SHALL show that source provenance as provider/profile context
- **AND** Scope Config SHALL NOT expose it as a third simultaneous Jira source filter on the same form

### Requirement: Contextual metadata discovery
Wizard SHALL 通过 provider、space、item type 和 field context 发现 field metadata、allowed values、users、statuses、areas 和 release targets，并 SHALL clearly mark metadata discovery context as advisory unless it is part of the selected source mode.

#### Scenario: Field options depend on issue type
- **WHEN** 用户选择 Jira project 和 issue type
- **THEN** wizard SHALL 从 Jira adapter 获取该上下文下可用 fields 和 allowed values，而不是使用全局硬编码列表

#### Scenario: HSD-ES field options depend on record context
- **WHEN** 用户选择 HSD-ES tenant 和 subject
- **THEN** wizard SHALL 从 HSD-ES adapter 获取该上下文下可用 fields、lookup values、owners、states、components、families 或 releases；static lookup MAY use `schema/lookupvalue?lookup_group=...` and dynamic lookup MAY use EQL or HSD-ES lookup endpoints such as families/releases/components

#### Scenario: Filter control selection
- **WHEN** 一个 field metadata 表示枚举、用户、日期、文本或多选值
- **THEN** wizard SHALL 使用适合该 field shape 的 control，例如 checkbox、searchable multi-select、user picker、date range 或 text input

#### Scenario: Metadata context is not a hidden runtime filter
- **WHEN** 用户在 `Custom JQL` mode 中填写 Selected Jira projects、issue types 或 metadata refresh context
- **THEN** 页面 SHALL 使用这些值刷新 metadata candidates
- **AND** 保存的 runtime source query SHALL remain the custom JQL unless the user switches to `Query Builder`
- **AND** 页面 SHALL label this distinction near the metadata controls

### Requirement: Semantic scope config is the source of truth
Wizard SHALL 保存 semantic scope config，而不是保存 UI 临时 tag 或仅保存生成出来的 provider query。For Jira-backed Scope Config, the saved semantic config SHALL include the selected source mode and the final source query used by sync/calculation.

#### Scenario: Scope saved from guided mode
- **WHEN** 用户保存 guided scope
- **THEN** 系统 SHALL 保存 provider、space、item type、semantic field mappings、filter selections、generated query、timezone、bucket granularity、correlation keys when selected 和 config version hash

#### Scenario: Scope saved from Query Builder mode
- **WHEN** 用户保存 Query Builder scope
- **THEN** 系统 SHALL 保存 provider、space、item type、semantic field mappings、filter selections、generated query、timezone、bucket granularity、correlation keys when selected 和 config version hash
- **AND** later refreshes SHALL reconstruct the page with Query Builder selected and the same builder selections visible

#### Scenario: Scope saved from Custom JQL mode
- **WHEN** 用户保存 Custom JQL scope
- **THEN** 系统 SHALL 保存 user-authored JQL、semantic field mappings、metadata discovery context when present、timezone、bucket granularity 和 config version hash
- **AND** later refreshes SHALL reconstruct the page with Custom JQL selected

#### Scenario: Dashboard renders a saved scope
- **WHEN** Bug Trend dashboard 使用 saved scope
- **THEN** dashboard SHALL 从 saved semantic config 和 durable calculation artifacts 读取 truth，而不是重新解释 UI tag、metadata options 或 live-query provider

## ADDED Requirements

### Requirement: Scope Config separates source, metadata and mappings
Scope Config 页面 SHALL visually and semantically separate source population, metadata discovery context, semantic mapping, and optional display fields so operators can understand what affects ticket membership versus what affects classification or display.

#### Scenario: User scans the source section
- **WHEN** 用户打开 Scope Config 页面
- **THEN** 页面 SHALL identify the source mode as the single authority for which Jira tickets enter the scope
- **AND** the source section SHALL show either Custom JQL controls or Query Builder controls, not both as active inputs

#### Scenario: User scans the mapping section
- **WHEN** 用户查看 semantic mapping fields
- **THEN** 页面 SHALL describe these controls as interpreting fetched tickets for bug trend calculation, evidence and display
- **AND** 页面 SHALL NOT imply these mappings independently query additional Jira tickets

#### Scenario: User adds optional display fields
- **WHEN** 用户配置 optional display fields such as Program Increment、Epic Link、Affected Products、Environment Found、Security Level 或 Labels
- **THEN** 页面 SHALL treat them as persisted display/evidence fields unless they are explicitly selected in Query Builder filters
- **AND** 页面 SHALL NOT silently add them to Custom JQL
