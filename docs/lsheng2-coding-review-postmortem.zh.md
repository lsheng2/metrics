# Lsheng2 Coding Review 收敛性复盘与 Skill 升级方案

日期：2026-08-20

## 背景

本次复盘来自 Bug Trend P0d 到 P3 长跑实现后的 `lsheng2-coding-review` exact-pass review。该 review 要求最后取得 2 个连续 clean pass。最终 gate 完成，但过程经历了 9 次 reviewer pass，其中 7 次 FAIL、2 次 PASS，累计发现 `P1=5`、`P2=6`、`P3=1`。

这些 finding 不是随机小问题，而是集中暴露了同一类工程失败：新增 authority field 或 governance contract 之后，只实现了部分 producer/consumer 路径，其他入口、导出、校验器、Grafana artifact、parity checker、audit event 或 selected-state bypass 在后续 review 中才逐步浮现。

本文件记录这次 learning，并定义两个 skill 的升级方向：

1. `lsheng2-coding-review`：增强 review 收敛性，避免同类 finding 逐轮串行出现。
2. `dag-based-planning`：增强 DAG plan 的 contract coverage，使 absence 在 implementation 前可见。

## 结论

这次难收敛不是单一 skill 或单一 DAG 的问题。

`lsheng2-coding-review` 的 gate/script 层是有效的。它成功阻止了假 PASS、重复 transcript、未闭环 finding、未 reset clean-pass counter 等流程问题。最终 clean pass 是被 gate 机械证明出来的，不是聊天里的口头承诺。

但该 skill 当前偏向记录和约束 review event，不足以强制 reviewer 在第一轮就建立完整的 contract propagation map。因此 reviewer 每一轮都会从一个新边界继续追，导致 finding 以串行方式浮现。

原 DAG plan 的 architecture 方向也基本正确。它已经声明了 `JiraScopeConfig`、`BugTrendPageQueryState`、`EvidenceContract`、Chart Catalog、Grafana validator、AI governance 等 authority。但不少 contract 的 consumers 和 disconfirming checks 仍是抽象描述，没有展开成 per-surface propagation matrix 和 negative-case matrix。

所以根因不是“review 太严格”，也不是“DAG 完全错”。真正的问题是：plan 和 review flow 之间缺少一个前置收敛层，用来枚举每个新增 authority 的所有 producer、consumer、bypass path 和 executable negative checks。

## 主要失效模式

### 1. Authority Field 只传播了一部分

典型例子是 `chart_id` 和 `chart_spec.series`。

它们一旦成为 chart/evidence/export 的 runtime authority，就必须同时约束：

- chart-data API；
- evidence API；
- evidence export；
- chart selector；
- Grafana data link；
- Grafana approved-surface validator；
- Grafana parity checker；
- audit event；
- selected bucket / selected series path。

实际 review 中，这些 consumer 不是一次性被发现，而是按轮次逐渐暴露：先发现 evidence/export 没吃 chart spec，再发现 Grafana allowlist、parity checker、Grafana evidence link、selected-series bypass 等后续缺口。

### 2. Finding 被当作 Instance 修，而不是 Failure Class 修

典型例子：

- 修了 malformed scope config POST id 后，下一轮发现 malformed scope config GET id。
- 修了 malformed scope id 后，后续又发现 malformed `begin/end`。
- 修了 range evidence 的 `chart_spec.series` 后，后续又发现 selected `series` 可以绕过。
- 修了 chart publish audit 后，后续又发现 scope config save/activate audit 缺失。

这说明 fix-loop 中缺少强制的 class expansion。每个 finding 在动手修之前，都应该先问：这是单个 bug，还是一类入口、状态或 consumer 的代表样本？

### 3. DAG Contract 有名字，但没有足够机械的 Consumer Matrix

原 DAG 已经有 Contract Registry，例如：

- `INV-P1A-PAGEQUERY-STATE`
- `INV-P1A-CHART-SELECTION-STATE`
- `INV-P2A-EVIDENCE-CONTRACT`
- `INV-P2B-CSTOCK-PARITY`
- `INV-P2B-CSTOCK-LINK-EVIDENCE`
- `INV-P3-AI-DRAFT-VALIDATION`
- `INV-P3-PUBLISH-AUDIT`

