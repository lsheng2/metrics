# Report Read Architecture

日期：2026-11-06；复核：2026-11-07。状态：实现、全部限定性能验收及独立证据复核通过。
独立设计审查：[performance-plan-review.md](performance-plan-review.md)，结论READY。
源码基线：`d21250a2d4eee0de6f4234029591b4340e607557`。
规格：[report-query-performance](specs/report-query-performance/spec.md)。
执行与验证：[performance-execution.md](performance-execution.md)。
唯一任务状态：[tasks.md](tasks.md) 中的 `W6.PERF.*`。
本文不替代原数据/权限/归档契约，不启用真实来源、模型或部署。

## 1. Evidence

本机同一隔离合成数据集的已保留证据：
`.tmp/dashboard-latency-20261106/{http-before.json,before-profile.json,before-profile.txt}`。
这些是已观察的单次结果，不是 p95 或性能承诺；实施前重新核对候选与数据指纹，
不为整理规格重跑原完整工作周。
可提交的去敏摘要与原证据hash见[performance-baseline.json](performance-baseline.json)。
原probe没有完整数据指纹；正式前后对照须在实施时冻结同一克隆重新测量，不能只对比
两份输入不明的计时。最多三次旧慢路径复测，保留历史记录而不补造旧指纹。

实施已固定独立克隆，原路径31.602s/169 Git。读取核心经两轮限定独立审查，
工作台已改用固定H/批量对象/请求级校验；初步样本首请求4.17s、随后3.08/2.96s，
不把这些少量样本当作p95。后续正式S0/S1、按钮和十次Ego语言验收均达标，
准确样本数、候选hash与收口状态见[交付回执](performance-delivery.md)。

| 边界 | 已观察结果 |
| --- | --- |
| 会议日历 GET | 0.039s |
| 语言切换 POST | 0.005s，返回302 |
| 随后的工作台 GET | 39.602s；响应约60KB |
| 独立后台 profile | 34.664s；169次 Git 子进程，累计27.937s |
| 草稿 / 定稿 / 采集列表 | 同次 profile 约11.0s / 11.4s / 9.5s |
| SQL | 57次；计时精度下显示0.0s，不代表绝对零成本 |

`ProjectLanguageView.post`仅激活语言、设置cookie、重定向。慢的是重建工作台。
`ProjectReportFacade.stage_context`分别建立读取链；
`ReportFinalizationPacketStore._committed`和`ReportPublicationReader.read_artifacts`
重复读取同一份六文件publication。采集列表逐项查提交、父提交和checkout。
`ReportPreparationCreateView`等操作还会先调用完整`stage_context`。
这是查询职责与I/O粒度问题；没有证据需要修改AI Base SDK。

## 2. Decision

采用模块内的轻量读写分离，保持现有Django单体、数据Git和运行态存储：

```text
GET / language redirect
  -> current actor / project / stage authorization
  -> ReportQueryService
  -> one request-owned ArchiveReadView pinned to H
  -> batched objects + shared verified packets
  -> existing list DTOs / templates

POST Save / Prepare / Finalize
  -> authentication + bounded syntax validation
  -> original-command replay
  -> existing business service and writer-lock checks
  -> exact revision / commit receipt
  -> redirect or JSON; no preliminary workbench listing
```

“轻量”指查询组合和返回对象；第一阶段不降低已选记录的校验级别。
同一publication的正文、snapshot、template和全部所需修订仍按原规则校验，
只是不重复读取、解析和验证；列表不会向页面返回整个审计包。

| 方案 | 判断 |
| --- | --- |
| 全页TTL缓存、全局`lru_cache`、并发启动原169个Git进程 | 不选；冷请求仍慢，权限/修订失效困难，放大Windows进程开销 |
| 统一查询入口 + 请求级固定快照 + Git批量读取 | 本次选择；消除已测瓶颈，首个请求也受益，不产生第二份持久真相 |
| SQLite物化查询索引 / Redis / 独立查询服务 | 后续有条件选择；只有批量化后规模测试仍显示目录/历史扫描是主瓶颈，才另行冻结索引协议 |

当前目录枚举仍是有界 O(历史记录数)，不是 O(页大小)；本设计不虚称批量读取等于
无限规模能力。后续索引必须能从Git和runtime重建，绑定已索引head/revision，
明确损坏、落后及重建状态，且不能成为发布成功或权限依据。本次不先建设该系统。

