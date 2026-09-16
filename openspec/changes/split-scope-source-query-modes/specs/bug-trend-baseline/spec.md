## MODIFIED Requirements

### Requirement: Saved Jira scope config owns project-specific semantics
系统 SHALL 使用 saved Jira scope config 作为 bug trend 的 project-specific semantic authority，包括 source mode、final source query、IP label、project label、bug type values、status/resolution lifecycle mappings、severity mappings、field mappings、display fields、timezone、bucket granularity、enabled state 和 config version hash。

#### Scenario: User saves scope semantics
- **WHEN** 用户创建、修改、启用或禁用一个 Jira bug trend scope
- **THEN** 系统 SHALL normalize list fields、validate required fields、persist semantic values、persist the selected source mode and final source query、calculate config version hash，并记录 scope audit event

#### Scenario: Scope semantics change
- **WHEN** source mode、final source query、builder filter selections、status mapping、severity mapping、field mapping、timezone 或 bucket granularity 改变
- **THEN** 系统 SHALL 产生新的 config version hash，使旧 calculation runs 不再作为当前 chart 的 authoritative result

#### Scenario: Metadata context changes without source authority change
- **WHEN** 用户只修改 metadata discovery context that is not part of the selected source mode
- **THEN** 系统 SHALL NOT treat that metadata-only context as an additional runtime filter
- **AND** config version hash SHALL change only when persisted source or semantic fields used by sync/calculation/evidence change

### Requirement: Jira sync materializes durable history before charting
系统 SHALL 通过 explicit Jira scope sync 将 saved scope 的 Jira issues、raw snapshots、status/resolution transitions 和 sync cursor materialize 到本地 durable store。

#### Scenario: Full scope sync runs
- **WHEN** operator 对 saved scope 执行 full sync
- **THEN** 系统 SHALL 使用 persisted final source query 和 scope field mappings 拉取 Jira payload、清理当前 scope state、存储 snapshots/issues/transitions、记录 reliable coverage window，并触发 calculation run
- **AND** metadata discovery context SHALL NOT be appended as an extra runtime filter

#### Scenario: Incremental sync runs
- **WHEN** operator 对已有 cursor 的 saved scope 执行 incremental sync
- **THEN** 系统 SHALL 使用 persisted final source query plus updated overlap condition、同步当前匹配 issues、检查已知 issue 的 out-of-scope changes，并拒绝 config hash 不匹配或 coverage expansion 的 unsafe incremental sync
