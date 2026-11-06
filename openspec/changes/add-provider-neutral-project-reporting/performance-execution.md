# Report Performance Implementation Plan

> For agentic workers: 按 `AI_CONTRACT.md`、Superpowers TDD 执行，状态只写本change的tasks。

**Goal:** 消除报告工作台与日常操作的重复Git读取，保持全部业务与安全保证。
**Architecture:** 模块内查询/命令分离，请求级固定head和中立批量读取port；不增加持久索引。
**Tech Stack:** 现有Python/Django、Git、Bulma/htmx、SDK0.2.0a1验证环境。
**Spec:** [架构/API](report-read-performance.md)、[规范场景](specs/report-query-performance/spec.md)。
profile_source: repo-local。agent_routing_mode: multiagent-configured，主agent为唯一实现写入者，
Architect Planner Reviewer承担独立设计/最终审查，验证设计并入同次审查；不额外复制ledger。

## 1. Scope And Invariants

源码基线`d21250a2d4eee0de6f4234029591b4340e607557`；13项既有Scope/config/main.css改动
以`.tmp/dashboard-presentation-20261106/protected-before-commit.json`核对并排除。
无真实来源/模型、正式DB迁移、发送、定时或服务切换授权。此轮创建规格不是产品性能通过。
沿用`source / accepted summary / editorial`三基线、原六文件、原命令幂等、scope/actor、
pinning、stale-save、skip、取消/未知结果和Git确认边界。禁止为性能删除任何负例。

读取依据为原profile，不把profile累计时间简单相加当总耗时，不声称根因是
Windows Defender/磁盘/代理/SDK；这些原因没有被本次证据证明。

## 2. Registry And Propagation

| ID / risk | Authority / producer | Consumers | 必须反证 |
| --- | --- | --- | --- |
| PERF-BATCH / high | `app/spi/archive_reads.py`、`storage/git_read_batch.py` | `archive_read_view.py`、原GitRunner | 错OID/type/mode/size、missing、截断、超限/超时/进程残留 |
| PERF-SNAPSHOT / high | `services/report_archive.py`、`storage/archive_read_view.py` | archive_reads、publication reads/packets、draft listing、history | H移动、身份变化、跨view复用、脏checkout和mutable runtime混版 |
| PERF-QUERY / high | `app/api/report_queries.py`、`services/report_queries.py` | `ui_web/facades/project_reports.py`与工作台模板 | 页大小/排序变化、坏记录被忽略、重复校验、零条假成功 |
| PERF-COMMAND / high | daily/forms/facade的窄入口 | preview、prepare、reprepare、detail、CLI/worker沿原service | 非法/foreign、CSRF、错误输入丢失、模板归档导致旧command不能重放 |
| PERF-WRITE / high | 原writer锁和最新revision/基线 | publication/resume、preparation reservation、skip占位 | 旧GET缓存绕过CAS、两窗口覆盖、提交后旧view复用 |
| PERF-EVIDENCE / normal | 有界本机性能runner | 回执、current guide、CI定向tests | 只计302/首屏、不计最终表格、p95样本不足、失败/重试排除 |
| PERF-LOCAL / high | `storage/read_workers.py`、`archive_read_view.py` | 工作树核验、只读草稿列表 | 最多4个本地读取任务、错误/期限后回收、顺序及原缺失/拒绝语义；不并行Git写入 |
| PERF-DECODE / high | `storage/report_decoding.py`、`app/domain/report_publication_validation.py` | draft intent/command/revision、publication revision | 精确完整输入hash、每view作用域、可变返回隔离，坏正文不得命中另一输入的成功校验 |
| PERF-RUNTIME / high | `storage/project_operations.py`、`report_drafts.py` | 原运行观察/恢复、修订链与发布 | 只在一次观察复用不可变request和命令扫描；损坏/重复/缺失的命令仍拒绝 |
| PERF-PATH / high | `storage/paths.py` | capture/report/runtime读写 | 单次不跟随链接的逐级检查；重解析点、硬链接、非目录、打开后身份变化仍拒绝 |
| PERF-RUN-READ / high | `services/project_operation_archive.py`、`storage/project_operation_reads.py`、query DTO | `ui_web/facades/project_runs.py`、`views/report_access.py` | 仅同归档复用；project/stage/actor/hash不匹配必须独立读取；运行结果不进入Git/AI新任务 |
| PERF-PROJECTION / high | `app/domain/report_queries.py`、`services/report_publication_reads.py` | 工作台、publication选择、weekly表单 | 原六文件完整validator每packet一次；只省略未被UI消费的checkout诊断，旧API仍校验并返回原状态 |

