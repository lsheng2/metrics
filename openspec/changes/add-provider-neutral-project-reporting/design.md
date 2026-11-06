# Generic Project Reporting Design

Status: accepted direction; implementation is staged by tasks.md.

2026-11-06用户要求根据实际延迟建立架构优化规格。
[读取架构](report-read-performance.md)与[执行/验收](performance-execution.md)
定义模块内读写分离、一次请求固定head的批量Git读取、packet复用及窄操作入口。
此项尚未实现，不改AI Base或归档writer，也不以全局TTL缓存替代权限与完整性。

2026-11-06用户确认“精简站会正文＋独立完整审计附件”。
[呈现契约](standup-presentation.md)在既有schema2模板上固定`standup/1`与新版renderer，
保留旧模板/发布六文件和原hash；完整证据不再强制附在新正文。
这是报告层行为修订，不改SDK、来源采集、AI接受或editorial baseline。

2026-11-05用户已释放SDK集成点，SDK020真实本地HTTP合成资格已通过。
随后批准Dashboard交付复评及开始执行，当前顺序由
[delivery sequence](delivery-sequence.md)补充本设计：
治理/环境、两天人工闭环、真实变化的增量闭环、ASSIST、导出样本、整周/跨周。
[SDK契约](sdk-020-integration.md)和[交付回执](sdk-020-join-delivery.json)保留原证据；
本次不修改已发布SDK/pack，不自动启动真实provider/model或正式部署。
下文早期实施状态是历史背景；当前状态仅由tasks当前入口维护。

技术附录（同一方案，不维护独立执行状态）：
[应用接入包](application-integration.md)、[统一Provider访问/凭据](provider-access.md)、
[源码移植目录](migration-catalog.md)。这些新增接口尚未实现，W1原评审不自动覆盖它们。
跨仓公共能力要求见[AI Base增强请求](ai-base-enhancement-request.md)，其协议由基座维护，
Dashboard只拥有consumer适配和领域接受；不得把本应用的Jira/英文/无工具规则升为平台全局规则。
2026-11-01用户批准[API-EVO-01](ai-api-evolution.md)：早期开发允许协调式破坏性API变更，
不默认维护旧SDK/同步接口；变更必须交付版本化差异和各应用迁移包。
对外委托见[AI Base review与增强handoff](ai-base-review-handoff.md)，不是仅兼容适配请求。
当前双方执行分工、依赖与联合验证统一见[执行handoff](execution-handoff.md)；
各仓分别维护实施规格。2026-11-02用户要求提前集成，下一切片为
[W5.JOIN](early-ai-integration.md)，复用已完成的catalog/capture/archive，
不冒充W3-W7均已实施就绪；C0仍只是SDK进件证据。
2026-11-02用户确认[HTML模板与人工定稿](html-report-authoring.md)，
对应[分层验收](html-report-validation.md)。这是报告层补充，不修改基座冻结协议；
HTML为首选输出，原Markdown/Excel要求保留。当前后台与过渡界面已有实现，
直接富文本编辑/复制及Outlook仍未验收。
2026-11-03后续要求统一见[Report Authoring V2](report-authoring-v2.md)：
只WYSIWYG、`#ID`唯一触发、Stage路由及详细错误策略、用户自建版本模板与显式AI填写。
其[契约](report-authoring-contracts.md)、[补全](report-completion.md)、
[验收](report-authoring-validation.md)属于本change；
执行只在tasks的W6.AUTHOR维护，不另建Chiplet或编辑器项目。
组件/字段细节是本轮建议，产品尚未实现；不再要求用户另请编辑器Agent，
也不把早先“模板设计器backlog”作为取消新需求的依据。
随后几轮已确认的逐票/AR/来源状态前缀、人工颜色保留、稳定行序与累计note，
以及新补齐的跨周和触发默认值，统一见[报告连续性架构](report-continuity.md)。
source/analysis/editorial 三种基线分开，定稿Git确认是正式日报基线提交点；
周视图和定时准备不冒充正式定稿。本次只更新设计，产品节点仍未实施。
用户随后要求连续执行到full-stack；[手动全栈切片](manual-full-stack.md)定义运行入口、
共享业务服务、单worker归属、取消/恢复和FS01-FS10。准备好的报告编辑器本身不等于
采集至报告全链路已完成，真实provider/model资格也不由合成链路代替。

