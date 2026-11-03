# Dashboard 对 AI Base 独立评审的回复

日期：2026-11-01。状态：我方已批准冻结task-run/1精确设计版本，回执见第10节；未实现/未部署。
来源：[基座独立评审](../../../../Report_creater_agent/docs/reviews/2026-11-01-project-reporting-ai-base-sdk-independent-review.md)。
本次读取的报告SHA-256：`B89AB28051A17AE4246DE30CB5432C55F801DEC025E2EAC4414975AA829DD744`。
不编辑对方报告的author response/sign-off，不把接受建议当问题已修复。
本文件是本次交接的最新入口。第1至9节保留评审与收敛过程；第10节是当前冻结结论及执行交接。
不再以第7/9节的历史“仅设计、等待CF确认”消息阻止已批准边界进入下一阶段。
冻结不等于运行资格；真实凭据、正式服务/数据迁移、真实模型调用仍遵循独立授权。
BASE-A随后已交付。当前产物接收、BASE-B与Dashboard并行安排见
[integration-execution](integration-execution.md)；第10节保留接口冻结回执，不再把BASE-A催办当最新任务。

## 1. 总体回应

认可“独立Task/Run + 公共执行层”的方向，也采纳首批机制收窄：
**HTTP/Python、polling、有界inline及submit原子seal、一个经过资格验证的backend**。
不要求独立持久Task实体、通用对象服务、全量TS改造、新CLI或所有业务Task化才开始接入。
Task profile是定义，Run是计算执行，Dashboard operation是业务编排，三者不合并成一个状态机。

这是**基座接入切片**收窄，不取消Dashboard的原业务要求。
Jira/HSD的provider-neutral结构、HSD诚实coverage、历史导入、获准依赖/附件等仍在原tasks；
首个有限场景可先用Jira，不得因此把Jira演示称完整topic关闭。
6-12人周等报告估算仅作量级参考，不采纳为承诺；具体代码闭包/实验和依赖冻结后再估算。

## 2. Q1：应用 schema 与合成验收材料

提供[review fixture说明](review-fixtures/README.md)、[schema](review-fixtures/summary-review.schema.json)、
[完整候选样例](review-fixtures/summary-golden.json)和[partial候选样例](review-fixtures/partial-golden.json)。
所有人物/工单/站点均为合成，文件不是正式ai_bundle、Run HTTP envelope或生产兼容承诺。
schema以旧摘要中的`what/current_position/next_actions/owner_basis/evidence`语义为基础，
把Jira-only `issue_id/workspace`边界改为provider/site/stable_id及Project/Stage绑定。

- `required_parts`由应用profile决定。本样例要求facts/comments/history，不作为所有任务的基座默认。
- `owner_basis=explicit/suggested/unknown`；explicit需要原文引用和可校验的身份依据。
  `owner_confirmed`固定false，模型不能代表用户确认或批准。
- 逻辑输入hash由应用对本样例`input`的规范JSON计算；source hash与effective input hash是不同概念。
- `baseline.summary_id/accepted_revision/capture_id`和`target_capture_id`区分已接受基线与采集目标。
- 即使平台schema验证通过，应用还需校验live权限/来源/policy、引用、hash和accepted CAS。
- 缺required part的partial候选可以被记录为未完成进度，但**不能推进完整摘要水位**。
  该fixture用于接受层防御/无模型进度视图，不是许可缺材料也调用完整摘要任务。
- stale、wrong-source、显式owner缺引文等反例在fixture说明中给出准确变换和拒绝结果。

这些材料足以让基座review输入/结果承载方式，不证明W4/W5接受服务已实现。
更复杂的多票合并、span引用与分片资源合同沿既有MIG条目逐步移植，不能把最小fixture当完整产品schema。

## 3. Q2：预算与 unknown

### 保证口径

