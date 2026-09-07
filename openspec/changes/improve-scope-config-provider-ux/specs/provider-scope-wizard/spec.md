## ADDED Requirements

### Requirement: Scope Config exposes provider-aware setup context
Scope Config 页面 SHALL 在 scope identity 与 raw provider query 之前展示 provider/profile context，使用户可以区分 Dashboard display labels、provider binding authority 和 provider metadata discovery source。

#### Scenario: Existing scope has a resolved provider binding
- **WHEN** 用户打开已保存 scope 的 Scope Config 页面
- **THEN** 页面 SHALL 显示当前 binding status、profile id、provider id、provenance 和 blocker 摘要
- **AND** 页面 SHALL 提供返回 Scope Library 修改或确认 binding 的明确入口
- **AND** 页面 SHALL NOT 要求用户通过 mutable `Name`、`IP` 或 `Project label` 猜测 runtime provider/profile

#### Scenario: New scope has no persisted binding
- **WHEN** 用户打开新 scope draft 页面
- **THEN** 页面 SHALL 先显示 provider pillar 选择，使用户在 Jira、HSD-ES 或未来 provider 之间作出明确选择
- **AND** 页面 SHALL 显示 provider/profile 可以随 Save Draft 一起保存为 explicit binding，或在保存后从 Scope Library 修复
- **AND** 页面 SHALL 解释 Jira metadata refresh 仍可基于 draft query 预览候选项
- **AND** 页面 SHALL NOT 暗示 HSD-ES metadata 已由 Jira metadata refresh 支持

#### Scenario: Provider colors guide users
- **WHEN** Scope Config 展示 provider pillar、profile option 或 binding context
- **THEN** Jira SHALL 使用绿色视觉标记
- **AND** HSD-ES SHALL 使用蓝色视觉标记
- **AND** GitHub SHALL 使用紫色视觉标记
- **AND** other future providers SHALL use configurable neutral styling until a product color is declared

#### Scenario: Provider choice renders as folder-style card tabs
- **WHEN** Scope Config 展示 Jira、HSD-ES、GitHub 或其他 provider choices
- **THEN** provider choices SHALL render as folder-style card tabs attached to a single provider-colored content panel
- **AND** the selected tab SHALL show a small circular green check in its upper-left corner
- **AND** the selected tab SHALL visually connect to the content panel below instead of looking like a separate standalone card
- **AND** the same content panel SHALL contain the selected provider's binding context, profile selector and detail guidance
- **AND** the tabs SHALL expose tablist/tab/tabpanel semantics for assistive technology

### Requirement: Scope Config explains field purpose and readiness levels
Scope Config 页面 SHALL 把字段按 Save Draft、Enable Scope、Provider Metadata 和 Dashboard/AI Readiness 的不同用途呈现，使用户知道哪些字段是必填、哪些字段影响 metadata discovery、哪些字段影响 sync/calculation/evidence。

#### Scenario: User reviews required fields
- **WHEN** 用户打开 Scope Config 页面
- **THEN** 页面 SHALL 显示 Save Draft 至少需要 scope name、provider query、bug type、timezone 和 bucket granularity
- **AND** 页面 SHALL 显示 Enable Scope 还需要 open status、severity field、critical/high values、medium/low values，以及 fixed 或 closed status

#### Scenario: User reviews metadata dependencies
- **WHEN** 用户准备刷新 metadata
- **THEN** 页面 SHALL 明确说明 Jira metadata discovery 使用 JQL project、selected projects 和 bug type values
- **AND** 页面 SHALL 明确说明 `IP` 和 `Project label` 是 Dashboard display/binding hints，不直接驱动 Jira metadata discovery

### Requirement: Metadata options map to Dashboard semantic fields
Scope Config metadata panel SHALL 将 provider metadata 按类型分组，并为常用 Dashboard semantic fields 提供可见映射动作，而不是只展示未解释的 tag 列表。

#### Scenario: Metadata refresh returns grouped options
- **WHEN** provider metadata refresh 返回 projects、item types、statuses、priorities、resolutions、fields、components 或 versions
- **THEN** 页面 SHALL 按 metadata 类型分组显示候选项和数量
- **AND** 每组 SHALL 说明这些候选项通常用于哪些 Scope Config semantic fields

#### Scenario: User maps discovered values
- **WHEN** 用户看到 item type、status、priority、resolution 或 field metadata option
- **THEN** 页面 SHALL 提供链接或按钮，把该 option 带回 Scope Config 并追加到对应 semantic field，且不立即保存 scope
- **AND** mapping action SHALL 保留 raw text fallback，使用户仍可手工编辑 semantic fields

#### Scenario: Metadata provider is unsupported
- **WHEN** 当前 provider 或 profile 没有 metadata adapter
- **THEN** 页面 SHALL 展示 unsupported/configuration-required 状态和下一步入口
- **AND** 页面 SHALL NOT 混用 Jira metadata options 来配置 HSD-ES provider-owned saved query

### Requirement: Provider detail forms are generated from extensible templates
Scope Config 页面 SHALL 通过 provider setup template 管理 provider-specific detail rows、query labels、metadata support copy 和 default source hints，使 Jira、HSD-ES 和未来 GitHub 等 provider 可以扩展而不需要复制整页模板。

#### Scenario: User selects a provider pillar
- **WHEN** 用户在 Scope Config 选择一个 provider
- **THEN** 页面 SHALL 根据该 provider 的 setup template 显示 source query label、metadata support 状态、recommended detail rows 和 profile choices
- **AND** provider-specific detail SHALL NOT be hardcoded as unrelated free text around the page

#### Scenario: Future provider is registered
- **WHEN** GitHub 或其他 provider 被加入 provider setup template registry
- **THEN** Scope Config SHALL be able to list it as a provider pillar with provider-specific labels and guidance
- **AND** existing Jira/HSD-ES templates SHALL NOT need to be rewritten for the new provider
