# Provider 连接与凭据

连接解析与受保护凭据采用已通过限定候选的独立评审；后续任务状态以
[项目报告任务](../../changes/add-provider-neutral-project-reporting/tasks.md)为准。
这不代表真实Jira/HSD登录、完整采集或AI报告已经通过验收。

## 连接来源

公开入口在`bug_metrics.app.api.provider_connections`。Jira同步、metadata、
HSD同步、连接测试和Current Tasks使用同一解析规则。
Current Tasks仍以调用者传入的`TasksConfig.jira`为准，不被全局settings覆盖。

- profile显式选择的受保护引用无效时立即拒绝，不换用settings token。
- settings凭据只能用于匹配的provider endpoint及认证方式。
- 原有profile内嵌凭据仍可显式使用，凭据版本保持unknown，不作为权限未变化证明。
- 服务端PAT不需要email；Cloud Basic需要对应用户名。
- HSD认证独立；Bearer模式尚无真实资格，不能当作Jira PAT的另一种用法。
- 客户端拒绝越过endpoint/base path、跟随重定向或执行未批准写方法；TLS不降级。
- 企业CA及代理配置由连接层绑定使用，公开状态不返回凭据或私有CA路径。

离线连接信息不验证上游principal；界面用户不是Jira/HSD身份。
metadata刷新或显式连接测试不等同于范围采集/摘要权限。

## 本机凭据采用

Windows使用项目依赖`pywin32==312`。首次采用仅接受已有受保护TOML文件中的
`[jira] token = "..."`，目标必须是Jira `server_pat` profile。
不复制整个旧配置、数据目录或环境，不改原凭据文件。

`METRICS_PROVIDER_SECRET_DIR`指定受保护目标根，默认在应用state下的`provider-secrets`；
`METRICS_PROVIDER_SECRET_MAX_BYTES`默认65536。新目录和文件具有禁止继承的受限DACL；
不自动修改现存未保护目录的权限。路径无效、权限不满足时明确失败。

从Dashboard根使用本项目Python：

```powershell
.\.venv\Scripts\python.exe manage.py provider_credentials preview --profile-id example-jira --source-file D:\Private\jira.toml
.\.venv\Scripts\python.exe manage.py provider_credentials apply --profile-id example-jira --source-file D:\Private\jira.toml --preview-file D:\Private\preview.json --apply --replace
```

以上ID和路径为示例，不是已部署配置。`--preview-file`接收前一步保存的非敏感JSON输出，
也接受其中的result对象。预览不写文件、profile或审计；apply重新检查来源文件身份和
profile版本。目标已有来源时需要`--replace`，否则拒绝。

成功输出单个版本化JSON；参数/业务失败输出单个安全JSON到stderr并非零退出。
token和源文件路径不进入结果、profile导出、审计或模型输入。源路径仍会出现在用户
明确输入的本机命令行中，这不是隐藏操作系统进程参数的功能。

## 一致性与失败

采用期间在SQLite真实条件更新中比较当前观察到的原始连接JSON、版本和更新时间，
然后在同一事务内写新引用与审计。公开预览不保存原始连接或token hash；
无状态的另一进程也能消费预览，不依赖代理记忆或服务内旧token缓存。

每个新secret revision先写不可变intent，再写token和绑定provider/profile/endpoint/auth的
metadata。数据库失败时旧引用不变，未引用文件保留在受保护库存中，不自动删除。
profile编辑器不会把旧表单里的内嵌token恢复到已采用的受保护引用上。
历史版本不会因替换而被清空；失效凭据和远端撤权仍需明确处理。

native测试使用真实Win32句柄、临时文件、临时SQLite和两个子进程；不读取真实凭据。
源码专项通过不代表已迁移用户token，实际采用只能经上述显式命令执行。
