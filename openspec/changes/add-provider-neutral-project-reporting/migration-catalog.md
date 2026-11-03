# Reuse And Porting Catalog

2026-11-01静态盘点。旧库根 `D:/AIGC/chiplet_programmgr`，
冻结参考commit `3d06b7a4a25434ee2fa133c9b4bef5f9c7c1366d`。
新执行根为Dashboard；下面的src/standup和tests路径除特别注明均相对旧库。
这是能力族盘点和代表性依赖/测试，不是已迁移文件清单或旧T12全部验收证明。

## 1. 如何判断能否直接搬

- A：算法/数据结构可优先复用，仍须改import/schema资源、provider身份边界并在目标环境测试。
- B：功能已经存在，但装配、持久化、权限或依赖耦合明显，移植其完整行为边界，不只拷一份入口文件。
- C：复用协议/测试思想，运行后端重新接线；旧进程、资格回执或环境不能原样接管。
- D：旧库只有设计/未完能力，不能统计成已实现可复用。

旧库要求Python>=3.14、Django5.2.18；Dashboard现为Python3.13.7、Django6.0.7。
不得通过安装整个旧wheel进入Dashboard环境，或editable/PYTHONPATH指向旧库来“完成迁移”。
允许在隔离服务间走固定API，或把通用代码移入目标模块/独立版本包；一个生产责任只有一个可修改实现。

## 2. 能力映射

| ID/类 | 已有代码、行为与代表测试 | 目标与必须适配的边界 | 对应叶任务 |
| --- | --- | --- | --- |
| MIG-01 A | `domain/{values,snapshots,delta_contracts,delta_observation,delta}.py`；`compare_snapshots/build_delta/equivalent_to_baseline`；tests/unit/test_delta{,_history,_order}.py | `project_management/app/domain/captures.py`、`delta.py`；扩provider/site/stable_id，保留连续已捕获B/C、accepted baseline与access-loss语义 | W4.DELTA |
| MIG-02 A | `domain/evidence.py`、`analysis_{validation,ownership,language,spans}.py`；tests/contract/test_analysis_span_quotes.py、tests/unit/test_analysis_authorization.py | `app/domain/evidence.py`与summary校验；旧issuelinks和Jira people字段改adapter提供；引文和owner_confirmed=false不放松 | W4.EVIDENCE/W5.ACCEPT |
| MIG-03 A/B | `analysis.py`、`analysis_chunks.py`、`analysis_{material,packing}.py`；tests/unit/test_analysis_chunks.py | `app/domain/analysis_input.py`；保留旧摘要+累计delta+必要证据、无损分块；schema加载从新包，不隐式加载旧RuntimeResources | W5.INPUT |
| MIG-04 A/可选 | `analysis_wire.py`、`wire_*.py`、`prompts/standup-wire.md`；tests/unit/test_analysis_wire.py | 保留经测试可逆codec为可选；先普通JSON适配基座，超长才选codec；wire hash与logical hash分离，不要求首批移全部压缩层 | W5.INPUT |
| MIG-05 A/B | `adapters/{spreadsheet,spreadsheet_archive}.py`、`services/spreadsheet_inputs.py`；tests/unit/test_spreadsheet_{archive,inputs,cli}.py | `out/spreadsheet_source.py`；ZIP/公式/超限拒绝复用，ID解析改provider策略，冻结名单需重新批准stage；不是Excel即自动授权 | W3.LISTS |
| MIG-06 B | `adapters/jira{,_capture,_scope,_transport}.py`、`jira_{consistency,comparison,evidence,retention}.py`；tests/contract/test_jira_{capture,scope,access_loss,consistency}.py | `provider_sync/out/jira_capture.py`等；复用完整采集与原文保留，接Dashboard身份/预算/TLS/endpoint，Node JQL依赖按成本决定是否固定包保留 | W3.GATEWAY/W3.CAPTURE |
| MIG-07 B | `adapters/jira_credentials.py`；tests/contract/test_jira_credentials.py | 迁移的是secret值或受保护reader能力，不是整个旧config；Dashboard显式来源解析、ACL/路径与CAS采用；绝不输出token | W3.CREDENTIALS |
| MIG-08 B | `storage/{archive,repository,objects,staging,paths,versioning,jira_codec,jira_snapshot}.py`；tests/integration/test_archive{,_lineage,_publication,_security}.py | 新独立capture archive/public API；复用Git权威/对象hash/先归档原则，安装路径、stage映射、JSON资源、metadata owner重新适配 | W3.ARCHIVE/W4.INDEX |
| MIG-09 B | `storage/index*.py`尤其`index_acceptance.py`、`storage/denial.py`；tests/integration/test_index_{transactions,boundaries,wal_recovery}.py | 可重建索引/accepted CAS，不重复建第二个业务真相；新DDL/migration及stage身份，不覆盖原Git记录 | W4.INDEX/W5.ACCEPT |
| MIG-10 B | `resources.py`、`resource_{ledger,capacity,retention}.py`、storage/admission.py；tests/unit/test_budget{,_edges,_review}.py | 业务预算/存储准入与AI Base usage关联；旧全局安装注册表必须解耦，不恢复free-disk检测、不清零unknown | W3.ARCHIVE/W5.CLIENT/W7.RUN |
| MIG-11 B | `adapters/history_import.py`、`services/history_import*.py`、`storage/import_archive.py`；tests/integration/test_history_import{,_offline,_segments,_consumers}.py | `project_management/history_import/`；源闭包/原文时间/hash原样保留，旧workspace到project-stage显式映射；CLI/Web是新接线，旧F1 UI未完成不能算复用通过 | W4.IMPORT |
| MIG-12 A/B | `report_{data,rendering,excel_writer,validation,row_validation}.py`、`reports.py`；tests/unit/test_report_{data,rendering,validation}.py、tests/integration/test_report_{export,failures,publication_order}.py | `project_management/reporting/`；English/公式注入防护/有界输出与不可变发布复用；provider安全链接重适配。HTML模板、人工编辑、邮件复制和显式定稿为新增能力，不能算旧代码直接迁入；openpyxl私有writer仍需锁版本/替代验证 | W6.RENDER/W6.PUBLISH及W6.HTML.* |
| MIG-13 A | `prompts/standup-summary.md`、`schemas/{analysis-input,summary-output,analysis-fragment-output}.schema.json`；`translation.py`、domain/translation.py | ai_bundle/prompt/schema；provider-neutral命名，保持raw Unicode、事实/推断、下一负责人依据；TranslationPort首版disabled | W5.APP |
| MIG-14 B/C | `services/runs.py`、`services/run_attempts.py`、`storage/operations.py`、`storage/operation_{submission,reads,cancellation,interruption}.py`；tests/integration/test_run_wire.py | 复用状态/原deadline/幂等/outcome协议；Dashboard operation服务与AI Base Run关联，不能同时控制同一个AI执行 | W7.RUN |
| MIG-15 C | `platform/*`、adapters/service_runtime.py、host/custody/IPC相关文件；原生资格测试 | 不整体移入；Dashboard已有lifecycle实例/共享消费规则，先owner矩阵再选后端；旧keeper退役/冷恢复单独维护，非“换包即修复” | W7.DEPLOY |
| MIG-16 B/条件启用 | `backup.py`、`external_backups.py`、`storage/backup_*.py`、`retention.py`、`scheduling.py`、`schedule_service.py`；tests/integration/test_backup.py、tests/contract/test_schedule_service.py | 先保留接口与历史不丢规则，接新安装/归档owner后验证；正式定时/异机备份另批准，不默认启用 | W7.PROTECTION |
| MIG-17 B/按需 | `adapters/remote_{profile,probe}.py`、domain/remote_target.py、storage/remote_attempts.py；tests/integration/test_remote_deployment.py | 用户指定数据Git remote的隔离资格与凭据；不继承代码origin，既有Dashboard无需求时保持待启用能力，不删旧要求 | W7.PROTECTION |
| MIG-18 不搬壳 | 旧web/templates/static、cli_*、runtime_application.py、整份config/default | 复用交互/拒绝场景，不搬第二个Django项目或Chiplet默认配置；Dashboard既有scope/profile/Workbench继续作为host | W2/W7 |
| MIG-19 D | 原F2依赖工单与F3附件正文，方案已写但未实现 | 仍要实现Grant/撤权/共享source chain/有界binary capture；现有普通metadata不算正文/跨范围采集 | W3.DEPENDENCIES/W3.ATTACHMENTS |