首批**不要求不可观察的货币账单硬上限**。金额可为estimate或unknown，不把null显示成0。
要求可验证的本平台派发次数、入站字节、返回字节、队列/本地并发及本地期限上限。
请求携带模型输入/输出token上限，但只有实际能执行并证明这些限制的backend才声明该能力。
输入token估算不是实际token；输出接收截断/本地超时也不能证明远端已经停止计费。
若调用者声明必须严格限制账单或实际provider内部请求数，而backend/gateway没有证明，则拒绝该能力组合。

首次资格优先评估报告建议的PydanticAI/OpenAI-compatible路径，并继续使用公司批准的模型配置。
这不是增加另一套Dashboard直连模型，也不是已有backend资格通过或真实模型调用授权。
Copilot可继续既有Chat；未证明的严格任务能力标unsupported，不要求同时资格化所有backend。

### unknown 不能只有一句“不当0”

| 观察状态 | 同一业务计算下一步 | 配额/材料处理 |
| --- | --- | --- |
| 确认尚未派发 | 相同clientRunKey和固定输入恢复/幂等提交；不是另开有新预算的Run | 保留关联；只有有证据的未消费reservation才可释放 |
| 可能已派发、结果未知 | 查询原Run；不换key、不自动重做相同工单/目标计算，新增该工单变化先累计保存 | 预留调用和token估算继续占用账；保留unknown调用债及输入，不因HTTP断开/跨日/换版本清零 |
| 已保存有效结果，usage未知 | 重取同一结果；应用完整验收可继续，但不把候选成功当usage已知 | 本地worker可释放；费用/usage保持unknown，预算保守记账，不重复计算或退款 |
| 后续取得可信usage/取消证据 | 补记同一run/attempt的回执revision，不能复活旧业务终态 | 幂等调整账目，保留旧观察；不是将两个层级费用相加 |

其他工单可在未决reservation和全局限额允许时运行，不因一个金额unknown永久占用本地worker。
如果provider是否仍运行未知，仍计入外部在途风险上限；释放本地worker不等于释放该风险额度。
当安全剩余额度无法确定、未知调用债达到界限或没有可用资格时，只允许查询/归档/恢复，停止新派发。
无证据的时间流逝不结清unknown。人工解决/放弃必须有审计和预算决定，不自动产生新调用。
具体数值待专属合成负载校准及部署配置freeze；本次不新设每日4次之类固定次数。

### W5/W7持久化边界

W5.CLIENT先定义应用持久attempt映射，至少包含operation关联、工单/分片、baseline/target、
profile/input hash、clientRunKey、baseRunId（可尚未知）、最后观察/usage revision。
它在发POST前落盘，回复丢失由同一记录查询；W7 operation复用该公共服务，不再造AI恢复账。
平台Run/dispatch状态由基座拥有；应用只存关联与观察，不覆盖基座状态。
W4.REPLAN必须冻结该存储API和W7消费者，未冻结不能开始W5代码。

## 4. Q3：部署与授权

确认首批设计为：本机单用户、可信Django服务端、独立candidate基座实例及独立测试数据。
对现有共享基座/旧Chat服务不自动切换、不停止、不迁移数据库。
基座不向浏览器暴露app token；回环网络仍须服务身份验证，不能把localhost当认证。

默认沿用同产品principal `metrics-dashboard`，任务使用独立的
`project-reporting.summary` profile及显式注册的Project/Stage opaque scope。
candidate实例的注册/secret引用须重新明确配置，不自动复制旧instance token或tracker PAT。
profile key只是建议名，精确schema/version由基座freeze。

Dashboard负责实际用户owner与provider可见性，可信服务端构造scope，不接受浏览器任意actor。
基座负责认证app、验证注册scope权限，并在每次submit/query/cancel/result操作核对对象归属。
scope前缀/格式匹配不能单独证明用户权限；未经验证的delegated actor只是审计声明。
首批不要求基座直接承担同app多用户SSO/delegation；将来共享多用户部署另冻结可信委托和跨用户反例。
同一产品principal不是全Project通行证，也不是把平台授权全部推给客户端。

## 5. Q4：缩减范围与逐项决定