## 1. Boundaries

Project -> immutable Stage -> source selection -> Capture -> Delta -> AI candidate
-> accepted summary -> verified report snapshot -> editable draft -> explicit finalization/Publication.
Draft preview/copy/export is not publication. Raw capture and AI acceptance keep their existing
automatic history; only final report publication requires the new explicit user confirmation.
`project_management` is the domain/application owner, not `chiplet_*`.
`ProjectProviderProfile` remains connection/mapping/source configuration, not the user's project object.
One project has many stages; each stage has exactly one rule. No implicit active stage is selected.
Jira/HSD-ES mixing in one stage is not initial scope; users create separate stages.

Provider-specific parsing stays in `out/dashboard_scope_catalog.py`.
No direct imports of bug_metrics ORM/private repositories outside that adapter's public API usage.
UI uses a module public API, never reads Git paths or model credentials.
AI Base Task/Run is a dependency for authoritative AI execution, not for project creation or reading stored results.

## 2. Wave 1 Exact Contract

### Domain values

- `ProjectActor(subject: str)`: trusted transport identity; validated nonempty bounded string.
  CLI creates `ProjectActor("local_operator")`; no `--actor` switch.
  It is not a bearer token or public HTTP identity proof. Wave 1 exposes no HTTP routes.
- Project: UUID, owner subject, key, display name, archived, UTC created_at.
  key is exact ASCII `[a-z0-9][a-z0-9_-]{0,63}`; name trimmed, 1..160 chars, no control characters.
  `(owner_subject,key)` unique. Repeated same key/name returns existing project; different name conflicts.
- `ScopeSelection(profile_id: str, scope_id: int | None)`: exact registered profile ID;
  Jira requires positive int scope_id, HSD-ES forbids scope_id.
- `ScopeDescriptor`: provider_id, profile_id, endpoint, source_ref, query_kind,
  query, source_version. All are strings, bounded; only this whitelist is persisted.
  Endpoint is a configured nonempty HTTP(S) origin/base path without userinfo/query/fragment.
  Source descriptor is a source definition, NOT current membership, complete capture or runtime permission.
- Stage: UUID, project FK with PROTECT, key/name, selection JSON, descriptor JSON, definition_hash, created_at.
  No FK to provider/scope ORM: external deletion cannot cascade.
  Hash = SHA256 of descriptor JSON, sorted keys, compact separators, ensure_ascii=True.
  Names/timestamps and credentials are excluded; stored input is deep copied.
- Audit: project FK PROTECT, optional stage ID, kind (`project_created/stage_created/project_archived`), actor, UTC.
  No raw connection dict, query text or credentials in audit payload.

### Public module API

`ApiForProjectManagement(catalog: ScopeCatalog)`

```text
create_project(actor, *, key, name) -> ProjectSummary
list_projects(actor, *, limit=50, offset=0) -> tuple[ProjectSummary,...]
get_project(actor, project_id) -> ProjectDetail(project, stages)
add_stage(actor, project_id, *, key, name, selection) -> StageSummary
archive_project(actor, project_id) -> ProjectSummary
```

List is stable by created_at/id, limit1..100, offset>=0. Max100 stages per project for bounded detail.
Detail returns frozen descriptor and `source_status` = current/source_changed/unavailable.
Source lookup uses local configuration only; never calls network/model.
Unexpected storage errors propagate as internal failures, not empty success.
On source lookup unavailable, frozen detail stays available; catalog business failure is mapped only at that boundary.

ScopeCatalog protocol: `resolve(selection) -> ScopeDescriptor`, raises `ProjectError("SOURCE_UNAVAILABLE")`
or `INVALID_SELECTION`. Production uses existing public bug_metrics scope API and profile registry.
Trusted caller may inject a fake catalog in tests, not through HTTP/CLI.

### Production source translation

Jira: use `get_scope_config(scope_id)` and explicit provider binding; profile ID/provider must match exactly.
Freeze raw JQL as query, kind `jql`, ref `scope:<id>`, source_version=hash(raw JQL).
Do not use whole metric config hash as membership authority: severity/labels/bucket edits must not change the rule.
Profile endpoint changes affect descriptor hash. Scope enabled/profile enabled checked each resolve.

