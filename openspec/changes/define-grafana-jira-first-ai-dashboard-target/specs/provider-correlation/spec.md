## ADDED Requirements

### Requirement: Jira and HSD-ES parity views remain parallel
Jira 与 HSD-ES SHALL 作为平行 provider 被 dashboard 和 AI 消费；correlation SHALL 关联事实，不得合并或覆盖任一 provider 的 native truth。

#### Scenario: Dashboard shows correlated Jira and HSD-ES quality facts
- **WHEN** Grafana dashboard 或 evidence view 同时展示 Jira 与 HSD-ES 数据
- **THEN** UI SHALL 标识每个 series、KPI、row 或 evidence item 的 provider 来源，并 SHALL 使用 correlation artifact 解释跨 provider 关系

#### Scenario: Provider states disagree
- **WHEN** Jira issue status 与 correlated HSD-ES article state 不一致
- **THEN** dashboard 和 AI SHALL 展示两边 native state，并 MAY 解释差异；系统 SHALL NOT 以其中一个 provider 的状态覆盖另一个

### Requirement: AI uses correlation evidence explicitly
AI SHALL 在解释 Jira-HSD-ES 关系时引用 correlation evidence，而不是凭字段相似性直接断言两个 work items 等价。

#### Scenario: AI proposes a Jira-HSD-ES relationship
- **WHEN** AI 根据 external id、link、title fingerprint、component/release overlap、owner 或时间窗口提出 correlation candidate
- **THEN** AI SHALL 输出 candidate relationship、confidence、matched fields、matched values 和 source provenance，并 SHALL 等待用户或 approved policy 确认

#### Scenario: AI answers cross-provider risk question
- **WHEN** 用户询问同一 milestone 或 release target 下 Jira 与 HSD-ES 风险是否相关
- **THEN** AI SHALL 基于 confirmed correlation 和 provider facts 回答，并 SHALL 区分 confirmed、candidate、rejected 和 stale relationship

### Requirement: Correlation uses canonical facts plus native evidence
Correlation SHALL compare Jira and HSD-ES through canonical facts and explicit native evidence, while keeping per-provider native fields and project fields separate.

#### Scenario: Correlation candidate is generated
- **WHEN** system generates a Jira-HSD-ES candidate
- **THEN** candidate evidence SHALL identify which matches came from canonical fields, project-specific mapped fields, provider-native fields, explicit links or external ids

#### Scenario: Provider seed query contributed evidence
- **WHEN** an HSD-ES saved query seed or Jira saved filter constrained the source population for a candidate
- **THEN** the correlation artifact SHALL record that query provenance separately from the matched item fields

#### Scenario: Native fields conflict with normalized fields
- **WHEN** a provider-native field suggests a different state, severity, milestone or component than the normalized canonical field
- **THEN** correlation output SHALL preserve both values and SHALL NOT silently prefer the normalized value without recording the mapping reason
