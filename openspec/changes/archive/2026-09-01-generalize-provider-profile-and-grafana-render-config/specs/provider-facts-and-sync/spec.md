## ADDED Requirements

### Requirement: Providers emit canonical facts before chart aggregation
Provider sync SHALL normalize Jira、HSD-ES and future provider payloads into canonical provider facts before chart recipes calculate aggregates.

#### Scenario: Jira and HSD-ES feed the same chart
- **WHEN** `open_bug_trend` or another approved quality chart is requested for a Jira profile and an HSD-ES profile
- **THEN** each provider adapter SHALL produce provider-specific raw provenance plus canonical fields sufficient for the same chart recipe to calculate provider-neutral aggregate rows

#### Scenario: Chart calculator receives provider-native payload
- **WHEN** aggregate calculation would require direct Jira issue JSON or HSD-ES article field shape
- **THEN** system SHALL first add or fix profile field bindings and canonical fact projection rather than embedding provider-native branching in the chart calculator

### Requirement: Aggregate artifact identity is range-mode neutral
Provider aggregate artifacts SHALL identify requested ranges with provider-neutral range mode、range start/end、range grain and display labels, rather than assuming every cache key is WW-only.

#### Scenario: WW range artifact is stored
- **WHEN** `range_mode=ww`
- **THEN** artifact identity SHALL include range mode, normalized calendar start/end resolved from `begin_ww`/`end_ww`, WW labels and chart version

#### Scenario: Date range artifact is stored
- **WHEN** `range_mode=date`
- **THEN** artifact identity SHALL include range mode, normalized date start/end, date display labels and chart version, and SHALL NOT reuse a WW artifact solely because old URL WW variables match

### Requirement: Aggregate generation is profile-dispatched
Sync and aggregate generation SHALL dispatch by selected profile and chart recipe compatibility, not by hardcoded provider/profile ids in consumer code.

#### Scenario: Generic profile sync command is used
- **WHEN** operator runs a provider/profile sync for any configured profile
- **THEN** system SHALL resolve adapter、source query、field set、mapping version、range mode and chart materialization plan from registry

#### Scenario: Latest artifact is requested
- **WHEN** Grafana or AI requests chart data for a selected profile
- **THEN** aggregate service SHALL find matching local artifacts by provider/profile/chart/range identity and SHALL return freshness/provenance state without invoking the external provider in the render path

### Requirement: Provider-specific artifacts remain auditable
Provider facts and aggregate artifacts SHALL preserve source query、field-set、mapping-version、snapshot、calculation-run and freshness provenance for both dashboard and AI use.

#### Scenario: AI explains a chart
- **WHEN** AI reads an aggregate artifact or evidence result
- **THEN** response payload SHALL include enough provenance for AI to state provider id、profile id、source population、fact snapshot、mapping version、calculation run and freshness status

#### Scenario: Profile mapping changes
- **WHEN** field bindings、value normalization、source query or chart binding changes for a profile
- **THEN** previously materialized facts and aggregates SHALL be treated as stale/non-authoritative unless their identity matches the current profile contract