具体旧消费者：
`services/{archive_reads,report_draft_listing,report_publication_reads,report_daily_baseline,
report_continuity_preview,report_continuity,report_period_views,report_meeting_occupancy,
report_preparation,report_publication,report_historical_references}.py`，
`storage/{report_drafts,report_publication_packets,report_draft_preparation_bindings}.py`。
所有路径以`project_management/`为根；UI只消费`app/api/`。
对高风险消费者必须有下表用例或明确保持原实现的理由，不能仅写“用了公共helper”。
补齐`services/report_sources.py::PinnedReadRepository`的明确批量适配，保留原固定commit与
不可暴露writer约束。`app/domain/capture_values.py`仅给精确JSON标量增加转换快路径，
不改变canonical bytes、浮点/非字符串key/bytes的拒绝规则。

### READ Implementation Amendment

2026-11-06固定克隆`2be188e9-7cce-4889-8297-f8ed268ec28a`的原路径31.602s/169 Git。
批量读取已降为8 Git，但未达SLO；无profile开销的边界计时显示本地工作树约0.8s、
草稿约1.5s。隔离四线程实验完整返回同页，稳态约3.72s，**不是正式验收**。
因此增加请求级、有界的本地文件读取重叠；不并行原逐文件Git，不增加全局缓存、持久索引。
只读任务保持输入顺序，最多4个in-flight；共享Git/cache访问串行，所有worker在view关闭前
回收。错误、取消或共同deadline到期时停止排队并等待已拥有任务退出；失败不能返回部分成功。
补测线程上限/顺序/错误回收、同packet解码复用、修订变化和worker来源读取。
本节新owner路径及`test_archive_read_limits.py`、`test_read_workers.py`、`test_report_read_reuse.py`
纳入READ，不扩展实际SDK/provider/数据格式权限。READ/REPLAN仍未完成，性能门槛不变。

同一次核心复审允许推进COMMAND实现；API/errors、其他消费者及正式SLO仍须验证。
`refreeze_actions=[{action:amend,reason:overlap bounded local reads and share the authorized operation read; retain final gates}]`。
`updated_artifacts`为本执行计划、`report-read-performance.md`和本change的`tasks.md`；
`rerun_gates=[W6.PERF.READ,W6.PERF.COMMAND,W6.PERF.ACCEPT.R]`；
`post_refreeze_preflight_result={method:source/consumer matrix and independent READ review cross-check,result:PASS}`。
新增控件与访问组合文件`ui_web/facades/report_controls.py`、`ui_web/views/report_access.py`
属于COMMAND；后者维持旧`project_reports`访问mixin及helper导入兼容。
预览/错误页使用`preparation_error.html`，不提供虚构的空历史。
HTML控件可单独读取有界capture选项；JSON和成功POST不需要这些选项。
`ReportDailyPreviewRequestForm`做有界语法校验；业务服务继续验证所有ID、模板和原命令重放。

2026-11-07：S0正式工作台20样本p95 2.896s，baseline 2.573s；S1持久夹具为100/100/100、
5修订、3票。旧临时S1遗失且checkout未物化的验证器问题已独立反例修复。
持久S1首次真实HTTP还揭示历史fixture的`selection_json.revision`不符合`ScopeSelection.scope_id`，
只修该合成目录记录，不改归档文件；修复后的20请求全200但p95 9.250s，未通过5s门槛。
分段计时为工作树5.280s，Git1.075s；16线程实验仅降到7.650s，**不进入产品**。
重新核对消费者后采用定稿列表专用投影，省去未显示的checkout计算；采集状态和旧API保持。
新增反例同时毒化未使用诊断并观测完整validator，防止把省诊断变成省完整性检查。
`refreeze_actions=[{action:amend,reason:the workbench must not compute an unconsumed global checkout diagnostic}]`；
`updated_artifacts=[report-read-performance.md,performance-execution.md,specs/report-query-performance/spec.md,tasks.md]`；
`rerun_gates=[READ projection/source/HTTP consumers,S0/S1 timing,W6.PERF.ACCEPT.R]`。
范围仍限本change的READ/COMMAND所有者，新增API只在工作台query返回值中使用；
不改变旧publication API、输出文件schema、writer权限、恢复边界或性能门槛。
实施结果：专用投影9项通过、独立复审READY，持久S1的20请求p95降至4.105s；
最终S0首请求3.860s、20请求p95 2.876s。READ及其REPLAN已完成。