## 3. Ownership And Interfaces

以下为新增目标接口，不是已发布API。使用现有类型与命名，只有这些职责需要新文件：

| 文件 | 职责 |
| --- | --- |
| `app/domain/report_queries.py` | 查询参数、页面读取结果、read limits，纯dataclass |
| `app/spi/archive_reads.py` | 中立只读port、blob请求和提交位置，不导入Django或Git |
| `storage/git_read_batch.py` | Git原生批处理及严格输出解析；不重写Git对象数据库 |
| `storage/archive_read_view.py` | 一次读取的head、对象复用、批量provenance与checkout观察 |
| `services/report_queries.py` | 组合页面查询，复用旧业务校验/DTO |
| `app/api/report_queries.py` | 对UI公开查询服务，隐藏repository与路径 |

路径均相对于`project_management/`。不拆成微服务；不改provider adapter和SDK。

```python
@dataclass(frozen=True, slots=True)
class ArchiveBlobRequest:
    commit_id: str
    path: str
    max_bytes: int

@dataclass(frozen=True, slots=True)
class ArchiveRecordLocation:
    commit_id: str
    parent_commit: str | None
    tree_id: str

class ArchiveReadView(Protocol):
    head_commit: str
    def read_files(self, requests: tuple[ArchiveBlobRequest, ...]) -> tuple[bytes, ...]: ...
    def locate_records(self, paths: tuple[str, ...]) -> Mapping[str, ArchiveRecordLocation | None]: ...
    def list_paths(self, prefix: str, *, commit_id: str | None = None) -> tuple[str, ...]: ...
    def checkout_states(self, commit_ids: tuple[str, ...]) -> Mapping[str, str]: ...

@dataclass(frozen=True, slots=True)
class ReportWorkspaceQuery:
    capture_after: str | None = None
    draft_offset: int = 0
    publication_offset: int = 0
    page_size: int = 20
    include_operations: bool = False

@dataclass(frozen=True, slots=True)
class ReportWorkspaceRead:
    archive_state: str
    archive_head: str | None
    observed_at: str
    captures: CaptureMetadataPage
    drafts: ReportDraftPage
    publications: ReportPublicationListPage
    operations: ReportOperationsRead | None = None

class ReportQueryService:
    def workspace(self, actor, project_id, stage_id, *, query: ReportWorkspaceQuery) -> ReportWorkspaceRead: ...
```

`build_report_query_service(...)`在既有`app/api/report_factories.py`装配。
`CaptureArchiveService._report_read_view(actor,project_id,stage_id)`为模块内context manager，
创建当前身份绑定的只读port；UI不直接持有它。
既有list/detail/publication的公共签名及返回语义保留；可加可选的内部`read_view`
参数，省略时创建独立scope。明确实现port的测试adapter，不通过`hasattr`静默回退
到无限逐文件查询。`_report_repository(write=True)`仍是原写入边界。

页面项目、系列、模板等轻量ORM选择由facade一次组装；`workspace()`承担归档
三列表，并可选读取本地运行记录。`ReportOperationsRead`携带project/stage/actor/stage-hash、
items和error_code。只有归档root、作者身份一致时，`ProjectRunFacade`才消费它；
该facade仍重新检查project/stage/actor/hash，不匹配或不同归档沿原独立读取入口。
本地运行读取使用同一view的期限和至多4个本地worker；不得调用远端Base。
定稿列表ID字典序、采集排序、offset/原capture cursor和20条分页均保持不变。

2026-11-07规模复核：工作台定稿行只消费manifest、manifest hash和commit，不显示checkout。
采用`ReportPublicationListItem(manifest, manifest_sha256, commit_id)`和
`ReportPublicationListPage(items,next_offset)`，没有`checkout_state`字段，不伪造current或stale。
列表仍经过相同六文件及修订完整校验；只是没有计算未渲染的工作树诊断。
旧`list_publications/get_publication/read_artifacts`继续返回原DTO并保留全部checkout语义。
工作台可见的capture checkout仍按原规则核验，不删字段或改成缓存猜测。
这属于已选查询/命令分离的具体投影，不新增持久索引、Windows专用文件系统模块或全局缓存。

## 4. Read View Consistency

一个view绑定`root identity + owner + project + stage + rule hash + head H`，
存活仅限一次HTTP查询，或写锁内一次验证阶段；禁止全局/跨请求复用。
权限先检查，返回前再次检查owner/stage访问权。Git配置、符号链接、目录/对象
边界等现有安全检查不因缓存而取消。

