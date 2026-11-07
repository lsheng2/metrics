# Reporting Development And Validation

Current development rules: [AI Contract](../../AI_CONTRACT.md).
Current behavior and task state:
[reporting guide](../../openspec/docs/current-baseline/project-reporting.md) and
[one task ledger](../../openspec/changes/add-provider-neutral-project-reporting/tasks.md).
The approved delivery order and interfaces are in
[delivery sequence](../../openspec/changes/add-provider-neutral-project-reporting/delivery-sequence.md).

## Environment

Reporting validation uses the existing separately installed interpreter:

```powershell
$reportingPython = Join-Path (Get-Location) '.tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe'
& $reportingPython -I -c "import sys, pywintypes, ai_base_application_sdk; from importlib.metadata import version; print(sys.executable); print(version('ai-base-application-sdk')); print(ai_base_application_sdk.__file__)"
```

Expected SDK is exactly `0.2.0a1`; its module must resolve under that selected venv.
It uses the unchanged `task-run/1` a2 pack. Exact wheel/pack and installation identities
remain in the [SDK contract](../../openspec/changes/add-provider-neutral-project-reporting/sdk-020-integration.md).
The retained main `.venv` contains SDK0.1.0a2 and is not a supported shortcut for migrated
report consumers. No current service is silently switched or upgraded.
The import check is environment evidence only, not a business test.

Use the existing no-dotenv entry, with explicit test nodes and a unique evidence filename:

```powershell
& $reportingPython -I scripts/validation/run_report_authoring_tests.py ui_web/tests/test_report_daily_ui_browser.py::TestReportDailyUiBrowser::test_shouldCarryEditablePersistentReferenceIntoActualNextDay -q --tb=short --durations=5 --junitxml=.tmp/dashboard-delivery-20261105/daily-two-day.xml
```

The named next-day case is the DAILY closure target; its existence alone is not a pass.
Do not run a missing test node as evidence. The tasks ledger records its implementation
and actual result. The runner denies external networking and suppresses dotenv loading;
local browser HTTP and separately scoped runtime IPC remain permitted.

## Validation Selection

| Layer | Proof | Fixture boundary |
| --- | --- | --- |
| L0 | schema, null/empty, dates, sort, fragments, delta, hashes | Pure values; no Git, database, browser or Base |
| L1 | durable command, CAS, recovery, source/summary/editorial preservation | Real isolated store only for the transaction being proved |
| L2 | auth, CSRF, forms/JSON, error codes, nullable serialization | Cheap boundary fixtures plus a small real-service wiring subset |
| L3 | real Milkdown editing, paint, keyboard, popup, Save/reopen | Mounted editor and real local HTTP/storage; synthetic upstream |
| L4 | matched application/SDK/Base/publication and complete week | Stable candidate, owned services/data, explicit normal cleanup |
| External qualification | actual provider/model/Outlook/deployment/scheduling | Separate authorization and evidence; never inferred from local JOIN |

Reuse immutable input/profile/source fixtures. Do not share mutable command, draft, archive
or acceptance state between independent cases. Case failures must preserve the actual response
and stop widening the test set until the relevant lower-level cause is understood.
Do not rebuild a week for every bad field or treat a passing same-source week as proof of delta analysis.

## Review And Publication

Use one writer and a bounded independent reviewer. A packet review can cover source, evidence
and the next dependency boundary; later evidence completion need not repeat unchanged source review.
After two equivalent failures without new evidence, change the hypothesis/diagnostic.
Review cost at packet boundaries and after 60 minutes on the same user problem.

Record runtime source, fixture/test and environment fingerprints separately.
For the SDK020 proof, the final strengthened test assertion did not change the runtime;
the delivery receipt explicitly preserves this distinction.
Do not extend that example to assume all test files are irrelevant: some are native fixture dependencies.

Stage only approved paths. The retained authoring WIP is not all another owner's work:
publish its verified closure separately from unrelated Scope/config/style edits.
A working-tree qualification is not a clean-install or formal deployment qualification.
Normal stop, emergency cleanup and still-running unrelated services are separate statements.

## DAILY Evidence

The current bounded packet is recorded in
[DAILY delivery evidence](../../openspec/changes/add-provider-neutral-project-reporting/daily-delivery.md).
The template counterexample exercises a single day's cell so another column cannot mask
reversed history/current-note ordering. The browser chain additionally proves actual next-day
creation, reference preservation, human text/paint and publication identity.
Observe GET/POST responses before waiting for navigation; retain failed attempts independently.
Same-meeting replay with changed effective choices intentionally returns 409 and the original
result. Test the visible unapplied-choice message and publication link; do not assume every
idempotent return redirects or change the service to silently ignore selected choices.
Only the complete chain plus its scoped review closes DAILY. This is not the full-week,
changed-source AI, clipboard/Outlook or clean-release qualification.

