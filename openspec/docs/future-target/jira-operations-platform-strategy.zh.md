# Work Item Provider Operations Platform 策略设计

Date: 2026-08-24

## 背景

Bug Trend 是 Metrics Dashboard 的第一个 Jira-backed feature，但 Jira 不应该成为唯一的架构中心。后续需求很可能扩展到 AI chat 更新 work item、scrum/sprint planning、release readiness、ticket triage、automation agent、GitHub issue/PR insights 和管理报告。如果每个 feature 都直接调用某个 provider API，系统会快速出现重复认证、重复分页、重复字段解释、重复 query 生成、重复权限控制和不可审计的 AI 写操作。

这里的 provider 不只包括 Jira。Jira 是第一位 rich work-management provider，拥有 issue、workflow、field context、board、sprint、release/fix version 等能力。Intel HSD-ES 应作为第二位 peer provider 纳入平台设计：它不是 Jira 的附属 enrichment source，而是另一个 work item / defect record system，需要和 Jira 平行建模、平行同步，并通过 correlation layer 做跨系统关联。GitHub Issues / GitHub Projects / GitHub Pull Requests 是另一类 provider，能力形状不完全对等：GitHub 没有 Jira Scrum 的同构概念，但它有 repository、issue、label、milestone、assignee、project item、PR review、CI/status checks 和代码事实。平台设计必须允许 provider capability 不对称，而不是为每个 provider 复制一个完整等价模块。

同时，`ankitpokhrel/jira-cli` 已经提供了成熟的 Jira CLI 经验：项目发现、createmeta、field metadata、JQL/search、issue 操作、sprint/release 操作、raw/plain 输出、Cloud/Server 兼容和多种认证方式。它值得认真借鉴，但不能不加边界地变成 Django dashboard 的生产 backend。

本文件定义长期 Work Item Provider Platform 方向，以 Jira 为第一位 provider，并评估三种利用 `jira-cli` 的路径：wrapper、Python subset rewrite、fork and maintain。

## 核心结论

不要完整重写 `jira-cli`，也不要把 `jira-cli` binary 直接作为 Metrics Dashboard 的主 backend。

推荐方向是：

```text
Build a Python-native Work Item Provider Operations Platform for Metrics Dashboard,
make Jira the first rich provider adapter,
make Intel HSD-ES the second peer provider for cross-provider correlation,
borrow jira-cli's proven discovery/query UX patterns,
optionally use jira-cli as a developer/operator sidecar, not as the core runtime dependency.
```

也就是说，我们要做的不是 Python 版 `jira-cli`，也不是 `JiraOperationsPlatform`、`HSDESOperationsPlatform`、`GitHubOperationsPlatform`、`AzureOperationsPlatform` 几套平行系统。正确方向是 provider-neutral core 加 provider-specific adapters：共享 identity、query/filter、metadata、fact projection、correlation、AI action governance、audit 和 dashboard consumption 模型；Jira、HSD-ES、GitHub、Azure DevOps 等 provider 只实现自己具备的 capability。

Bug Trend Scope Wizard 是第一位 consumer；后续 AI Chat、Sprint Planning、Release Readiness、GitHub issue/PR insights 和 Automation 都复用同一层。Jira-specific planning/scrum 能力应该以 capability extension 形式存在，不应该污染不具备该能力的 provider。

## 目标

1. 为所有 work item / tracker-backed dashboard/AI feature 提供统一 provider 能力入口。
2. 把 read-only discovery/search 与 write action 分开治理。
3. 支持用户友好的 Scope Wizard，而不是暴露 raw `JiraScopeConfig` 表单。
4. 为 AI chat 和 automation 提供可审计、可预览、可确认的 provider action plan。
5. 保持 Python/Django-native，实现可测试、可部署、可审计。
6. 明确 `jira-cli` 的利用边界，避免盲目 fork 或重写。

## 非目标

1. 不复制 `jira-cli` 的完整 CLI/TUI 产品。
2. 不在第一阶段实现 issue create/edit/assign/move/comment/worklog 的全部能力。
3. 不让 AI 直接调用 Jira write API。
4. 不把生产 dashboard runtime 绑定到本地用户的 `.jira/.config.yml`、keyring、shell env 或 CLI stdout。
5. 不在 Bug Trend 第一阶段做 provider-neutral 数据库大迁移，但新 API/DTO 必须按 provider-neutral 方向命名。

## Provider 抽象策略

平台不应该假设所有 provider 都拥有 Jira 的全部能力，也不应该为每个 provider 创建一套等价模块。更稳的抽象是：共享 core 定义 capability contract，provider adapter 按能力声明自己支持什么。

### Capability 分层