这些 contract 名称和 authority boundary 是有价值的，但它们没有强制列出所有实际 consumer。比如 `active_chart_id` 不应只声明属于 `BugTrendPageQueryState`，还应明确列出它必须被哪些 API、template、script、artifact、export 和 audit path 消费。

### 4. Closure Gate 偏命令列表，不偏 Coverage Proof

`pytest`、`manage.py check`、Grafana validator、file-size、whitespace 都是必要的，但它们只能证明已有检查通过。它们不能证明没有遗漏 consumer。

缺失的 consumer 是 absence。结构化 gate 无法看见 absence，除非 plan 先声明完整 universe，再让 checker 或 reviewer 去比对 implementation 是否覆盖 universe。

## 可共享 Learning

这些 learning 不限于 Metrics 或 Bug Trend。它们适用于任何有跨层 contract、public API、schema、configuration、artifact、audit、export、cache、background job 或 UI state 的项目。

### Learning 1：每个新增 Authority 都需要 Propagation Matrix

通用模板：

| Field | Meaning |
| --- | --- |
| Authority field | 新增或改变语义的字段、状态、配置、权限、selector、version、contract id。 |
| Producer | 谁创建或改变该值。 |
| Consumers | 所有必须读取、保留、验证或拒绝该值的路径。 |
| Negative checks | 证明 consumer 不能绕过 authority 的测试或检查。 |
| Non-goals | 明确不消费该 authority 的路径及原因。 |

一个 authority field 没有完整 propagation matrix 时，不应进入 implementation closure。

### Learning 2：Exact Review 前需要 Preflight Review Planning Pass

该 pass 不计入 exact clean pass。它的目的不是找代码 bug，而是让 reviewer 先建立 review map。

输出必须包括：

- changed authority inventory；
- producer/consumer matrix；
- public entry-point list；
- artifact/script/docs consumer list；
- likely bypass matrix；
- focused review itinerary。

后续 exact-pass review 应按这个 itinerary 执行，而不是边 review 边发现地图。

### Learning 3：每个 Finding 修复前必须做 Class Expansion

每个 finding 进入 fix-loop 前，主 agent 必须先写出：

- reported instance；
- suspected failure class；
- sibling entry points；
- sibling consumers；
- required negative checks；
- rejected siblings and rejection reason。

只有完成 class expansion 后，才允许进入代码修复。否则 fix 很容易只关闭 reviewer 报告的那个 instance。

## `lsheng2-coding-review` Skill 升级方案

### 目标

保持现有 exact-pass gate 的强审计能力，同时提升 review 的前置覆盖能力和后续收敛能力。

升级后，该 skill 不只回答“这个 PASS 是否真实”，还要帮助回答“这一轮 review 是否系统性覆盖了本次 change 的 contract universe”。

### 升级 1：增加 Preflight Review Planning Pass

在 gate `init` 之前、解析出 `review_target`、`top_goal`、`issue_fixed` 和 project config 之后，新增一个不计数的 planning pass。planning pass 使用即将写入 gate 的同一组 scope 字段，产出的 artifact 再作为 gate `init` 输入。这样 gate 可以在创建 state 时校验 planning artifact，而不会依赖 init 之后才出现的回填数据。

该 pass 使用 configured reviewer subagent，但 transcript 不作为 `PASS`/`FAIL` 记录。它输出 `review_plan_receipt`，建议存为 gate state 旁边的 JSON 或 Markdown artifact；升级后的 `exact_pass_gate.py init` 应保存该 artifact 的路径、摘要和 digest。

必需输出：

```text
REVIEW_PLANNING_PASS: yes
REVIEW_TARGET: <same as gate state>
TOP_GOAL: <same as gate state>
ISSUE_FIXED: <same as gate state>

AUTHORITY: <id>|<field/state/contract>|<owner>|<summary>
PRODUCER: <authority-id>|<path/function/artifact>|<summary>
CONSUMER: <authority-id>|<path/function/artifact>|<required behavior>
NEGATIVE_CHECK: <authority-id>|<check target>|<bypass prevented>
NON_GOAL: <authority-id>|<path/surface>|<reason>

REVIEW_ITINERARY:
- <ordered review slice>
```