The 2026-11-05 manual two-day chain and three direct template cases are qualified in the
current worktree. The existing publication is reachable from a same-day conflict result;
history is displayed before the current source-status prefix within each cell.
That original docs-only checkpoint is superseded for source packaging by the verified
authoring/DAILY/delta closure `4cb995b` on main. Its unrelated Scope/config/style changes
were excluded. Request latency and the recorded native diagnostic incident remain explicit
limitations, not implied fixes.

## ASSIST Validation

The [ASSIST packet](../../openspec/changes/add-provider-neutral-project-reporting/assist-execution.md)
specifies the current profile, API, local receipt and editor contracts. Its task/qualification
state remains in the single ledger. Use the selected SDK interpreter, not the legacy venv.

Run pure profile/target tests and `test_report_assist_service.py` /
`test_report_assist_recovery.py` before `ui_web/tests/test_report_assist_browser.py`.
The browser cases mount the actual editor and save via real local HTTP; only the upstream
SDK transport is synthetic at this layer. They cover receipt retirement and same-text
acceptance as well as text/paint/cancel/unavailable states and mobile contrast/hit targets.

`project_management/tests/test_report_assist_http.py` separately uses the installed SDK,
the fixed Base source, a distinct registered authoring profile, and real data Git.
It verifies Save, subsequent human paint/provenance, publication and next-day inheritance.
Its source record is synthetic and it does not call a real provider or model.
The existing Base fixture accepts an explicit hash-matched profile; its default summary
profile/pack remains unchanged. Base-only dependencies are loaded in the Base process.

Evidence is retained under `.tmp/dashboard-assist-20261106/`, with unique XML and native
run directories. Do not count initial RED or an earlier happy-path source as final closure.
The export/clipboard sample and original five-day/cross-week chain now have separate
delivery receipts. This single-target Base proof retains its own bounded scope.

## Derived Export Validation

[The export packet](../../openspec/changes/add-provider-neutral-project-reporting/export-execution.md)
uses saved HTML as its source, with separate Markdown/Excel adapters and no new
publication files. Pure compiler checks precede one real-Git sample and mounted
browser downloads. The published path must pass with the renderer/source/finalize
methods poisoned, and preserve both publications' original bytes and Git head.

Run `project_management/tests/test_report_exports.py` without Git/browser fixtures.
Large parameterized values need explicit short pytest IDs on Windows; otherwise
`PYTEST_CURRENT_TEST` itself can exceed the OS environment-variable bound.
Repeatability tests change controlled clocks, not the system time. Bounds must
reject content rather than rely on openpyxl's truncating string assignment.

`ui_web/tests/test_report_export_browser.py` verifies actual downloaded files and
browser Clipboard API readback after Save, including paint in HTML. That proves
the browser route, not Outlook/native-app paste. Current evidence and limitations
are in [export delivery](../../openspec/changes/add-provider-neutral-project-reporting/export-delivery.md).
The original full-week/cross-week scenario has its own retained qualification receipt.

## Full Week Qualification

Use the existing owned launcher and the
[week packet](../../openspec/changes/add-provider-neutral-project-reporting/week-qualification.md).
The fixed `full-week` scenario uses three synthetic Jira records and the installed
SDK/local Base, with actual source capture and accepted summaries on the first day.
Later unchanged captures reuse those summaries. The browser driver performs the
six meeting dates through the actual templates, editor, Save and Finalize routes.

```powershell
& $reportingPython -I scripts/validation/project_full_stack.py prepare --work-root .tmp/sdk-020-join-20261105 --scenario full-week
```

Use the exact owned `run_dir` returned by `prepare` for `start`, `status` and
`project_week_browser.py --run-dir`. Do not select a run by directory age or use
another application's port. The driver stops its owned services in its finalizer
and retains all artifacts. Initial setup, per-operation deadlines and the service
lifetime are independent bounds; never extend an existing operation to make it pass.

After an interruption or PC restart, inspect the prior run's responses, canonical
checkpoints and stop receipt before starting anything. A finalized day needs its
verified publication, not only a screenshot or a successful Save. A failure and
normal cleanup are separate conclusions. A changed runtime requires a new frozen
candidate; do not combine its days with an earlier failed candidate or rewrite
historical request/hash bytes.

