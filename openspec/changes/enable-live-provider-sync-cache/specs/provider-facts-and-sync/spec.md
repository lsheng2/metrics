## ADDED Requirements

### Requirement: Live provider sync materializes facts before dashboard use
Live provider sync SHALL convert external provider search/detail results into durable local facts and approved aggregate artifacts before those facts are used by Grafana, Metrics UI or AI dashboard answers。

#### Scenario: Live sync succeeds for a provider profile
- **WHEN** a provider profile live sync fetches work item data from its external provider
- **THEN** the system SHALL persist provider raw snapshot provenance、normalized facts、source query identity、field-set hash、mapping version、sync cursor/freshness metadata and generated aggregate artifacts before marking the profile data current

#### Scenario: Dashboard renders after live sync
- **WHEN** Grafana renders a provider-backed chart after live sync has succeeded
- **THEN** chart data SHALL be read from matching local aggregate artifacts and SHALL include provider/profile/source/snapshot freshness metadata

#### Scenario: Dashboard renders before live sync is configured
- **WHEN** a selected profile has no configured live backend credential or required provider configuration
- **THEN** chart APIs SHALL return seeded-preview, configuration-required, stale or unavailable state according to available local artifacts, and SHALL NOT infer backend readiness from browser SSO

### Requirement: HSD-ES saved query uses the generic live sync contract
The first live HSD-ES implementation SHALL use the same provider-neutral sync/cache/facts contract as other providers while preserving HSD-ES native provenance inside the adapter boundary。

#### Scenario: HSD-ES NVU saved query is synced
- **WHEN** live sync runs for profile `nvu-ttl-hsdes`
- **THEN** sync SHALL use the configured HSD-ES source query `queryId=15017652869` as the source population, preserve tenant、subject、query id、criteria/hash、field set、permission assumptions and observed result contract, and emit normalized facts compatible with the existing provider chart aggregate contract

#### Scenario: HSD-ES API behavior is uncertain
- **WHEN** implementation needs endpoint shape、auth mode、pagination、field expansion、permission behavior、saved-query execution semantics or response schema details
- **THEN** implementers SHALL consult the authoritative Intel HSD-ES API documentation or project-owner-provided source before coding or changing the provider contract

#### Scenario: HSD-ES browser access exists
- **WHEN** an operator can view or download the saved query data in a browser
- **THEN** the system SHALL treat that as user access evidence only and SHALL still require backend sync credentials/configuration before live synced dashboard data is claimed

### Requirement: Provider sync preserves previous successful artifacts on failure
Provider sync SHALL never replace a previously successful fact snapshot or aggregate artifact with empty or partial data unless the new artifact is explicitly marked complete and authoritative。

#### Scenario: Provider returns partial or failed data
- **WHEN** a provider sync receives timeout, auth failure, permission failure, rate-limit response, schema drift, partial page, malformed payload or projection error
- **THEN** the system SHALL record failed sync status and error category, preserve previous successful artifacts, and expose stale or unavailable status rather than silently publishing incomplete current data

#### Scenario: Mapping drift is detected
- **WHEN** live provider data no longer matches the profile's expected field set, source query hash, tenant/space, subject/item type or mapping version
- **THEN** sync SHALL mark the profile or snapshot drifted/configuration-required and SHALL NOT publish current aggregate artifacts until the profile is reviewed or refreshed
