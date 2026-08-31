## 1. Target Freeze And Contract Preflight

- [x] 1.1 Record the Grafana reference dashboard inventory with variables, sections, panels, observed Mongo aggregate shapes, screenshots or notes, and verify the artifact names every visible reference element from `In-fly Indicator v2.0`.
- [x] 1.2 Define the canonical/project/provider field layering contract and verify Jira and HSD-ES native fields are mapped without flattening provider-specific payloads into one global schema.
- [x] 1.3 Define the Project Provider Profile schema and verify it covers provider/project identity, source query ownership, native query reference/text/hash, field bindings, value normalization, chart support, evidence rules and mapping version.
- [x] 1.4 Define the Jira-first semantic field mapping for first-wave quality dimensions, and verify execution, automation, shift-left and escaped bug panels are explicitly classified as deferred, unsupported, or configuration-required.
- [x] 1.5 Define the provider-neutral dashboard query state contract and verify it covers provider id, profile id, static scope labels, space/project, release target or milestone, begin/end WW, run or snapshot id, chart id, chart version, bucket and series selection.
- [x] 1.6 Capture HSD-ES provider seed evidence for `NVU All Bugs` (`queryId=15017652869`, `ip_fw_sw_sensing.tenant`, `ip_fw_sw_sensing.bug`, base criteria and exclusions) and verify it is modeled as provider-owned profile configuration, not dashboard schema.
- [x] 1.7 Implement first-phase Jira source query ownership as Metrics-managed JQL `project = "131600" AND component = "team_int_qemu"` stored in the Project Provider Profile, and verify optional Jira saved filter support remains a future compatible ownership mode without changing Grafana contracts.
- [x] 1.8 Define the chart recipe and provider binding contract and verify each reference panel can declare required canonical fields, optional project fields, evidence capability, provider support state and unsupported/configuration-required behavior.
- [x] 1.8A Define the daily/WW metric aggregate ownership contract and verify metrics such as `daily_new_standard_bug_count` are calculated by Metrics from facts/profiles/recipes, not by Grafana panel-local queries.
- [x] 1.9 Update the Grafana approved data surface allowlist for the new parity dashboard surfaces and verify the validator rejects unapproved datasources, raw provider credentials, arbitrary SQL, and panel-local business semantics.
- [x] 1.10 Run plan preflight against proposal, specs, design and tasks; verify provider sequence is Jira first, HSD-ES second, Project Provider Profiles govern mappings, and AI support spans both without granting direct provider writes.

## 2. Jira-First Facts And Aggregates

- [x] 2.1 Add or extend Jira-derived durable facts for first-wave quality panels and verify component bug, rolling valid bug, open bug trend, total bug trend and aging data can be produced from a fixed Jira scope fixture.
- [x] 2.2 Add explicit deferred/configuration-required/unsupported responses for execution, automation, shift-left and escaped bug panels, and verify no unvalidated facts or fake zero aggregates are produced for those categories.
- [x] 2.3 Add approved aggregate row contracts shaped for Grafana and verify each row preserves provider identity, scope, WW range, calculation run or fact snapshot provenance.
- [x] 2.3A Add materialized daily/WW aggregate rows for metrics such as daily new standard bug count and verify each row records metric id, bucket grain/date or WW, dimensions, value, chart version, mapping version, provider id, profile id, fact snapshot id and calculation run id.
- [x] 2.4 Add stale/unavailable handling for missing aggregate artifacts and verify Grafana-facing APIs do not silently return mismatched scope, range or snapshot data.
- [x] 2.5 Run focused provider facts tests for the touched `jira_sync/`, `jira_history/` and `bug_metrics/` owner paths and verify all Jira-first aggregate contracts pass.
- [x] 2.6 Add mapping-version provenance for canonical/project/provider field projections and verify remapped Jira or HSD-ES facts cannot be confused with earlier aggregate runs.
- [x] 2.7 Add source query ownership provenance for facts and snapshots and verify provider-owned saved queries and Metrics-managed Jira JQL produce the same source population contract.

## 3. Grafana Parity Dashboard

