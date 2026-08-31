# Phase 1 Contract Preflight

本文是 `define-grafana-jira-first-ai-dashboard-target` 的 Phase 1 验收记录。它把 proposal、design、delta specs、profile seed 和 Grafana allowlist 对齐成一个可执行前置合同，避免后续实现时把 Jira、HSD-ES、Grafana 和 AI 的职责边界混在一起。

## Scope

Phase 1 只冻结合同和配置 seed，不实现 2.x 的 facts/aggregate producer，不实现 3.x 的 Grafana parity dashboard，也不实现 6.x 的 HSD-ES adapter。

## Task Coverage Matrix

| Task | Preflight result | Evidence |
| --- | --- | --- |
| 1.1 Reference inventory | covered | 本文 `Reference Dashboard Inventory` |
| 1.2 Field layering | covered | 本文 `Field Layering Contract`; `specs/work-item-provider-platform/spec.md` |
| 1.3 Project Provider Profile | covered | 本文 `Project Provider Profile Contract`; `profiles/*.yaml` |
| 1.4 Jira-first semantic mapping | covered | 本文 `First-Wave Jira Mapping`; `profiles/chiplet-2a-jira.yaml` |
| 1.5 Dashboard query state | covered | 本文 `Provider-Neutral Dashboard Query State`; `specs/grafana-dashboard-parity/spec.md` |
| 1.6 HSD-ES seed evidence | covered | 本文 `HSD-ES Provider Seed`; `profiles/nvu-ttl-hsdes.yaml` |
| 1.7 Jira source query ownership | covered | `profiles/chiplet-2a-jira.yaml`; Metrics-managed JQL is the first source population |
| 1.8 Chart recipe and provider binding | covered | 本文 `Chart Recipe Matrix`; `specs/grafana-dashboard-parity/spec.md` |
| 1.8A Daily/WW metric aggregate ownership | covered | 本文 `Daily And WW Aggregate Ownership`; `specs/provider-facts-and-sync/spec.md` |
| 1.9 Approved data surface allowlist | covered | `openspec/docs/current-baseline/grafana-approved-data-surfaces.json` includes `0.2` provider chart surfaces |
| 1.10 Plan preflight | covered | 本文 `Preflight Assertions` |

## Reference Dashboard Inventory

The inspected reference is Intel Grafana `In-fly Indicator v2.0`. Observed Grafana variables and query state:

| Variable | Observed value | Metrics interpretation |
| --- | --- | --- |
| `IP` / `var-query_ip` | `NVU` | provider-neutral IP/product dimension |
| `Project` / `var-query_prj` | `NVU1.0_TTL` | provider-neutral project/product scope |
| `Milestone` / `var-query_ms` | `NVU_TTL_FWSW0.8` | release target or milestone |
| `Begin_WW` / `var-begin_ww` | `25WW15` | WW range start |
| `End_WW` / `var-end_ww` | `26WW32` | WW range end |

Observed reference aggregate shapes:

| Section | Reference element | Observed aggregate shape | First-wave state |
| --- | --- | --- | --- |
| QUALITY | Top 10 Bugs By Component | `component_bug_data_new`: `ip_name`, `prj_name`, `Component`, `Bug` | Jira supported after aggregate implementation; HSD-ES configuration-required |
| QUALITY | Previous 4 WW Valid Bug Avg | rolling valid bug aggregate | Jira configuration-required until standard-bug mapping is versioned |
| QUALITY | Previous 4 WW Valid Bug | recent WW valid bug counts | Jira configuration-required until standard-bug mapping is versioned |
| QUALITY | Open Bugs Trend | `open_bug_data_full_new`: `xData`, open/new/closed series | Jira supported after aggregate implementation; HSD-ES configuration-required |
| QUALITY | Internal Escaped Bugs | escaped bug classification | deferred |
| QUALITY | External Escaped Bugs | escaped bug classification | deferred |
| QUALITY | Escaped Details | escaped issue evidence rows | deferred |
| EXECUTION | Execution Statistics | `execution_data_new`: attempt/pass/fail/block rates | deferred |
| EXECUTION | Milestone Schedule Chart | schedule/scheduling aggregate | deferred |
| EXECUTION | Milestone Progress Chart | `execution_scheduling_data`: passed/failed/blocked/to-be-tested | deferred |
| EXECUTION | Total Bugs Trend & Status | total submitted/valid/status trend | Jira supported after aggregate implementation; HSD-ES configuration-required |
| EFFICIENCY | Automation Statistics | automation aggregate | deferred |
| EFFICIENCY | Shift-left Statistics | shift-left aggregate | deferred |
| EFFICIENCY | Open Bugs Aging | aging buckets | Jira supported after aggregate implementation; HSD-ES configuration-required |

Reference Mongo queries are evidence of target aggregate shapes only. They are not production logic for this project, and they must not be copied into Grafana panel SQL or datasource queries.

## Field Layering Contract

