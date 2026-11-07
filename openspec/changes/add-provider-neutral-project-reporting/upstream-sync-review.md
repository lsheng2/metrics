# Upstream Sync Review

日期：2026-11-07，检查完成于15:45（UTC+8）。
状态：评估完成，`no-op`；不存在待同步的上游提交，因此未执行rebase。
文档影响：development / maintenance；当前操作指南见
[upstream-sync](../../../docs/development/upstream-sync.md)。
唯一执行记录仍在本change的[tasks](tasks.md)，不建立第二份任务清单。

## Scope

用户要求检查主线所基于的开源项目，评估新功能/bug fix收益；有价值的新提交才做
rebase并更新规格。这里的上游是Git remote `upstream` 指向的 `clutcher/metrics`，
不是Milkdown编辑器、AI Base SDK或`sd-metrics-lib`依赖库的独立升级。

本次只访问公开GitHub源码/元数据，不读取真实工单、凭据或模型配置。
不改正式服务，不执行数据迁移，不启动定时任务。

## Observed Baseline

以下日期以GitHub UTC为准，避免将“最新Release”和“最新main”混用。

| 项目 | 已核实结果 |
| --- | --- |
| 上游仓库 | `https://github.com/clutcher/metrics` |
| 默认/已列出的公开分支 | `main` |
| 最新正式Release | `1.22`，2026-07-14 07:59:00 UTC |
| Release对应提交 | `5133a9fb3ade2b9afed3211fb0a3ccb056e4ac7c` |
| 最新main | `dce92c9801628184fa04f0caf4b4f7471a2eb4fd` |
| main最新提交时间 | 2026-07-17 17:41:52 UTC；中国时间2026-07-18 01:41:52 |
| 本项目main | `11583075f4db277f5b264064fd58cb2dc82019ef` |
| merge-base | 与最新upstream/main相同 |
| 本地独有 / 上游独有提交数 | `152 / 0` |

GitHub repository、commits、branches、releases/latest和tags API均实际读取。
`git ls-remote --symref upstream HEAD`与API返回相同HEAD；
`git fetch --no-tags upstream main`成功后再次核对祖先关系。

Release 1.22之后上游还有三个提交：PR gateway、board view、依赖更新。
三个都已经在本地main的历史中。上游版本号较小，不代表本分支需要退回该tag。

## Benefit Assessment

下面是上游近期值得保留的内容，**不是本项目尚未同步的新提交**。
每项均实际运行`git merge-base --is-ancestor <commit> HEAD`确认已包含，
并对关键当前源文件与上游进行比较。

| 提交 / UTC日期 | 类型 | 对本项目的价值 | 当前裁定 |
| --- | --- | --- | --- |
| `2bc564d` / 07-17 | 功能：Current Tasks看板视图 | 日会中按阶段扫描工作项；保留空阶段与稳定排序 | 已包含；view和分组实现与上游一致。它不是报告编辑器，也不自动扩展报告scope |
| `b3ef37b` / 07-17 | 功能：PR policy gateway | 在任务行观察关联PR审核/阻塞状态，减少来回切页 | 已包含；核心lookup/view一致。实际可用性仍取决于PR provider连接，未在本轮验证Intel业务接入 |
| `5133a9f` / 07-14 | 功能：PR按release/iteration筛选 | 聚焦当前release与迭代的PR，辅助会前准备 | 已包含；筛选工具与上游一致 |
| `e147dda` / 07-14 | 功能：Current Tasks独立iteration | release与iteration分别处理，避免把两类字段混用 | 已包含；Jira转换器仍保留可配置iteration字段与解析。需要实际field配置，不等同于站会周标签 |
| `bf0ef28` / 07-08 | 修复：Azure Available Members查询超时 | 分离普通更新时间和状态变化时间的查询，降低错误/高成本查询风险 | 已包含；Azure实现未改变。对当前Jira报告Git读延迟不是直接修复 |
| `d801abb` / 07-04 | 功能：速度图选择状态保留 | 保留筛选、期间、开发者和rolling average选择，减少重复操作 | 已包含；team/dev velocity view与上游一致 |
| `ae8773f` / 07-03 | 修复：速度统计日期语义 | Azure使用StateChangeDate过滤，并修正速度查询/零结果处理 | 已包含；不据此宣称Jira与Azure有相同历史查询语义 |
| `6e0ba0b` / 07-01 | 修复：自定义story points排序 | 恢复排序并避免多余读取，减少任务页重复I/O | 已包含；排序与字段提取核心一致。它不改变报告的工单自然排序 |
| `dce92c9` / 07-17 | 维护：依赖更新 | `sd-metrics-lib 7.1.0`、`Django 6.0.7`、`pytest 9.1.1` | 当前requirements已有这些版本；保留本项目新增的存储、导出、Windows及浏览器依赖 |

