# Excel 名单解析

当前公共入口为 `project_management.app.api.spreadsheet`：
`inspect_workbook` 检查工作表；`extract_workbook` 提取显式指定的表、列和起始行。
只处理调用方提供的字节，不读取文件路径、调用 Jira/HSD 或批准 Stage。
完整名单服务的实施状态见[任务清单](../../changes/add-provider-neutral-project-reporting/tasks.md)。

## 原文和身份

返回原工作簿的 SHA-256、选定列的有序唯一 tokens、原始有效行和行诊断。
重复行保留原位置和值，同时指出首次出现的行；不会读取其他列作为范围。
Jira 接受数字 ID 或 Jira key 语法，HSD 只接受数字 article ID 语法。
语法正确不代表该工单存在或当前账号有权限。

`resolved=false` 始终表示尚未完成上游身份核验。解析结果的 `can_confirm`
只表示没有阻止后续处理的语法错误，不是 Stage 已批准或可以直接调用模型。
后续服务仍需执行项目权限、来源身份和批准哈希检查。

## 安全边界

解析保留旧项目的 ZIP/XML 前置检查、公式拒绝、行序检查和数值精度约束。
工作簿上限为512KiB输入、8MiB展开、128个归档项、32张工作表、
100000个XML元素、64层深度、10000行扫描、500项工单及500条诊断。
调用方可以降低限额，不能以0、布尔值或更大数值解除限额。

公式、错误单元格、日期/布尔值、非整数或超过15位精度的数字都产生诊断，
不把其余有效行作为一个成功的部分批准名单。长数字字符串保持字符串。
不执行宏，不提取ZIP文件到磁盘，不加载外部链接，不检查磁盘剩余空间。

调用方的取消/期限检查会原样传播失败；已经打开的工作簿和行迭代器会关闭。
原文件字节由调用方持有，本模块不会修改它们。

## 复用范围

移植自固定旧版本的 `spreadsheet_archive.py` 和 `spreadsheet.py`，
只改错误类型、provider语法与返回字段。固定依赖为
`openpyxl==3.1.5` 和 `et-xmlfile==2.0.0`。
来源映射见[移植记录](../../changes/add-provider-neutral-project-reporting/provider-lists-source.json)。
## 在线身份解析

内部公共入口 `provider_sync.app.api.list_identity.ProviderListIdentityResolver`
可以在建立 Stage 前解析显式 Jira key/数字 ID 名单。调用方提供
`ProviderRequestContext`、项目、选定连接 profile、预期 endpoint 和有序 tokens，
并显式指定 `online=True`；缺少确认不会访问来源。

当前只实现 Jira Data Center `server_pat`。一次解析只选择一次凭据，
请求前及完成时重查项目 owner 和连接公开元数据，并在前后核对 `/myself`。
身份、endpoint、auth/TLS/transport 或凭据选择发生变化时拒绝完成。
所有请求共用原期限、次数和下载预算；重复 stable ID、错误数字 ID、
失败记录及部分结果都不能形成成功名单。错误保留失败位置和累计用量。

返回 stable ID、当前 display key、主体与观察用量，不返回原始响应或凭据。
这个入口不创建 Stage、不保存工作簿、不产生批准哈希，也不代表真实 Jira
环境已验证。HSD 在线解析仍明确拒绝为未资格能力。
不可变名单落库和CLI仍由后续名单工作包接线。
