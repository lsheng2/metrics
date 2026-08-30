## Purpose

Provider Sync Cache 定义所有 work item provider 共享的 live sync、durable fact snapshot、aggregate artifact cache、freshness 状态和测试契约。它保证 Jira、HSD-ES 和后续 provider 都能用同一套 provider/profile agnostic 缓存语义支持低延迟 dashboard 与可追溯 AI。

## ADDED Requirements

### Requirement: Provider/profile agnostic cache identity
系统 SHALL 使用 provider-neutral cache identity 表达 sync input、fact snapshot 和 aggregate artifact，而不是为某个 provider 或某个 profile 设计专用 cache key。

#### Scenario: Cache key is built for a provider profile
- **WHEN** sync 或 chart aggregate 需要判断缓存命中
- **THEN** cache identity SHALL include provider id、profile id、source query ownership/ref/hash、tenant or space when available、subject or item type when available、requested field set hash、mapping version hash、chart id、chart version、bucket/range selection 和 fact snapshot id when applicable

#### Scenario: Provider-specific fields are present
- **WHEN** Jira custom field ids、HSD-ES article field names、GitHub labels 或其他 native provider fields 参与事实投影
- **THEN** cache identity SHALL record them only through normalized field-set or mapping hashes and provenance payloads, and SHALL NOT expose provider-native query semantics as Grafana panel-local cache controls

#### Scenario: Profile configuration changes
- **WHEN** a Project Provider Profile changes source query, field binding, value normalization, mapping version, scope labels or chart recipe binding
- **THEN** previously materialized cache artifacts SHALL become stale or non-authoritative for current dashboard requests unless their recorded identity still matches the current profile contract

### Requirement: Cache is enabled by default and debug-bypassable
系统 SHALL enable provider sync cache by default for production-like runtime，并提供 explicit debug-only bypass controls without changing dashboard source-of-truth semantics。

#### Scenario: Runtime uses default cache settings
- **WHEN** no cache override is configured
- **THEN** provider sync, metadata discovery and aggregate generation SHALL use enabled cache behavior with configured TTL/staleness limits

#### Scenario: Cache is disabled for debugging
- **WHEN** an operator disables provider cache through configuration for local debugging
- **THEN** sync operations SHALL bypass eligible cache reads and refetch/recalculate through the provider adapter, but dashboard render paths SHALL still read the resulting local durable artifacts rather than live-querying the external provider

#### Scenario: Forced refresh is requested
- **WHEN** an explicit sync operation requests refresh or bypass for a profile
- **THEN** the system SHALL bypass stale-eligible cache reads for that operation, update durable facts and aggregate artifacts on success, and record refresh provenance without exposing secrets

### Requirement: Durable facts and aggregate artifacts are separated by cache layer
系统 SHALL separate provider raw snapshot、normalized facts、aggregate artifacts 和 short-lived request cache so each layer has a clear authority and invalidation rule。

#### Scenario: Provider data is fetched successfully
- **WHEN** a live provider sync completes for a profile
- **THEN** the system SHALL persist raw snapshot provenance, normalized provider facts, sync cursor/freshness metadata and approved aggregate artifacts before those results are treated as current dashboard data

#### Scenario: Grafana requests chart data
- **WHEN** Grafana or another dashboard consumer requests chart data for a profile and range
- **THEN** the response SHALL come from matching local aggregate artifacts or an explicit unavailable/stale state, and SHALL NOT wait on a live external provider request

#### Scenario: Duplicate chart requests occur in one render window
- **WHEN** multiple dashboard panels request the same provider/profile/range/chart artifact during the same render window
- **THEN** the system MAY use short-lived request or process cache to avoid duplicate local reads or calculations, while preserving the durable artifact as the authoritative result

### Requirement: Stale-while-revalidate and failure fallback
系统 SHALL prefer fast, explicit stale data behavior over blocking dashboard rendering on slow or failed external provider calls。

#### Scenario: Cached artifact is fresh
- **WHEN** a matching aggregate artifact is within configured freshness limits
- **THEN** chart APIs SHALL return it with freshness metadata such as `fresh`, `live_synced`, or equivalent current status

#### Scenario: Cached artifact is stale but usable
- **WHEN** the latest successful artifact is older than the configured freshness limit and no newer successful sync exists
- **THEN** chart APIs SHALL return the latest successful artifact only with explicit stale freshness metadata and a reason, or return unavailable when stale data is not allowed for that chart

#### Scenario: Live sync fails after previous success
- **WHEN** a live sync fails because of auth, permission, timeout, rate limit, partial response, schema drift or provider error
- **THEN** the system SHALL preserve the last successful durable facts and aggregate artifacts, record the sync failure, and SHALL NOT replace charts with misleading zero-valued data

#### Scenario: Concurrent refresh attempts target the same cache identity
- **WHEN** multiple sync or refresh attempts target the same provider/profile/source/range identity at the same time
- **THEN** the system SHALL apply single-flight or equivalent stampede protection so only one external provider fetch owns the refresh while other callers observe running, stale or latest-successful state

### Requirement: Cache status is observable and secret-safe
系统 SHALL expose cache and sync freshness through provider-neutral status fields suitable for dashboard readiness, Data Health and AI context。

#### Scenario: Consumer requests profile readiness
- **WHEN** UI, Grafana or AI asks for provider profile readiness
- **THEN** the response SHALL include provider id、profile id、source query provenance、latest successful sync time、cache freshness status、cache age or staleness window、artifact id/snapshot id when available、and explicit blocker/error category when not fresh

#### Scenario: Status includes provider auth failure
- **WHEN** sync cannot authenticate or lacks permission to read a provider source query
- **THEN** readiness and Data Health SHALL expose a redacted auth/permission status and approved access-check guidance, and SHALL NOT include tokens, cookies, passwords or raw secret-bearing headers

#### Scenario: AI consumes cached provider facts
- **WHEN** AI generates an explanation from provider facts or chart aggregates
- **THEN** AI context SHALL identify whether data is live-synced, stale, seeded preview, unavailable or configuration-required, and SHALL cite the snapshot/artifact provenance rather than implying real-time provider access

### Requirement: Cache behavior is validated with focused, deterministic, performance and live tests
系统 SHALL validate provider sync cache behavior with deterministic fake data, focused unit/integration tests, performance tests and bounded live smoke tests。

#### Scenario: Fake provider tests cache correctness
- **WHEN** focused tests run with a fake provider returning deterministic pages, errors, partial responses and slow responses
- **THEN** tests SHALL verify cache hit/miss, TTL expiry, forced refresh, disabled cache behavior, pagination merge, dedupe, stale fallback and sync failure handling without requiring live provider access

#### Scenario: Performance tests use large deterministic payloads
- **WHEN** performance validation runs against synthetic provider payloads
- **THEN** tests SHALL measure sync/materialization time, aggregate generation time, repeated chart API latency and concurrent refresh behavior against explicit thresholds

#### Scenario: Live provider smoke test runs
- **WHEN** credentials and network access are explicitly configured for a live provider profile
- **THEN** a bounded live test SHALL verify one sync, expected result-count or field-contract parity against provider evidence, secret redaction, Data Health status and dashboard chart rendering without becoming a required default unit-test dependency