Save正式20样本曾为2.236s，证据保留；形状表单并未消费snapshot却预读草稿。
`ui_web/report_authoring_forms.py`的snapshot参数改为可选，Save v2先按owner/project/stage
校验和有界语法解析，直接进入原锁内业务服务。v1、target/reference/assist/CAS校验不变。
7项HTTP拒绝/保存用例通过；在同一稿第24到43修订继续20次实际Save，p95 1.839s、
全200、重新打开成功。新测量脚本`profile_report_saves.py`与`profile_report_language.py`
及`test_report_save_validation.py`归ACCEPT；正式采样只在同候选且无并行测试时执行。
Preparation详情只在`can_reprepare`为真时读取capture选项；定稿详情没有此UI，禁止为
未显示控件重读归档。原拒绝/可重新准备的控件与绑定输入不变。

| Consumer category | 裁定 |
| --- | --- |
| public API / internal facade | applies：query service、旧list/detail、只读port |
| UI route/template | applies：工作台、daily preview/actions、错误页；无视觉重设计 |
| export/report | applies：original-byte equivalence、同packet复用；不改内容 |
| audit/log | applies：仅低基数字节/次数/时间诊断，不写用户正文或凭据 |
| validation script | applies：专用性能选择与现有runner扩展点，不建测试平台 |
| migration/schema | not-applies：无DB迁移、原文档schema保持 |
| background job/scheduler | worker为affected consumer；不新增后台索引/调度，scheduler仍独立后置 |
| cache/index/search | 请求级缓存applies；持久索引deferred，须规模profile证明必要后另获批准 |
| external artifact | 六文件读取applies；历史数据/制品格式和远端不变 |
| CLI/admin | 原CLI服务调用受影响；无新业务CLI，仅内部验证命令 |
| docs/operator | applies：本包、当前报告指南和验证指南 |
| fake/fixture | applies：明确read adapter、隔离真实Git、多规模合成记录 |

## 3. Execution Graph

```text
W6.PERF.PLAN.R
  -> W6.PERF.READ
  -> W6.PERF.READ.REPLAN
  -> W6.PERF.COMMAND
  -> W6.PERF.ACCEPT.R
```

READ是第一个完整纵向切片：批处理、共享view、工作台实际GET和对照数据一起交付，
不先写完大基础设施再发现页面未使用。READ.REPLAN复核实际瓶颈和后续消费者，
任何amend/supersede/retire都在tasks记`refreeze_actions/updated_artifacts/rerun_gates/
post_refreeze_preflight_result`。COMMAND依赖这个复核，不重复原全部作者资格。

| Node | owner_paths / 产物 | RED -> GREEN / Exit |
| --- | --- | --- |
| PLAN.R | 本三份规格、tasks、design导航、current/development指南 | 反例与范围检查、独立设计/验证审查、OpenSpec strict；不是实施完成 |
| READ | 新`project_management/{app/domain/report_queries.py,app/spi/archive_reads.py,storage/git_read_batch.py,storage/archive_read_view.py,services/report_queries.py,app/api/report_queries.py}`；既有`storage/git.py`、`repository.py`、`report_publication_packets.py`、`report_drafts.py`及section2读取消费者、`app/api/report_factories.py`、`ui_web/facades/project_reports.py`；对应测试 | 第一工作台真实GET使用新路径、校验/原bytes等价，Git计数下降；输出完整不靠延迟加载；先证明下述P01-P12 |
| READ.REPLAN | tasks与本执行计划、profile回执 | 冷读和规模计数符合目标或明确改设计；不能靠增加超时继续；必要索引为新批准边界 |
| COMMAND | `ui_web/{views/report_daily.py,views/project_reports.py,facades/report_daily.py,facades/project_reports.py,report_daily_forms.py,report_forms.py,report_daily_responses.py}`、`templates/projects/reports/{daily_preparation,preparation,preparation_error}.html`；原writer/helper必要consumer | P13-P18：成功动作不构建历史列表；失败输入保留；最新锁内校验、作用域销毁 |
| ACCEPT.R | 两个新测试fixture/runner、current/development指南、源码范围回执、tasks | 匹配候选的20样本、浏览器用户流程、负例、独立复核、scoped commit与远端SHA |

文件数增长不放宽source400/test600行规则。`storage/git.py`只提取共享安全进程runner
所需最小部分；不进行无关格式化或writer重构。脚本`profile_report_reads.py`复用既有
no-dotenv、owned-run和loopback限制；fixture命名在下一节。原临时profile脚本仅作为证据。

### First Failing Checks