| Capability | 通用语义 | Jira 映射 | GitHub 映射 | 是否进入 shared core |
| --- | --- | --- | --- | --- |
| `ProviderConnection` | endpoint、auth、health、capabilities | Jira Server/Data Center 或 Cloud URL、PAT/basic/mTLS | GitHub.com/GHE host、token/GitHub App | 是 |
| `WorkItemSearch` | 搜索 work items | JQL issue search | GitHub issue/PR search query 或 GraphQL | 是 |
| `WorkItemMetadata` | projects/spaces、item types、fields、allowed values | project、issue type、field、allowedValues | org/repo、issue/PR、labels、milestones、assignees、projects fields | 是 |
| `WorkItemFacts` | issue/ticket facts、comments、history | issue fields、comments、changelog | issue/PR fields、comments、timeline events、review states | 是 |
| `WorkItemActions` | proposed update/comment/state/assignment actions | update issue、transition、assign、comment | update issue、label/milestone/assignee/comment、close/reopen | 是，执行由 adapter 实现 |
| `Planning` | backlog/sprint/iteration planning | boards、sprints、rank、versions | GitHub Projects iterations 可部分映射；普通 GitHub Issues 不支持 Scrum | optional capability |
| `Release` | release/milestone/fix-version readiness | fixVersions、versions | milestones、releases/tags | optional capability |
| `CodeReview` | PR/review/CI facts | Jira 本身不提供，需和代码平台关联 | PR、reviews、checks、commits | optional capability |

关键点：shared core 只要求 provider 声明 capability，不要求 provider 伪造不具备的概念。例如 GitHub 不需要实现 Jira board/sprint；它可以实现 `WorkItemSearch`、`WorkItemMetadata`、`WorkItemFacts`、部分 `WorkItemActions`、`Release` 和 `CodeReview`。

### HSD-ES 作为第二个 Peer Provider

HSD-ES API wiki 显示，HSD-ES 的推荐接口是 REST API，基础地址形态是：

```text
Production:    https://hsdes-api.intel.com/rest
PreProduction: https://hsdes-api-pre.intel.com/rest
Swagger:       https://hsdes-api.intel.com/rest/doc
```

认证方面，HSD-ES API 首选 Kerberos。Windows integrated auth 可用；Linux 需要 `kinit`。HSD-ES token/basic auth 也支持，但 URL 需要使用 `/rest/auth/...` 形态，例如 `/rest/auth/query/execution/eql?...`。这和 Jira Server PAT 是完全不同的 auth shape，因此必须放在 HSD-ES adapter，不应该泄漏到 shared core。

HSD-ES 的核心数据模型不是 Jira issue，而是 `article`。Article 通过 `tenant` 和 `subject` 区分业务域和类型，字段以 `fieldValues` 数组传输。常见 REST surface 包括：

| API surface | Method / path shape | Platform mapping |
| --- | --- | --- |
| Read article | `GET /rest/article/{id}` | `WorkItemFacts.get_detail` |
| Insert article | `POST /rest/article` with `tenant`, `subject`, `fieldValues` | future approved `ProviderActionPlan` only |
| Update article | `PUT /rest/article/{id}` with `tenant`, `subject`, `fieldValues` | future approved `ProviderActionPlan` only |
| Bulk insert/update | `/rest/article/bulk/sync/{tenant}/{subject}` | batch action executor, with partial/error handling |
| Query by EQL | `POST /rest/query/execution/eql?start_at=&max_results=` | `WorkItemSearchCapability.search` |
| Saved query | `GET /rest/query/execution/{id}` | saved provider filter mode |
| Comments | comment is an article with `subject=comments` and `parent_id` | comments facts and comment action plan |
| Children/comments | `GET /rest/article/{parent_id}/children?child_subject=comment...` | timeline/comment projection |
| Links | `POST /rest/relation/add`, `GET /rest/article/{id}/links` | correlation evidence and relationship facts |
| Clone | `POST /rest/article/{id}/clone` | future write action, disabled until reviewed |

EQL 是 HSD-ES 的 query language，基本形态是：

```text
SELECT <fieldlist> [WHERE <filters>] [SORTBY <sortfieldlist>]
SELECT <fieldlist> [WHERE Parent(...), Child(...) or LINK_<type>(...)] [SORTBY ...]
```

重要约束：

- string literal 使用单引号，不应在 EQL 内使用双引号；
- field 可以是 global field、`subject.field` 或 `tenant.subject.field`；
- tenant custom field 形态是 `tenant.subject.field`；
- 支持 `AS` short name；
- 支持 `AND` / `OR`、`BETWEEN`、`IN` / `NOT_IN`、`CONTAINS`、`STARTS_WITH`、`ENDS_WITH`、比较操作、`IS ME`、`IS_EMPTY`、`IS_NOT_EMPTY`、`REPORTS_TO`；
- 支持 `DaysAgo(N)`、`MinutesAgo(N)`、`Today` 等 date helpers；
- 支持 `SORTBY field ASC|DESC`；
- 支持 Parent / Child / Link relationship filters，其中 wiki 建议逐步使用 Link clauses 代替 Child clauses；
- query result pagination 使用 `start_at` 和 `max_results`，默认返回 100 rows，示例说明可按 page size 迭代，response 包含 `total` 和 `data`。

