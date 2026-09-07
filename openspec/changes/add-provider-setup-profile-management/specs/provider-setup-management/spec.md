## Purpose

Provider Setup Management 定义客户自助创建、维护和迁移 provider profiles 的后台工作流。它让低上下文用户先选择 provider，再完成 source、metadata、field mapping、readiness 和 scope handoff，而不是手写 JSON 或混淆 profile 与 scope。

## ADDED Requirements

### Requirement: Provider Setup is a first-class navigation surface
系统 SHALL 提供 Provider Setup 菜单入口和页面，使用户可以像管理 Scope 一样管理 Provider Profile，并清楚看到 Provider、Profile、Scope 和 Binding 的关系。

#### Scenario: User opens Provider Setup from navigation
- **WHEN** 用户打开 Dashboard 主菜单
- **THEN** 系统 SHALL 提供 `Provider Setup` 或等价菜单入口
- **AND** 入口 SHALL 与 Scope Library、Data Health 和 AI Workflow 的视觉风格一致
- **AND** 页面 SHALL 说明 Profile 是 provider/source/mapping authority，Scope 是 Dashboard calculation/use-case view，Binding 连接二者

#### Scenario: Low-context user starts setup
- **WHEN** 用户打开 Provider Setup
- **THEN** 页面 SHALL 先展示 provider-first 选择，而不是先展示 JSON、raw field map 或高级配置
- **AND** Jira SHALL 使用绿色视觉标记
- **AND** HSD-ES SHALL 使用蓝色视觉标记
- **AND** GitHub SHALL 使用紫色视觉标记
- **AND** other future providers SHALL use configurable neutral styling until a product color is declared

#### Scenario: User creates or edits one profile
- **WHEN** 用户 selects New Profile or Edit for an existing profile
- **THEN** system SHALL open a dedicated Provider Profile Config editor instead of appending the editor below the profile inventory
- **AND** the editor SHALL keep Provider Setup in the breadcrumb/back action so users can return to the inventory
- **AND** the inventory table SHALL NOT compete with the active profile form on the same screen

#### Scenario: Provider editor uses one provider-colored frame
- **WHEN** the Provider Profile Config editor renders provider tabs, profile identity, advanced JSON and bottom actions
- **THEN** the selected provider color frame SHALL contain the tabs, tab body, advanced JSON configuration, action buttons and hash line
- **AND** nested context/detail panels inside that frame SHALL use neutral thin borders rather than repeating a provider-colored left rail
- **AND** the selected provider color SHALL remain visible through the outer frame and the active provider tab

### Requirement: Provider setup flow is template-driven
Provider Setup SHALL 使用 provider setup template 定义每个 provider 的表单段、字段标签、metadata capability、默认帮助文案、验证步骤和下一步动作，使 Jira、HSD-ES 和未来 GitHub provider 可以扩展而不复制整页流程。

#### Scenario: Jira profile setup
- **WHEN** 用户选择 Jira provider
- **THEN** 系统 SHALL 展示 Jira site、project、issue type、JQL、metadata refresh、field mapping 和 value mapping 步骤
- **AND** Jira metadata refresh SHALL only use Jira adapter-backed metadata

#### Scenario: HSD-ES profile setup
- **WHEN** 用户选择 HSD-ES provider
- **THEN** 系统 SHALL 展示 HSD-ES tenant、subject、saved query id/name、source ownership、field binding 和 readiness 步骤
- **AND** 页面 SHALL NOT present Jira JQL metadata refresh as if it applies to HSD-ES
- **AND** HSD-ES live metadata、write behavior 或 permission semantics SHALL remain blocked until authoritative HSD-ES API behavior is confirmed

#### Scenario: Future provider setup
- **WHEN** GitHub 或其他 provider 被加入 provider setup template registry
- **THEN** Provider Setup SHALL list it as a provider option with provider-specific labels、metadata status、detail rows and validation copy
- **AND** existing Jira/HSD-ES flows SHALL NOT require duplicated templates or page rewrites

### Requirement: Profile creation and editing are guided
Provider Setup SHALL 支持 guided profile creation 和 editing，使用户通过 provider-specific 表单建立 source population、scope labels、field bindings、value mappings、chart support 和 readiness policy。

#### Scenario: User creates a profile
- **WHEN** 用户完成 provider-specific setup steps and selects Save Draft
- **THEN** 系统 SHALL persist a disabled or draft provider profile with stable profile id、provider id、display name、source population、scope labels、field bindings、value mappings、chart bindings、sync policy、readiness policy and mapping version hash
- **AND** draft profile SHALL NOT become selectable for production Dashboard/Workbench/AI flows until enabled

#### Scenario: User edits a profile
- **WHEN** 用户 edits source population、field bindings、value mappings、chart bindings or readiness policy
- **THEN** 系统 SHALL recalculate mapping/source version fingerprints
- **AND** downstream readiness SHALL show that sync、calculation or scope binding may need refresh before current results are trusted