1. 只读打开不会初始化归档、写DB、创建Git提交或修复runtime指针。
2. `main`在view入口解析一次为H。显式历史commit必须是H可达的获准记录；
   原capture cursor可固定更早head，不借旧cursor访问另一项目。
3. blob缓存键含`commit/path/object id`及隐含完整view身份；对象内容仍检查
   Git object hash和原业务hash。缓存值为bytes；可变DTO不得泄露给调用方修改。
4. 验证结果按`validator revision + identity + all file hashes`在view内复用。
   不能因为manifest相同便跳过另一份正文/edits校验；失败结果不缓存为成功。
5. runtime不是Git快照。每个draft捕获`current revision/hash`、finalization身份，
   验证所选不可变修订后重读这些小指针；变化返回冲突，不拼接两版正文。
   同一页不同草稿可有不同观察时间，不能宣称Git和SQLite/runtime具备全局事务快照。
6. `finalized`要求在H中核对publication与原待提交六文件；后来才出现的commit
   不算当前view已确认。新请求看到新head。未知/损坏不能当作未提交或空列表。
7. Save/Finalize仍在原写锁下重新检查revision、基线、scope、skip和active preparation。
   写入前的新验证view不得复用之前的GET/预览view；append后销毁旧view。

通过单次`verified_publications()`共享已校验packet，供草稿已定稿状态和定稿列表消费。
`read_public_artifact`、`snapshot`复用同一packet中的bytes，不再`get`后另查同文件。
metadata目录可以批量读取，但已选publication和基线读取不能降为manifest-only。

实现中的`open_read_view()`：在原repository上创建新的短期view，在现有view上仅借用
同一作用域，不关闭外层或刷新期限。基线、period/list消费者借此在写锁内建立新观察，
批量预取后保留完整验证；append以后禁止沿用之前的view。

## 5. Bounded Native Git Reads

复用本机Git及`GitRunner`的环境隔离、无窗口进程、stdout/stderr上限和正常回收。
不新增pygit2/libgit2、Redis或另一个持久helper。批处理用现成Git协议，不手写pack解析。
本机`git version 2.53.0.windows.2`；已实际检查`cat-file --batch-check`返回
blob/type/size/mode和missing。部署能力预检必须验证所用flags/atoms；缺失时明确
`ARCHIVE_READ_UNSUPPORTED`，不隐藏降级为逐文件慢路径。

原生协议依据：随本机Git安装的`git-cat-file.html`、`git-log.html`，对应文档入口：

```text
https://git-scm.com/docs/git-cat-file
https://git-scm.com/docs/git-log
```

### Object Reading

以经验证的`<40-hex commit>:<safe relative path>`经stdin传递，禁止caller任意rev表达式、
换行、NUL、选项、任意仓库路径。先`--batch-check`取得OID/type/size/mode，
拒绝非blob或非100644文件。成功项再以OID交给`--batch`读取原始bytes。
按声明size精确消费内容及分隔符，不能对整个stdout按行split。
missing、歧义、非整数/负size、长度不符、截断、额外记录和非零退出均拒绝整批。
重复输入保持返回顺序，但相同对象只读取一次。

一次view默认总读取预算64MiB、至多4,096个不同blob；单文件维持其原caller上限，
不能借批处理扩大历史文件额度。单批至多256个请求及16MiB内容，单大文件可独立
成批但不得超过原单文件上限或view余额。`GitRunner.output_limit`计入协议开销，
不直接用“内容正好16MiB”作为stdout上限。预检先阻止超大分配。
同一view共享10秒单调时钟I/O预算；每批只用剩余预算。到期关闭stdin、回收
已拥有的子进程/读写线程，禁止重置期限或后台继续读取。写操作沿原operation期限，
不得把该GET预算套成“写入超时即取消/回滚”的新语义。

### Provenance And Checkout

逐路径`git log -1`/逐commit`rev-list`改成一次有界历史扫描：
从H起读取commit、parent、tree及变化路径，映射每个已请求path的最近影响提交。
实现使用`log --raw --no-abbrev`同时取得文件mode/OID；从单父链重建H的head tree，
与原`ls-tree`逐项对照。历史cursor仍能明确读取H可达的旧tree，不依赖可修改checkout。
固定格式/NUL记录、禁rename启发式；请求路径分批避免Windows命令行长度上限。
候选实现须以真实Git对照原逐项算法验证，不能用自己生成的映射作为golden。
托管数据历史为单父append链；遇到多父、不可达/缺对象或扫描截断不得猜测，
返回明确历史不可用。最多10,000提交及16MiB历史输出；未找到和搜索未完成严格区分。

