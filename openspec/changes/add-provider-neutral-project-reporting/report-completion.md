# Hash-ID Completion And Errors

日期：2026-11-03。状态：proposed；父设计：[authoring](report-authoring-v2.md)。
只处理富文本正文中明确输入的 `#ID`，不建设全站搜索、批量扫描或写工单功能。

## 1. Trigger And Routing

触发符固定 ASCII `#`，首批不提供多个用户可配置触发方式。
Jira 展示 key 候选语法 `[A-Z][A-Z0-9_]*-[1-9][0-9]*`；
HSDES ID 候选语法 `[0-9]+`，全程用字符串保留，不转 JS Number，不锁死长度或 `150` 前缀。
这是本应用输入形状，不是对全部 Jira 部署 project-key 规则的普遍断言。
adapter 还要按选定 provider/profile 的实际规则验证。示例使用合成 `#DEMO-123`、`#15000000001`。
用户提供的真实 URL 只作私下格式依据，不访问、抓取或写进公开 fixture。

第一版识别从段落/可编辑节点起点，或 Unicode 空白后开始的 token。
`#` 后不得有空白；`# 标题`/`##`、email/URL fragment、代码块/inline code、现有链接及只读 data 块
不触发。中文可写“检查 #DEMO-123”；紧贴“检查#DEMO-123”的支持不隐式承诺，
若产品要求这种边界，先证明 adapter 不需要上游 fork，再在同规格扩充。
有效ID暂保留已冻结的最大31字符产品上限；该值最初来自Vditor hint边界，
现已选Milkdown，不再视为组件限制。超出时明确`COMPLETION_ID_TOO_LONG`，不截断成另一票。
上限需在真实输入样本核验后版本化调整，不表示上游ID永远小于32字符。

至少两个 ID 字符后进行250ms防抖；完整语法满足后查精确 ID，不做全站前缀枚举。
仅 `#`/尚未形成 key 时是输入中，不显示“不存在”。继续输入取消前一请求的显示资格。
无快捷键/补全按钮/URL入口；关闭再试由修改或重新输入同一个 `#ID` 完成。
错误状态可以有导航到现有 source 配置页面的链接，但不是另一个补全触发按钮。

从所属 draft -> Stage 的冻结 descriptor 取 provider/profile/endpoint/query，不读全局默认第一个。
Jira 使用 `ScopeSelection(profile_id,scope_id)` 与显式 binding；
HSDES 使用 `ScopeSelection(profile_id,None)` 和 saved-query descriptor。
一个 Stage 只有一个 provider，混合来源不在首版，不新增 `#jira:`/`#hsd:` 语法。
语法不匹配显示 provider mismatch，不偷偷转查另一个系统或凭据。

## 2. Scope Membership Is Not The Same As Visibility

采用 **本报告 pinned capture 的完整成员集合**作为补全范围。
这与用户看到的来源 cutoff 一致，不在编辑时重新执行一整份 saved query、添加成员或推进采集水位。
最新 title/assignee 是另一份只读 observation，不改 report snapshot 中当时的事实。
新进 scope 而未在本报告快照里的工单，需要通过正常 Run 产生新报告；补全不得隐式更新范围。

公共typed证明：

```text
ReportSourceReader.membership(actor, project_id, stage_id,
                              snapshot:ReportSourceSnapshot) -> ScopeMembershipSnapshot
CaptureArchiveService.read_report_membership(actor, project_id, stage_id, *,
    capture_id, source_commit) -> ScopeMembershipSnapshot
ScopeMembershipSnapshot(schema_version=1, capture_id, source_commit, manifest_sha256,
    source_as_of, rule_hash, principal_id, state="complete"|"unknown",
    observed_count:int|null, total_count:int|null,
    members:tuple[ScopeMember,...], proof_hash)
ScopeMember(identity:WorkItemIdentity, source_key:SourceChainKey)
```

