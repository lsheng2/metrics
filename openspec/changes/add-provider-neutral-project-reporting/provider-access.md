# Unified Provider Access And Credential Adoption

状态：待实施；当前已有 `project_catalog`、`sync_provider_profile`、`sync_jira_scope`，
本文件里的 `provider_access` 是目标接口，不是已经存在的命令。
2026-11-01用户允许采用Dashboard设置或迁移旧项目token。本轮未读取/复制真实token、未联网验证身份。
W3.CREDENTIALS的准确函数/DTO、文件边界、SQLite CAS、TLS/代理/重定向、
Windows原生保护与逐层反例以[provider-foundation](provider-foundation.md)细化；
它不替代本文件的能力要求或授权边界。

## 1. 决定：统一CLI与服务，不是CLI独占所有调用

用户/脚本 -> `manage.py provider_access` -> ProviderAccessService -> ConnectionResolver -> provider adapter。
Web、指标同步、报告worker调用同一个服务，不能为每次内部调用spawn CLI再parse stdout。
Jira/HSD-ES在相同CLI中按已选profile路由；不建Chiplet CLI或每项目一个脚本。

“同一Jira database”这里解释为同一Jira站点通过受支持API访问，不直连Jira内部数据库。
同endpoint不保证同权限/同视野；必须绑定实际principal与stage scope，不能共享不同身份的缓存。
当前站点是否相同、token是否等价尚未实测，不凭历史样例URL宣称已验证。

## 2. 目标命令

所有命令以固定安装Python运行manage.py；表中的ID是用户实例，不是生产硬编码。

| 子命令 | 参数 | 副作用/完成判据 |
| --- | --- | --- |
| `profiles` | 可选provider过滤 | 本地元数据列表，脱敏；不返回connection_settings原dict |
| `status` | `--profile-id` | 本地配置/凭据来源是否就绪，不调用上游，不显示secret |
| `verify` | `--profile-id --online` | 显式有界只读身份/连接探针；返回provider/site/principal及版本，不抓全库 |
| `scope` | `--project-id --stage-id` | 默认读取冻结规则及本地状态；显式`--online`才验证实际成员/查询，必须预算准入 |
| `item` | `--project-id --stage-id --item-id --capture-id` | 只读已捕获材料；没有完整capture就报coverage，不偷偷发起详情抓取 |
| `capture`（W7.RUN only） | `--project-id --stage-id --request-id` | 本地业务写入+只读上游；写操作日志、按原期限采集并归档；不以同步CLI代替durable job |
| `operation`（W7.RUN only） | `status/cancel --operation-id` | 同一业务操作日志/owner，取消不重置预算或删除原文 |

W3只交付profiles/status/verify/scope/item及adapter合成采集；capture派发和operation控制待W7，
W3若注册这两个命令，入口只能返回 `CAPABILITY_UNAVAILABLE`，零capture/operation写入、零上游，
不能返回伪造operation ID。W3.CAPTURE是内部服务+合成集成验证，不是公开命令激活。
查询参数不接受raw URL、path、token、任意JQL或actor。探索新JQL走Scope草案/批准流程，
不能在已批准stage下用CLI绕过范围。主票外依赖需要单独Grant，而不是任意item-id。

输出单一JSON envelope：`schema_version/result/error`；code/message英文，status/coverage为结构化字段，
raw source保留原文。分页/字节上限与continuation必须显式，不能取前N票宣称完整。
logs走stderr且无secret；新接口domain错误stdout为空、stderr安全JSON、非零exit，
不要沿用旧 `CommandError:`文字前缀作为机器协议。旧命令在兼容期保留原输出，不让脚本突然失效。

### 命令协议唯一矩阵

| 命令族 | stdout成功 | stderr业务失败/exit | 兼容约束 |
| --- | --- | --- | --- |
| 已有project_catalog | schema_version/result/error JSON | `CommandError:`前缀+安全JSON，非零 | W1行为不暗改，未来版本显式迁移 |
| 新provider_access | schema_version/result/error JSON | 单个安全JSON envelope，非零；无混入普通日志 | stdout/stderr/exit用subprocess fixture验证 |
| 新provider_credentials | 同上，只返回非secret采用状态 | 同上；原路径/secret绝不插入错误 | --source-file只在本地用户调用中出现 |
| 新ai_integration | 同上，明确ready/blocked | 非ready=非零安全JSON，不伪造可用 | inspect/validate离线；verify才显式连接基座 |
| 旧sync两命令 | 保留原text/JSON形状 | 保留原失败口径 | 委托共享service不改旧脚本输出；fixture锁定 |