15个检查的核心文件中，13个Git blob与upstream/main完全相同。
差异文件是`tasks/out/jira_task_repository.py`和`requirements.txt`：
前者保留本项目的Server PAT、企业CA、统一连接与Server provider适配；
后者保留本项目扩展依赖。不能通过覆盖上游整文件的方式“同步”而丢失这些能力。
UI样式有本地调整，不把核心相同扩大为所有页面完全相同。

## Decision

1. `upstream/main`已经是`HEAD`的祖先。普通rebase到同一上游没有新内容可带入。
2. 不使用`--force-rebase`、`--root`或移动到Release tag来制造“完成了升级”的结果。
3. 不创建无用途工作树、不stash当前未提交工作、不改branch HEAD、不强推main。
4. 按用户条件完成本轮评估，停止源码升级；这不是因冲突或测试失败而未完成的rebase。
5. 未来有上游独有提交时，再按当前指南执行收益/冲突评估和隔离验证。

本轮不判断各依赖库是否另有更新，也不是依赖漏洞审计。
“上游main已全部包含”不能当作所有第三方依赖都已最新或无漏洞的证明。

## Validation

选定SDK 0.2.0a1环境，使用现有no-dotenv且禁止外网的测试入口：

```powershell
& .tmp/sdk-020-join-20261105/app-venv/Scripts/python.exe -I scripts/validation/run_report_authoring_tests.py `
  ui_web/tests/test_unit_task_grouping_utils.py `
  ui_web/tests/test_unit_pull_request_filter_utils.py `
  ui_web/tests/test_unit_task_sort_utils.py `
  tasks/tests/test_unit_jira_task_converter_iteration.py `
  velocity/tests/test_api_velocity_search_criteria.py `
  -q --tb=short --junitxml=.tmp/upstream-metrics-20261107/retained-features-01.xml
```

结果：**74 passed，0失败/错误/跳过**。覆盖看板分组、PR筛选、任务排序、
Jira iteration转换及速度查询参数；不是PR provider实时验证或全栈浏览器资格。
产品源码未改，不重跑此前真实三日演示或完整报告周。

本机证据：

- `.tmp/upstream-metrics-20261107/upstream-review.json`：
  GitHub/API/Git身份、9个已包含提交、15个源文件blob及16个既有脏文件hash。
  SHA256：`ab2d057c615017f56fc6666e0cc06ac74c757881651d25c69cb08915b3b7e3da`。
- `.tmp/upstream-metrics-20261107/retained-features-01.xml`：
  SHA256：`5ec4bd1daea345ee7f503a57f2ddf67ea14a8750592a4042604e2e2638d0e492`。

OpenSpec strict、适用的文件长度规则、空白检查和新文档3个相对链接均通过。
16个既有脏文件内容保持不变：tasks仅新增本轮记录，移除这段新增文字后的hash
与检查前一致；其余15个文件直接hash一致。HEAD仍为`1158307`。
此前真实演示文档与无关Scope/config/style改动保留，上述评估阶段没有进行提交或推送。

用户随后授权限定发布这些非敏感文档到本方`origin/main`（`lsheng2/metrics`），
并明确禁止向`upstream`（`clutcher/metrics`）推送。发布不改变本次无需rebase的结论，
不纳入真实工单截图/报告或无关Scope/config/style修改；推送边界见维护指南。