| Layer | Owner | Purpose | Examples |
| --- | --- | --- | --- |
| Canonical fields | Metrics platform | Shared dashboard/evidence/AI/correlation semantics | `provider_id`, `source_item_id`, `normalized_state`, `component_or_area`, `release_target`, `created_at`, `ww_bucket` |
| Project fields | Project Provider Profile | Per-project dimensions and mapping inputs | `standard_bug_rule`, NVU-specific milestone, Jira custom severity field |
| Provider fields | Provider adapter | Raw/native payload preservation and audit | Jira custom fields, HSD-ES article fieldValues, tenant/subject/query metadata |
| Static scope labels | Project Provider Profile | Dashboard labels when item-level provider fields are not confirmed | Jira `IP=chiplet_ip`; HSD-ES `Milestone=NVU_TTL_FWSW0.8` |

Rules:

- Canonical fields are the only fields Grafana and AI may assume across providers.
- Project fields may feed a chart recipe only when the profile declares and versions them.
- Provider fields remain available for audit/remapping but are not global dashboard schema.
- Static labels are fixed profile dimensions and do not prove item-level provider mappings.

## Project Provider Profile Contract

A profile must include:

| Area | Required content |
| --- | --- |
| Identity | `profile_id`, `provider_id`, `project_scope`, `mapping_version`, status |
| Source query | ownership, native query reference or text, query hash/snapshot requirement |
| Scope labels | configured label source, label values, mapping version |
| Field bindings | canonical field to native/project field mapping |
| Value normalization | state/outcome/severity/type mappings where confirmed |
| Chart support | `supported`, `configuration_required`, `unsupported`, or `deferred` per chart |
| Evidence rules | bucket/range/summary evidence behavior |
| Provenance | profile id, mapping version, source query version/hash, fact snapshot, calculation run |

First profile seeds:

- `profiles/chiplet-2a-jira.yaml`
- `profiles/nvu-ttl-hsdes.yaml`

These seed files are planning/config artifacts for this change. Production config and loaders belong to later implementation tasks.

## First-Wave Jira Mapping

The first Jira source population is Metrics-managed JQL:

```jql
project = "131600" AND component = "team_int_qemu"
```

Jira saved filters remain a future-compatible ownership mode, but the first wave uses profile-managed JQL so Metrics can version, audit and hash the source population. Grafana must receive only `provider_id`, `profile_id`, WW range, chart id/version and optional snapshot/run selectors. It must never receive raw JQL, Jira custom field ids or Jira semantic lists as panel-local query logic.

First Jira static labels:

| Label | Value | Source |
| --- | --- | --- |
| IP | `chiplet_ip` | user-configured static text |
| Project | `chiplet` | user-configured static text |
| Milestone | `2a` | user-configured static text |

First-wave deferred categories:

| Category | First-wave state | Reason |
| --- | --- | --- |
| execution | deferred | execution/test status mappings are not confirmed |
| automation | deferred | automation coverage semantics are not confirmed |
| shift-left | deferred | shift-left classification is not confirmed |
| escaped bug | deferred | escaped-defect classification is not confirmed |

## Provider-Neutral Dashboard Query State

Approved Grafana query state:

```text
provider_id
profile_id
space_id optional
release_target optional
milestone optional
begin_ww
end_ww
chart_id
chart_version optional
fact_snapshot_id optional
calculation_run_id or run optional where evidence is requested
bucket optional
series optional
```

`comparison_provider_id` and `comparison_profile_id` are reserved for a future explicit comparison/correlation surface. They are not allowed in the normal selected-profile Grafana chart query path.

Disallowed in Grafana panel-local query state:

```text
raw_jql
jira_customfield_*
hsdes_tenant
hsdes_subject
hsdes_eql
hsdes_article_field
standard_bug_rule
critical_high_values
native status/resolution classification lists
```

Provider-native query details belong to profile/source provenance, not dashboard variables.

## HSD-ES Provider Seed

First HSD-ES quality seed:

| Attribute | Value | Modeling |
| --- | --- | --- |
| Saved query id | `15017652869` | provider-owned source seed |
| Query title | `NVU All Bugs` | human label |
| Tenant | `ip_fw_sw_sensing.tenant` | provider config |
| Subject | `ip_fw_sw_sensing.bug` | provider config |
| Operator | `All` | criteria semantics |
| Include rules | `id > 0`; `family in NVU-FW`; `HSD_type in bug`; `release in NVU-FW.trunk/NVU-FW1.0_RZL/NVU-FW1.0_TTL` | criteria snapshot |
| Exclusions | selected validation/tool components; `[chrome]`; `[catalog]` | criteria snapshot |

HSD-ES seed evidence is enough to define first profile configuration. It is not enough to implement HSD-ES production sync until API behavior, pagination, permissions, lookup/detail fields and chart mappings are rechecked against the official HSD-ES API source.

First HSD-ES static labels:

| Label | Value | Source |
| --- | --- | --- |
| IP | `NVU` | user-configured static text |
| Project | `NVU1.0_TTL` | user-configured static text |
| Milestone | `NVU_TTL_FWSW0.8` | user-configured static text |