参数错误的新命令也输出安全envelope（`INVALID_ARGUMENTS`），帮助/版本沿CLI惯例；
内部异常由边界转换为`INTERNAL_ERROR`和correlation，不输出traceback/原值。

## 3. 公共API与owner

| 产物 | 建议目标 / 责任 |
| --- | --- |
| ProviderAccessService与DTO | `provider_sync/app/api/access.py`、`access_contracts.py`；供CLI/worker/UI消费 |
| 单一连接解析 | `bug_metrics/app/api/provider_connections.py`；复用/收敛现有profile解析，其他模块不读secret存储 |
| Jira完整只读adapter | `provider_sync/out/jira_capture.py`；移植旧分页/一致性/边界，输出provider-neutral envelope |
| HSD-ES adapter | 复用 `provider_sync/app/api/hsdes.py`，通过相同port暴露实际支持部分 |
| CLI | `provider_sync/management/commands/provider_access.py`；thin transport，可信本机actor |
| 旧调用者 | `sync_provider_profile.py`、`sync_jira_scope.py`、连接测试、`tasks/out/jira_task_repository.py`、metadata adapter |

新DTO至少：
`ProviderIdentity(provider_id, endpoint_id, principal_id, credential_revision)`；
`AccessContext(actor, project_id, stage_id, rule_hash, operation_id?, absolute_deadline, remaining_budget)`；
`CaptureEnvelope(identity, rule_hash, membership_ref, items, raw_refs, coverage, request_usage, source_hash)`。
包含项目绑定的请求先检查owner/stage，之后才解析凭据/发网。

唯一credential/endpoint解析authority是 `bug_metrics/app/api/provider_connections.py`背后的resolver。
provider_sync不另建secret/settings fallback；`provider_sync/out/connection.py`若存在，只是消费句柄的
transport adapter，不读取环境/secret存储、不选择其他身份。
Resolver返回不含可公开secret字段的opaque运行期连接句柄，公开metadata只有nonsecret reference/revision；
认证注入由句柄封装的方法在校验目标origin后完成，repr/序列化不可暴露内部凭据。
`ResolvedConnection`必须同时绑定provider、endpoint、auth mode、credential source；
禁止base_url取profile而token自动来自不相关default。
带子路径的Jira endpoint与旧transport只接受HTTPS根origin的差异必须在W3明确支持/拒绝，
不能截掉path连错站点。生产TLS不降级；合成HTTP仅显式test transport。

## 4. 凭据采用优先顺序与迁移

当前Dashboard实际helper优先profile.credentials，其次profile顶层字段，再用settings fallback。
`settings:`字符串目前只是回退标记，并不是通用vault实现。本契约是拟收敛行为，不说现代码已满足。

1. 默认采用用户选择的Dashboard profile已配置凭据；若该profile明确指向部署settings，
   使用相应 `METRICS_JIRA_*` / `METRICS_HSDES_*`。显式来源未就绪就失败，不认证失败后换token。
2. 必须核对endpoint/auth mode/来源；只有与目标绑定相符的默认settings才可继承，
   endpoint被profile改写时禁止不加检查地继承另一个站点的token。
3. 旧token迁移仅在Dashboard缺失或用户明确选择替换时执行；不覆盖既有有效值、不清空旧文件。
4. 不复制旧 `.local`、CODEX_HOME、config或整份TOML。只读取指定受保护文件的 `jira.token`
   （或显式选定环境来源），保存到Dashboard受保护secret位置，由profile持有引用。
5. 默认预览只输出source kind、target profile、endpoint、auth mode、是否冲突；
   不输出token/hash/长度，不把原文件路径返回浏览器。应用私有审计可记录版本ID，不记录secret值。
6. 真正写入要求可信本机 `provider_credentials adopt --source-file --profile-id --apply`，
   source-file是路径而非token；读取前验证大小/编码/文件归属/ACL，拒绝reparse/链接风险。
   目标独立受保护secret文件/既有安全store，不把token放导出profile JSON、SQLite业务事实或Git。
   保存先临时受保护写+原子发布，再CAS更新profile引用；失败不替换旧引用、原文件不删除。
7. 目标已有值时默认拒绝。替换需预览版本ID和显式replace确认；回滚恢复原引用，不能为回滚再次泄露旧token。
8. 显式在线verify确认实际身份和范围；401/403停止，绝不切浏览器cookie或备用token重试。