新增`project_management/tests/report_read_fixtures.py`提供受控真实Git的三份publication，
通过原公开Save/Finalize建立；`stage_read_fixture`返回`queries/actor/project_id/stage_id/
git_calls/expected_rows`。不得直接拼错误的最终context代替合法writer。
`ui_web/tests/report_query_fixtures.py`复用既有daily HTTP与browser支持，只替换外部来源。

```python
def test_workbench_reads_each_original_blob_once(stage_read_fixture):
    f = stage_read_fixture
    page = f.queries.workspace(
        f.actor, f.project_id, f.stage_id, query=ReportWorkspaceQuery(),
    )
    assert len(page.publications.items) == 3
    assert f.git_calls.full_publication_blob_fetches == 18
    assert f.git_calls.repeated_blob_fetches == 0
    assert f.git_calls.total <= 16
```

计数在实际transport观察，不通过mock替代被测读取逻辑。创建fixture的Git调用不计入
被测GET，计数器在请求前重置；预热对象缓存不得藏在fixture setup里。
旧实现预期因重复读取/进程数或尚无API失败，先保留RED再实施。

```python
def test_prepare_success_does_not_list_workbench_history(daily_http_fixture):
    f = daily_http_fixture
    f.poison_workspace_listing()
    response = f.submit_saved_capture_manual()
    assert response.status_code == 302
    assert f.preparation_count() == 1
    assert f.new_model_calls == 0
```

poison只作用于页面历史列表，不屏蔽原服务的baseline、source、authority验证。
测试既有业务逻辑，不以“mock被调用”当成功。

## 4. Layered Cases

| ID | 层 / 目标文件 | 内容与拒绝结果 |
| --- | --- | --- |
| P01 | L0 `test_git_read_batch.py` | 二进制含LF/NUL、空blob、重复对象/不同路径，字节与请求顺序正确 |
| P02 | 同上 | missing、ambiguous、非blob/mode、错OID、坏size、尾部额外数据、断包，整批拒绝 |
| P03 | L1 `test_archive_read_view.py` | 每批/每view额度、共同deadline、子进程失败/取消/清理，无遗留helper |
| P04 | 同上 | head H读取中追加H2，view仍是H；下一view必须看H2，跨owner/stage/cursor拒绝 |
| P05 | 同上 | 批量provenance与原逐项Git对照；oldcommit、同tree不同commit、缺记录、历史截断不能假报None |
| P06 | 同上 + `test_capture_archive_git_native.py` | 不信任可修改checkout，手改文件/index后stale；原writer不覆盖手工checkout |
| P07 | L1 `test_report_query_service.py` | 草稿与publication共享六文件，一份packet每view一次完整校验；文件坏hash仍拒绝 |
| P08 | 同上 + `test_report_listing.py` | 20条分页、100条上限、字典序/采集cursor、旧schema和坏记录维持原语义 |
| P09 | 同上 | draft current/finalization指针中途移动返回409，不能混版；新Save后新scope读取新revision |
| P10 | `test_report_query_consumers.py` | baseline、period、historical reference、skip occupancy、preparation binding都走限定view且不降低验证 |
| P11 | 同上 + `test_report_publication_security.py` | get/snapshot/下载/审计相同commit的原bytes；foreign、corrupt、未知schema拒绝 |
| P12 | L2 `ui_web/tests/test_report_query_views.py` | cold工作台实际HTTP用新query；含全部表格、CSRF/copy/finalize入口正常，不以隐藏历史达标 |
| P13 | 同上 | 语言POST零归档读取，保留next/语言cookie/owner；重定向后HTML lang正确 |
| P14 | 同上 | JSON baseline/detail不构建HTML/三列表；HTML仅加载必要controls |
| P15 | 同上 | prepare/reprepare成功不调用workbench listing；manual/no-change零模型 |
| P16 | 同上 | 非法/CSRF/foreign、pending/skip/CAS拒绝；错误页面保留绑定输入及原command |
| P17 | L1 `test_report_query_consumers.py` | 保存前外部窗口推进revision、editorial head或skip变更，旧GET缓存不能绕过写锁校验 |
| P18 | 同上 | Git提交应答丢失恢复仍读原packet；query read timeout不等于取消、失败重派或退款 |
| P19 | L3 `ui_web/tests/test_report_query_browser.py` | 实际切换en/zh、preview、Save/reopen、重复prepare、Finalize/原HTML下载；可见最终内容计时 |
| P20 | L1/L3 `scripts/validation/profile_report_reads.py` | S0/S1固定规模、首请求/20样本、并发读/写及计数回执，低基数无凭据输出 |