Lookup API 是 Scope Wizard 的关键。Wiki 说明：

- static lookup 可通过 `schema/lookupvalue?lookup_group=...` 获取；
- static 和 dynamic lookup values 都可从 `Lookup/{field}` endpoint 获取；
- dynamic lookup 也可以通过 EQL 查询规则背后的条件；
- 已有便捷 endpoints 获取 families、releases、components。

因此 HSD-ES Scope Wizard 不应该硬编码 family/release/component/status/owner 等列表，而应该通过 HSD-ES adapter 的 lookup/metadata capability 动态发现。

### Jira-HSD-ES Correlation Strategy

Jira 与 HSD-ES 必须平行接入，然后通过 correlation artifact 建立关系：

```text
Jira issue facts ─┐
                  ├─ ProviderCorrelation(candidate / confirmed / rejected / stale)
HSD-ES facts  ────┘
```

Correlation candidate 可以来自：

- explicit HSD-ES relation link 或 Jira/HSD-ES cross-link；
- shared external id；
- title/summary fingerprint；
- area/component/family overlap；
- release target / stepping overlap；
- owner overlap；
- created/updated/resolved time window；
- comment 或 description 中出现的对方 provider id。

每个 correlation 必须保存 provider item identity、matched fields、matched values、matching method、confidence、source、created_at 和 review state。Dashboard 可以把 correlated Jira issue 与 HSD-ES article 并排展示，但不能把 HSD-ES state 覆盖 Jira status，也不能把 Jira resolution 覆盖 HSD-ES lifecycle。

### HSD-ES Adapter Boundary

HSD-ES adapter 应封装以下 provider-specific mechanics：

- Kerberos vs `/rest/auth/...` token/basic auth；
- base URL: prod/pre；
- EQL generation、escaping、date helper、Parent/Child/Link clauses；
- `/rest/article/{id}` detail shape；
- `tenant` / `subject` / `fieldValues` payload shape；
- static/dynamic lookup APIs；
- article bulk sync 的 `success` / `partial` / `error` response；
- comment as `subject=comments` article；
- article children、links、clone；
- `start_at` / `max_results` pagination；
- rate limit、permission filtering、normalized errors；
- required fields and send_mail behavior per target tenant/subject。

Shared core 只接收 normalized DTO：`ProviderCapabilityManifest`、`ProviderSpace`、`WorkItemType`、`WorkItemField`、`WorkItemFieldValue`、`WorkItemSearchPage`、`WorkItemFacts`、`ProviderTimelineEvent`、`ProviderCorrelation` 和 `ProviderActionPlan`。

### Provider Capability Manifest

每个 provider adapter 应暴露一个 manifest，而不是靠 UI 猜测：

```python
@dataclass(slots=True)
class ProviderCapabilityManifest:
    provider: str
    supports_work_item_search: bool
    supports_field_metadata: bool
    supports_field_allowed_values: bool
    supports_status_transitions: bool
    supports_comments: bool
    supports_assignment: bool
    supports_planning: bool
    supports_release: bool
    supports_code_review: bool
    query_language: str
    unsupported_reasons: dict[str, str]
```

UI 和 AI workflow 根据 manifest 决定显示哪些步骤、隐藏哪些动作、给出什么 unsupported reason。这样 GitHub provider 不会被迫出现 “Sprint” 页面，Jira provider 也不会被要求提供 PR review state。

### 通用领域词汇

| Provider-neutral term | Jira | GitHub |
| --- | --- | --- |
| Provider | Jira | GitHub |
| Space | Project | Organization / repository |
| Work item | Issue | Issue / pull request |
| Item type | Issue type | Issue vs pull request; label/type convention; GitHub Projects item type |
| State | Status / workflow state | Open / closed / draft / merged; project status field |
| Outcome | Resolution | Closed reason / merged / not planned / label convention |
| Area | Component | Label / repository / project field |
| Release target | Fix version | Milestone / release / tag |
| Owner | Assignee | Assignee / reviewer / code owner |
| Planning bucket | Sprint / board / version | Project iteration / milestone |
| Query | JQL | GitHub search query / GraphQL filter |

Shared UI 应优先使用 provider-neutral term，再在 provider-specific hint 中显示 Jira/GitHub 术语。例如：`Scope Query (JQL)`、`Release target (Jira fix version)`、`Area (GitHub label)`。

