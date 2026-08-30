## Purpose
Work Item Provider Operations Platform 定义 Metrics Dashboard 面向 Jira、Intel HSD-ES、GitHub、Azure DevOps 等 work item provider 的长期统一能力层。它的目标是让 dashboard、AI chat、automation、planning、correlation 和 reporting 复用同一套 provider-neutral contracts，而不是为每个 provider 建立平行产品系统。

## Requirements

### Requirement: Provider-neutral capability core
系统 SHALL 提供 provider-neutral core 来表达 connection、metadata、search、facts、actions、planning、release 和 code review 等能力，并允许每个 provider adapter 只声明和实现自己真实支持的 capability。

#### Scenario: Provider declares asymmetric capabilities
- **WHEN** Jira adapter 支持 planning、HSD-ES adapter 支持 defect/record facts and correlation、GitHub adapter 只支持部分 issue、PR、release 和 code review facts
- **THEN** shared core SHALL 接受这种能力不对称，并且不得要求 HSD-ES 或 GitHub adapter 伪造 Jira board、sprint 或 workflow 概念

#### Scenario: UI resolves unsupported capability
- **WHEN** UI 或 AI workflow 请求 provider manifest 中不支持的 capability
- **THEN** 系统 SHALL 返回明确的 unsupported reason，而不是显示不可执行的步骤或静默降级

### Requirement: Provider capability manifest
每个 provider adapter SHALL 暴露 `ProviderCapabilityManifest`，描述 provider 名称、query language、支持的 read/write/planning/release/code-review capability，以及不支持能力的原因。

#### Scenario: Scope Wizard loads a provider
- **WHEN** Scope Wizard 选择某个 provider connection
- **THEN** UI SHALL 根据 manifest 决定显示 search、metadata、field options、planning 或 release 控件

#### Scenario: AI chooses an action
- **WHEN** AI workflow 准备生成 provider action proposal
- **THEN** workflow SHALL 先读取 manifest，并只生成 adapter 声明支持的 action type

### Requirement: Shared terminology with provider-specific hints
用户可见 workflow SHALL 优先使用 provider-neutral terms，例如 Provider、Space、Work item、Item type、State、Outcome、Area、Release target、Owner、Planning bucket 和 Query；provider-specific terms 只作为上下文提示出现。

#### Scenario: Jira scope configuration
- **WHEN** 用户配置 Jira-backed scope
- **THEN** UI SHALL 使用 provider-neutral labels，并可以在 hint 中显示 Jira Project、Issue Type、JQL、Fix Version 等术语

#### Scenario: GitHub provider arrives later
- **WHEN** 第二个 provider 映射到 GitHub organization、repository、issue、pull request、label、milestone 或 project field
- **THEN** shared UI SHALL 复用 provider-neutral workflow，而不是复制一套 GitHub-only 产品页面

#### Scenario: HSD-ES provider arrives as the second provider
- **WHEN** HSD-ES adapter 映射到 HSD-ES tenant、subject、article/record、status、owner、priority/severity、component、family、release 或 stepping 字段
- **THEN** shared UI SHALL 复用 provider-neutral workflow，并只在 provider-specific hints 中显示 HSD-ES 原生术语

### Requirement: Adapter boundary
系统 SHALL 把 external provider quirks 放在 provider-specific adapter 中，把 action plan、approval、audit、query/filter semantic model、metadata DTO、scope wizard UI pattern 和 AI citation contract 放在 shared core 中。

#### Scenario: Jira-specific pagination
- **WHEN** Jira API 需要处理 JQL pagination、custom field id 或 changelog endpoint 差异
- **THEN** Jira adapter SHALL 封装这些细节，并向 shared core 输出稳定 DTO

#### Scenario: HSD-ES-specific API mechanics
- **WHEN** HSD-ES API 使用 Kerberos 或 `/rest/auth/...` token/basic auth、EQL query grammar、article id/rev、`tenant`/`subject` schema、`fieldValues` payload、`start_at`/`max_results` pagination、lookup APIs、relation links 或 comments-as-articles endpoints
- **THEN** HSD-ES adapter SHALL 封装这些细节，并向 shared core 输出稳定 DTO

#### Scenario: Product feature consumes provider facts
- **WHEN** Bug Trend、Velocity、Forecast、AI Chat 或 future reporting feature 需要 work item facts
- **THEN** consumer SHALL 依赖 provider-neutral facts 或 semantic services，而不是直接调用 provider REST API

### Requirement: Python-native production runtime
生产 runtime SHALL 使用 Python/Django-native provider subset 作为核心执行路径，并把 `jira-cli` 仅作为 optional developer/operator diagnostic sidecar，除非未来 review 明确提升其生产地位。

#### Scenario: Dashboard request path
- **WHEN** dashboard 页面、HTMX partial、durable sync 或 AI workflow 在生产路径读取 provider data
- **THEN** 系统 SHALL 使用 Python-native typed API，而不是通过 subprocess 调用本地 `jira` binary

#### Scenario: Developer compares adapter behavior
- **WHEN** 开发者需要对照 Jira REST adapter 与 `jira-cli` 查询结果
- **THEN** 可选 wrapper MAY 调用 `jira-cli`，但结果不得成为生产 source of truth

### Requirement: Provider-specific modules implement integration only
Provider-specific modules SHALL 只拥有外部系统集成、同步、auth、pagination、error mapping 和 raw projection，不得复制 shared product workflows。

#### Scenario: New HSD-ES adapter
- **WHEN** HSD-ES 成为 Jira 之后的第二个 provider
- **THEN** 项目 MAY 增加 HSD-ES adapter module 来实现 HSD-ES API 细节，但 SHALL NOT 复制 Scope Wizard、AI action approval、audit、correlation 或 dashboard consumption 的完整产品层

### Requirement: Provider platform extraction timing
在只有 Jira provider 的阶段，项目 MAY 继续把实现放在 `jira_sync` 和相关现有模块中；当第二个 provider 落地或多个 consumers 证明 contract 形状稳定时，系统 SHALL 将 shared contracts 提取到 `provider_ops` 或 `work_items` 模块。

#### Scenario: Jira-only Phase 1
- **WHEN** Phase 1 只实现 Jira-backed Scope Wizard
- **THEN** public DTO/API names SHALL 尽量使用 `Provider*`、`WorkItem*` 或 provider-neutral 命名，以降低未来提取 shared module 的成本

#### Scenario: Jira and HSD-ES parallelization pressure
- **WHEN** HSD-ES is accepted as the second provider before Jira Phase 1 finishes
- **THEN** Phase 1 SHALL keep shared provider contracts provider-neutral from the start and MAY implement thin Jira/HSD-ES capability manifests early to expose asymmetry and correlation needs before deeper feature work