- [x] 3.1 Create the first Grafana dashboard artifact with `QUALITY`, `EXECUTION` and `EFFICIENCY` sections and verify supported quality panels render one selected Project Provider Profile at a time while execution, automation, shift-left and escaped bug panels show explicit deferred/configuration-required/unsupported states.
- [x] 3.2 Wire Grafana variables to the provider-neutral query state and verify dashboard URLs preserve provider, profile id, static labels, scope/project, milestone/release target, begin WW and end WW.
- [x] 3.3 Implement Grafana panels for supported quality trends and verify rendered values match Metrics aggregate API values for the same Jira/HSD-ES profile scope and WW range.
- [x] 3.4 Implement Grafana panels for execution and efficiency and verify each panel renders data, no-data, unsupported, or configuration-required states consistently with the field mapping contract.
- [x] 3.5 Validate the Grafana artifact with the approved data surface validator and verify no panel bypasses Metrics-owned chart data, facts, or aggregate contracts.
- [x] 3.6 Validate every Grafana panel against its Metrics chart recipe and provider binding, and verify Grafana contains no provider-native query semantics beyond approved datasource parameters.
- [x] 3.7 Verify Grafana requests use profile id or profile-compatible query state and never include raw Jira custom field ids, raw JQL, HSD-ES article field names, HSD-ES saved query criteria, or EQL in panel-local business logic.
- [x] 3.8 Verify daily/WW metric panels such as daily new standard bug count only request approved Metrics data surfaces and do not compute standard-bug classification, native date selection, provider field mapping or count aggregation in Grafana config.

## 4. Evidence And Drilldown

- [x] 4.1 Assign evidence capability to every parity panel and verify panels are classified as `bucket_series`, `range_only`, or `summary_only`.
- [x] 4.2 Implement evidence-backed Grafana link or event payloads for supported panels and verify clicked bucket/series resolves to Metrics evidence API with provider, scope, run/snapshot, chart, bucket and series.
- [x] 4.3 Implement unsupported and summary-only evidence states and verify clicking or inspecting summary-only panels cannot display stale ticket rows.
- [x] 4.4 Run browser or Grafana runtime evidence validation and verify at least one quality trend panel reaches the same evidence row count and title as the Metrics reference path.

## 5. AI Capability For Jira-First Dashboard

- [x] 5.1 Add AI-readable chart catalog and provider facts context for the selected-profile Jira/HSD-ES dashboard and verify AI prompts can retrieve approved chart definitions, series, evidence capabilities and provider provenance.
- [x] 5.2 Add AI explanation workflow for supported quality panels and deferred states, and verify answers cite provider facts, chart data, evidence rows, aggregate artifacts or deferred reasons rather than prompt memory.
- [x] 5.3 Add AI chart draft workflow for Grafana parity charts and verify drafts are rejected unless they use provider-neutral intent, approved series, approved datasource surfaces and declared evidence capability.
- [x] 5.4 Add AI entry placement support for Grafana App/Scenes and Metrics UI sidebar, and verify the same backend contracts can support a separate AI dashboard surface if embedded layout is not acceptable.
- [x] 5.5 Add Jira ProviderActionPlan proposal support where in scope and verify AI suggestions create preview/audit-ready plans without directly calling Jira write APIs.

## 6. HSD-ES Second Provider Preparation

- [x] 6.1 Configure the first HSD-ES quality-facts seed using the discovered `NVU All Bugs` query (`queryId=15017652869`, `ip_fw_sw_sensing.tenant`, `ip_fw_sw_sensing.bug`, `All` rules, NVU-FW family/release filters and exclusions), and verify it is captured as provider configuration with provenance.
- [x] 6.2 Configure user-configured static scope labels for the first Jira profile (`IP=chiplet_ip`, `Project=chiplet`, `Milestone=2a`) and first HSD-ES profile (`IP=NVU`, `Project=NVU1.0_TTL`, `Milestone=NVU_TTL_FWSW0.8`), and verify they are marked as fixed profile labels rather than provider-derived fields.
- [x] 6.3 Confirm HSD-ES identity fields, article detail fields, lookup APIs, EQL/search behavior, pagination, permission and per-chart field mappings, and verify unresolved items remain explicit blockers rather than guessed defaults.
- [x] 6.4 Validate HSD-ES Project Provider Profile drift detection and verify saved query tenant, subject, criteria snapshot or field set changes are reported before aggregate generation.
- [x] 6.5 Implement the HSD-ES provider capability manifest and verify unsupported planning/write capabilities are reported with clear reasons.
- [x] 6.6 Implement HSD-ES read/search/detail/facts projection behind provider-neutral contracts and verify article id, rev, tenant, subject, fieldValues, pagination, comments, links and errors are normalized.
- [x] 6.7 Produce HSD-ES quality aggregate artifacts compatible with the first selected-profile Grafana dashboard and verify provider provenance remains separate from chart value fields.
- [x] 6.8 Keep HSD-ES writes disabled and verify AI can only produce non-executable HSD-ES action suggestions until write governance is separately approved.