For a validator-only failure after publication, `--resume-after` can continue the
same run before the weekly-view step. It permits only the explicitly named
validator files to differ, verifies every retained day by reading actual original
artifacts again, and writes a new evidence directory. Application/shared-fixture
changes, incomplete checkpoints or a different source commit require a new run.
Old failures remain part of the evidence even if corrected validation later passes.

The refresh preparation binding uses the validated content hash; its active slot
separately binds the full stored intent. Initial saved-capture and replacement
formats retain their existing hash definitions. The shared producer/consumer rule
is covered by `test_report_preparation_publication_guard.py`; stale, superseded,
missing and downgraded bindings must continue to refuse publication.

The [qualified week receipt](../../openspec/changes/add-provider-neutral-project-reporting/week-delivery.md)
binds six daily publications, a weekly view, explicit empty-note/gap handling and
42 original-file rechecks. It is an operation/continuity qualification, not a
performance qualification. Concise business output and separate audit downloads
are covered by the later presentation receipt below, without rewriting that week.
Profile the recorded long prepare/view waits before choosing an optimization;
do not use more week runs to locate a read-path problem. The later Report Read
Performance section records that profiling and the qualified optimization.

## Concise Presentation

`standup/1` is a template presentation profile, not a new AI or source protocol.
It selects `template-document/2`; missing profile preserves legacy hashes/bytes.
Read/Save/render/Finalize route all user or pinned-renderer claims through the
strict validator. The builder must preserve the profile on Save.

Run the pure `test_report_standup.py` / `test_report_audit.py`, then the focused
`test_report_standup_publication.py` real-Git successor and original-byte test.
`test_report_presentation_guards.py` attacks an internally rehashed unknown
renderer through actual draft consumers. HTTP tests are
`ui_web/tests/test_report_standup_views.py`; the mounted sample is
`test_report_standup_browser.py`. Use the same selected SDK/no-dotenv entry.
No extra full week or Base dispatch is needed for this presentation boundary.

Audit export reads all six original files in one owner-checked, verified
publication pass. The deterministic ZIP has a separate generator revision and
does not alter publication format or re-render its body. The 32 MiB limit applies
before and after packaging. Runtime source/accepted/editorial authorities are
unchanged; original-week public readback remains separate from preview generation.

Evidence: `.tmp/dashboard-presentation-20261106/` and
[presentation delivery](../../openspec/changes/add-provider-neutral-project-reporting/presentation-delivery.md).

## Skipped Meetings

The [skip packet](../../openspec/changes/add-provider-neutral-project-reporting/meeting-skips.md)
adds a local append-only Django calendar chain. It does not change the SDK/profile
or start providers, scheduling or model work. Apply migration `0004` only in an
authorized deployment; tests use the isolated runner database.

Pure cases: `project_management/tests/test_report_meeting_contracts.py`.
State/admission: `test_report_meetings.py`, including an intent-only interruption
and original-command repair. Joined real-Git consumers:
`test_report_meeting_resumption.py`; retained legacy seed replay:
`test_report_history_core.py::test_should_prepare_immutable_context_seed_from_source_publication_and_template_use`.
The comparison normalizes absent legacy authority to `None` without changing bytes.

HTTP: `ui_web/tests/test_report_meeting_views.py`.
Mounted editor: `ui_web/tests/test_report_meeting_browser.py`, using real HTTP,
ORM, archive and Git. Finalize Friday, record two skipped weeks, resume Monday,
Save/reopen/Finalize, export and restore. The external source is synthetic and the
AI client is forbidden. A separate Chinese/390px case checks language navigation.
This is a direct two-date jump, not fourteen artificial daily runs.

Keep evidence under `.tmp/dashboard-skips-20261106/` with unique XML/run directories.
The seed snapshot uses its originally pinned calendar, even if the series policy
advances while preparation is delayed. Never read a live calendar to render an
already saved or published report. Validate old/new context readers, weekly
selection, original-byte downloads and missing-versus-skipped coverage separately.

## Source Observations

[The source-observation packet](../../openspec/changes/add-provider-neutral-project-reporting/source-observation.md)
separates source comparison from accepted-summary note eligibility. It keeps the
v1/v2 context shape and original source hashes. The source reader must continue
to check completeness before emitting `summary_pending` or `summary_stale`;
otherwise legacy `pending` plus a hash would no longer prove a complete capture.
Do not replace this invariant with a new interpretation of partial coverage.