### 模块策略

不要为每个 provider 创建完全等价的 vertical module，例如 `jira_operations`、`github_operations`、`azure_operations` 各自拥有自己的 UI、AI action、scope、audit、history。那会造成 parallel truth。

推荐模块边界：

```text
provider_ops/ or work_items/        # future shared core, when second provider arrives
    app/api/                          # provider-neutral contracts
    app/domain/                       # manifests, facts, action plans, query/filter models
    app/spi/                          # provider adapter interfaces

jira_sync/                          # first provider adapter and durable Jira sync owner today
    out/                              # Jira REST/API adapter implementation
    app/api/                          # Jira-backed implementations of provider-neutral contracts

github_sync/ or github_provider/     # future GitHub adapter, not a full parallel platform
    out/                              # GitHub REST/GraphQL adapter implementation
    app/api/                          # GitHub-backed implementations of provider-neutral contracts

hsdes_sync/ or hsdes_provider/       # second provider adapter after Jira
    out/                              # HSD-ES REST/EQL adapter implementation
    app/api/                          # HSD-ES-backed implementations of provider-neutral contracts

bug_metrics / velocity / forecast / ui_web
    consume provider-neutral facts, scopes, actions, and manifests
```

短期在只有 Jira 的情况下，可以继续把实现放在 `jira_sync`，但新增 public DTO/API 应尽量使用 `Provider*`、`WorkItem*`、`Tracker*` 等通用命名。等第二个 provider 真正落地时，再把已验证的 shared contracts 提取到 `provider_ops` 或 `work_items` 模块。

### 什么时候创建 provider-specific module

创建 provider-specific module 的条件是它要拥有外部系统集成和同步实现，而不是复制产品功能。

| 应该 provider-specific | 应该 shared core |
| --- | --- |
| Jira REST endpoint quirks | action plan / approval / audit |
| Jira auth modes | provider connection profile contract |
| JQL generation details | query/filter semantic model |
| Jira field context and custom field IDs | field metadata DTO |
| Jira changelog pagination | fact projection contract |
| HSD-ES Kerberos/token auth, `/rest/auth/...` URL shape | provider connection profile contract |
| HSD-ES EQL syntax, escaping, Parent/Child/Link clauses | query/filter semantic model |
| HSD-ES tenant/subject/article/fieldValues payload shape | work item metadata and facts DTO |
| HSD-ES lookup APIs for families/releases/components | field metadata DTO and Scope Wizard option model |
| HSD-ES article children/comments/links | timeline, comment, relationship and correlation contracts |
| GitHub GraphQL pagination | durable sync cursor abstraction |
| GitHub labels/milestones API | scope wizard UI pattern |
| GitHub PR review/checks API | AI chat evidence/citation contract |

Provider-specific modules implement adapter behavior。Shared core owns user-facing semantics, AI safety, audit, review/approval, and dashboard-facing contracts.

## 未来 Provider + AI 能力地图

### 1. Read / Search / Discovery

基础能力：

- search work items by provider query
- get work item detail
- get changelog/history
- get comments
- get transitions
- get worklogs
- list projects
- list issue types
- list fields
- list field allowed values
- list components
- list versions/releases
- list boards/sprints/iterations when supported
- validate provider query
- preview issue count

AI 能力：

- 自然语言生成 provider query，例如 JQL 或 GitHub search query
- 解释 query 为什么没有结果
- 总结 work item、comments、changelog/timeline
- 找出某个 scope 下的主要 root cause / component cluster

### 2. Scope / Dashboard Configuration

基础能力：

- guided scope creation
- project + issue type selection
- field mapping
- filter value selection
- generated query preview
- scope validation
- saved scope versioning
- calculation run binding
- evidence drilldown

AI 能力：

- 自动推荐 status grouping：open / fixed / closed / excluded
- 自动推荐 priority/severity mapping
- 检查 scope 是否漏掉某些状态或字段值
- 从用户自然语言创建 scope draft

### 3. Ticket Update / AI Chat Action

基础能力：

- update summary / description
- update priority / severity / custom field
- assign owner
- add comment
- transition status
- link issues
- update fix version / component
- batch update candidate tickets

AI 能力：

- 根据聊天内容生成 ticket update proposal
- 根据 CI/test failure 生成 provider comment draft
- 建议 owner reassignment
- 建议 status transition
- 批量提出字段修复建议

治理要求：

```text
AI proposes -> UI previews diff -> user approves -> executor writes -> audit event records
```

### 4. Sprint / Scrum Planning

基础能力：

- list boards
- list active/future sprints
- get backlog
- get sprint issues
- move issues into sprint
- rank/reorder backlog
- sprint health
- carryover analysis
- blocked issue tracking

AI 能力：

