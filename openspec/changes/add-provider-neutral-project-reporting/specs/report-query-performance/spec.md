## ADDED Requirements

### Requirement: Report queries use bounded shared snapshot reads
报告查询 SHALL 在当前owner/project/stage身份检查后，使用一次请求拥有的固定Git head读取
作用域。作用域 SHALL 在请求结束时释放，SHALL NOT 作为跨请求的权限或发布成功缓存。
优化 SHALL 保留原记录校验、分页顺序、来源完整性和原始publication字节。

#### Scenario: Language switch reloads the actual workbench
- **WHEN** 用户从英文切到中文并返回同一报告工作台
- **THEN** 语言POST SHALL 只执行认证、语言cookie和重定向，不读取报告归档
- **AND** 重定向GET SHALL 通过统一query service批量加载完整所选列表
- **AND** 验收 SHALL 计到目标语言和列表可用，不仅计302或loading出现

#### Scenario: Draft and publication lists need the same packet
- **WHEN** 草稿状态验证和定稿列表消费相同commit的六文件
- **THEN** 同一作用域 SHALL 读取每个对象一次并复用已验证packet
- **AND** 校验 SHALL 包含原始正文和修订，不得只凭manifest存在判定完整

#### Scenario: A workbench publication row does not display checkout diagnostics
- **WHEN** 工作台只显示定稿manifest、修订、提交和选择控件
- **THEN** query SHALL 返回不含checkout字段的专用列表投影，并仍执行完整六文件校验
- **AND** query SHALL NOT 为未使用的字段扫描整个工作树或伪造current/stale
- **AND** 旧公开publication API与可见的capture checkout状态 SHALL 保持原校验与含义

#### Scenario: New source appears while a page is read
- **WHEN** view固定H后其他操作发布H2
- **THEN** 当前Git读取 SHALL 保持H的一致快照
- **AND** 下一view SHALL 重新核对身份和head，能够看到H2
- **AND** runtime草稿指针中途改变 SHALL 返回明确冲突而非混版

### Requirement: Batch transport preserves integrity and resource bounds
批量读取 SHALL 复用Git原生协议并限定对象数量、字节、共同deadline和子进程生命周期。
缺对象、错误类型/模式/哈希、协议截断或额度耗尽 SHALL NOT 返回貌似完整的列表。

#### Scenario: A batch contains a missing or oversized object
- **WHEN** 任一必需对象missing或超过原文件/view额度
- **THEN** 该批 SHALL 失败并保持原稿和所有基线不变
- **AND** 系统 SHALL NOT 静默截断、重置deadline或降级成无界逐文件查询

#### Scenario: A materialized checkout was edited
- **WHEN** Git发布对象有效而工作树/index内容被人工修改
- **THEN** 查询 SHALL 保留原current/stale语义并仍从获准Git对象读取报告
- **AND** 优化 SHALL NOT reset、覆盖工作树或把head相同当作内容一致

### Requirement: Commands do not rebuild unrelated report lists
Prepare、reprepare、Save和Finalize SHALL 保留原命令恢复与业务校验边界，
SHALL NOT 为表单处理预先重建全部工作台历史。JSON操作 SHALL NOT 先渲染HTML上下文。

#### Scenario: Preparation succeeds
- **WHEN** 合法准备请求已具备所选系列、模板、来源和基线
- **THEN** 服务 SHALL 直接返回原业务结果并保持同日去重
- **AND** 成功路径 SHALL NOT 调用工作台三列表查询或引入模型调用

#### Scenario: Original command is replayed after choices changed
- **WHEN** 已有命令关联的模板后来归档或当前页面选择发生变化
- **THEN** 服务 SHALL 先按原命令/请求hash执行合法恢复
- **AND** 精简form SHALL NOT 因新下拉选项缺少旧模板而错误拒绝

#### Scenario: A stale editor tries to finalize
- **WHEN** 读取页面后revision、scope、editorial head或停会状态变化
- **THEN** 写入 SHALL 在原写锁下核对最新权威数据
- **AND** 早先GET的缓存 SHALL NOT 允许覆盖、重复提交或跳过冲突

### Requirement: Performance acceptance measures completed user outcomes
实施 SHALL 使用固定候选、数据和环境记录首请求与稳态样本，
并满足`performance-execution.md`的耗时、次数和字节验收门槛。
规格或设计评审通过 SHALL NOT 被当作优化结果。

#### Scenario: A performance result is published
- **WHEN** 宣称报告读取优化完成
- **THEN** 回执 SHALL 包含实际工作台、语言往返、preview、Save及规模场景的样本和结果
- **AND** 冷请求、失败/并发、原文件hash及cleanup SHALL 保留证据
- **AND** 无真实来源/模型授权时 SHALL 仅声明合成资格，不扩大为生产SLA