该 planning pass 失败或缺失时，不允许开始 counted exact-pass review。用户可以选择把本次 review 降级为普通人工/顾问式 review，但该 run 不能进入 exact-pass gate，也不能声明 clean-pass closure。

### 升级 2：Reviewer Prompt 必须使用 Planning Artifact

每一轮 counted review prompt 必须包含 planning pass 的 authority/consumer matrix，并要求 reviewer：

1. 检查每个 declared consumer 是否真的消费 authority。
2. 检查是否存在 implementation 中新增但 plan 未声明的 consumer。
3. 对每个 changed authority 至少尝试一个 bypass 思路。
4. 把每个 finding 同时归到 `authority_id` 和 `failure_class`，而不是只归到文件路径。

升级后的 reviewer transcript 和 ledgers 需要把这两个值作为机器字段，而不是藏在 summary 中。建议把 finding schema 升级为：

```text
FINDING: <id>|<severity>|<authority_id>|<failure_class>|<reference>|<summary>
```

对应的 findings ledger、closure ledger 和 gate state event 也必须保存 `authority_id` 与 `failure_class`。`review_process_report.py` 的 `findings_by_authority` 和 `repeat_failure_class_count` 只能从这些机器字段计算，不能从 summary 文本中解析。

这样 review 可以从“自由探索”变为“按 contract universe 系统扫描”。

### 升级 3：FAIL 后强制 Finding Class Expansion

现有流程是：record FAIL → fix findings → closure ledger → next review。

升级后改为：record FAIL → class expansion → fix expanded class → closure ledger → next review。`record --verdict FAIL` 只能校验 reviewer 当轮给出的 findings ledger；class expansion 在 FAIL 之后生成，并由后续 closure 记录校验。

新增 `finding_class_expansion` artifact，格式建议：

```json
[
  {
    "finding_id": "BT-P1-001",
    "authority_id": "AUTH-CHART-SPEC-SERIES",
    "reported_instance": "selected series bypasses chart_spec.series",
    "failure_class": "chart_spec series authority is not applied before all evidence/export selection filters",
    "sibling_entry_points": [
      "range evidence",
      "bucket evidence",
      "bucket-series evidence",
      "CSV export",
      "Grafana evidence link"
    ],
    "negative_checks": [
      "restricted chart plus disallowed selected series returns no rows",
      "restricted chart export excludes disallowed series"
    ],
    "rejected_siblings": []
  }
]
```

Closure ledger 的 summary 应引用 `authority_id` 和 class expansion，而不是只说 reported instance fixed。升级后的 gate 应在下一次 `record` 时要求：凡是 state 中存在 pending findings，必须同时提供 `--closure-ledger` 和覆盖这些 pending finding id 的 `--class-expansion-artifact`。也可以新增独立的 `attach-class-expansion` 子命令，但它必须写入同一个 gate state，不能成为 gate 外的并行权威。

### 升级 4：Process Report 增加收敛指标

`review_process_report.py` 可增加以下统计：

| Metric | Meaning |
| --- | --- |
| `authority_count` | planning pass 声明的 authority 数量。 |
| `consumer_count` | planning pass 声明的 consumer 数量。 |
| `findings_by_authority` | finding 是否集中在少数 authority。 |
| `repeat_failure_class_count` | 同一 failure class 是否跨轮重复出现。 |
| `late_consumer_findings` | 第 N 轮后才发现的 consumer-propagation 缺口数量。 |
| `class_expansion_coverage` | 每个 FAIL finding 是否有 class expansion artifact。 |

这些指标可以让 review 过程自己暴露是否仍在串行发现同类问题。

### 升级 5：配置保持项目化

不要把 Metrics 专属词汇写进 global skill core。项目相关内容应放在 project profile 或 project-local config 中，例如：

- reviewer agent；
- preferred model；
- authority categories；
- consumer categories；
- validation commands；
- severity threshold；
- project-specific examples。

通用 skill core 只保留机制和模板。

## `dag-based-planning` Skill 升级方案

### 目标