## 6A. Post-First-Wave Deferred Field Mapping

- [x] 6A.1 Keep provider-specific fields for execution, automation, shift-left and escaped bug charts marked as TBD after the first wave, and verify those TBD mappings do not block supported quality chart implementation.

## 7. Jira And HSD-ES Correlation

- [x] 7.1 Add correlation candidate generation based on explicit links, external ids, title fingerprints, component/release overlap, owner and time windows, and verify every candidate records evidence and confidence.
- [x] 7.2 Add confirmed/rejected/stale correlation state and verify provider-native Jira and HSD-ES fields remain separate in dashboard and AI outputs.
- [x] 7.3 Add Grafana or Metrics evidence views for cross-provider comparison and verify each series, row or KPI names its provider source.
- [x] 7.4 Add AI cross-provider risk explanation and verify answers distinguish confirmed, candidate, rejected and stale relationships.

## 8. Closure Gates

- [x] 8.1 Run OpenSpec validation for this change and verify all proposal, spec, design and task artifacts are valid.
- [x] 8.2 Run the Grafana artifact validator and verify the final parity dashboard only uses approved Metrics-owned data surfaces.
- [x] 8.3 Run focused provider/bug_metrics/ui tests selected by touched owner paths and verify the Jira-first dashboard contracts pass.
- [x] 8.4 Run runtime Grafana parity validation and verify visible panels render nonblank data, no-data, unsupported or configuration-required states as expected.
- [x] 8.5 Run AI governance validation and verify AI chart drafts, explanations and action proposals cannot bypass provider facts, evidence contracts, approved datasources or write approvals.
- [x] 8.6 Perform close review and verify the final evidence records show Jira-first parity, HSD-ES second-provider readiness, AI support coverage, residual risks and any C-plugin upgrade trigger.

## 9. Profile-Primary Dashboard Selection

- [x] 9.1 Update Grafana dashboard variables so `profile_id` is the primary user selector and `provider_id` is not exposed as an independent dropdown that can drift from the selected profile.
- [x] 9.2 Add provider-profile resolution in the Metrics provider chart API and verify chart/evidence requests can derive `provider_id` from `profile_id` while rejecting mismatched explicit provider/profile pairs.
- [x] 9.3 Preserve explicit runtime fields for WW range and optional scope overrides, and verify dashboard URLs remain provider-neutral without raw Jira/HSD-ES query semantics.
- [x] 9.4 Run focused artifact/API/E2E validation for Jira and HSD-ES profile selections and verify both paths use profile-derived provider identity.
- [x] 9.5 Hide profile-derived scope variables from the stock Grafana dashboard and verify HSD-ES profile selection cannot display stale Jira `space_id`, `release_target`, or `milestone` values.

## 10. Profile Readiness And Override Clarity

- [x] 10.1 Add a Metrics-owned provider profile readiness API surface and verify it resolves provider identity, static scope labels, source ownership, mapping version, readiness status and blockers from `profile_id`.
- [x] 10.2 Add a top-level Grafana profile status panel and verify the stock dashboard visibly explains Jira-ready vs HSD-ES configuration-required/blocked states without exposing provider or scope dropdowns.
- [x] 10.3 Validate the updated dashboard artifact and focused API tests, and verify stale URL variables for profile-derived fields remain outside approved panel requests.
- [x] 10.4 Add an HSD-ES access-check hyperlink for `configuration_required` readiness and verify it is sourced from Metrics readiness payload rather than hardcoded provider query logic in Grafana.

## 11. HSD-ES Seed Aggregate Runtime Preview

- [x] 11.1 Document that HSD-ES browser SSO does not configure the Django backend, and define the interim seed-backed aggregate path separately from live HSD-ES sync readiness.
- [x] 11.2 Add a local normalized HSD-ES seed fact source for `nvu-ttl-hsdes` and verify the public provider chart API returns supported `component_bug` Grafana rows with HSD-ES provenance.
- [x] 11.3 Refresh the local Grafana runtime and verify the selected HSD-ES profile displays a non-empty chart while remaining explicit about live sync limitations.

## 12. Dashboard Range Control Clarity

- [x] 12.1 Add a visible Grafana explanation for `Range Mode`, `Begin WW` / `End WW`, and the Grafana browser time picker relationship.
- [x] 12.2 Add `range_mode=ww/date` to approved provider chart data/evidence requests and verify `Date` mode uses Grafana `${__from}` / `${__to}` dates for backend filtering.
- [x] 12.3 Verify HSD-ES date-mode requests do not reuse WW-keyed aggregate artifacts when the browser date window differs from the WW variables.
