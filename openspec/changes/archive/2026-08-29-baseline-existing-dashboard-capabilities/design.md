## Context

See `proposal.md` - Why. 当前仓库是一个已经实现了多块能力的 Django modular monolith：`ui_web` 提供 server-rendered dashboard 和 HTMX partials，`tasks`/`forecast`/`velocity`/`pull_requests` 提供已有 engineering metrics，`bug_metrics`/`jira_sync`/`jira_history` 提供 Jira Bug Trend durable analytics。OpenSpec 是中途引入的，因此这次 change 不是新增产品行为，而是把现有代码事实转成可 archive 的 baseline specs。

当前已有主规格偏向未来 provider platform 目标：`work-item-provider-platform`、`provider-facts-and-sync`、`provider-scope-wizard`、`provider-ai-actions`、`provider-correlation`。本 baseline change 需要补上当前 Django dashboard 和 Jira Bug Trend 的实际状态，避免后续 HSD-ES、Grafana-first 和 AI work 从模糊半成品出发。

## Goals / Non-Goals

**Goals:**

- 用代码事实定义当前 baseline，而不是照搬旧设计文档中的未来目标。
- 将当前页面、API、durable facts、calculation artifacts、evidence、audit、Grafana contract 和 AI chart draft governance 纳入 OpenSpec。
- 为后续文档迁移建立准则：旧 `docs/` 可以迁入 OpenSpec，但必须先判定是 current baseline、future target、validation evidence、runbook 还是历史记录。
- 保留已有 provider-neutral OpenSpec 主规格，并只在 `provider-facts-and-sync` 中补充当前 Jira facts baseline。

**Non-Goals:**

- 不改生产代码、不新增 HSD-ES adapter、不切换最终 UI 到 Grafana。
- 不声明 execution、automation、shift-left、escaped bug charts 已实现。
- 不把所有旧 docs 一次性移动；迁移在 apply 阶段按任务执行，并保留可追溯路径。

## Decisions

### Decision: Baseline specs split by current product surface

当前 baseline 拆成三个新 capability：

- `dashboard-ui-baseline`：用户可见 Django 页面、partial、facade federation 和 frontend stack。
- `engineering-metrics-baseline`：已有 task board、forecast、velocity、pull request review dashboard。
- `bug-trend-baseline`：已有 Jira Bug Trend durable analytics、evidence、audit、chart catalog、Grafana data surface 和 AI chart draft governance。

Rationale: 这三个能力对应当前代码的独立产品 surface，也对应后续迁移风险：UI runtime、scrum engineering metrics、Jira/Grafana bug trend analytics。把它们拆开后，未来 Grafana-first change 可以选择替换 UI surface，但仍保留 engineering metrics 和 bug trend facts baseline。

Alternatives considered:

- 把所有 baseline 放进一个 `existing-dashboard-capabilities` spec：简单但过大，后续 archive 后难以精确引用。
- 把每个页面单独建 capability：过细，会把当前 UI route 结构冻结得太硬，不利于 Grafana-first 迁移。

### Decision: Existing provider specs stay provider-neutral

`provider-facts-and-sync` 只新增当前 Jira facts baseline，不把 Jira implementation 变成 provider platform 的唯一形状。

Rationale: 未来 HSD-ES 和 Jira 需要并行接入，现有 Jira sync/history 是事实来源和经验输入，但不能让 provider-neutral core 继承 Jira-only 命名和假设。

Alternatives considered:

- 直接修改 `work-item-provider-platform`：这会把当前 Jira implementation 和未来 platform target 混合。
- 不触碰 existing provider specs：会导致 provider facts 主规格看不到当前 Jira durable baseline。

### Decision: Code is source of truth, docs are migration inputs

Baseline 判定顺序为：当前代码和测试 > OpenSpec 主规格 > 当前仍准确的 `docs/` > 历史或 backlog 文档。旧 docs 中与代码不一致的内容不能直接进入 baseline requirement，只能进入 migration task、risk 或 future-target spec。

Rationale: 用户希望后续项目走 OpenSpec 标准流程。为了从半成品回归标准流程，必须先把现有行为锁定，再把旧 docs 分类迁移。

Alternatives considered:

- 直接移动全部 `docs/` 到 OpenSpec：速度快，但会把过期计划、已完成实现和未来目标混在同一层。
- 保留 `docs/` 完全不动：短期安全，但 OpenSpec 仍缺少现有项目知识，后续 agent 容易重复发现。

### Decision: Docs migration happens after validation

本 change 的 apply 阶段先验证并同步 baseline specs，再迁移旧 docs，最后 archive change：current baseline 内容合并进主 spec，future target 内容留在对应 active/future change，validation/runbook 进入 `openspec/docs/` 下的 supporting docs 或保留带指针的兼容入口。

Rationale: 先 archive baseline 能得到稳定主规格路径，再迁移旧文档会更清楚；同时避免大规模文件移动影响当前未完成工作。

Alternatives considered:

- 在 propose 阶段直接移动 docs：违反 propose 阶段只生成 planning artifacts 的边界。
- 等所有未来功能完成后再迁移：会让 OpenSpec 在接下来的实施中继续缺失 baseline。

## Risks / Trade-offs

- [Risk] Baseline spec 过度描述当前实现细节，未来重构变困难。→ Mitigation: specs 只写用户/consumer 可观察行为；文件、类、命令细节放在 design/tasks。
- [Risk] 旧 docs 有未来目标，被误 archive 成当前事实。→ Mitigation: apply 阶段按 current/future/validation/historical 分类迁移，并以代码和测试为最高优先级。
- [Risk] `provider-facts-and-sync` 新增 Jira baseline 后被解读为 provider-neutral 目标已完成。→ Mitigation: requirement 明确当前 Jira facts baseline 是未来 provider-neutral extraction 的输入，而不是最终 multi-provider contract。
- [Risk] 大规模 docs move 影响链接。→ Mitigation: 迁移时保留 redirect/index 或在旧位置留下指针；每次移动后运行链接/grep 检查。
- [Risk] Baseline specs 与 active future-target change 重叠。→ Mitigation: 本 change 不写 HSD-ES implementation 和 final Grafana-first behavior，只写 current baseline 与 migration rules。

## Migration Plan

1. Validate this change with `openspec validate "baseline-existing-dashboard-capabilities" --strict`。
2. Review delta specs against current code/tests and old docs。
3. Archive this baseline change into `openspec/specs/`，使当前项目能力成为 OpenSpec 主规格。
4. Classify existing `docs/`:
   - Current baseline: 合并进对应 OpenSpec main spec 或 supporting note。
   - Future target: 迁入或链接到对应 active change，例如 Grafana-first/Jira-HSD-ES target。
   - Validation/runbook: 保留为 operational evidence/runbook，或移动到 OpenSpec supporting docs 并更新链接。
   - Historical/postmortem: 保留 archive 指针，不作为 normative spec。
5. Update `docs/README.md` 或等价 index，让用户和 agents 知道 OpenSpec 是 normative source，旧 docs 只作为 historical/supporting material。
6. Run `openspec validate --strict` and focused link/path checks after each migration batch。

Rollback: 如果迁移旧 docs 后发现链接或归属错误，恢复该批 docs move，保留已经 archive 的 baseline specs；baseline specs 本身不依赖旧 docs 的物理路径。