## Chart Recipe Matrix

Each chart recipe must define `chart_id`, `chart_version`, section, semantic metric, required canonical fields, optional project fields, supported providers, evidence capability and unsupported-state policy.

| Chart recipe | Section | Required canonical fields | Optional project fields | Evidence | Jira first | HSD-ES second |
| --- | --- | --- | --- | --- | --- | --- |
| `component_bug` | QUALITY | `component_or_area`, `source_item_type`, `normalized_state` | standard-bug/type mapping | range/evidence-backed | supported after aggregate | configuration-required |
| `rolling_valid_bug` | QUALITY | `created_at`, `ww_bucket`, `normalized_state` | valid/standard-bug rule | summary-only/range-only | configuration-required | configuration-required |
| `open_bugs_trend` | QUALITY | `created_at`, `resolved_at`, `closed_at`, `normalized_state`, `ww_bucket` | critical/high mapping | bucket-series | supported after aggregate | configuration-required |
| `total_bug_trend` | EXECUTION | `created_at`, `normalized_state`, `ww_bucket` | valid/status grouping | bucket-series | supported after aggregate | configuration-required |
| `open_bug_aging` | EFFICIENCY | `created_at`, `updated_at`, `normalized_state` | aging buckets | range/evidence-backed | supported after aggregate | configuration-required |
| `escaped_bug_internal` | QUALITY | TBD | escaped classification | deferred | deferred | deferred |
| `escaped_bug_external` | QUALITY | TBD | escaped classification | deferred | deferred | deferred |
| `execution_statistics` | EXECUTION | TBD | test/execution mapping | summary-only | deferred | deferred |
| `milestone_schedule` | EXECUTION | TBD | schedule/POR mapping | summary-only | deferred | deferred |
| `milestone_progress` | EXECUTION | TBD | execution progress mapping | summary-only | deferred | deferred |
| `automation_statistics` | EFFICIENCY | TBD | automation coverage mapping | summary-only | deferred | deferred |
| `shift_left_statistics` | EFFICIENCY | TBD | shift-left mapping | summary-only | deferred | deferred |

## Daily And WW Aggregate Ownership

Metrics owns daily/WW calculations. Grafana may select the chart/profile/range, but it may not define business semantics.

Required aggregate row shape:

```json
{
  "metric_id": "daily_new_standard_bug_count",
  "chart_id": "open_bugs_trend",
  "chart_version": 1,
  "provider_id": "jira",
  "profile_id": "chiplet-2a-jira",
  "bucket": {
    "grain": "day",
    "date": "2026-08-25"
  },
  "dimensions": {
    "ip": "chiplet_ip",
    "project": "chiplet",
    "milestone": "2a"
  },
  "series": "new_standard_bugs",
  "value": 37,
  "fact_snapshot_id": "snapshot-id",
  "calculation_run_id": "run-id",
  "mapping_version": 1,
  "source_query_version": 1
}
```

If `standard_bug` rules, source population, mapping version or chart version changes, aggregate rows must record enough provenance for Grafana and AI to distinguish old and new results.

## Approved Grafana Data Surfaces

Phase 1 adds provider-neutral `0.2` surfaces to `openspec/docs/current-baseline/grafana-approved-data-surfaces.json`:

| Surface | Required params | Purpose |
| --- | --- | --- |
| `/api/provider-charts/data/` | `provider_id`, `profile_id`, `begin_ww`, `end_ww`, `chart_id` | provider/profile/WW parity chart rows |
| `/api/provider-charts/evidence/` | `provider_id`, `profile_id`, `begin_ww`, `end_ww`, `run`, `chart_id` | evidence rows for a provider/profile/WW chart selection |

The static validator remains responsible for rejecting:

- unapproved datasources
- raw SQL
- direct Jira/HSD-ES table or query semantics
- raw provider credentials or secret-shaped fields
- unapproved query params such as raw JQL, HSD-ES EQL, tenant/subject, article field names or custom field ids

## Preflight Assertions

| Assertion | Result |
| --- | --- |
| Provider sequence is Jira first, HSD-ES second | pass |
| Reference HSD-ES dashboard defines parity target, not provider order | pass |
| Project Provider Profile governs source query, mapping, static labels and chart support | pass |
| Jira first profile uses Metrics-managed JQL | pass |
| HSD-ES first profile uses provider-owned saved query seed | pass |
| Grafana receives provider-neutral query state, not native provider query criteria | pass |
| Daily/WW metrics are calculated by Metrics, not Grafana | pass |
| Execution/automation/shift-left/escaped bug panels are first-wave deferred/configuration-required/unsupported | pass |
| AI can explain/read/draft through Metrics contracts for both providers | pass |
| AI cannot directly write Jira or HSD-ES | pass |

## Phase 2 Entry Criteria

Phase 2 may start when OpenSpec validation and Grafana validator tests pass with this Phase 1 contract. The next implementation should start with Jira-derived quality facts and aggregate contracts, not with HSD-ES adapter code or Grafana panel SQL.
