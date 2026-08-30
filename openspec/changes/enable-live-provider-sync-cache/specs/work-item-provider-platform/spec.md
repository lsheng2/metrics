## ADDED Requirements

### Requirement: Shared provider cache and materialization core
Provider sync cache and artifact materialization SHALL be modeled as shared provider platform behavior, while provider-specific modules own only external API mechanics and raw-to-normalized projection。

#### Scenario: A provider adapter participates in cached sync
- **WHEN** Jira、HSD-ES、GitHub、Azure DevOps or a future provider is configured for live sync
- **THEN** the adapter SHALL expose provider-specific fetch/projection capability through provider-neutral sync inputs and outputs, and SHALL NOT define a separate dashboard-specific cache model

#### Scenario: Product features consume provider artifacts
- **WHEN** Grafana, Metrics UI, AI chat, reporting or correlation consumes provider data
- **THEN** consumers SHALL depend on provider-neutral facts, snapshots, aggregate artifacts and freshness metadata rather than provider-specific cache tables, raw API payloads or live provider calls

#### Scenario: Provider capability manifest includes sync/cache status
- **WHEN** UI or AI reads a provider capability manifest
- **THEN** the manifest SHALL distinguish read/search support, live sync readiness, cache/materialization readiness, write/action support and unsupported capabilities so consumers do not infer production data readiness from generic connectivity alone

### Requirement: Provider-specific modules keep external quirks local
Provider-specific sync modules SHALL encapsulate auth, paging, rate limits, retries, endpoint differences, native query execution and secret handling, while shared cache rules remain provider/profile agnostic。

#### Scenario: HSD-ES and Jira use different source query ownership
- **WHEN** HSD-ES uses provider-owned saved query references and Jira uses Metrics-managed JQL
- **THEN** both SHALL map to the same source population provenance contract, cache identity shape and freshness behavior, while preserving native query details inside provider-specific provenance

#### Scenario: A new provider is added
- **WHEN** a future provider adds live sync support
- **THEN** it SHALL reuse the shared cache identity, freshness states, failure fallback and test expectations instead of introducing a provider-only dashboard rendering path