proof_hash=除自身外全部规范字段的canonical hash；members按provider/endpoint/stable_id稳定排序。
由现有 `CaptureManifest.membership.items/coverage/raw_page_ids`、intent.source及已校验的commit读取，
不从report rows反推、不另建范围数据库。read_report_membership验证commit归属/manifest
hash、source/principal/rule、页与membership完整性证明；缺证明state=unknown或损坏拒绝。
只有membership.coverage.state=complete、observed_count=total_count=len(unique members)
且报告/manifest identity与cutoff一致才为complete。schema1 report snapshot可以独立关联此读接口，
不改写其hash。snapshot.rows缺成员详情不丢member；source_key由intent.source和identity构造。
查找与回执绑定该proof_hash，incomplete负查询只能返回scope_unverified。
该小型read projection可重建，读取不写cache或启动capture；结果限制沿ReportLimits。

顺序固定：

1. HTTP认证/CSRF -> project/stage/draft owner -> 生命周期/expected revision/hash -> target可编辑。
2. 当前本地 descriptor/profile 与冻结来源一致；snapshot/rule/source principal 已验证。
3. 获取上述 ScopeMembershipSnapshot，只按其完整证明判断是否在集合。`coverage.complete` 的整报告布尔值不能替代
   membership 项本身；摘要 pending 不妨碍已确认成员补全，membership incomplete 则不作否定结论。
4. token 对应的已知展示 key/stable identity 只匹配一个成员，匹配零个时返回范围错误且0上游请求。
5. 仅对该成员使用已绑定 credential 进行有界最小字段读取，实时权限失败不回退到另一个身份。
6. 返回前再次检查本地绑定/revision/owner；字段观察时间、稳定 ID 与源身份必须一致。

重要：集合中没有此 ID，只能证明“未列入本报告范围”，不能证明全站不存在。
因此该路径的公共文案明确包含“或 ID 有误”，不为区分这两种情况查询范围外详情。
集合中曾有此成员但上游404，显示“不存在或当前账号无法访问”，不能伪造确定不存在。
只有 adapter 有确切且允许披露的删除证据才可细分已删除；首批不依赖这种能力。
网页 owner 权限、provider principal 可见性、scope membership 三者都须满足。

## 3. Minimal Services

```text
CompletionRequest(request_id, token, expected_revision, expected_revision_hash,
                  snapshot_hash, region_target, editor_epoch, local_version)
ReportCompletionService.suggest(actor, project_id, stage_id, draft_id,
                               request:CompletionRequest) -> CompletionResult

ProviderReferenceReader.read(context:ReferenceReadContext,
                             member:WorkItemIdentity) -> ReferenceObservation
ReferenceReadContext(actor, project_id, stage_id, frozen_descriptor,
                     principal_id, rule_hash, deadline_at, request_id)
```

CompletionRequest 最大8KiB。region_target 使用服务器签发的可编辑 target，不接受 CSS selector。
provider reader 是 `provider_sync/app/api/references.py` 的公共门面，复用
ProviderAccessService 的来源/身份检查与 `bug_metrics.app.api.provider_connections`，
不借 `open_capture/capture_item` 做全票采集，不创建 CaptureIntent/worker/摘要 attempt。
网络请求需要已部署且批准的 `report_completion` read capability；
页面 GET、模板创建、渲染和保存都不触发它。没有该资格时明确 unavailable，人工仍能写。
工单传输只允许 GET 到已绑定 API origin 的白名单路径，redirect/cookie/PAT fallback 禁止。

Jira 最小字段为 stable id/key/summary/assignee/updated，
按已核实的 `/rest/api/2/issue/{issueIdOrKey}` 获取，不需要 comments/changelog。
HSDES 的浏览链接 `/resource/<id>` 不等于 API：
现有 [provider evidence](provider-api-evidence.md) 指向 `/rest/article/{id}`，
tenant/subject/fields 与实际认证和字段语义须先合格，不能照搬 Jira payload 或默认 Bearer。
HSDES 单票 reader 未合格返回 `COMPLETION_PROVIDER_UNQUALIFIED`，不是空结果。
报告 scope 已明确但缺现场资格时 fake 合约可以通过，真实 HSDES 仍须单列。