HSD-ES: use selected profile's `source_population.source_query_ref` and `source_query_hash`,
query is bounded canonical JSON of query reference, criteria/exclusion snapshot, tenant_or_site, subject_or_issue_type.
kind `saved_query`, source_ref=query ref. Empty ref/hash is SOURCE_UNAVAILABLE.
This freezes configured selection/version evidence, not a live saved-query definition. Wave3 must revalidate remotely
under explicit authorization before capture. Never claim remote query immutability from local metadata alone.
Only allowlisted scalar fields used; raw connection_settings are never persisted or emitted.

### Transactions

Ownership checked before source lookup. Writes serialized using transaction.atomic and locking the project.
Database unique constraints enforce exact identity; on concurrent unique conflict reread and compare immutable content.
On SQLite lock contention return PROJECT_BUSY, no blind retries. Unique constraints also prevent duplicate stage keys.
Reject stage insertion after archive; no unarchive/delete/edit-stage API in Wave1.
Source resolved twice before commit; differing descriptors fail SOURCE_CHANGED without a row.
This is optimistic configuration consistency, not a lock across all provider editors.
Later execution MUST resolve/check again; no Wave1 descriptor grants runtime authority.

Idempotency for stage: key/name/exact descriptor must match. Otherwise STAGE_RULE_IMMUTABLE.
Project archive and creation audit written atomically; repeat calls create no extra mutation event.
Errors: PROJECT_NOT_FOUND, PROJECT_ARCHIVED, PROJECT_KEY_CONFLICT, STAGE_RULE_IMMUTABLE,
INVALID_PROJECT, INVALID_SELECTION, SOURCE_UNAVAILABLE, SOURCE_CHANGED, PROJECT_LIMIT, PROJECT_BUSY.
Messages English, never include raw provider exceptions/connection values.

### CLI

`manage.py project_catalog` subcommands:
create --key --name; list --limit --offset; show <project-uuid>;
add-stage <project-uuid> --key --name --profile-id [--scope-id]; archive <project-uuid>.
Success stdout JSON `{schema_version:1,result:...,error:null}`.
Domain failure contains a safe JSON envelope after Django's standard CommandError prefix on stderr,
and nonzero exit via CommandError(returncode=1);
unexpected internal failure is not falsely reported as a domain success.
Real DB migration/deployment is separate. Wave1 validation uses dedicated test DB, not user's existing db.sqlite3.

## 3. Remaining API Boundaries

Each wave refreezes detailed code/test nodes against its actual dependencies before implementation.
These are concrete ownership contracts, not permission to implement placeholders.

| Wave | Producer / consumer | Contract / errors / side effects |
| --- | --- | --- |
| W2 Workbench | project_management API -> ui_web/facades/project_management.py -> views/templates | Authenticated owner mapping; GET list/detail read-only; POST create/stage/archive with CSRF; source_changed blocks execution, not historical reads; UI en/zh, safe errors |
| W3 Provider capture | provider port -> project capture service -> immutable archive | WorkItemIdentity(provider,endpoint,stable_id,key); CaptureEnvelope(scope_hash,principal_fingerprint,parts,coverage,source_hash,captured_at); unauthorized zero reads; partial comments/history cannot be complete |
| W4 Delta/history | capture/accepted baseline -> deterministic delta -> AnalysisInput | Added/edited/deleted comments by ID, previously captured versions retained, delta from last accepted summary; Git raw authority separate from ORM projection; source lost => pending, no watermark advance |
| W5 AI | summary service -> AI Base Task client -> candidate validator | Fixed policy/input/output schema, idempotent clientRunKey, unknown usage retained, evidence/owner/language validation; no implicit chat history; invalid result not accepted |
| W6 Reports | accepted summaries + pending work -> snapshot/templates/draft -> confirmed publication | HTML-first/email copy plus Markdown/Excel; separate human edits; all open actions, coverage/as-of and explicit prior-meeting baseline; one immutable data-Git writer, no auto-push |
| W7 Runtime/deploy | operator command -> operation log -> owned worker -> services | Manual trigger/status/cancel; original deadline/budget; no free-disk check, no automatic schedule; own process only; shared AI Base cannot be stopped by Dashboard |