各叶任务source closure仍须展开代表文件族的实际import，不能把表中的代表路径当完整依赖集合。
本轮明确区分“某文件存在”与“完整链路已有资格”，原未决可靠性问题保持未决。

## 3. 迁移包完成标准

每个MIG实施前生成该叶任务的source closure清单：
源commit、准确文件/资源/test blob、直接依赖、目标路径、许可证/NOTICE、保留语义/有意差异。
使用Git固定源版本，不把本地另一代理未验改动混入；source freeze不自动拉取remote。
文件名之外还要检查schema资源、fixtures、Node bundle、Python/依赖版本和安装路径消费者。

每个MIG只有在以下条件满足才可勾选所属叶任务：

1. 源测试中与保留行为相关的案例已经映射到目标测试，不能只跑旧库tests。
2. 新producer有真实API/CLI/worker消费者，不是复制后无人调用的孤立类。
3. 两个非Chiplet项目使用不同scope；至少Jira与HSD合成DTO通过，能力缺失明确拒绝。
4. 旧原文/summary/publication历史只读验证或显式导入；不因新字段改写旧hash/水位。
5. 涉及schema/provider/语言/预算变化的资格重验，旁路单测不替代安装/权限/恢复门禁。
6. 当前Dashboard手册与执行清单一致，未启用部分和旧故障保持可见。

最终删除旧产品入口或搬走数据不属于源码port自动副作用，须有单独退役/回滚记录。

## 4. 数据与token不是普通源代码

源码/测试/无secret模板可以按固定版本port。
token采用沿provider-access.md的预览/ACL/原子写流程；本轮没有执行真实采用。
旧captures/报告/账本必须通过MIG-11的历史导入，不复制整个旧 `.local` 或运行进程的数据库。
Git remote、调度任务、机器重启、AI Base实模调用仍分别受既有授权边界约束。

## 5. 本次盘点限制

Graph覆盖检查与当前源码用于确认代表能力；schema/测试具体全闭包由各叶任务执行前核对。
本表不是穷举旧库所有文件，也不承诺所有A类零改动。
尤其evidence仍识别Jira issuelinks、Excel token仍使用Jira key规则、report URL只允许Jira，
这些已确认耦合必须在provider-neutral改造中有对应负例。
