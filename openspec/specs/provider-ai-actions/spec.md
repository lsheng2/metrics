## Purpose
Provider AI Actions 定义 AI chat、automation 和 batch workflows 如何安全地提出、预览、审批、执行和审计 work item provider 写操作。它的核心规则是 AI 只能生成 action plan，不能直接写 Jira、HSD-ES、GitHub 或其他 provider。

## Requirements

### Requirement: AI proposes action plans only
AI SHALL NOT directly call provider write adapters. AI MAY generate `ProviderActionPlan` objects that describe intended work item updates, before/after values, reason、risk、provider、work item id 和 required confirmation。

#### Scenario: AI suggests a Jira comment
- **WHEN** 用户要求 AI 根据测试失败给 Jira ticket 写 comment
- **THEN** AI SHALL create a proposed action plan with comment body preview，而不是直接调用 Jira comment API

#### Scenario: AI suggests an HSD-ES update
- **WHEN** 用户要求 AI 修改 HSD-ES record、添加 comment、更新 owner、priority/severity、state 或 release-like field
- **THEN** AI SHALL create a proposed action plan with before/after preview，并 SHALL NOT call HSD-ES `/rest/article`、bulk update、comment insert/update、relation add 或 clone APIs directly

#### Scenario: Unsupported write action
- **WHEN** provider manifest 不支持某种 action type
- **THEN** AI SHALL NOT generate executable plan for that action，并 SHALL explain unsupported reason

### Requirement: Human approval before provider write
每个 provider write SHALL 经过 preview 和 explicit approval，除非未来 policy 明确允许某类低风险 automation 走预批准队列。

#### Scenario: User approves a field update
- **WHEN** 用户在 UI 中批准 `ProviderActionPlan`
- **THEN** executor SHALL route the approved plan to the matching provider adapter and execute only the approved before/after diff

#### Scenario: User rejects a proposed action
- **WHEN** 用户拒绝 action plan
- **THEN** 系统 SHALL NOT call provider write API and SHALL record rejected or discarded state when an audit record exists

### Requirement: Audit event for every write attempt
系统 SHALL 为每次 provider write attempt 记录 audit event，包括 provider、work item id、action type、before、after、reason、risk、approver、executor、execution result、timestamp 和 error details if any。

#### Scenario: Provider write fails
- **WHEN** approved action execution fails because of permission、stale state、validation error 或 provider outage
- **THEN** audit event SHALL capture failure result and normalized error without leaking secrets

### Requirement: Read and write contracts remain separate
Provider read/search/facts APIs SHALL remain separate from write/action APIs so dashboard rendering、AI answer generation 和 metadata discovery cannot accidentally mutate external systems。

#### Scenario: AI chat read-only mode
- **WHEN** Phase 2 AI Chat is configured as read-only
- **THEN** workflow SHALL only call provider facts/search capabilities and SHALL NOT expose write executor tools

#### Scenario: HSD-ES write API is not yet approved
- **WHEN** HSD-ES write API contract、tenant/subject required fields、permission model、`send_mail` behavior 或 approval policy has not been reviewed
- **THEN** HSD-ES provider SHALL expose read-only capabilities only, and write action executor SHALL remain unavailable for HSD-ES

### Requirement: Batch and automation actions use the same governance
Scheduled jobs、batch proposals 和 automation agents SHALL use the same `ProviderActionPlan`、preview、approval、policy check 和 audit model as interactive AI chat。

#### Scenario: Daily stale ticket automation
- **WHEN** automation identifies stale P1/P2 tickets
- **THEN** it MAY create proposed update queue entries, but SHALL NOT modify provider state without the configured approval policy