同类错误用参数化L0；不每个坏字段开Git/browser/Base。先完成READ纵向切片，再跑
受影响consumer，最后一个浏览器组合流程；不重建完整工作周或真实SDK任务。

## 5. Performance Gates

以下数字是本次设计的**验收目标**，不是已经达成的优化结果。网络/model执行不计作
应用本地读取SLO，但必须单独披露实际端到端耗时，不能删掉请求等待来美化数字。

数据集S0：复用原症状规模，8 captures、9 drafts、7 publications及原修订/大小；
在owned数据克隆上做写操作，保留原周证据只读。记录clone/源文件hash、code SHA、
Git/Python/SDK/浏览器版本、CPU/进程并发、响应大小。
S1：100 captures、100 drafts、100 publications，页20，每稿5修订，3票固定文本。
此为有界规模验证，不声称覆盖无限历史；大input单独走字节额度负例。

| 指标 | S0目标 |
| --- | --- |
| language POST，不含后续GET | p95 <=150ms；归档Git调用0 |
| 工作台GET | 进程首请求 <=5s；稳态p95 <=3s |
| 点击Apply至目标语言和全部列表可用 | p95 <=3.5s |
| baseline preview / preparation detail本地读取 | p95 <=3s |
| 已加载编辑器的Save POST，不含导航 | p95 <=2s；若写I/O占主导，须独立profile，不能豁免 |
| healthy工作台Git进程数 | <=16；不能随选中每份文件产生一个进程 |
| 同一view重复publication完整blob读取 | 0；validator对相同packet至多一次 |
| S1工作台页20 | 稳态p95 <=5s；Git次数 <=24；read预算/结果完整 |

首次应用进程请求和稳态分开；进程首请求不等于清理OS文件缓存，禁止清用户缓存或停安全软件。
S0优化后至少20次串行独立HTTP请求，p95使用nearest-rank并保留全部样本/失败。
UI至少10次语言往返；报告实际最大值及样本数，不混作20次HTTP的同一统计。
baseline旧慢结果仅作已存单次对照，不把它冒充分位数；需要同机复核时最多3次。
第一实际GET仍>10s或计数未下降，立即定位，不先跑20次慢测试。
并发场景两reader、一writer受控交错，单列正确性/峰值内存，不能共享全局权限缓存。
超目标时READ.REPLAN明确继续/缩小假设/修改设计，不静默提高门槛。

## 6. Commands And Evidence

执行环境固定为SDK0.2.0a1、原a2 pack；主`.venv`不用作报告验证。
所有目标在实现前明确为待建，不以collect-only、文件存在或mock日志作为通过。

```powershell
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py project_management/tests/test_git_read_batch.py project_management/tests/test_archive_read_view.py -q --junitxml=.tmp/dashboard-read-performance-20261106/io.xml
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py project_management/tests/test_report_query_service.py project_management/tests/test_report_query_consumers.py -q --junitxml=.tmp/dashboard-read-performance-20261106/service.xml
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py ui_web/tests/test_report_query_views.py ui_web/tests/test_report_query_browser.py -q --junitxml=.tmp/dashboard-read-performance-20261106/ui.xml
openspec validate add-provider-neutral-project-reporting --strict --no-interactive
```

profile runner参数固定为`--run-dir`（经`require_owned_run_dir`）、`--output-dir`
（owned evidence目录）、`--scenario workbench|baseline|editor`、`--samples 20`。
启动只接受明确manifest绑定的合成实例；不读.env、不切8017、不可接受任意外部URL。
每次命令结果独立文件，不覆盖RED/失败记录。输出request阶段、Git count/bytes/time、
SQL time、状态码、body hash、freshness及cleanup；不记录Authorization/cookie/query原文。
HTML/body语义对照忽略CSRF和诊断时间等非业务字段，publication六文件仍逐字节相等。

尺寸/空白、isolated Django check、文档链接、strict OpenSpec、独立评审和scoped
commit/push为最终交付门槛。若发布检查只改文档，不重跑未变产品；若改共享读取，
必须补consumer测试，旧整周证据仅在文件/版本/权限语义不变的边界复用。
单问题60分钟复核投入；两次同类失败无新信息就变更假设或instrumentation。

## 7. Design-Only Exit

本轮完成规范、接口、消费者与执行分解；`W6.PERF.PLAN.R`可以按独立评审关闭。
READ/COMMAND/ACCEPT在真实实现与计时前保持未完成。更新当前指南的已知瓶颈和设计导航，
不能把“规格已写好”描述成延迟已修复。原更大Dashboard及live资格不因本包关闭。