- 推荐 sprint cutline
- 识别 sprint risk
- 生成 planning summary
- 生成 daily scrum blocker report
- 结合 velocity/forecast 模块做 capacity-aware planning

### 5. Release / Fix Version / Milestone Management

基础能力：

- list versions
- create/update versions when allowed
- assign fix version
- release readiness
- unresolved issue by version
- bug burn-down by release
- release note generation

AI 能力：

- 总结 release risk
- 生成 release notes
- 推荐延期/升级 ticket
- 解释 fix version readiness gap

### 6. Triage / Quality Workflow

基础能力：

- duplicate detection input set
- missing field detection
- stale ticket detection
- owner gap detection
- severity mismatch detection
- reopen analysis
- regression cluster detection
- component routing

AI 能力：

- 聚类相似 bug
- 找缺少 repro steps 的 ticket
- 推荐 component/owner
- 识别 severity/priority 不一致

### 7. Knowledge / Chat Over Work Items

基础能力：

- issue fact retrieval
- semantic search index handoff
- issue timeline reconstruction
- cross-ticket relationship extraction
- cited answer payload

AI 能力：

- “过去一个月 chiplet bugs 的主要风险是什么？”
- “这些 tickets 跟哪个 component 或 release 相关？”
- “给 manager 写一份状态更新。”
- “解释 STDEL-123 为什么影响当前 release。”

要求：AI answer 必须基于 provider facts，不允许凭空生成 ticket、issue、PR 状态或字段值。

### 8. Automation / Agent Workflow

基础能力：

- scheduled sync
- notification triggers
- proposed update queue
- policy checks
- batch action queue
- audit log

AI 能力：

- 每日 bug risk digest
- P1/P2 stale ticket alert
- fixed bug missing release target proposal
- CI failure -> provider update proposal

## 建议架构

```text
ui_web
  Scope Wizard
  AI Chat
    Sprint Planning UI when provider supports planning
    Review/Approve Provider Actions

bug_metrics / velocity / forecast / future modules
    Consume provider-neutral facts and semantic services

provider_ops/ or work_items/  (future shared core)
    Provider Transport Contracts
    Provider Capability Contracts
    Provider Semantic Layer
    AI Provider Action Planning Layer

jira_sync
    Jira adapter implementation for provider contracts
    Jira durable sync owner today

github_sync/ or github_provider/  (future adapter)
    GitHub adapter implementation for provider contracts

jira_history
    Durable Jira issue snapshots, transitions, comments/changelog projections today
    Future shared history extraction may move to provider_ops when a second provider lands
```

### Layer 1: Provider Transport Layer

职责：

- auth
- base URL / host / server-vs-cloud handling
- HTTP request execution
- pagination
- retries / timeout
- rate limit mapping
- error normalization
- secret redaction

建议模块：

```text
provider_ops/app/spi/provider_transport.py        # future shared contract
jira_sync/out/jira_rest_client.py                 # current Jira implementation
jira_sync/out/jira_auth.py
jira_sync/out/jira_error_mapping.py
github_sync/out/github_rest_graphql_client.py      # future GitHub implementation
```

### Layer 2: Provider Capability Layer

职责：暴露 provider 原子能力，但不嵌入 dashboard 业务语义。Provider 可以只实现自己 manifest 声明支持的 capability。

建议 API：

```python
class ProviderSpaceCapability:
    def search_spaces(self, text: str) -> list[ProviderSpace]:
        ...

    def get_space(self, key_or_id: str) -> ProviderSpace:
        ...


class WorkItemMetadataCapability:
    def list_item_types(self, space: str) -> list[WorkItemType]:
        ...

    def list_fields(self, space: str, item_type: str) -> list[WorkItemField]:
        ...

    def list_field_options(self, space: str, item_type: str, field_id: str) -> list[WorkItemFieldValue]:
        ...


class WorkItemSearchCapability:
    def search(self, query: str, start_at: int, max_results: int, fields: list[str]) -> WorkItemSearchPage:
        ...

    def validate_query(self, query: str) -> ProviderQueryValidationResult:
        ...
```

Jira adapter 可以把 `space` 映射成 project，`item_type` 映射成 issue type，`query` 映射成 JQL。GitHub adapter 可以把 `space` 映射成 org/repo，`item_type` 映射成 issue/PR 或 label/project convention，`query` 映射成 GitHub search query 或 GraphQL filter。

### Layer 3: Provider Semantic Layer

职责：把 provider raw metadata 转换成 dashboard/AI 可理解的语义。

例子：

- `ScopeMetadataProvider`
- `ScopeQueryBuilder`
- `StatusSemanticClassifier`
- `FieldControlResolver`
- `ScopeConfigDraftBuilder`
- `ProviderFactProjector`

### Layer 4: AI Workflow Layer