| ID | Dashboard回应 | 首批/后续边界 |
| --- | --- | --- |
| E1 | 接受 | 独立Task compiler，复用受控底层；不复用隐式Chat preparation |
| E2 | 接受modify | inline-first，submit时原子seal；完整性/原bytes与结果身份不可省，独立upload/blob后置 |
| E3 | 接受 | durable受理、client key、claim、恢复/取消/unknown必需，不以demo替代 |
| E4 | 接受modify | 小型不可变执行revision和必要loader；不另建agent管理UI |
| E5 | 接受modify | app/scope对象授权、有界执行与unknown账；不建设企业账单/多租户调度平台 |
| E6 | 接受modify | HTTP/schema + 可安装Python client先行；TS只做真实受影响消费者，新CLI后置 |
| E7 | 接受 | 合成通用性、typed回执和能力资格；计数/估算/真实费用分开 |
| E8 | 接受defer | 必需profile/prompt/schema loader随E4；额外skills/MCP/connector不进首批 |
| E9 | 接受defer | 多模态、交互等待、通用workflow不作为接入前置 |
| API-01 | 接受modify | 原生内部消费者可用同受控port，不强迫走HTTP；真实签名变化必须适配 |
| API-02 | 接受modify | typed恢复/版本准入优先；不为统一命名重写无影响widget |
| API-03 | 接受modify并分波 | RCA/Sample业务接受缺陷由其owner修复；全业务Task化不是Dashboard隔离切片前置 |
| API-04 | 接受defer | 不全面异步化SoC/GUI；真正被公共签名影响的调用不能延期不修 |
| API-05 | 接受modify | 默认metrics-dashboard principal + task profile；仅有独立信任域需要时再拆ID |
| API-06 | 接受 | 显式材料/结构化候选/真实回执；应用负责语义接受 |

SoC GUI仍由其owner补精确builder/parser/apply/恢复路径及语义验收，Dashboard不能代签。
RCA缺陷保持独立待修项，不隐藏；在未触及这些路径的隔离Task候选上不把全部RCA重构作为前置。
若基座宣称发布包含RCA工作流可用性，则必须单独处理对应问题，不能把Task通过外推为RCA通过。

## 6. 对 AIB 问题的作者回应

| ID | 回应/owner | 本轮证据和后续动作 |
| --- | --- | --- |
| AIB-001 | 同意，基座compiler + 应用材料 | 提供Q1，基座freeze后执行实际request捕获；未修复/未验收 |
| AIB-002 | 同意，基座Run + W5 attempt接口 | 按Q2区分未派发/未知/结果持久化，补同key恢复；未验收 |
| AIB-003 | 同意，基座backend + 双方预算 | 单后端资格、货币estimate/unknown及硬限制能力声明；没有新live证据 |
| AIB-004 | 同意，基座SDK | 本轮直接读helper确认EOF/错误结构风险，不重复对方内存探针；Task以查询结果为准 |
| AIB-005 | 同意，双方身份/配置 | Q3确认信任关系；mutable profile不作为已受理revision |
| AIB-006 | 同意，双方交付 | 上述首批切片收窄，业务要求/真实breaking消费者不删除 |
| AIB-007 | 同意静态风险，RCA owner | 直接读_record_review_session确认异常分支合成ID；应只重试接受，不重复模型 |
| AIB-008 | 同意静态风险，RCA owner | 直接读preflight分支确认error/status判断不一致；未做浏览器复现 |
| AIB-009 | 同意静态风险，RCA owner | 直接读parser确认坏JSON被默认化；schema失败不能当正常否定评审 |
| AIB-010 | 接受纳入基座census，Agent设置owner | 依据对方带路径的签名分析；本轮未复跑该route，基座需按默认装配验证 |

这是设计答复而不是Final sign-off。完整性/幂等等P1须有实现与证据才关闭。
本轮使用当前文件读取核对上述SDK/RCA路径；图索引coverage不可用，未据此做穷举/缺失断言。
旧schema与资源账仅用于语义比对，不代表其实现可原样移植；不修改对方仓库或重跑其测试。

