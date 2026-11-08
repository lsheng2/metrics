# 旧站会工作区退役与恢复

状态：2026-11-08，退役迁移完成，独立审查通过，旧目录已达到可删除条件。
本轮没有删除旧目录。删除前仍须关闭旧工作区并遵循本文的最后检查步骤。
当前产品目录为 `D:\AIGC\scrum_dashboard`。
旧目录为 `D:\AIGC\chiplet_programmgr`，本轮保持只读，不直接删除。

## 迁移含义

这次迁移把“继续维护的产品”和“必须保留的历史”分开：

- 当前应用、业务模块、接口、测试和开发规则由 Dashboard 维护。
- 尚未移植的通用代码、全部旧 Git 历史、未提交研究与测试改动、
  原始工单记录、历史报告、凭据和验证材料进入代码仓库外的私有归档。
- 归档不是新的运行数据库，不自动导入或接受历史摘要，不激活旧服务。
- `W4.IMPORT`、`W7.PROTECTION` 等功能仍按原任务执行，不因删除目录而完成。
- 同盘归档避免误删旧目录导致的数据丢失，不保证磁盘损坏后的恢复。

## 目录和访问

本次归档固定为 `D:\AIGC\retired_workspaces\chiplet_programmgr-20261108\`。
已保管 128,752 个普通文件、13,429 个目录，文件总量 2,059,470,928 字节。
23 个内部链接的目标全部已保管；2 个外部链接指向共享缓存，只保留链接元数据。
确切哈希及验收范围见
[删除就绪回执](../../openspec/changes/retire-legacy-standup-workspace/delivery.json)；
不得选择“最新目录”猜来源。
归档 ACL 仅允许当前 Windows 用户和 SYSTEM，代码 Git 不收录归档内容。

| 位置 | 内容 |
| --- | --- |
| `snapshot/.git/` | 原始 Git 对象、refs、index、reflog、配置 |
| `snapshot/src/standup/`、`snapshot/tests/` | 完整旧实现及测试，包括未提交修改 |
| `snapshot/docs/`、`snapshot/openspec/` | 原始设计、研究、复盘和未完成规格 |
| `snapshot/.local/`、`snapshot/outputs/`、`snapshot/.tmp/` | 原始材料、报告、实验和本地证据 |
| `snapshot/.local/preflight.secrets.toml` | 原凭据字节，仅保管，不输出、不自动采用 |
| `history.bundle` | 无远端依赖的完整 refs 恢复包 |
| `inventory.json` | 逐文件长度/SHA-256、空目录、未跟随的链接 |
| `capture.json`、`evidence/` | 来源、复制、恢复、验证回执 |

所有普通文件都保留，包括可重建缓存，不根据文件名推测某份数据没有价值。
链接只存元数据：内部目标内容已按正常目录保留；共享 Node 缓存不属于旧项目，
不跟随复制、更不递归删除其目标。

## 今后查阅旧资料

以归档 `snapshot` 为原目录的新位置，保持原相对路径：

- 作者层复盘：`docs/development/2026-11-05-report-authoring-postmortem.md`。
- AI Base/SDK 建议与交接：`docs/development/ai-base-sdk-copilot-handoff.md`、
  `2026-11-05-ai-base-public-sdk-review-handoff.md` 及 owner-feedback。
- 迁移与 SDK 研究：`docs/research/2026-11-01-*.md` 和 `assets/`。
- 增量、生命周期、历史导入和保护设计：原 `src/standup/`、测试、
  `openspec/changes/add-durable-standup-workspaces/`。
- 未实施的双后端设计：`openspec/changes/add-dual-model-backends/`。
- 早期 Excel/Markdown 报告：`outputs/20261022_crc_2b_p1_ego9/`。

旧文档中的暂停状态、路径、commit、source hash 均是历史事实，不覆盖当前
[Dashboard 任务](../../openspec/changes/add-provider-neutral-project-reporting/tasks.md)。
历史文档原字节不改写；旧相对链接按本表定位。
完整 MIG-01..19 能力归属仍见[移植目录](../../openspec/changes/add-provider-neutral-project-reporting/migration-catalog.md)。

## 校验与恢复

从 Dashboard 目录执行：

```powershell
pwsh -NoProfile -File scripts/maintenance/archive_workspace.ps1 `
  -Action Verify `
  -ArchiveRoot 'D:\AIGC\retired_workspaces\chiplet_programmgr-20261108'
```

如果原目录仍在，追加 `-SourceRoot 'D:\AIGC\chiplet_programmgr'`，
确认归档后没有新的未保存内容。失败不能忽略，也不能手改成功回执。

只需某个原文件时，从 `snapshot` 读取；不得为查看历史启动旧服务。
只需固定提交源码时，在新的私有目录克隆 `history.bundle` 后使用
`git show <commit>:<path>`；不要把 snapshot 的 dirty overlay 误称为冻结提交。
需要恢复全部未提交/ignored 数据时复制 `snapshot` 到新的私有目录，
再验证 inventory；bundle 单独不能恢复这些材料。
归档链接按 inventory 查目标，默认不重建绝对链接。

已实际从 bundle 恢复 85 个提交和全部 2 个 refs，`git fsck --full` 通过。
另恢复核对了报告、未提交测试改动、复盘和凭据共 7 份样本，未读取原目录。
这些是保管与恢复证明，不是将历史记录导入 Dashboard UI 的证明。

## 验证边界

归档工具 17 项测试和 Dashboard 17 项采集、跨日发布、恢复测试均通过。
后者在独立进程中禁止旧路径的 Python 文件/导入操作及子进程参数、工作目录引用；
两个拒绝反例先证明守卫生效，实际业务运行没有旧路径或网络访问尝试。
这不是操作系统级沙箱，也不是重新验收真实 Jira、模型或 Outlook。
当前配置、数据库、解释器 `.pth`/editable 指针、服务、任务和快捷方式已作定向检查。
另检查了应用、构建文件及运行环境的 5,183 个目录和 7 个根路径祖先，
没有发现指向旧目录的 junction/symlink 或活动源码引用。
历史 source-root 字段、Codex 的旧项目 trust 登记不是 Dashboard 运行依赖，保留不改。

机器回执和原始 XML 位于归档 `evidence/`。归档中的 `independence_probe.py`
是已执行探针的源码保管件；复现时应放回 Dashboard 的
`.tmp/workspace-retirement-20261108/`，使用
[指定的 SDK 环境](../development/reporting-delivery.md#environment)运行。
不要直接从归档目录执行这个依赖相对位置的探针。

## 删除条件

只有全部满足后才可删除旧目录：

1. 本次 `delivery.json` 明确 `deletionReady=true`，所有必要验证通过。
2. `Verify -SourceRoot` 仍通过；归档后在旧目录产生的新改动必须另行保全。
3. Codex、编辑器、终端等切换到 Dashboard 或关闭旧工作区。
4. 只删除确切的旧根，不删除 `chiplet_programmgr_validation`、共享缓存或归档。
5. 链接必须按链接本身处理，绝不能沿 junction 递归删除外部目标。

本轮不会自动删除原目录，不会移动正式 Dashboard 数据，不会推送数据 Git、
泄露凭据、切换真实服务或声明所有原需求已经完成。

执行依据：[OpenSpec](../../openspec/changes/retire-legacy-standup-workspace/proposal.md)、
[唯一任务](../../openspec/changes/retire-legacy-standup-workspace/tasks.md)、
[分层用例](../../openspec/changes/retire-legacy-standup-workspace/validation.md)。