职责：生成和执行受控 provider action。

核心对象：

```python
@dataclass(slots=True)
class ProviderActionPlan:
    id: str
    provider: str
    work_item_id: str
    action_type: str
    before: dict
    after: dict
    reason: str
    risk: str
    requires_confirmation: bool


class ProviderActionPlanner:
    def propose_update(self, user_request: str, work_item_facts: dict) -> ProviderActionPlan:
        ...


class ProviderActionExecutor:
    def execute_approved(self, plan: ProviderActionPlan, approver: str) -> ProviderActionResult:
        ...
```

AI 只能生成 `ProviderActionPlan`；write executor 根据 `plan.provider` 路由到 Jira、GitHub 或其他 provider adapter，并且只接受 approved plan。

## Scope Wizard 作为第一位 Consumer

Bug Trend Scope Config 应升级为向导，而不是 raw config form。第一版可以只启用 Jira provider，但向导结构应使用 provider-neutral 词汇：source mode、space、item type、fields、filters、review。Jira 页面可以在辅助文案中显示 Project、Issue Type、JQL；GitHub 页面未来可以显示 repository、issue/PR、labels、milestones、GitHub search query。

建议步骤：

1. Source mode：Guided / Saved provider filter / Advanced query。
2. Space：搜索并选择 provider space；Jira 是 project，例如 `131600`；GitHub 是 organization/repository。
3. Item type：选择 work item type；Jira 是 `Bug`；GitHub 可以是 issue/PR 或 label/project convention。
4. Fields：把 provider fields 映射到 Priority、Severity、State、Area、Owner、Release target 等语义角色。
5. Filters：按字段类型展示 checkbox、searchable multi-select、user picker、date range 或 text input。
6. Review：展示 human-readable summary 和 generated provider query。
7. Save：保存 draft 或 enable。

关键 UX 决策：

- Guided mode 下 provider query 不是必填输入，而是 generated preview。
- Advanced query mode 才要求用户输入 provider-specific query，例如 JQL 或 GitHub search query。
- Status 应支持快捷操作，例如 `Select all non-closed`。
- Field options 需要从 `provider + space + item type + field` 上下文发现。
- 用户保存的是 semantic scope config，不是 UI 上临时生成的 tag 展示。

## `jira-cli` 利用路线评估

### 路线 A: Wrapper `jira-cli` Binary

形态：Django 通过 subprocess 调用安装好的 `jira` binary，例如：

```text
jira project list --plain
jira issue list --raw -q "project = 131600"
```

优点：

- 启动快，不需要我们实现所有 REST endpoint。
- 可直接利用 `jira-cli` 已有认证、Cloud/Server 兼容和 JQL/search 行为。
- 对开发者本地 debug 很方便。
- 适合作为临时 operator tool 或对照验证工具。

缺点：

- 生产部署依赖额外 binary、版本、PATH、OS compatibility。
- README 标注 Windows support 是 partial，和当前 Windows dev 环境存在风险。
- CLI config 依赖 `.jira/.config.yml`、env、`.netrc`、keyring，不适合服务端统一 secret governance。
- stdout JSON 是 CLI 输出 contract，不是稳定 application API。
- subprocess 超时、错误映射、pagination、redaction、observability 都要再包一层。
- 很难把 AI write action preview/audit 做成强 contract。

适用场景：

- developer diagnostic tool
- one-off migration/check script
- comparing our REST adapter result with jira-cli output
- emergency fallback for read-only issue search

不适用场景：

- production dashboard runtime
- durable Jira sync
- AI write execution
- Scope Wizard metadata source of truth

结论：可以作为 optional dev/operator wrapper，不作为核心 backend。

### 路线 B: Python Subset Rewrite

形态：不重写整个 `jira-cli`，只用 Python 实现 dashboard 所需能力子集。

优点：

- 符合当前 Django/Python 架构。
- 可使用现有 `.env` / deployment secret / Django settings。
- 易于测试、mock、审计和与 `jira_history` / `bug_metrics` 集成。
- DTO contract 可由 dashboard 需求驱动，而不是受 CLI 输出影响。
- 可以逐步扩展到 AI action plan 和 sprint planning。

缺点：

- 需要自己实现缺失 endpoint、pagination 和 edge cases。
- 需要维护 Jira Cloud/Server/Data Center 差异。
- 需要为 field option discovery、JQL validation、status grouping 建测试资产。

适用场景：

- production dashboard runtime
- Scope Wizard
- durable sync
- AI read/search/facts
- approved Jira write actions

结论：推荐主路线，但范围必须是 dashboard-specific subset，不是 Python `jira-cli` clone。

### 路线 C: Fork and Maintain `jira-cli`

形态：fork `ankitpokhrel/jira-cli`，维护内部版本，可能添加 machine-readable API 或 service mode。