## 7. 给基座Agent的下一条消息

此节保留上一轮Q1-Q4交接记录；基座已回传草案，当前应转交第9节末尾的CF消息。

```text
请读取Dashboard回复：
D:/AIGC/scrum_dashboard/openspec/changes/add-provider-neutral-project-reporting/ai-base-review-response.md
以及同目录review-fixtures。

本轮仍只做合同收敛，不开始实现、服务或真实模型调用。
请确认Q1材料是否足够，并对Q2的unknown准入、Q3信任关系、Q4首批范围回应。
如有异议，按Q/AIB编号给出差异、依据和最小修订；不重新泛评全部历史。
请特别给出：第一版协议的精确字段/错误/支持组合、可校准的limit策略、
Run结果可取回窗口及幂等过期规则、scope注册授权办法、应用attempt与Run关联建议。
这些在基座canonical OpenSpec中形成待freeze草案，不回写或覆盖本方材料。
材料足够时明确“设计可freeze”的条件；实现启动与真实资格仍须后续明确。
```

## 8. 本轮验证与未证明部分

OpenSpec严格检查、空白、14份相关文档的38个相对文件目标及代码块配对通过。
复用基座现有Python环境，仅导入jsonschema/标准库：schema自检、2份golden结构、
2个input hash、4个source hash及3个schema拒绝样例通过；未导入App/设置、安装包或发起网络。
fixture中引用/owner quote做了内存自洽核对，不是生产引用校验/权限/CAS验收。
完整反例矩阵仍是未来消费者测试期待；没有运行产品测试、服务、真实模型或数据迁移。
对方报告保持原样；本回复不更改AIB项的修复/签合状态，也不关闭W1.R或旧T12。

## 9. task-run/1 草案的 CF 答复

本节为此前修订请求与验证历史；CF-A/B已被基座最终版本接受，当前结论以第10节为准。

依据：[基座待冻结设计](../../../../Report_creater_agent/openspec/changes/define-app-scoped-task-run-contract/design.md)。
本次读取SHA-256为`D2119D19E1BBDB50091241D4C8331F4A8C8D87B6B3FFEA2114208031F65E38DC`。
不修改该设计或其freeze状态。本轮为应用方确认/修订请求，不启动实现或凭据配置。

| 条件 | 应用方结论 | 最后需基座处理的内容 |
| --- | --- | --- |
| CF-01 | 确认隔离、固定schema、本地引用和三类hash；提供实际strict投影 | 采纳下述CF-A：input_hash由应用绑定，不要求模型生成；仅完整summary进入strict profile |
| CF-02 | 确认初始candidate运维方式 | 逐app签名service-account、operator精确scope/profile登记；没有额外权限请求 |
| CF-03 | 确认持久库、deadline裁决、分期留存和tombstone机制 | 按CF-B明确已有key与新受理的检查顺序，避免重复POST再次被新任务deadline/配额拒绝 |

### CF-A：原始模型结果与应用候选需区分

原草案第2节要求只发fixture.input，再将fixture.candidate投影收窄为summary。
但前者没有input_hash，后者将input_hash列为必填；直接照此注册会要求模型计算或猜一个
SHA-256值。这是本方原fixture的模型/应用结果分层不够明确，不是基座运行故障。

推荐采用[严格输入投影](review-fixtures/strict-summary-input.schema.json)、
[严格输出投影](review-fixtures/strict-summary-output.schema.json)和
[原始输出样例](review-fixtures/strict-summary-output-golden.json)：

- input仍是原fixture.input，绝不发送candidate、acceptance_context或整个fixture包装。
- input schema固定本review profile的required_parts及其complete要求，调用者不能自行缩减。
- 原始输出只允许kind=summary，排除input_hash及其他未声明字段；partial仍是应用侧防御样例。
- 应用先核对RunResult的runStoreId/runId/scope/profile/outputSchemaSha256/inputSha256/
  logicalInputHash与持久attempt，再校验content原bytes hash和严格输出。
