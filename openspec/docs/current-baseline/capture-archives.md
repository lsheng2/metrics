# 原文采集归档

当前实现提供阶段级原始材料归档 API，独立评审与执行结果见
[任务清单](../../changes/add-provider-neutral-project-reporting/tasks.md)。
它不自行连接 Jira/HSD，不调用模型，不代表完整日报已经上线。
归档基础 API 已完成独立评审；[采集网关](provider-capture.md)在后续工作包接线，
其新增来源定义和失败封存接口已随采集工作包独立验收，不代表后续摘要接受或正式部署通过。

## 数据根

必须显式配置 `METRICS_PROJECT_ARCHIVE_ROOT` 为代码仓库以外的本机数据目录。
Git 作者由 `METRICS_PROJECT_ARCHIVE_AUTHOR_NAME` 和
`METRICS_PROJECT_ARCHIVE_AUTHOR_EMAIL` 指定；不继承代码仓库或全局 Git 身份。
空根表示未配置，不会回落到当前目录。测试只使用独立临时目录。

每个 Project/Stage 拥有独立的 `archive/.git`、原文 `objects/sha256` 和
`runtime/pending`。没有默认数据 remote、自动备份或定时采集。
根和阶段身份绑定 owner、项目、阶段、规则及 Git 作者；不自动采用未知非空目录。

## 归档流程

公共入口是 `project_management.app.api.capture_archive.CaptureArchiveService`，
配置装配在 `project_management.container.build_capture_archive_service`。
每次操作通过公共 Project API 检查 owner 和阶段；浏览器不能直接传文件路径取原文。

1. `initialize_stage` 初始化独立 Git 历史。
2. `prepare` 固定 capture ID、来源身份、规则、原期限和本次额度。
3. `append_page` 先保存页意图，再保存原始字节与回执。相同页标识的不同字节被拒绝。
4. `append_snapshot` 保存规范化数据、覆盖范围及已归档页引用，产生受控版本链。
5. `finalize` 提交完整或明确部分采集；`finalize_partial` 只封存已有材料，
   可接收已知成员名单，不因详情失败丢掉待处理的范围成员。

范围成员完整不等于每票详情完整。部分详情、拒绝访问、失败页与已取得的原文不会被
转换成“完整空结果”。工单显示key可以变化，来源链按provider、站点、稳定ID、principal和规则区分。
归档记录采集层提供的principal，不替代真实上游身份验证。

## 一致性与读取

原始字节按SHA256存储；Git commit保存采集清单、快照和引用，工作树只用于人工查看。
提交使用独立index、commit-tree和原HEAD的ref比较。提交候选持久保存，重试不重新生成另一份
业务结果；Git提交、采集回执和工作树状态分别记录。

用户改过的工作树文件不会被覆盖。工作树无法更新时保留Git提交并报告stale；
历史读取使用提交内容，不把手工修改当原始数据。
`read_capture/read_page/read_snapshot` 必须带Project、Stage及capture身份。
列表和来源链使用固定历史HEAD的分页游标，后续提交不会混进原分页结果。

捕获到的A/B/C各版本保留；本模块不选择“上次接受摘要”基线，后续delta/接受模块负责该语义。
归档项目仍允许授权历史读取和封存已经捕获的失败材料，不允许新增采集。

## 容量

额度覆盖根目录、单阶段、单次采集、原文文件、Git、暂存及未结算预留。
默认根50GiB、阶段10GiB、单次256MiB，均是可配置应用额度，不是磁盘空闲要求。
达到额度后拒绝新材料，不截断原文或删除历史。永久不检查磁盘剩余空间。

根预算锁与阶段锁按固定顺序取得，网络请求不能在持锁期间执行。
原采集已记录的额度用于恢复封存；新的额度调整不能续期原采集或清零未决预留。
实际写入失败仍明确失败并保留恢复材料，不推进完整采集、更不能推进摘要或发布状态。

## 当前限制

当前没有 `provider_access capture` 的正式运行入口；W7再装配持久操作和手动触发。
自动调度、迁移旧数据、远端备份、AI接受和报告发布均不是这份归档API的完成声明。
运维启用前须沿用户部署流程初始化真实数据根，不能把临时Git验证当正式部署。