limits：单建议全程10秒、最多5个上游请求、单响应256KiB/合计1MiB、无自动重试；
配置可在测量后版本化调整，不延长已接受请求期限。初始每用户/Stage 每分钟30次 live 查询，
同 token 的显示期复用同一响应，编辑变更后不重复全票抓取。
共享限流必须服务端生效，不能只在 JS 防抖。超限反馈 Retry-After，不计模型次数。
缓存不得跨 actor/principal/profile/endpoint/rule/snapshot；缓存 title/owner 不得冒充最新。
首批不持久保存 provider 响应原文，只保留经验证的最小 observation 收据。

### Deployment And Shared Admission

公共工厂`provider_sync.app.api.references.create_provider_reference_reader`仅供补全POST服务使用。
`METRICS_REPORT_COMPLETION_ENABLED=false`为默认；资格表
`METRICS_REPORT_REFERENCE_QUALIFICATIONS=[]`默认空。开关为true本身不能产生资格。
每项资格精确绑定`profile_id,provider_id,endpoint_id,auth_mode,principal_id,
adapter_revision,qualification_ref`；与当前连接/已批准principal不符一律拒绝。
qualification_ref必须来自独立获准的部署验收记录，UI不能提交或覆写；本次合成测试使用
明确注入reader，不修改生产资格。当前HSD reader无实际字段/auth资格时保持unqualified。

`ReportCompletionService`拥有actor/Stage速率额度，provider只负责单建议transport预算。
所有本地权限、revision、target、membership及capability检查成功后，使用已有root/stage锁
调用`CompletionAdmissionStore.admit(actor,stage,request_id,now)`；释放锁后才进行网络读取。
每次实际lookup占一格，失败也计入；范围外、坏输入、缺资格不占live额度。
相同request_id不作新请求重试：客户端仅复用同一有效显示期的结果，不自动重发。

运行态配额文件为原stage runtime内`report-reference-budget.json`，不是业务历史或source authority。
精确结构`{schema_version:1,last_observed_at,buckets:[{actor_hash,admissions:[{request_id,admitted_at}]}]}`；
actor_hash由完整subject确定性hash得到。只保留最近60秒，单bucket最多30条，
最多64个活跃bucket，总文件<=64KiB；原路径/配额/atomic write守卫仍适用。
同actor跨两个service实例共享额度；写锁内先容量准入再发布新记录，无disk-free检查。
过期记录可丢，因为只属于速率窗口；文件坏格式或时钟倒退时fail-closed返回
`COMPLETION_SCOPE_UNAVAILABLE`，不能清空后继续。第31次返回429及最早记录释放后的Retry-After。
真实读取结束再次校验当前权限/binding/revision，失败不撤销已消费额度。

### Transport Error Metadata

在现有`RawResponse`末尾增加可选`retry_after:str|null=None`，保留旧位置参数及所有`.code`语义。
BoundCaptureReader仅复制长度<=128、无控制字符的Retry-After，不透出其他上游header。
`AccessError`增加可选`provider_status:int|null`、`retry_after_seconds:int|null`；
ProviderReadSession按HTTP错误构造上述字段，原capture/list消费者继续读取原code。
Retry-After支持十进制delta-seconds和HTTP-date，通过标准parser换成向上取整秒，
范围0..86400；缺失/无效用60秒安全提示，不使用响应正文或原header作UI文案。
completion服务仅在单票读取步骤把404/不可披露403映射ITEM_UNAVAILABLE，
身份验证步骤403不冒称工单不存在。429返回固定code、数值retry_after_seconds及
HTTP Retry-After；不自动重试、不延长原10秒期限。原capture的404仍保留PROVIDER_HTTP_ERROR code。
新增metadata不改变已有provider连接认证/TLS或允许的请求路径。

## 4. Results And Display

