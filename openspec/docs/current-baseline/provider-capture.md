# Provider 采集接口

当前实现把 Project/Stage、显式连接、已核验的上游身份、原始响应和 Git 归档连接起来。
执行与评审状态以[唯一任务清单](../../changes/add-provider-neutral-project-reporting/tasks.md)为准。
当前没有启用正式采集、模型、自动调度或远端数据备份。
Jira 内部采集链路和诊断 CLI 已完成合成验证与独立评审；HSD 的准确响应资格、
名单导入、范围外依赖和附件正文仍在后续工作包中。

## 入口和范围

`provider_sync.app.api.access.ProviderAccessService` 提供只读诊断、范围枚举和受限采集 lease。
`project_management.app.api.project_capture.build_project_capture_service` 装配内部同步采集服务。
它不会因打开页面而执行；公开 `provider_access capture/operation` 在 W7 前返回
`CAPABILITY_UNAVAILABLE`，不生成 operation ID。

本包支持 Jira Data Center PAT 的合成验证路径。HSD 和其他未取得准确响应契约的组合明确
返回 `PART_CONTRACT_UNQUALIFIED`；这不表示 HSD 没有评论或历史 API。
真实站点和凭据资格仍须分别验证，不能从合成响应测试推导。

## 采集顺序

1. 核对 Project owner、阶段状态和固定 descriptor，再读取所选 profile 的连接材料。
2. 同一 lease 核验 `/myself`、固定 JQL 解析器、递归过滤器定义和服务端严格查询验证。
3. 在阶段归档写入首次核验的来源定义；后续定义或 principal 变化要求新阶段，不覆盖旧记录。
4. 准备 capture，将此前有界暂存的身份和定义响应写入归档。
5. 完整枚举成员，再按本轮详情额度读取字段、全部评论分页和已返回的字段历史。
6. 再读详情、成员、过滤器定义和身份。漂移或缺页只能形成明确部分结果。
7. 封存 capture。完整成员、完整详情、成功摘要和已发布报告不是同一个状态。

所有请求共用原期限和累计请求、解码后字节额度。没有失败自动重试、替换凭据、跟随重定向
或范围外工单抓取。字段、评论和原始响应保持原文，不把 Closed/Fixed 当作忽略更新的依据。
附件及依赖在此包只保留元数据，正文与范围外访问属于后续显式授权能力。

原始响应在 JSON 解析前保存；截断响应、HTTP 拒绝和格式错误不会被当作完整空结果。
失败封存保留已知完整成员名单，即使只有一部分工单拿到了详情。
存储/提交失败保留未决材料并报错，不伪造另一个成功或部分提交候选。

## 本地诊断

以下命令使用可信本机 operator，不接受 actor、token、任意 URL 或 JQL 参数：

```text
python manage.py provider_access profiles --provider-id jira
python manage.py provider_access status --profile-id <profile>
python manage.py provider_access scope --project-id <uuid> --stage-id <uuid>
python manage.py provider_access item --project-id <uuid> --stage-id <uuid> --capture-id <uuid> --item-id <stable-id>
```

这些命令只读本地配置或归档。`verify` 和 `scope --online` 另需显式 `--online`、
`--project-id`、`--stage-id`、`--deadline-at <UTC ISO8601>`。
`--max-requests`、`--max-download-bytes`、`--max-members` 只允许降低配置额度。
在线诊断返回累计 usage，`archived=false`，不把诊断当作已完成的 capture。
离线 scope 的 `first_resolution_hash`、`first_principal_id` 表示首次已归档的来源核验，
不是本次已经重新访问上游或仍有权限的证明。

## 数据与复用

原文目录、容量和 Git 事务见[归档说明](capture-archives.md)。
首次来源定义保存在 `source_resolution/first.json`；原始响应保留自己的字节哈希。
只在派生比较中处理已知且 schema 验证过的 Jira 插件对象地址，不改写原字段或 source hash。

JQL bundle 和许可证从旧项目固定版本移植，运行时校验 manifest 和 Node 版本。
来源及有意适配见[移植清单](../../changes/add-provider-neutral-project-reporting/provider-capture-source.json)。
无变化复用、累计 delta、摘要接受和报告发布属于后续 W4/W5/W6，不由此接口宣称完成。