让 DAG plan 不只表达 dependency order，还表达 contract universe。计划阶段必须让 absence 可见，避免 implementation 和 review 阶段才发现未声明 consumer。

### 升级 1：Contract Registry 增加 Propagation Matrix

现有 Contract Registry 字段是 owner、consumers、disconfirming check。升级后，每个 contract 必须增加或链接一张 propagation matrix。

建议模板：

```markdown
### Contract Propagation Matrix

| contract_id | authority_field | producer_paths | consumer_paths | required_behavior | negative_check | non_goal_paths |
| --- | --- | --- | --- | --- | --- | --- |
| INV-* |  |  |  |  |  |  |
```

规则：

1. `consumer_paths` 不允许只写大类，例如“UI/API”。必须写到 route、facade、API method、script、artifact、template 或 test surface。
2. 每个 `consumer_paths` 必须有 `required_behavior`。
3. 每个 authority 至少有一个 negative check；高风险 authority 每个 consumer 都要有 negative check。
4. 没有 consumer 的 authority 要么是 dead design，要么必须写 `non_goal_paths` 和 reason。

高风险判定由 DAG plan owner 在 Contract Registry 中声明，并由 `PLAN.R` reviewer 复核。建议增加 `risk_level` 字段，取值为 `high`、`normal` 或 `low`：

| risk_level | 判定规则 | negative check 要求 |
| --- | --- | --- |
| `high` | 影响权限、安全、审计、导出、外部 artifact、跨模块 public API、数据删除/覆盖、用户可见 routing 或 runtime authority。 | 每个 consumer 都必须有 negative check 或明确 non-goal reason。 |
| `normal` | 影响普通业务行为或内部模块协作，但不直接触碰上述高风险面。 | 每个 authority 至少一个 negative check；关键 consumer 需要 check。 |
| `low` | 纯文案、局部展示、非行为性整理。 | 可用 reviewer-accepted rationale 代替 executable check。 |

如果 plan owner 未声明 `risk_level`，默认按 `high` 处理，不能由 implementation agent 在 closure 时降级。

### 升级 2：新增 Consumer Universe Checklist

每个 DAG plan 应根据项目类型选择 consumer categories。通用 checklist：

- public API；
- internal service/facade；
- UI route/template/component；
- export/report；
- audit/log/event；
- validation script；
- migration/schema；
- background job/scheduler；
- cache/index/search；
- external artifact；
- CLI/admin command；
- docs/operator workflow；
- test double/fake/fixture。

计划阶段必须逐项判断：applies、not applies、deferred-with-trigger。不能静默省略。

### 升级 3：Plan Preflight 增加 Absence Checks

现有 preflight 检查 Contract Registry、node table、Mermaid graph、ledger、validation commands、owner paths 是否一致。

应增加：

1. 每个 changed authority 是否有 propagation matrix。
2. 每个 matrix consumer 是否出现在某个 DAG node 的 `owner_paths`。
3. 每个 matrix negative check 是否出现在 validation plan。
4. 每个 audit/governance action 是否枚举 event type。
5. 每个 external artifact/script 是否有 validation owner。

如果某个 consumer 不在任何 owner path 内，plan preflight 应失败。

### 升级 4：DAG Node 增加 Contract Coverage 字段

Node template 建议新增：

```markdown
| contract_coverage | Which authority fields and consumers this node produces or consumes. |
| negative_cases | Bypass or malformed paths this node must disconfirm. |
| sibling_entry_points | Similar entry points explicitly included or rejected. |
```

这能避免 node 只写“实现 X API”，却不说明 X API 是哪个 authority 的 producer 还是 consumer。

### 升级 5：Closure Gate 从 Test List 升级为 Coverage Closure

每个 DAG close 节点必须回答：

1. 哪些 authority fields 被新增或改变？
2. 它们的 producer 是否全部存在？
3. 它们的 consumers 是否全部存在？
4. 每个 consumer 是否有 check 或明确 non-goal？
5. 有没有 implementation 中出现但 plan 未声明的新 consumer？
6. 有没有 tests 断言了一个不存在的 producer？

这比单纯列 validation commands 更接近 architecture closure。