- 本地适配层以已核对的attempt.logicalInputHash补齐应用候选input_hash，再执行引用/owner/CAS。
  保留原始模型content和平台hash，不把补齐后的JSON冒充平台原输出。
- envelope不符或缺本profile所需logicalInputHash时拒绝；不能用本地补值掩盖平台返回错误。

该改法不改变task-run/1运输字段，也不新增平台业务字段注入/模板系统。
三份schema完整本地解析；未解析引用/未知dialect拒绝；不同业务profile自行选择输出结构。
需要基座把第2节输出投影说明更新为“原始结果 -> 应用绑定候选”，再确认CF-01。

### CF-02：确认凭据与 operator scope

接受逐app签名service-account，不使用旧全实例token，不从tracker PAT/模型凭据转换。
`metrics-dashboard`只是principal选择器；新的candidate需明确安装该principal的唯一auth policy。
每请求仍验证签名、app/issuer/audience/expiry与当前policy；每个对象操作检查scope授权。
新Stage可先创建/采集/归档；没有operator批准的精确scope/profile revision就显示AI未就绪，
`scope_not_allowed`不触发自动登记、通配grant或换token重试。

本机operator与可信Django服务端是不同职责；浏览器不能提交任意actor获得权限。
签名凭据轮换不重置runStoreId或app/clientRunKey去重空间，撤权不删除历史/unknown债。
这些只是设计确认，本轮不产生任何secret、signed token、scope grant或真实服务变更。

### CF-03：确认恢复、期限和留存

接受runStoreId作为持久authority，绑定在本地attempt；普通重启/升级不变化。
收到run_store_mismatch必须停止并保留attempt，不自动discovery后改投空库或跨实例重试。
应用只在operator明确绑定candidate时记录初始authority，不从未知endpoint自动接受新库。

接受deadline在派发/完成CAS时裁决，`now >= deadlineAt`优先timed_out；
不得用provider声称的早完成时间倒填本地成功，不靠延长客户端等待刷新deadline。
记录原exactSubmitPayload、输入/版本/限额，恢复只重用它，不重建一个“等价但新deadline”的请求。

接受结果载荷窗口与Run/receipt观察窗口分离。应用明确请求可承受的最小结果窗口，
按手动/未来离线恢复间隔与裕量配置，不把未经量测数字当SLA；
服务不能承诺该值就拒绝，而非静默缩短。
结果过期只转result_expired，应用继续观察可用Run/receipt；不得因取不到结果而自动重新调用。
涉及实际派发/硬配额的unknown继续pin并占风险账；只剩非硬准入的金额unknown时可按草案结束观察，
但应用必须保留unknown，不能视为零费用或退款。

接受registration-lifetime tombstone和容量满时拒绝新受理。
client key永久不复用；app删除/epoch轮换不属于普通client能力；
活动库克隆/failover不在v1，不通过清tombstone、换ID或重建库恢复“可用”。
operator归档/迁移不自动等于可以删除应用原文或改写历史。

### CF-B：区分已有 key 重放与新请求准入

草案第7.1节“先grant/limits/schema验证”与第8.1节“结果到期后同指纹POST仍返回200”
需要明确限定：已有请求的deadline已经在过去，当前配额也可能已满，不能再次按新受理判断。
建议写入如下顺序，不改变鉴权和撤权规则：

1. auth/contract/runStoreId/current grant及有界请求结构检查始终执行。
2. lookup同app/key并检查scope，使用已固定profile定义和原请求字段比较fingerprint；
   当前授权/profile不可验证的拒绝例外保持草案语义，不能因此产生新Run。
3. 已有且同指纹：返回原快照200，或tombstone的410；不同指纹409。
   不再检查新任务的未来deadline、当前剩余队列/预算或再次reserve。
4. 只有不存在的key才执行新受理deadline/limits/schema/资格/配额检查及原子唯一提交。
   lookup到提交之间的并发仍由唯一约束和事务处理，不把先查一次当幂等保证。

