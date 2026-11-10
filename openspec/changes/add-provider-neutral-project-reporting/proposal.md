# Provider-Neutral Project Management And Reporting

## Why

用户于2026-11-01决定在Dashboard仓库执行项目管理/站会报告建设。
Chiplet只是一个项目实例，不能作为生产模块名、默认范围、prompt或provider约束。
用户应能创建自己的Project/Stage，并显式绑定Jira范围或HSD-ES saved-query profile。

## What Changes

- 2026-11-11 AI接入改为[MDB-2](../embed-ai-base-runtime-in-process/proposal.md)进程内运行时：未完成的W4.REPLAN/W5
  经project_management同步task-run端口与`ai_profiles`精确`id@version`调用；下列SDK/注册/connector/pack条目仅为历史。
- 2026-11-06根据语言跳转后的工作台39.6秒、169次Git调用的诊断，
  新增[读取性能架构](report-read-performance.md)及[实施/验收](performance-execution.md)：
  模块内读写分离、固定head的批量读取、请求级校验复用与窄操作入口。
  当前只建立优化规格，不新增持久索引、不改AI Base、不降低原字节和权限校验。
- 2026-11-05补齐[SDK 0.2分工与迁移](sdk-020-integration.md)及[集成后执行](sdk-020-post-integration.md)：
  固定0.2.0a1 SDK与原a2 pack，保留业务守卫，先发布spec，再只执行到`IP-SDK020-READY`等待。
- 增加独立 `project_management` 模块，Project是用户业务容器，不是provider profile的别名。
- Stage冻结一个明确的来源定义；来源变化须新建Stage，不覆盖历史。
- 先交付本机CLI与持久目录，随后接入双语工作台、coverage-aware采集与报告。
- 复用 `bug_metrics/app/api`、`provider_sync/app/api`；AI执行经进程内`ai-base-runtime`的task-run端口（MDB-2）。
- 完整摘要/行动、Git原文、成功接受/发布水位沿既有站会要求移植，不重建Chiplet专属应用。
- HSD-ES以同一公共流程接入；缺少完整评论/历史能力时明确partial/unsupported，不伪装完整。
- 新增应用AI接入的明确产物与消费者（`ai_profiles`精确版本profile），区分无工具权威Task和可选只读助手tool。
- 统一Provider CLI与连接/凭据服务，优先复用Dashboard设置；旧PAT仅按明确目标和受保护采用流程迁移。
- 以MIG-01至19盘点旧实现、依赖、目标模块、测试与不能直接搬的部分，拆成可执行叶任务。
- 按用户批准的API-EVO-01不默认兼容旧AI接口；2026-11-11起由MDB-2嵌入运行时版本准入记录版本、受影响消费者和验收。
- 2026-11-02确认报告模板化，以邮件兼容HTML为主产物；支持网页内人工编辑/注释、
  带格式复制和下载，用户明确选择定稿并提交独立数据Git。保留原始摘要、人工修改和
  每日不可变版本；模板切换/编辑不调用模型，Markdown/Excel原要求不取消。
- 2026-11-03后续明确只需WYSIWYG，无源码模式；工单补全仅由`#ID`输入自动触发，
  来源由Stage决定，范围外/不存在或无权限/超时等错误保持正文不变。
- 增加用户可视化创建的版本化模板、填写槽和受控数据块；
  人工填写不依赖AI，显式AI填写使用独立profile和候选接受，不把渲染变成模型调用。
  详细接口、历史兼容与执行见[Authoring V2](report-authoring-v2.md)，仍是本change的一条新lane。
- 将后续效果确认补入[报告连续性](report-continuity.md)：逐票稳定行序、来源状态日期前缀、
  AR、彩色富文本的人工最终版本继承、同周累积、跨周最近更新及未结束行动。
- 明确来源/分析/正式报告三种baseline，手动“生成今日草稿”不等于定稿；
  可选定时沿同一准备服务，默认关闭并在W7单独资格，不自动推进正式报告基线。

## Non-Goals

本变更不自动迁移旧chiplet运行数据、终止keeper、修改AI Base仓库、启用周期任务、
写Jira/HSD-ES或执行真实收费模型调用。第一阶段不修改其他Copilot正在编辑的Scope UI。
不统一两库Django运行环境，不通过跨仓PYTHONPATH依赖旧源码。
HTML编辑不包含自动发邮件、任意HTML模板上传、离线编辑回导或自动Git push。

## Scope And Authorities

Dashboard是产品host；project_management拥有项目/阶段/报告业务。
bug_metrics拥有可变范围/指标；provider适配器拥有来源解析；进程内AI Base运行时拥有AI执行事实（MDB-2）。
本目录tasks.md是此变更唯一执行清单，原chiplet T12没有被自动标完成或恢复。
详细边界见design.md，阶段与依赖见tasks.md。
2026-11-01用户另行允许旧Jira token迁移；这是有界credential adoption授权，
不覆盖写Jira/HSD、无限采集、拷贝整个运行目录或自动启用任务。