`ReferenceObservation`：
`identity, requested_key, current_key, canonical_url, title:str|null,
assignee:{id:str,display_name:str}|null, assignee_state:"assigned"|"unassigned"|"unknown",
observed_at, source_updated_at:null|str, lookup_kind:"live", scope_snapshot_hash`。
canonical_url 由 provider adapter 按已配置 web origin 生成，不能直接拼 API origin。
Jira path为 `/browse/<key>`，HSDES path为 `/resource/<id>`；UI绝不把ID当任意URL抓取。

`CompletionResult={request_id,editor_epoch,local_version,status:"ready"|"error",
snapshot_hash,observed_at:null|str,options:CompletionOption[],error:null|CompletionError}`。
成功始终按以下顺序给三个 option，失败给空 options：

| option_id | 片段 | enabled 条件 |
| --- | --- | --- |
| `id` | link(current_key, canonical_url) | identity与URL合格 |
| `id_title` | link + U+0020 + literal title | title存在且字段合格 |
| `id_title_owner` | 上项 + U+0020 + literal `@display_name` | assigned且显示名合格 |

每项含 `option_id,enabled,disabled_reason:null|str,fragment,receipt`；
disabled option 的 fragment/receipt 为 null，不可用 Enter 选择。
未指派显示第三行“未指派负责人”；字段权限/不合格显示“负责人不可用”，不插 `@None`。
不截断真实写入 title；菜单可滚动/换行。存在同名人时内部保留稳定 assignee ID。
`@名字` 只是文字，既不发通知也不改工单指派。title/owner 中的 markup 一律文字转义。
全部选项写入的数据是一份 observation，不能在同菜单内混用多个读取时间。
live观察晚于报告 cutoff 时，注释/引用详情显示两种时间；旧生成事实区仍保留原值。

## 5. UI State Machine

`idle -> composing/input -> debouncing -> loading -> ready | error -> closed`。
close 后除新输入外不自动重开；旧 request 即使完成也不得覆盖新 ready/error。

- `editor_epoch` 随编辑器/报告/target重建变化；`local_version` 随文本和选区上下文变化。
- HTTP响应、候选应用和保存前分别验证 capture，token删除/光标离开/切换草稿使 capture失效。
- 同一事务替换原 `#ID`；保留紧随其后的标点/空白，插入后光标在结果后，菜单关闭。
- loading/error 不提供可接受选项；Enter维持编辑器正常行为但不提交外层表单。
- 只有ready时上下键用于选择；IME composition优先于菜单。Esc关闭不清除输入。
- 页面重排、滚动、视口底部保持菜单锚定且不遮挡被编辑行，长菜单限制在可视区域。
- menu展示文本用 textContent 或受控节点；不得 innerHTML 拼接上游 title。
- 从第三方 hint 到受控错误状态的适配必须用公开入口/应用控制器，不 monkeypatch 私有方法。

## 6. Error Matrix

统一：正文、原 token、unsaved 内容和已保存 revision 均保持原样；失败不会插“半个结果”。
英文 code/message 是 API 权威；下表中文是 zh-CN 静态文案，参数必须转义。