优点：

- 继承大量已实现 Jira operations。
- 可以定制缺失能力，例如 stable JSON schema 或 server mode。
- 如果团队长期需要 CLI 工具，也可能有额外价值。

缺点：

- 我们会变成 Go CLI/TUI 项目的维护者。
- 上游升级、依赖漏洞、平台兼容、release packaging 都成为成本。
- fork 后仍然需要 Django/Python integration layer。
- 很容易把产品重心从 dashboard/AI workflow 拉偏到通用 CLI。
- 需要安全审查 keyring/config/secret 行为是否符合内部部署规则。

适用场景：

- 组织明确要维护内部 Jira CLI。
- 上游不接受必要的 machine API / JSON schema 改动。
- dashboard 之外还有强烈 CLI 标准化需求。

结论：当前不推荐。只有当 wrapper 被证明有高价值且上游无法满足 machine-readable contract 时，再考虑 fork。

### 路线 D: Upstream Contribution

形态：不 fork，向 `jira-cli` upstream 贡献增强，例如更稳定的 JSON schema、metadata commands、non-interactive config export。

优点：

- 避免长期 fork 维护成本。
- 回馈开源，降低私有 patch 漂移。
- 如果贡献被接受，可改善 operator/dev tooling。

缺点：

- 上游路线和节奏不可控。
- 不能作为 Metrics Dashboard 关键路径依赖。
- 仍然不能替代 Python-native production adapter。

结论：可作为长期 optional path，不阻塞内部平台建设。

## 推荐路线

| 场景 | 推荐路线 | 说明 |
| --- | --- | --- |
| Scope Wizard production backend | Python provider subset | 必须 Python-native、typed、testable、可审计；Jira 是 first adapter。 |
| Durable provider sync | Python provider subset | 需要 cursor、snapshot、transition/timeline、calculation-run 绑定；Jira first，GitHub later。 |
| AI chat read/search | Python provider subset | 需要 facts contract 和 citation，可覆盖 Jira issue、GitHub issue/PR。 |
| AI write/update work item | Python provider subset | 需要 action plan、preview、approval、audit，由 provider adapter 执行。 |
| Developer local comparison | jira-cli wrapper | 可选工具，用于对照 API 行为。 |
| One-off import/export | jira-cli wrapper | 不进入生产 request path。 |
| Enterprise internal CLI | fork/upstream | 只有另一个明确产品目标出现时才考虑。 |

最终建议：

```text
Primary: Python-native Work Item Provider Operations Platform.
Secondary: Optional jira-cli wrapper for dev/operator diagnostics.
Avoid: Full Python rewrite or immediate fork of jira-cli.
```

## Phase Plan

### Phase 1: Provider Metadata + Jira Scope Wizard

目标：替换 raw Scope Config 表单为用户友好的 guided flow。实现上以 Jira 为 first provider，但新增 API/DTO 使用 provider-neutral 命名，避免第二个 provider 到来时重写 UI 和 AI governance。

Deliverables：

- `ProviderCapabilityManifest`
- `ProviderSpaceCapability.search_spaces`
- `WorkItemMetadataCapability.list_item_types`
- `WorkItemMetadataCapability.list_fields`
- `WorkItemMetadataCapability.list_field_options`
- `ScopeQueryBuilder` with Jira JQL implementation first
- `ScopeValidator.validate_query` with Jira JQL validation first
- Scope Wizard pages and htmx partials
- UI smoke test creating a scope without hand-written JQL in guided mode

### Phase 2: Provider Facts for AI Chat

目标：AI 可以可靠回答 provider-backed work item 问题，但不写外部系统。Jira issue facts 是 first implementation；GitHub issue/PR facts 可以作为第二 provider 扩展。

Deliverables：

- issue search facts
- issue detail facts
- comments/changelog/timeline projection
- cited answer payload
- natural language -> candidate provider query preview
- HSD-ES article search/detail facts after target tenant/subject contract review
- HSD-ES comment/link/children projection when API permission allows

### Phase 2B: Jira + HSD-ES Correlation

目标：让 Jira 与 HSD-ES 可以作为平行 provider 被 dashboard 同时消费，并通过 correlation artifact 关联，而不是互相覆盖字段。该阶段必须先确认目标 HSD-ES tenant/subject 的 read/search/detail/comment/link 权限。

Deliverables：

- HSD-ES `ProviderCapabilityManifest`
- HSD-ES REST/EQL adapter contract review
- HSD-ES article facts projection
- HSD-ES lookup metadata projection for families/releases/components and target fields
- `ProviderCorrelation` model
- correlation candidate generation based on explicit link/shared id/field overlap/time window/text mention
- confirmed/rejected/stale correlation state
- dashboard/API evidence payload showing both provider-native facts

