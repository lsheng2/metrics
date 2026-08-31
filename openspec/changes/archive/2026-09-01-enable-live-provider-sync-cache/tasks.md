## 1. API Preflight And Contract Lock

- [x] 1.1 Review the authoritative Intel HSD-ES API documentation for auth, saved-query/EQL execution, pagination, field expansion, permissions and error payloads, and verify the findings are captured in the change notes or implementation comments without secrets.
- [x] 1.2 Define the generic provider sync/cache identity DTO and verify focused tests show the identity is stable for Jira JQL, HSD-ES saved query and future provider-like fake inputs.
- [x] 1.3 Define provider-neutral freshness/status values for live-synced, seeded-preview, stale, unavailable, configuration-required, running and failed states, and verify readiness payload tests cover each state.
- [x] 1.4 Define generic cache configuration knobs with cache enabled by default and verify settings tests show provider-level defaults are used before provider-specific overrides.

## 2. Generic Sync Cache Core

- [x] 2.1 Add durable provider snapshot/fact artifact storage boundaries and verify model/API tests persist provider id, profile id, source query identity, field-set hash, mapping version hash, snapshot id and freshness metadata.
- [x] 2.2 Add aggregate artifact cache lookup by provider/profile/source/range/chart identity and verify chart API tests return local artifacts without calling a provider adapter.
- [x] 2.3 Add cache TTL, stale-while-revalidate and last-successful artifact fallback behavior and verify tests cover fresh hit, stale usable artifact and unavailable artifact paths.
- [x] 2.4 Add debug bypass behavior for sync operations and verify tests show disabled cache or forced refresh bypasses cache reads while still materializing local dashboard artifacts.
- [x] 2.5 Add single-flight/stampede protection for the same provider/profile/source/range identity and verify concurrent fake sync tests produce one external fetch owner.

## 3. HSD-ES Live Sync Adapter

- [x] 3.1 Implement a thin HSD-ES read/search adapter behind provider-neutral sync inputs and verify fake-client tests cover auth failure, permission failure, pagination, partial page and malformed payload normalization.
- [x] 3.2 Implement live sync for `nvu-ttl-hsdes` using saved query `queryId=15017652869` and verify deterministic fake data produces normalized facts compatible with the existing HSD-ES projection contract.
- [x] 3.3 Materialize HSD-ES live facts into the generic provider snapshot/fact cache and verify repeated syncs dedupe by article id/revision and preserve source query provenance.
- [x] 3.4 Generate HSD-ES quality aggregate artifacts from live facts and verify component bug, rolling valid bug, open bug trend, total bug trend, open bug aging and daily new standard bug count match deterministic fake expectations.
- [x] 3.5 Preserve the current seed-backed preview as fallback when live sync is not configured and verify existing HSD-ES seed preview tests still pass.

## 4. Dashboard, Data Health And AI Surfaces

- [x] 4.1 Update provider profile readiness to expose generic cache/materialization status and verify Jira, HSD-ES seeded preview, HSD-ES live synced and HSD-ES failed/stale cases render distinct readiness rows.
- [x] 4.2 Update Data Health to include provider-neutral sync/cache status and verify view/API tests show latest successful sync, current status, cache age, stale reason and redacted error category.
- [x] 4.3 Update provider chart API metadata so Grafana rows remain provider-neutral while payload metadata exposes live/seed/stale freshness and verify Grafana surface contract tests reject provider-native query leakage.
- [x] 4.4 Update AI provider facts context to carry cache freshness and snapshot provenance and verify AI context tests distinguish live-synced, stale, seeded-preview and configuration-required data.

## 5. Test Strategy And Performance Gates

- [x] 5.1 Add focused fake provider tests for cache hit/miss, TTL expiry, forced refresh, disabled cache, pagination merge, dedupe, stale fallback and sync failure handling, and verify they run without live network access.
- [x] 5.2 Add deterministic large-payload performance tests for 10k and 50k fake work items and verify sync/materialization time, aggregate generation time and repeated chart API latency are reported against documented thresholds.
- [x] 5.3 Add a live HSD-ES smoke test command or pytest marker that runs only when credentials/network are explicitly configured and verify it checks query result parity, secret redaction, sync health and Grafana chart availability.
- [x] 5.4 Add regression tests proving Grafana dashboard render path never calls HSD-ES live API and verify a patched failing live adapter does not break chart rendering from local artifacts.

## 6. Runtime Validation And Closure

- [x] 6.1 Run focused provider-sync/cache tests and verify all new fake/cache unit tests pass.
- [x] 6.2 Run affected `bug_metrics`, `ui_web`, and existing provider parity tests and verify current Jira and seed-backed HSD-ES behavior remains compatible.
- [x] 6.3 Run `python manage.py check` and verify settings, migrations and Django app wiring are valid.
- [x] 6.4 Run Grafana artifact/data-surface validation and verify dashboard panels still use only Metrics-owned provider chart APIs.
- [x] 6.5 Run the optional live HSD-ES smoke test when configured and verify `nvu-ttl-hsdes` charts show live-synced data with non-secret provenance; otherwise record live test as skipped because credentials are not configured.
- [x] 6.6 Run OpenSpec validation for `enable-live-provider-sync-cache` and verify proposal, specs, design and tasks are valid before apply closure.