| Code / HTTP | 成立条件 | 用户提示（中文） | 行为/恢复 |
| --- | --- | --- | --- |
| `COMPLETION_INVALID_ID` / 422 | token已结束但不符合所选provider格式 | 工单编号格式不正确，请检查 # 后的编号。 | 0上游；编辑原输入 |
| `COMPLETION_ID_TOO_LONG` / 422 | ID超过已支持长度 | 工单编号超过当前支持长度，未进行查询。 | 不截断；保留输入 |
| `COMPLETION_PROVIDER_MISMATCH` / 422 | 已完整ID明显不匹配Stage来源 | 当前报告使用 {provider}，该编号格式不匹配。 | 不切换provider，不调用另一系统 |
| `COMPLETION_SCOPE_UNAVAILABLE` / 409 | binding缺失、禁用、歧义或profile未就绪 | 报告来源未就绪，请检查阶段的来源配置。 | 不猜第一个scope |
| `COMPLETION_SOURCE_CHANGED` / 409 | 当前配置与冻结Stage不一致 | 来源规则已变化，当前报告不能继续补全。 | 通过既有新Stage/新报告流程处理 |
| `COMPLETION_SCOPE_UNVERIFIED` / 409 | 缺完整membership证明 | 尚不能确认本报告的完整范围，请先完成范围采集。 | 不是outside；0单票请求 |
| `COMPLETION_OUTSIDE_REPORT_SCOPE` / 422 | 完整成员集合无匹配ID | 该编号未列入本报告范围，或编号有误；未插入内容。 | 0范围外查询；不自动扩大scope |
| `COMPLETION_ITEM_UNAVAILABLE` / 404 | 已知成员上游404/无法披露的权限拒绝 | 工单不存在，或当前来源账号无法访问；未插入内容。 | 不确定不存在；不返回旧title |
| `COMPLETION_AUTH_REQUIRED` / 503 | provider认证失效/缺凭据 | 来源认证不可用，请检查 Provider 设置。 | 禁止换token/浏览器cookie fallback |
| `COMPLETION_PRINCIPAL_CHANGED` / 409 | 当前来源账号与批准源身份不一致 | 来源访问身份已变化，请重新核验报告范围。 | 不复用旧principal缓存 |
| `COMPLETION_PROVIDER_UNQUALIFIED` / 503 | reader/字段/auth组合未合格 | 当前来源尚不支持已验证的工单补全。 | 人工编辑仍可用；不伪装not found |
| `COMPLETION_RATE_LIMITED` / 429 | 本地/上游限流 | 查询过于频繁，请稍后重新输入编号。 | 有Retry-After；不循环自动请求 |
| `COMPLETION_TIMEOUT` / 504 | 总期限到期 | 查询超时，正文未改变。 | 旧响应无显示资格；可重新输入 |
| `COMPLETION_NETWORK_ERROR` / 503 | 网络/TLS连接失败 | 无法连接工单来源，正文未改变。 | 不回退到不验证TLS |
| `COMPLETION_RESPONSE_INVALID` / 502 | ID不一致、非法URL/过大/错误schema | 来源返回的数据无法验证，未插入内容。 | 不静默解析部分成功 |
| `REPORT_REVISION_CONFLICT` / 409 | server head已变化 | 草稿已有新版本；保留了你的未保存内容。 | 不自动覆盖或重放到新版本 |
| `REPORT_NOT_FOUND` / 404 | foreign/missing project、stage或draft | 无法访问该报告。 | owner检查前0source访问，不泄露存在性 |
| `REFERENCE_RECEIPT_EXPIRED` / 409 | 查询后未保存的引用过期 | 引用验证已过期；正文已保留，请重新验证或保留为人工内容。 | 按contracts处理，不自动联网保存 |
| `REFERENCE_CONTENT_CHANGED` / 409 | 保留reference_id却改了链接key/href | 工单链接标识已修改；请恢复原链接或保留为人工链接。 | 不改正文，不伪造来源 |
| `REFERENCE_INVALID` / 422 | 未签发/重复/跨target的引用ID或坏签名 | 引用信息无法验证；正文已保留。 | 不保存为可信引用 |

unassigned/title缺字段属于已验证结果的 disabled option，非全局 error。
缓存/离线旧值首批不作为“最新 owner”候选；读旧报告不依赖实时来源。

## 7. Membership Changes And Free Text

scope 限制约束的是补全查询及可信引用，不是禁止用户在人工说明里键入任意普通文字。
失败 token 可以作为未解析的人工文字保存，但在 editor 显示未解析提示，不被标为已核实工单。
手工写一个 HTTPS 链接不会获得 provider observation 或进入 report register/count。
若未来允许 scope外引用，必须独立批准访问范围和资格，不在错误菜单加入“强制查询全站”。
补全未改变Stage成员规则、采集基线、摘要覆盖或publication水位，也不改变历史报告。