已有Run的后续实际dispatch仍按原deadline和实时授权/资格/预算处理；
重复POST返回快照不代表续期或允许派发。普通查询不延长任何已承诺留存。
请据此给出一个“已终态/结果已过期/队列满时原body重提”的合成合同用例。

### 当前冻结结论与下一条消息

除CF-A和CF-B的明确修订/澄清外，应用方没有新增业务范围或运维前提。
数值limits、服务/SDK产物和真实资格仍属后续门禁，不作为本轮语义讨论无限扩大的理由。
请基座确认两点并回传最终design hash；在此之前不宣称双方已freeze。

```text
请读取Dashboard回复第9节及review-fixtures新增strict投影：
D:/AIGC/scrum_dashboard/openspec/changes/add-provider-neutral-project-reporting/ai-base-review-response.md

CF-02及CF-03机制已获应用方确认。
CF-01请采纳CF-A：原始模型输出不要求input_hash，由应用核验RunResult/attempt后绑定。
CF-03请按CF-B区分已有key重放与新受理的deadline/配额检查。
请只回应这两点，更新基座canonical design和对应合成用例，回传design hash及CF结论。
仍只做设计收敛，不开始产品实现、服务/凭据配置或真实模型调用。
```

CF材料离线核验：3份schema自检、2个正例、8个拒绝例、本地候选重建均通过；
未登记引用被显式拒绝，未联网获取schema。OpenSpec/空白检查通过，14份文档42个相对文件目标可解析。
这些不验证真实签名、grant、RunResult、CAS、deadline、quota或tombstone实现；
对方草案保持原样，CF-A/B仍需其确认。

## 10. FZ-01：设计冻结确认与执行交接

**我方结论：批准冻结，无新增设计阻断项。**
用户要求尽快结束边界往返；本次仅复核最终版本及CF闭环，不重新发起全平台架构评审。
冻结对象是[基座设计](../../../../Report_creater_agent/openspec/changes/define-app-scoped-task-run-contract/design.md)
的如下精确字节版本：

```text
contract: task-run/1
base change: define-app-scoped-task-run-contract
design SHA-256: ff7899333c8ed8f0717b47fc7c1d6a6e5928db575a15553d2501045f123719da
dashboard decision: accepted-for-design-freeze
date: 2026-11-01
```

基座已接受CF-A/B并回传该hash，我方本次读取的hash完全一致。
双方对CF-01至03的语义已无未决差异；请基座将本回执登记到自己的OpenSpec并标记设计冻结。
本轮不替基座修改文件；其当前标题仍为proposed是待其完成的状态登记，不是要求再审批一次。
仅修改状态/引用本回执导致文件hash变化时，记录`acceptedFrom`为上面的hash及新hash即可，
无需重新讨论已一致的语义。后续若改了真实协议/权限/持久化语义，按API-EVO-01记录版本化差异和受影响方。

### 本次复核

| 项目 | 结论及证据 |
| --- | --- |
| CF-01 / CF-A | 第2、6、8.2节已区分原模型结果与应用候选；strict schema排除input_hash，应用验RunResult/attempt后绑定，不改平台content/hash |
| CF-02 | 第4节保持逐app签名service-account、唯一注册authority及operator精确scope/profile grant；没有隐式授权或token迁移 |
| CF-03 / CF-B | 第7.1、7.1.1、8、9节明确重放先于新准入；返回200/410/409，不再reserve/入队/派发，仍保留auth/撤权/dispatch检查 |
| Tombstone | 已保留固定profileKey/revision/definitionSha256，重放不依赖被回收载荷或latest profile |
| 合成向量 | 本轮重新计算第7.1.1节的input SHA-256和requestFingerprint，与草案相符；8条重放/新准入/撤权/并发场景明确 |
| 未验证部分 | 没有运行Run服务或8条事务用例，没有真实签名/存储恢复/模型资格；这些是实现测试，不阻止语义冻结 |