## 推荐执行顺序

### Phase 1：文档和模板先行

先更新两个 skill 的文档和模板，不改 gate script。此阶段只发布为 draft workflow，不能把 planning artifact 或 class expansion 当作 exact-pass gate 的强制完成标准：

1. 在 `dag-based-planning` 中加入 propagation matrix、consumer universe checklist、coverage closure 字段。
2. 在 `lsheng2-coding-review` 中加入 preflight planning pass 和 finding class expansion 的 workflow 要求。
3. 增加 examples，使用通用术语，不绑定 Metrics domain。

### Phase 2：Review Prompt 增强

修改 `lsheng2-coding-review` 的 subagent prompt 生成规则：

1. counted review 前必须先生成 planning artifact。
2. counted review 必须引用 planning artifact。
3. finding 必须同时带 `authority_id` 和 `failure_class`。
4. prompt 级 enforcement 在此阶段仍是 draft enforcement；如果 gate script 尚未校验 artifact，最终报告必须把它标为 residual process risk，不能声明 upgraded exact-pass workflow 已完成。

### Phase 3：Gate Script 强制增强

在流程稳定后，让 script 强制关键 artifact。只有完成本阶段后，planning pass、class expansion 和 coverage closure 才能成为 `lsheng2-coding-review` 的 exact-pass release 标准：

1. `exact_pass_gate.py init` 必须接受并校验 `--review-plan-artifact`，或者在 gate state 中记录明确的 `mode=legacy`。`legacy` mode 不允许声明 upgraded exact-pass closure。
2. Reviewer transcript、findings ledger、closure ledger 和 gate state event 必须支持机器字段 `authority_id` 与 `failure_class`。
3. `record --verdict FAIL` 继续只记录 reviewer findings；当 state 存在 pending findings 时，下一次 `record` 必须同时接受并校验 `--class-expansion-artifact` 和 `--closure-ledger`。可选实现是新增 `attach-class-expansion` 子命令，但该子命令必须更新同一 gate state，并由下一次 `record` 验证所有 pending finding 已覆盖。
4. report 可统计 late consumer findings 和 repeat failure classes。

这一步不应过早做。先让模板和 prompt 被实际使用几轮，避免把不成熟的流程硬编码进 gate；但在脚本强制前，新 artifact 只能作为 advisory draft，不能成为另一套并行 completion authority。

## 适用范围

这些升级适合共享给其他项目，但要保持两层结构：

| Layer | 内容 | 是否通用 |
| --- | --- | --- |
| Skill core | exact-pass gate、preflight planning pass、propagation matrix、class expansion、coverage closure | 通用 |
| Project profile | domain authorities、consumer categories、validation commands、reviewer agent/model、examples | 项目专属 |

不能共享原样硬编码的内容包括：

- `BugTrendPageQueryState`；
- `JiraScopeConfig`；
- `EvidenceContract`；
- Grafana-specific artifact names；
- Metrics-specific test commands；
- P0d/P1/P2/P3 的业务分段；
- 当前 reviewer agent 和 model 名称。

可以共享的内容是方法：authority propagation、review planning、finding class expansion、coverage closure。

## 新的完成定义

在升级后的 gate script 支持 planning artifact 和 class expansion artifact 后，一个 DAG-backed implementation 进入 exact-pass review 前，必须满足：

1. 每个 changed authority 有 propagation matrix。
2. 每个 matrix consumer 被某个 DAG node 覆盖。
3. 每个 high-risk consumer 有 negative check，且 `risk_level` 由 plan owner 声明、`PLAN.R` 复核。
4. Review planning pass 已生成 reviewer itinerary。
5. 每个 FAIL finding 在修复前完成 class expansion。
6. Closure claim 引用 coverage closure，而不只引用 green tests。

在 gate script 尚未支持这些 artifact 前，上述规则可以作为 draft checklist 使用，但不能作为 exact-pass clean closure 的独立权威。此时 final report 必须明确标注 legacy gate mode 和未被脚本强制的 residual process risk。

这样 exact-pass review 的目标就从“靠 reviewer 逐轮发现遗漏”变成“让 reviewer 验证一个已经声明完整的 contract universe”。