source-file真实路径只能在可信本地终端/进程argv中由用户提供；不得进入profile、audit、
operation log、JSON、stderr、浏览器或模型输入。审计只保存安全的adoption ID/source kind/目标版本。
这不宣称能隐藏操作系统进程列表里的文件路径；token值本身始终不进入argv。
采用命令属于W3.CREDENTIALS，未实现前不进行手工旁路复制。
若Dashboard设置已可用，完全无需迁移token。新增secret reference reader必须接到所有计划消费者，
否则“保存成功但某条命令仍用旧settings”不算完成。
旧环境token来源若比文件优先，采用工具必须明确选哪个来源，不能把非实际使用的文件值当作当前凭据。

## 5. 统一不能丢失现有场景

- `sync_provider_profile`已有HSD路径、Jira路径和coverage语义，先委托共享服务，保留兼容输出。
- `sync_jira_scope`是旧指标入口，必须指定确切scope；新项目路径按stage选择，
  不通过“profile对应的第一个enabled scope”代替明确的stage。
- 旧Current Tasks可仍有探索查询语义，不因统一连接层就给它stage报告资格；
  收敛连接与transport时保留原API行为，逐消费者替换，不同时强改全部业务模型。
- 指标GET不触发新采集；metadata/verify明确在线与预算；error不得显示token/header/原provider异常。
- 已捕获历史保留原principal/endpoint，换凭据不直接重写旧数据身份；
  新权限收窄后按旧visibility重建规则处理，不把旧摘要带入新模型。
- HSD-ES登录方式独立，不把Jira PAT塞给HSD；不支持的评论/历史标记明确，不能用fact hash冒充完整输入。

## 6. 验收

| ID | 用例 / 目标测试 | 判据 |
| --- | --- | --- |
| ACCESS-01 | `provider_sync/tests/test_provider_connections.py` | profile与settings来源明确；端点不符零发网；401后无身份fallback |
| ACCESS-02 | `test_provider_credentials_adoption.py` | secret及source-path canary覆盖公开metadata/audit/operation/log/JSON/stderr/浏览器；无apply零写；冲突不覆盖；失败原引用保持 |
| ACCESS-03 | `test_provider_access_command.py` | status/item离线；W3 capture/operation只能CAPABILITY_UNAVAILABLE且零ID/零写/零上游；协议矩阵准确 |
| ACCESS-04 | `test_project_capture_access.py` | 错owner/stage/跨站同key、主范围外ID未授权拒绝；冻结规则漂移拒绝 |
| ACCESS-05 | `test_jira_capture_contract.py` | 完整comments/pages、请求/字节上限、更新漂移、部分权限与Closed更新 |
| ACCESS-06 | `test_provider_access_consumers.py` | 新CLI、现有同步、连接测试和受影响metadata/task消费者都用同一已批准连接来源 |
| ACCESS-07 | `test_hsdes_capture_contract.py` | 独立认证、saved-query变更、局部coverage，不构造Jira假评论 |

## 7. Coverage到接受/发布的门禁

每个Capture有独立facts/comments/history/attachments/dependencies五部分。
每部分含`state=complete|partial|unsupported|access_lost|not_requested`、source version、observed count及
可用时total；未知total不能写0，unsupported也不是“完整空列表”。
这些状态不是简单大小顺序：只有complete能满足该部分的完整要求，access_lost额外触发可见性重建。

task profile版本声明`requiredParts`。当前完整站会至少要求facts/comments完整；
history默认允许明确gap沿原规则处理，某profile将history设required时就必须完整。
附件默认metadata_only，dependencies未授权时not_requested，不能伪造已读取正文/范围外票。
所需部分由任务语义/版本决定，不能由模型或UI在失败后临时去掉以换取成功。

任一requiredPart不完整：W5.ACCEPT不推进accepted watermark，保留pending/原summary来源，
即使模型输出JSON且基座succeeded也不能放行。可发布不调用模型的partial进度/旧有效摘要视图，
但publication status必须partial并列出覆盖限制，不能称完整日报。
未来如需facts-only摘要，应是独立profile及独立覆盖标记，不能占用完整站会的accepted位置。
ACCESS-07和APP-04必须通过同一缺comment/缺history-required的合成输入验证这个拒绝链。

合成验证先行；真实verify受当次公司访问范围/预算约束。用户允许token迁移不等于无限抓库、
访问任意其他站点、导出凭据或启用正式任务。