### 应用侧冻结材料

路径均相对当前change的`review-fixtures/`，保护双方采用同一schema和样例。
原JSON字节hash只是版本绑定，不证明运行行为。

| 文件 | SHA-256 |
| --- | --- |
| summary-review.schema.json | `407efd28e77bb5827d340e43587986d7c378b1540113bb95615ff836a6072574` |
| strict-summary-input.schema.json | `39674c0086ef1eebc53da4f4c5962c14502c81105ee8cf855f567e11c6cb2fc5` |
| strict-summary-output.schema.json | `818669b74818c0cc010b56a5d0ebde092c2f665b1ff6ad87cf1fafc23b025517` |
| strict-summary-output-golden.json | `36e483987655891b052f0913949b56c60e136118df93ec03d402a4a67379f9c8` |
| summary-golden.json | `cede12005931b476664368815af7d53dd77a7696c593f9141375405ab5781827` |

冻结的是此增量单票review profile的边界；首次/分片/HSD等业务profile仍需对应schema/测试。
通用运行合同不因此要求全部业务profile同时就绪，其他应用也不强制迁成strict summary。

### 进入执行，不再重复冻结讨论

基座下一阶段应直接在**自己的唯一OpenSpec tasks**中细化可执行叶任务并推进BASE-A；
已有design已给出公共边界，不再建立第二份架构方案或把“所有平台能力齐备”作为首个交付前提。

| 下一交付 | 基座负责 | 可观察退出条件 |
| --- | --- | --- |
| 冻结登记与最小任务包 | 记录FZ-01、对应spec delta、准确owner_paths/依赖/反例；沿同一change管理 | 返回冻结状态及首个执行节点，不再次征询已确认CF事项 |
| BASE-A合成纵向闭环 | schema/profile、独立compiler、最小durable Run与fake backend、HTTP/Python入口 | 合成input提交->原key查询->结果取回；重复请求不重复派发，非法输入拒绝；提供可复现命令和结果 |
| 首个可消费contract pack | 版本化DTO/schema/golden及Python最小包/导入方式，明确synthetic_only | Dashboard可据同一pack开始适配；不要求等CLI/全部TS或所有旧业务迁移 |

durability/unknown/取消/权限及资格按原BASE-B继续，不把BASE-A演示称可靠运行已经全部通过。
BASE-C只迁移真实breaking消费者；有新增关键风险才回到对应局部设计，不能因普通实现细节重开所有CF。
缺少真实凭据/服务部署/收费模型授权不阻塞合成实现；需要这些副作用时单列并遵循原授权。
Dashboard按自己的tasks推进不依赖基座成品的工作，W5接线仍需实际pack和W4.REPLAN；
本回执不关闭W1.R、不恢复旧T12执行、不替代各仓实际代码验收。

### 可直接转交基座Agent

```text
Dashboard已完成最终复核，批准冻结：
task-run/1
design SHA-256 = ff7899333c8ed8f0717b47fc7c1d6a6e5928db575a15553d2501045f123719da

正式回执：
D:/AIGC/scrum_dashboard/openspec/changes/add-provider-neutral-project-reporting/ai-base-review-response.md
请读取第10节FZ-01。CF-01至03及CF-A/B均已闭环，没有新的应用方设计阻断项。

请尽快在你的OpenSpec登记冻结，并在既有授权内直接细化叶任务、推进BASE-A合成纵向闭环。
不要再重复征询已经确认的CF事项，或仅回传另一份proposed设计。
仅状态登记产生的hash变化请记录acceptedFrom和新hash，不需要再来回审批。
下一次请返回：已完成任务节点、实际测试结果、可消费contract pack/最小客户端位置、
下一最小动作和真正阻断项。优先交付合成submit->query->result及原key幂等，不等全面平台改造。

本次推动的是冻结后的有界实现/合成验证，不是授权真实凭据配置、正式服务切换、
业务数据迁移或收费模型调用；这些仍按各项既有授权处理。
```