### Phase 3: Proposed Provider Write Actions

目标：AI 可以提出 work item 修改建议，但用户确认前不能写。Jira adapter 支持 issue update/transition/comment；HSD-ES adapter 的 write capability 必须等 target tenant/subject required fields、permission model、`send_mail` behavior 和 approval policy review 后再启用；GitHub adapter 可支持 issue comment、labels、milestone、assignee、close/reopen 等 capability。

Deliverables：

- `ProviderActionPlan`
- diff preview UI
- approval workflow
- add comment / update field or label / transition or close-reopen / assign MVP
- audit events

### Phase 4: Agile Planning

目标：支持 provider-supported planning。Jira 支持 board/sprint/backlog；GitHub 只在 GitHub Projects/iterations 可用时启用 planning capability。

Deliverables：

- board/sprint/backlog capabilities
- provider unsupported-state UX for providers without planning
- capacity-aware planning inputs from velocity/forecast
- sprint risk summary
- proposed sprint move action plan

### Phase 5: Automation

目标：把 read insights 和 approved action proposals 定时化。

Deliverables：

- scheduled insight jobs
- proposed batch update queue
- notification hooks
- policy checks
- audit dashboards

## Governance Rules

1. Read APIs and write APIs must be separate modules/contracts.
2. AI cannot call provider write adapters directly.
3. Every write must have before/after preview, reason, approver, execution result and audit event.
4. Secret values must never be rendered, logged, committed or returned in tool output.
5. Provider metadata is read-only assistance; saved semantic config remains the source of truth.
6. Dashboard render paths must read durable local history/calculation artifacts, not live-query providers on every render.
7. `jira-cli` wrapper, if added, must be explicitly marked non-production unless a later review promotes it.
8. Provider adapters must declare unsupported capabilities instead of fabricating equivalent Jira concepts.
9. Jira-HSD-ES correlation must preserve both provider-native states and must not merge or overwrite provider truth.
10. HSD-ES write APIs must stay disabled until the target tenant/subject required fields, `send_mail` behavior, permission model and approval policy are reviewed.
11. HSD-ES `fieldValues`, comments, links, children and bulk partial/error responses must be normalized before they reach dashboard or AI workflows.

## Open Questions

1. Should guided Scope Wizard support three mutually exclusive modes, or allow advanced provider query as an additional constraint on guided filters?
2. For Intel Jira project `131600`, is Severity a dedicated custom field or is Priority reused as severity source?
3. Does “non-closed status” mean only exclude literal `Closed`, or exclude all terminal states such as `Done`, `Fixed`, `Resolved`, `Won't Fix`?
4. Where are provider credentials allowed to live for web onboarding: deployment env only, encrypted DB secret reference, OS keyring, or external secret manager?
5. Should provider connection profiles be global, per deployment, per team, or per Django user?
6. Are write actions in AI chat allowed in MVP, or must Phase 2 remain read-only until governance is reviewed?
7. Do we need Jira Cloud support now, or only Intel Jira Server/Data Center?
8. Which provider should be second after Jira: GitHub Issues/PR, Azure DevOps, or another tracker?
9. Should durable history become provider-neutral in a new module when the second provider lands, or should each provider keep its own history module with shared DTOs?
10. Which HSD-ES tenant/subject is the first target for dashboard correlation, and which fields map to Provider Space、Item type、State、Outcome、Area、Release target、Owner、Severity/Priority?
11. Which HSD-ES identity should be canonical: article `id`, a display key, a tenant/subject/id tuple, or another stable external identifier?
12. Which HSD-ES fields can reliably correlate to Jira: explicit Jira key/link, external id, title, component/family, release/stepping, owner, created/updated date, or relation link?
13. Can the service account use Kerberos in deployment, or do we need HSD-ES token/basic auth through `/rest/auth/...`?
14. What are the HSD-ES rate limits and retry expectations for EQL query, article detail, comments/children, links and lookup endpoints?
15. Does HSD-ES expose enough history/state-change data for trend calculations, or only current article state plus comments/children/links?
16. Are HSD-ES writes in scope for this platform, or should HSD-ES remain read-only plus correlation for the first two phases?

## Decision Record

Current decision for next implementation wave:

```text
Implement Phase 1 as Python-native provider-neutral capabilities with Jira as the first adapter,
and reserve HSD-ES as the second peer provider before DTOs harden.
Use jira-cli as design reference and optional development comparison tool.
Do not fork or embed jira-cli in production runtime at this stage.
Do not enable HSD-ES writes until tenant-specific API and governance rules are reviewed.
```

Revisit the `jira-cli` fork/wrapper decision only after Phase 1 exposes a concrete missing capability where upstream behavior demonstrably saves more maintenance than it adds.