The W2 exact API, trusted browser identity, session preview/hash confirmation, gettext boundary,
file ownership and U01-U12 tests are in [workbench-plan](workbench-plan.md).
That packet is reviewed at W1.REPLAN; its existence does not close W1.R or authorize skipping W2.R.
The first W3 connection/credential packet is [provider-foundation](provider-foundation.md),
with pinned donor references in provider-foundation-source.json. It is gated by W2.R/W2.REPLAN;
other W3/W4 capture/storage boundaries still require their declared pre-implementation detail.
The W3.ARCHIVE packet now has exact DTO/read/write/locking/quota/Git recovery contracts in
[capture-archive](capture-archive.md), with pinned source/resource/test inventory.
Its independent plan gaps were corrected and the packet is ready conditional on full W3.CREDENTIALS.
Provider documentation checked for later adapters is recorded in [provider-api-evidence](provider-api-evidence.md);
documentation discovery is not a claim that a live Jira/HSD source or complete response decoder is qualified.

HSD-ES initial capture may supply current canonical facts without full comment history:
same flow returns part coverage and blocks complete summary claims. Add adapter capability only after official
endpoint/schema confirmation and qualified samples, never infer Jira comment APIs apply to HSD.
No provider writes or unsupported live calls are part of this plan's initial authorization.

## 4. Reuse And Migration

- Scope/profile editor and provider registry retained; do not build a second connection-settings UI.
- Prior chiplet domain/delta/evidence/summary/archival logic are reviewed porting candidates in W4-W6.
  No editable dependency, raw PYTHONPATH, bulk copied runtime data or per-project hardcoded module.
  Explicit credential-only adoption is now authorized under provider-access.md; source code, credentials,
  history import and process ownership are four different migrations.
- Existing charts pin calculation_run_id/fact_snapshot_id; links to summaries include capture/publication IDs/as-of.
- Duplicate frontends may be retired only after feature parity and ownership qualification, not in Wave1.
- New project module does not imply old T12, all Dashboard apps or AI Base are complete.

## 5. Current Authorization And Isolation

Work directly in user-selected Dashboard checkout; preserve existing dirty Scope UI changes.
Single implementation writer, independent plan/validation/behavior reviews.
Default data root/db existing state is not migrated during tests.
UI beauty/mobile/multibrowser are backlog; desktop Chrome/Ego functional acceptance first.
Business output English, UI en/zh, raw text unchanged; TranslationPort remains separate/deferred.
No implicit live calls, schedules, provider writes or clearing history. No disk-free checks.

## 6. Integration And Porting Amendment

Before this amendment, W3-W7 named broad capability groups only; app-owned integration assets,
credential adoption and exact donor-to-consumer mapping were not fully enumerated.
The appendices now enumerate these obligations without claiming that implementation or runtime verification passed.

ProviderAccessService is the common owner behind new provider_access CLI and Web/worker consumers;
internal service calls do not spawn CLI. Current legacy command output remains stable during delegation migration.
Same Jira endpoint is not proof of same principal or scope. Dashboard configured credentials are preferred,
with explicit endpoint binding and no post-auth-failure fallback. Never directly access the Jira database.

Capture depends on a working immutable archive/admission boundary before real source collection.
Therefore W3.ARCHIVE precedes W3.CAPTURE; W4 extends it with version index, cumulative delta and import,
not an unrelated second archive. Old mandatory F2/F3 capabilities are listed as unimplemented work,
not quietly treated as reusable donor modules.

The AI package reuses the existing English summary instructions, schema and evidence validators,
but runtime Task and optional Chat use separate profiles. CLI tools/skills are not required by the
first strict summarizer. Optional tooling is disabled until its authority and actual loader are validated.
Fixed task compilation/publishing APIs belong to AI Base; project report acceptance/publication remains here.

AI Base may replace the proposed API/SDK/profile shapes after review. W4.REPLAN must freeze the actual
contract pack and affected Dashboard consumer paths before W5. Existing workbench migrations belong to
W5.MIGRATE, not optional W5.CHAT. New or changed interfaces require version rejection and migration tests;
old protocol assertions may be replaced only with an explicit change-to-test mapping that preserves business guarantees.