Run `project_management/tests/test_report_source_observations.py` for manual
same/different hashes, uncertain sources and baselines, late/revised summaries,
old canonical bytes, human deletion/paint/link/AR, saved-empty notes and both
renderers. `ui_web/tests/test_report_source_observation_ui.py` covers actual
view-model/template output and gettext. Source producer tests separately protect
complete-source gating and unchanged accepted-summary reuse.

`test_report_source_observation_publication.py` uses the native capture service,
source reader, preparation worker and local Git with a synthetic provider and
`manual_only`. It captures twice, finalizes two days, verifies no duplicated note,
checks all six old files and inspects the derived Markdown/Excel.
`ui_web/tests/test_report_source_observation_browser.py` mounts Milkdown, verifies
the observation is not editable, then saves and reopens a colored human note.
The browser fixture is distinct from the native-Git proof; do not call it live
provider or model qualification. It checks EN/zh-Hans, 1440px/390px, text fit,
page overflow and observation contrast.

Evidence stays under `.tmp/dashboard-source-observation-20261107/`.
Keep failed runs separately; a test-fixture error is not a product regression.
No full-week, S1, Base dispatch or real enterprise-source run is needed for this
boundary. The installed SDK environment and no-dotenv entry above still apply.
Changing UI labels requires regenerating the checked-in zh-Hans `.mo` from its
`.po` with the existing `polib` compiler before bilingual validation.

## Report Read Performance

2026-11-06的症状与profile已固定为
[性能基线](../../openspec/changes/add-provider-neutral-project-reporting/performance-baseline.json)：
语言POST为毫秒级，工作台GET的主要成本是169次串行Git读取及重复packet校验。
这是历史单样本诊断，不是p95；原probe缺完整数据指纹，实施时需固定同一合成克隆做对照。

[架构](../../openspec/changes/add-provider-neutral-project-reporting/report-read-performance.md)
与[执行计划](../../openspec/changes/add-provider-neutral-project-reporting/performance-execution.md)
已落实读取与窄操作入口，任务状态仍以唯一ledger为准，完整验收不等于源码复审通过。
原始数据Git、权限、最新写锁校验和六文件bytes不变；不引入默认跨请求缓存或持久索引。

`scripts/validation/profile_report_reads.py`对已有owned synthetic实例运行真实Django HTTP；
`--scenario workbench|baseline|preparation|editor --samples 20`保留首请求与所有稳态样本，
`--dataset s1`选择页20/5秒规模门槛。输出目录只能在该run的evidence下，出站网络被禁止。
结果包含代码、运行数据、SDK/Django路径和前后指纹；`passed`只代表对应场景，不能替代
实际点击到最终列表可用的浏览器证据。首次超过10秒时停止扩样定位，不能提高期限。

S1使用`prepare_report_scale.py --manifest-from <owned-synthetic-run>`构建一次持久数据，
再运行reader采样。构建时的buffered Git/identity/quota替身只缩短测试准备，实际来源读取、
Git对象、checkout物化、六文件校验都恢复正常实现。不要用临时pytest目录保留大型验收数据，
不要把未物化index的fixture误判为健康checkout性能，也不要反复构建100份数据定位读取问题。
`profile_report_saves.py`接受同run的实际浏览器种子，可用`--resume-receipt`继续已确认修订；
每次用新命令和最新CAS，不修改或重放旧请求bytes。

验证先跑`test_git_read_batch.py`、`test_archive_read_limits.py`，随后query/consumer及
`ui_web/tests/test_report_query_views.py`与`test_report_query_browser.py`。
小规模原生fixture检验无误后才运行持久S1；`test_s1_scale_fixture_materializes_100_native_publications`
是显式慢门槛，不属于每次快速回归。手工Ego任务页消失时停止该surface并请求重建授权，
不接管用户页或把两次预检冒充十次最终样本。本次不授权8017、真实来源或正式模型切换。

2026-11-07用户授权新建专用验证空间后的十次实际语言切换全部通过；
从Apply点击到目标语言及五张完整表格绘制后的p95为3.101s，门槛仍为3.5s。
该次只补浏览器门槛，运行代码和S0数据前后hash一致，未重跑整周或重建S1；
旧测试与性能回执先核对文件hash和适用边界再复用，不冒充本次重新执行。
具体原始样本、截图、代码/数据/环境指纹与正常清理记录见
[性能交付回执](../../openspec/changes/add-provider-neutral-project-reporting/performance-delivery.md)。
此结果仅关闭本机限定性能门槛，不授权真实来源/模型、定时任务或生产服务切换。