#### Scenario: User makes risky field changes
- **WHEN** 用户 changes canonical field bindings used by chart recipes or evidence
- **THEN** 页面 SHALL show affected chart/readiness impact before enablement
- **AND** system SHALL prevent silent publication of charts with missing required canonical fields

### Requirement: Profile lifecycle mirrors safe Scope lifecycle
Provider Setup SHALL support archive、protected delete、duplicate、export and import with safety semantics consistent with Scope Library, while preserving provider-profile-specific blast radius information.

#### Scenario: User archives a profile
- **WHEN** 用户 archives an enabled provider profile
- **THEN** profile SHALL be removed from normal provider/profile selectors
- **AND** existing historical facts、sync cache、scope bindings and audit history SHALL remain available for diagnosis
- **AND** bound scopes SHALL show configuration_required or archived-profile blocker rather than silently using stale provider values

#### Scenario: User deletes an archived profile
- **WHEN** 用户 requests hard delete for a profile
- **THEN** system SHALL allow deletion only when the profile is archived
- **AND** system SHALL require an explicit confirmation token
- **AND** UI SHALL show delete impact including bound scopes、sync cache、provider facts、aggregate artifacts、audit events and imported package references before deletion

#### Scenario: User exports a profile
- **WHEN** 用户 exports a provider profile
- **THEN** system SHALL download a versioned JSON package containing provider id、profile id、display name、source population、scope labels、field bindings、value mappings、chart bindings、sync/readiness policy and non-secret metadata
- **AND** export SHALL NOT include credentials、raw provider facts、calculation outputs、AI workspace artifacts or secrets

#### Scenario: User imports a profile
- **WHEN** 用户 imports a provider profile package
- **THEN** system SHALL validate package format、provider template compatibility、profile id conflict policy and non-secret constraints
- **AND** imported profile SHALL start archived or draft until reviewed and explicitly enabled
- **AND** import SHALL NOT overwrite an enabled profile unless user selects an explicit conflict action

#### Scenario: User duplicates a profile
- **WHEN** 用户 duplicates a profile
- **THEN** system SHALL create a draft copy with a new profile id and disabled state
- **AND** the copied profile SHALL preserve source/mapping values for review without copying runtime freshness as current truth

### Requirement: Metadata and mapping are understandable
Provider Setup SHALL show provider metadata and mapping in grouped, action-oriented sections so users can understand how discovered native fields and values become Dashboard canonical fields.

#### Scenario: Metadata discovery succeeds
- **WHEN** provider metadata adapter returns projects、subjects、item types、fields、statuses、priorities、resolutions、components、versions、owners or lookup values
- **THEN** UI SHALL group options by semantic use
- **AND** each option SHALL offer explicit mapping actions such as use as status field、use as severity field、add open value、add fixed value or add critical/high value

#### Scenario: Metadata discovery is unavailable
- **WHEN** selected provider lacks live metadata capability
- **THEN** UI SHALL show a configuration_required or unsupported state with next steps
- **AND** UI SHALL keep manual mapping fields available with clear risk/readiness feedback

#### Scenario: Mapping validation runs
- **WHEN** 用户 asks to validate mappings
- **THEN** system SHALL report missing required canonical fields、unsupported chart recipes、unknown provider fields、empty source result risk and permission blockers without saving partial invalid state as enabled

### Requirement: Provider Setup hands off cleanly to Scope Config
Provider Setup SHALL provide explicit actions to create a first scope from a profile or bind an existing scope, while keeping profile and scope authorities separate.

#### Scenario: User creates scope from profile
- **WHEN** 用户 chooses Create Scope from Provider Profile
- **THEN** Scope Config SHALL open with provider/profile preselected
- **AND** it SHALL prefill display labels、query hints、bug type/status/severity mappings when safe
- **AND** the user SHALL still review and save the scope before it becomes enabled

#### Scenario: User binds existing scope
- **WHEN** 用户 chooses Bind Existing Scope
- **THEN** system SHALL show candidate scopes and binding impact
- **AND** saving the binding SHALL NOT mutate provider profile source or mapping config

#### Scenario: Scope references archived profile
- **WHEN** a scope is bound to an archived profile
- **THEN** Scope Config、Scope Library、Workbench and Data Health SHALL show an actionable blocker
- **AND** provider-backed consumers SHALL NOT silently use the archived profile for fresh runtime work

### Requirement: Provider Setup is safe for low-context users
Provider Setup SHALL prevent common monkey-user mistakes through progressive disclosure、clear required markers、reversible defaults、dirty-change warnings and explicit destructive confirmations.

#### Scenario: User leaves required fields empty
- **WHEN** 用户 attempts to save or enable a profile with missing provider-required fields
- **THEN** UI SHALL show field-level errors in provider language
- **AND** errors SHALL distinguish save-draft blockers from enable/readiness blockers

#### Scenario: User navigates away with changes
- **WHEN** 用户 edits provider setup fields and tries to leave
- **THEN** UI SHALL warn about unsaved changes using the same dirty-form behavior as Scope Config

#### Scenario: User performs destructive action
- **WHEN** 用户 archives、deletes or imports over an existing profile
- **THEN** system SHALL require explicit intent and show impact in plain language before mutation