checkout不是publication真实性来源，但既有`current/stale`含义仍保留。
正常index匹配H时，先核对一次H的index/工作树内容；请求commit的tree不同则stale，
tree相同则复用这次观察。**不能用`commit == H`代替内容核验**。
index不匹配H时允许有界原逐commit检查以保留正确性，记录slow-path原因；
不能自动reset/read-tree/materialize。此异常慢路径不参与健康checkout的进程次数SLO，
但必须受总预算约束并独立测试。写入materialization仍执行原新鲜检查。

## 6. Lean Commands And Shared Consumers

`ProjectReportFacade.stage_context`只服务工作台GET，不是所有操作的前置条件。
增加`control_context`（项目、Stage、系列/模板目录及本地runtime能力），不读报告历史。
POST form先做严格schema/类型/UUID/hash/date检查；提交的selected ID由业务服务验证。
原命令恢复必须先于“当前模板是否仍在下拉框”检查，避免破坏已归档模板的合法重放。

| 入口 | 本次目标 |
| --- | --- |
| 语言POST | 保持cookie+302，无任何归档读取；不能把语言结果改为AI翻译 |
| 工作台GET | 一次query service、一次read view，三列表共享对象/验证 |
| baseline preview GET/JSON | 只读系列、所选基线和pending drafts；JSON不构建工作台 |
| prepare/reprepare POST | 不预读全部列表；成功直接返回原operation/draft/publication |
| preparation detail GET | 只读该准备详情与必要控件，不加载不相关历史 |
| Save/Finalize/resume | 保留原事务/校验，采用锁内短期批量view；不复用早先GET |
| 下载/复制/审计 | 原bytes及权限语义不变；同一请求重复取packet可复用 |
| skip/restore calendar | 不改语义；occupancy与历史消费者复用新的批量read port |

HTML错误页保留绑定输入、原command、CAS、gap和错误信息，只重建该操作需要的控件。
可抽出`preparation_error.html`复用现有`daily_preparation.html`，提供返回工作台链接；
不把未加载列表伪装为“没有报告”。JSON错误不得为了渲染HTML先走昂贵列表。
不新增前端框架，不靠loading动画或后台预热掩盖完成时间。

## 7. Errors, Compatibility And Rollback

| 情况 | 对外结果 / 保证 |
| --- | --- |
| 非法查询/批协议输入 | `REPORT_INVALID` / 400或既有422，读取前拒绝 |
| 当前用户无权 | 原401/404，不从缓存泄漏内容 |
| runtime修订移动 | `REPORT_REVISION_CONFLICT` / 409，保留编辑内容，不自动重试 |
| 原文件/manifest/hash/历史关系错误 | 原`REPORT_ARTIFACT_INVALID`，不降级空列表 |
| 读取预算超限 | `REPORT_LIMIT` / 413，不能截断成完整结果 |
| Git I/O超时或暂不可用 | `REPORT_STORAGE_UNAVAILABLE` / 503，无成功/已取消宣称 |
| Git缺少批处理能力 | 内部`ARCHIVE_READ_UNSUPPORTED`映射503，明确操作员诊断 |

新的内部code在`app/domain/captures.py`现有错误注册与report映射一起加入。
没有迁移、文档schema升级或历史文件改写。旧公共list/detail返回值的资格保持；
测试double通过明确adapter实现批处理，不用生产弱fallback。
回滚为部署上一源码版本并正常重启应用；数据格式和已确认基线无需回滚。
性能发布前先在独立合成数据克隆上验证，不改变保留的原周证据。

## 8. Acceptance And Non-Goals

必须满足[执行与性能验收](performance-execution.md)，其中延迟数字均为目标、尚未达成。
不能只凭“169变成更少”或warm cache绿色关闭；首个请求、失败/并发、原bytes和用户
操作完成时间都需要证据。最终只声明已测量的场景，不把本机p95推成生产SLA。
本次不改AI Base、真实Jira/HSD、SDK/pack、定时、完整输入能力或原始归档writer。
