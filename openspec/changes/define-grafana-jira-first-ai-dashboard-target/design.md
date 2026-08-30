## Context

See `proposal.md` for motivation. Existing project docs already point toward Grafana C-first, Metrics-owned facts/evidence, AI chart governance, provider-neutral contracts, Jira first, and HSD-ES as a second peer provider. This change freezes those threads into one target.

The reference page inspected in Edge is Intel Grafana dashboard `In-fly Indicator v2.0`. The visible query state was:

| Dashboard variable | Observed value | Product interpretation |
| --- | --- | --- |
| `IP` / `var-query_ip` | `NVU` | Provider-neutral space/IP dimension |
| `Project` / `var-query_prj` | `NVU1.0_TTL` | Provider-neutral project/product scope |
| `Milestone` / `var-query_ms` | `NVU_TTL_FWSW0.8` | Provider-neutral release target / execution milestone |
| `Begin_WW` / `var-begin_ww` | `25WW15` | WW range start |
| `End_WW` / `var-end_ww` | `26WW32` | WW range end |

Panel inspect showed Grafana Enterprise 9.0.3 using `grafana-datasource-mongodb` and Mongo aggregate collections. Examples observed:

| Reference panel | Collection / query shape | Key fields |
| --- | --- | --- |
| Top 10 Bugs By Component | `db.component_bug_data_new.aggregate(...)` | `ip_name`, `prj_name`, `Component`, `Bug` |
| Open Bugs Trend | `db.open_bug_data_full_new.aggregate(...)` | `ip_name`, `prj_name`, `xData`, `All Open Bugs`, `All Open Critical/High`, `Weekly New Critical/High`, `Weekly New Medium/Low`, `Closed Bugs (WW)` |
| Execution Statistics | `db.execution_data_new.aggregate(...)` | `milestone`, `Attempt Rate`, `Pass Rate`, `Fail Rate`, `Block Rate`, `To Be Tested Rate` |
| Milestone Progress Chart | `db.execution_scheduling_data.aggregate(...)` | `milestone`, `xData`, `passed_case`, `failed_case`, `blocked_case`, `to_be_tested_case`, `attempted_scheduling`, `attempt_rate`, `pass_rate` |

This proves the reference dashboard is an aggregate dashboard, not a direct HSD-ES frontend. For our project, those aggregate shapes are useful targets, but the first production source is Jira-derived durable facts.

A follow-up inspection of the HSD-ES saved query behind the user's traditional non-AI workflow found a concrete provider seed, not a product-wide data model:

| HSD-ES query attribute | Observed value | Architecture interpretation |
| --- | --- | --- |
| Saved query id | `15017652869` | Provider-specific query seed for one NVU bug scope |
| Query title | `NVU All Bugs` | Human-facing saved-query label, not a canonical dashboard concept |
| Community / tenant display | `ip_fw_sw_sensing.tenant` | HSD-ES connection/tenant context |
| Query subject | `ip_fw_sw_sensing.bug` | HSD-ES article type for this seed query |
| Required query operator | `All` rules | Equivalent to AND across visible rules |
| Base scope rules | `id > 0`, `family in NVU-FW`, `HSD_type in bug`, `release in NVU-FW.trunk/NVU-FW1.0_RZL/NVU-FW1.0_TTL` | HSD-ES provider-specific source filter before dashboard-level scope filters |
| Exclusions | `component not in sw.val/sw.val.tools/ip.sw.val.tool`, title does not contain `[chrome]`, title does not start with `[catalog]` | Provider/project-specific exclusion policy |

This confirms the target HSD-ES adapter should separate connection scope, base query seed, field mapping, and dashboard scope. The Grafana URL variables (`IP`, `Project`, `Milestone`, `Begin_WW`, `End_WW`) remain dashboard query state over aggregate data; they are not the same layer as the HSD-ES saved query criteria.

## Goals / Non-Goals

**Goals:**
- Make Grafana the final dashboard UI and chart layer.
- Match the reference dashboard's functional level: quality, execution, efficiency, trend, schedule, progress, aging, escaped bugs, automation and shift-left views.
- Build the first provider implementation from Jira facts.
- Add HSD-ES as a second peer provider through the same provider-neutral contracts.
- Release the first Grafana dashboard as a selected-profile dashboard: one Project Provider Profile is active at a time, while Jira and HSD-ES share the same chart contracts and preserve provider provenance.
- Make AI work across Jira and HSD-ES using facts, chart contracts, evidence and correlation.
- Preserve Metrics as semantic owner for indicators, facts, evidence, audit and AI governance.

**Non-Goals:**
- Do not implement application code in this planning change.
- Do not treat HSD-ES as the first production provider.
- Do not copy the reference Grafana Mongo queries as production business logic.
- Do not let AI write Jira or HSD-ES directly.
- Do not block Jira-first dashboard work on unknown HSD-ES tenant/subject details.
- Do not implement execution, automation, shift-left, or escaped bug charts in the first dashboard wave; show explicit deferred/configuration-required/unsupported states instead.
- Do not force stock Grafana to support same-page evidence if its event model cannot do it reliably.

## Decisions

### Decision 1: Grafana-first UI, Metrics-owned semantics

Grafana will own dashboard composition, variables, panels, chart rendering and the final user-facing dashboard surface. Metrics will own provider sync, normalized facts, approved aggregates, chart catalog, evidence contracts, permission checks, audit and AI governance.

Alternative considered: keep Django/Bulma/Chart.js as the long-term primary UI and embed Grafana selectively. This preserves more direct control but conflicts with the stated goal of final Grafana UI and would leave two dashboard mental models alive too long.

### Decision 2: Functional parity target is HSD-ES dashboard, data first source is Jira

The reference HSD-ES dashboard defines the desired dashboard level, not the provider sequence. We will first produce Jira-backed equivalents for the same functional categories, then add HSD-ES-derived facts as a second provider.

This avoids waiting for HSD-ES tenant/subject confirmation while still preventing Jira-only architecture from hardening around Jira-specific names.

The first implementation wave will prioritize quality facts and charts that can be supported without ambiguous execution/test infrastructure mappings: component bug counts, valid bug counts, open/new/closed bug trends, total bug trend and aging. Charts containing execution, automation, shift-left, or escaped bug semantics are deferred for the first wave and must render `deferred`, `configuration_required`, or `unsupported` states with reasons rather than placeholder numbers.

### Decision 3: Use provider-neutral query state

The dashboard query state should converge on:

```text
provider_id
range_mode
space_id or product_scope
release_target or milestone
begin_ww
end_ww
begin_date optional
end_date optional
calculation_run_id or fact_snapshot_id
chart_id
chart_version
selected_bucket_id optional
selected_series_name optional
```

For Jira, `space_id` maps to project or project set, `release_target` maps to fix version/milestone-like configuration, and quality/execution dimensions map through configured Jira fields. For HSD-ES, `space_id` may map to IP/project-like fields, while tenant/subject remain provider-specific connection and item-type hints.

Provider-specific seed queries must not leak into the dashboard query state. A saved Jira JQL filter or HSD-ES saved query can define an adapter's base population, but Grafana variables and AI prompts must reference the provider-neutral state above. Provider adapters translate that state into native filters and record the translation as provenance.

The first user-facing dashboard selector should be profile-primary. Users choose a Project Provider Profile such as `chiplet-2a-jira` or `nvu-ttl-hsdes`; Metrics resolves `provider_id`, static scope labels, source query ownership, field bindings and mapping version from that profile. `provider_id` may remain in API payloads and provenance, but stock Grafana should not expose it as an independent dropdown that can drift away from the selected profile.

Runtime filters have two classes:

| Runtime value | Default source | Override behavior |
| --- | --- | --- |
| `provider_id` | selected profile | derived/internal, not user-overridden in stock Grafana |
| `space_id` / IP | selected profile static label or future field binding | may be overridden only as explicit runtime scope override |
| `release_target` / project | selected profile static label or future field binding | may be overridden only as explicit runtime scope override |
| `milestone` | selected profile static label or future field binding | may be overridden only as explicit runtime scope override |
| `range_mode` | dashboard runtime selection | chooses whether backend data range comes from WW variables or Grafana browser date range |
| `begin_ww` / `end_ww` | dashboard runtime selection | normal time-window filter, not a profile identity change |
| `begin_date` / `end_date` | Grafana native time picker macros | used by Metrics only when `range_mode=date`; ignored for backend filtering when `range_mode=ww` |

If a richer Grafana App/Scenes or Metrics profile editor is introduced, overridden profile-derived fields should be visually marked and should offer `save as new profile` or controlled `update profile` flows. Stock Grafana may implement the first step by hiding derived fields from normal variable controls and passing only `profile_id` plus runtime filters to Metrics APIs.

Stock Grafana should still make the derived values visible. The dashboard should include a top-level profile status panel backed by a Metrics-owned provider profile readiness surface. That surface resolves the selected `profile_id` into `provider_id`, configured static scope labels, source query ownership, mapping version, readiness status and blocker reasons. For `nvu-ttl-hsdes`, the panel should explain that the profile is selected correctly but HSD-ES quality chart data remains `configuration_required` until runtime field bindings and permissions are validated. This avoids presenting an empty chart as if the profile selector failed.

`configuration_required` is intentionally broader than "needs login". For HSD-ES it can mean the operator still needs to validate SSO/service-account access, saved-query visibility, article detail permissions, lookup group metadata and chart-level native field bindings. When the selected profile has a known HSD-ES saved-query target, Metrics should emit an action label and URL in the readiness payload. Grafana may render that as a hyperlink such as "Open HSD-ES saved query / sign in"; the link is an access/configuration check entry point, not a guarantee that authentication alone will unlock aggregates.

The stock dashboard does not provide profile override editing. If an old URL still carries stale `var-space_id`, `var-release_target` or `var-milestone` parameters, those values should be ignored by stock dashboard panel requests. A later App/Scenes or Metrics profile editor can add editable fields; at that point it must mark overridden values and provide a save-as-new-profile or controlled update path.

Grafana's native time picker remains date/time based, while the legacy reference dashboard and many IP-quality workflows use work-week ranges. The stock dashboard therefore exposes `range_mode`:

| Range mode | Backend data range owner | Grafana browser time picker role |
| --- | --- | --- |
| `ww` | Metrics resolves `begin_ww` / `end_ww` into calendar dates and filters aggregates by that range. | Display-window control only; operators should keep it wide enough to include returned bucket dates. |
| `date` | Metrics uses `${__from:date:YYYY-MM-DD}` / `${__to:date:YYYY-MM-DD}` passed as `begin_date` / `end_date`. | Both display-window control and backend data-range control. |

Date mode must not reuse a cached artifact solely because stale `begin_ww` / `end_ww` URL variables match an existing materialized artifact. WW-keyed artifacts are valid for `range_mode=ww`; `range_mode=date` should rebuild from latest provider facts, or return a clear unavailable/configuration state if facts are unavailable.

### Decision 4: Use approved aggregate artifacts for Grafana

Grafana should consume Metrics-approved API surfaces or artifacts rather than live-querying Jira/HSD-ES per render. The reference dashboard's Mongo collections show the right pattern: precomputed aggregate rows shaped for dashboard consumption.

Our equivalent can be:

```text
Provider API -> sync/raw archive -> normalized facts -> indicator run -> approved aggregate rows -> Grafana panel
```

The storage can evolve from JSON/API-backed facts to DB/materialized views, but the contract must stay Metrics-owned.

Daily calculated metrics, such as "daily new standard bug count", belong in the Metrics chart recipe and aggregate layer, not in Grafana dashboard JSON or panel-local datasource logic. Grafana may select `metric_id`, `profile_id`, scope, date/WW range and visualization options, but it must not define what qualifies as a standard bug, which native provider fields represent creation date/type/severity, or how a daily bucket is counted.

For example, a Jira-backed `daily_new_standard_bug_count` chart should follow this ownership split:

| Layer | Responsibility |
| --- | --- |
| Provider connection | Fetch native Jira issues through approved JQL/filter or HSD-ES articles through approved saved query/EQL/API, preserving raw payload and source provenance |
| Project Provider Profile | Bind native fields such as Jira `created`/`issuetype` or confirmed HSD-ES create-date/type fields to canonical roles, and define project-specific `standard_bug` rules |
| Canonical facts | Store provider-neutral work item facts such as `canonical_type=bug`, `is_standard_bug=true`, `created_date`, `ww_bucket`, `project_or_product`, `milestone`, `provider_fields` and `project_fields` |
| Chart recipe and aggregate | Define `metric_id=daily_new_standard_bug_count`, filter `is_standard_bug=true`, group by day or WW, count source items, record `chart_version`, `mapping_version`, `fact_snapshot_id` and `calculation_run_id` |
| Grafana | Render the approved time series using dashboard variables and panel visualization settings only |
| AI/evidence | Explain the metric from the same chart recipe, aggregate rows and evidence API, including provider/profile/query provenance |

An approved aggregate row for this example should be shaped as a Metrics-owned data contract, such as:

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
    "project_or_product": "chiplet",
    "milestone": "2a"
  },
  "series": "new_standard_bugs",
  "value": 37,
  "fact_snapshot_id": "snapshot-...",
  "calculation_run_id": "run-...",
  "mapping_version": 1
}
```

This keeps Jira and HSD-ES asymmetry out of Grafana. Jira can source the population from Metrics-managed JQL, HSD-ES can source it from a provider-owned saved query, and both providers still produce the same approved aggregate contract before Grafana or AI consumes the result.

### Decision 5: Start with C-stock, keep C-plugin as the upgrade path

First implementation should prove a stock Grafana dashboard can render the required sections and consume approved data surfaces. If stock Grafana cannot reliably support click-to-evidence, AI chart catalog, or dashboard state synchronization, the product should upgrade to Grafana App/Scenes.

The first released Grafana dashboard should support one selected Project Provider Profile at a time for supported quality facts. During implementation, Jira facts can land before HSD-ES facts, but the first Grafana dashboard contract should keep chart series provider-neutral and preserve provider provenance in metadata so Jira and HSD-ES do not appear as unrelated projects on the same default page.

### Decision 5A: Use an explicit HSD-ES seed aggregate bridge before live sync

HSD-ES browser SSO and the Metrics backend are different trust surfaces. When the operator opens the saved query in the browser, that validates a human access path, but it does not provide Django/Grafana with a reusable backend credential or a synced fact snapshot. Until the HSD-ES service-account/Kerberos or token path is configured and validated, Metrics may expose a clearly labeled local seed fact artifact for the first `nvu-ttl-hsdes` profile.

The seed bridge is allowed only for first-wave quality charts whose field bindings are already represented by normalized HSD-ES facts. It SHALL preserve `provider_id=hsdes`, `profile_id=nvu-ttl-hsdes`, saved-query provenance, mapping version, fact snapshot id and freshness metadata. It SHALL mark freshness as seed-backed/materialized so the user can see chart data without mistaking it for a live HSD-ES sync.

The seed bridge does not relax the live provider requirements. HSD-ES article search/detail, lookup metadata, pagination, permissions, field drift detection, and production sync still require official HSD-ES API validation before the profile can be called live-ready.

Local runtime validation must distinguish source-code behavior from already-running services. If the provider aggregate contract or HSD-ES seed support changes, the Django process backing Grafana must be restarted and the dashboard artifact must be re-imported before judging the Grafana page. A stale local backend can still return older `configuration_required` states even when the current source tree and tests return seed-backed `supported` rows.

The decision should be evidence-based:

| Gate | Stock Grafana succeeds if |
| --- | --- |
| Parity | Jira-derived panel numbers match Metrics reference calculations |
| Evidence | Click/link carries chart, run/snapshot, bucket and series back to Metrics evidence API |
| Governance | Grafana artifacts pass datasource/query allowlist validation |
| AI | AI draft charts enter Metrics validator before publication |
| Fallback | Metrics can explain unavailable/stale state without stale rows |

### Decision 6: AI is a governed consumer and proposer

AI should answer questions, explain trend drivers, draft chart specs, suggest correlation candidates and create provider action proposals. It should not own source credentials, call provider write APIs directly, or publish Grafana dashboards without Metrics validation.

The preferred AI entry points are a Grafana App/Scenes experience and a Metrics UI sidebar. The placement remains flexible: if the Grafana layout cannot carry the AI interaction cleanly, the AI surface may be split into a separate dashboard agent or page while continuing to use the same Metrics facts, chart, evidence, correlation and action-plan contracts.

The same AI contracts should work for Jira-only phase and Jira+HSD-ES phase:

```text
User prompt
  -> AI intent
  -> Metrics capability/facts/chart/evidence/correlation APIs
  -> AI answer or draft spec/action plan
  -> Metrics validator / approval / audit
```

### Decision 7: Separate canonical fields from project-specific mappings

Metrics should not ask Grafana charts to know every Jira custom field or HSD-ES article field. Instead, each provider/project combination should have a `ProjectProviderProfile` config that binds native fields and values to platform semantics:

```yaml
profile_id: nvu-ttl-hsdes
provider_id: hsdes
project_scope: nvu-ttl
mapping_version: 1

source_query:
  ownership: provider_saved_query
  id: "15017652869"
  tenant: ip_fw_sw_sensing.tenant
  subject: ip_fw_sw_sensing.bug
  description: NVU All Bugs

scope_labels:
  source: user_configured_static_text
  ip: NVU
  project: NVU1.0_TTL
  milestone: NVU_TTL_FWSW0.8

fields:
  source_item_id: id
  source_item_type: HSD_type
  title: title
  native_state: status
  priority: priority
  severity_or_exposure: exposure
  component_or_area: component
  release_target: release
  affected_release: release_affected
  milestone: target_MS
  owner: owner
  submitter: submitted_by
  created_at: submitted_date
  updated_at: updated_date
  implemented_at: implemented_date
  closed_at: closed_date

values:
  normalized_state:
    open: [open, change_defined]
    done: [complete, implemented]
    rejected: [rejected]
```

```yaml
profile_id: chiplet-2a-jira
provider_id: jira
project_scope: chiplet-2a
mapping_version: 1

source_query:
  ownership: metrics_managed_native_query
  jql: project = "131600" AND component = "team_int_qemu"

scope_labels:
  source: user_configured_static_text
  ip: chiplet_ip
  project: chiplet
  milestone: 2a

fields:
  source_item_id: key
  title: summary
  native_state: status.name
  priority: priority.name
  component_or_area: components[].name
  release_target: fixVersions[].name
  milestone: customfield_12345
  owner: assignee.emailAddress
  created_at: created
  updated_at: updated
```

The raw provider payload is never rewritten. The profile maps it into canonical fields for charting while retaining original values for audit and remapping.

Metrics should define canonical semantic fields used by dashboard, evidence, AI and correlation:

```text
provider_id
source_item_id
source_item_type
source_scope
source_state
normalized_state
outcome
severity_or_priority
component_or_area
release_target
project_or_product
milestone
owner
submitter
created_at
updated_at
resolved_at
closed_at
ww_bucket
project_fields
provider_fields
```

Jira and HSD-ES adapters map native fields into these canonical fields, but provider-native data stays available under `provider_fields`, and project-specific dashboard dimensions stay under `project_fields`.

For example, Jira may map project, issue type, status, resolution, component, fix version, assignee and priority into canonical fields while retaining custom fields in `project_fields`. HSD-ES may map `id`, `HSD_type`, `status`, `reason`, `priority`, `exposure`, `component`, `release`, `release_affected`, `target_MS`, `owner`, `submitted_by`, `submitted_date`, `updated_date`, `implemented_date`, `closed_date`, `team_found`, `pss_escape` and `days_open` into canonical or project fields while retaining the full article payload in `provider_fields`.

### Decision 7A: Model query ownership explicitly

The first Jira implementation will use Metrics-managed JQL stored in the Project Provider Profile, with the initial base JQL set to `project = "131600" AND component = "team_int_qemu"`. Jira saved filters remain a future optional pattern where teams already maintain provider-owned filters. The inspected HSD-ES workflow will use an HSD-ES-owned saved query as its first quality-facts seed. This is a real difference, but it should be normalized as source population provenance, not exposed to Grafana.

| Source query pattern | Example | Owner of query definition | Metrics responsibility |
| --- | --- | --- | --- |
| Provider-owned saved query | HSD-ES `queryId=15017652869` | HSD-ES | Store id, tenant, subject, expected criteria snapshot, permissions and result contract |
| Metrics-managed native query | Jira `base_jql` in project profile | Metrics config | Store JQL, validate allowed fields/functions, version it with the profile |
| Provider-owned saved filter | Jira filter id, if chosen later | Jira | Store filter id and expected owner/scope, snapshot effective JQL if API allows |
| Metrics-managed scope parameters | Jira project list plus issue type/status configs | Metrics config | Generate native query from structured profile fields |

All four patterns should emit the same source population contract:

```text
profile_id
provider_id
source_query_ownership
source_query_ref
source_query_hash optional
native_query_text optional
tenant_or_site optional
subject_or_issue_type optional
mapping_version
fact_snapshot_id
```

This means HSD-ES can use its built-in query model naturally, while Jira uses our profile-managed JQL naturally in the first phase. Both become equivalent before facts reach chart recipes or Grafana.

### Decision 7B: Allow configured static scope labels when provider fields are not yet confirmed

Dashboard-level `IP`, `Project`, and `Milestone` values may initially be represented as user-configured raw/static text in the Project Provider Profile. The first Jira profile will expose `IP=chiplet_ip`, `Project=chiplet`, and `Milestone=2a`. The first HSD-ES profile will expose `IP=NVU`, `Project=NVU1.0_TTL`, and `Milestone=NVU_TTL_FWSW0.8`. These values are valid as fixed scope labels or dimensions for a profile, but they are not provider-derived item fields unless the profile separately binds them to native provider fields.

Static scope labels must record:

```text
profile_id
label_name
label_value
source = user_configured_static_text
mapping_version
effective_date optional
```

If a chart later needs dynamic grouping, filtering, correlation, or evidence by IP/project/milestone from each provider item, the profile must add confirmed provider field bindings or aggregate artifact bindings. Static text is acceptable for the first Jira and HSD-ES quality profiles, but it cannot substitute for provider field mappings where item-level semantics are required.

### Decision 8: Define charts as provider-neutral recipes with provider bindings

Each parity chart should be defined as a Metrics-owned chart recipe:

```text
chart_id
chart_version
section
semantic_metric
required_dimensions
required_time_grain
required_canonical_fields
optional_project_fields
series_contract
evidence_capability
supported_providers
provider_binding
unsupported_state_policy
```

The provider binding maps a recipe to Jira facts, HSD-ES facts, or explicit cross-provider correlation facts. Grafana consumes the approved chart data surface produced from the recipe; it does not own the semantic calculation. This lets one chart definition render from Jira first or HSD-ES second through a single selected profile; side-by-side provider data is reserved for a clearly labeled comparison/correlation mode when both mappings are available.

Chart support should be explicit per provider:

| Chart support state | Meaning |
| --- | --- |
| `supported` | Provider mapping and aggregate contract are validated |
| `configuration_required` | Provider can support the chart after project-specific field mapping is supplied |
| `unsupported` | Provider lacks the required facts or semantics |
| `deferred` | Provider mapping is intentionally out of current implementation scope |

## Reference Dashboard Element Map

| Reference section | Reference element | Jira-first interpretation | HSD-ES second-provider interpretation | Evidence capability |
| --- | --- | --- | --- | --- |
| Global filters | IP | Provider-neutral product/IP scope, initially mapped from Jira project/scope config | HSD-ES IP-like field or lookup | scope state |
| Global filters | Project | Jira project or configured product scope | HSD-ES project-like field | scope state |
| Global filters | Milestone | Jira fix version, release target, or configured milestone field | HSD-ES milestone/release field | scope state |
| Global filters | Begin/End WW | Jira date bucket range | HSD-ES xData/week range | scope state |
| QUALITY | Top 10 Bugs By Component | Jira component/area defect count | HSD-ES component field aggregate | range/evidence-backed if rows retained |
| QUALITY | Previous 4 WW Valid Bug Avg | Jira valid bug rolling average | HSD-ES valid defect rolling average | summary-only |
| QUALITY | Previous 4 WW Valid Bug | Jira recent WW valid bug counts | HSD-ES recent WW valid defect counts | range-only |
| QUALITY | Open Bugs Trend | Jira open/critical-high/new/closed trend | HSD-ES equivalent open/new/closed trend | bucket-series |
| QUALITY | Internal Escaped Bugs | First wave deferred; later requires escaped classification mapping | HSD-ES escaped defect field/query after mapping | deferred initially |
| QUALITY | External Escaped Bugs | First wave deferred; later requires customer escape classification mapping | HSD-ES external escape field/query after mapping | deferred initially |
| QUALITY | Escaped Details | First wave deferred; later evidence rows after escaped mapping | HSD-ES article evidence rows after mapping | deferred initially |
| EXECUTION | Execution Statistics | First wave deferred; later requires execution/test status mapping | HSD-ES execution aggregate after mapping | deferred initially |
| EXECUTION | Milestone Schedule Chart | First wave deferred; later requires milestone POR/actual artifact or config | HSD-ES milestone schedule artifact after mapping | deferred initially |
| EXECUTION | Milestone Progress Chart | First wave deferred; later requires execution progress fields over WW | HSD-ES scheduling aggregate after mapping | deferred initially |
| EXECUTION | Total Bugs Trend & Status | Jira total submitted/valid/critical-high trend | HSD-ES total defect/status trend | bucket-series |
| EFFICIENCY | Automation Statistics | First wave deferred; later requires automation coverage mapping | HSD-ES automation aggregate after mapping | deferred initially |
| EFFICIENCY | Shift-left Statistics | First wave deferred; later requires shift-left classification mapping | HSD-ES shift-left aggregate after mapping | deferred initially |
| EFFICIENCY | Open Bugs Aging | Jira aging buckets from created/updated/status facts | HSD-ES aging buckets | range/evidence-backed |

## Architecture

```text
Provider connection layer
  Jira REST / JQL / configured project fields
  HSD-ES REST / EQL / tenant / subject / saved query seeds

Provider adapter layer
  native field extraction
  ProjectProviderProfile loading
  provider-owned or Metrics-owned source query execution
  permission and pagination handling
  provider_fields preservation

Canonical facts layer
  provider-neutral work item facts
  project_fields overlays
  mapping_version and source_query provenance
  normalized state/outcome/severity/component/release/WW fields
  fact snapshot and calculation run provenance

Chart recipe and aggregate layer
  Metrics-owned chart recipes
  provider bindings
  daily/WW metric calculations
  approved aggregate rows or materialized metric views
  evidence capability declarations

Grafana layer
  variables over provider-neutral query state
  approved data surfaces only
  no panel-local provider field mapping or business aggregation
  panel rendering and dashboard layout

AI and evidence layer
  chart catalog read/explain/draft workflows
  provider evidence API
  provider action plans
  Jira-HSD-ES correlation
```

Short term, existing Jira-specific modules may continue to own Jira implementation. New public DTO/API names should still use provider-neutral terms. When HSD-ES lands or the contracts stabilize across multiple consumers, shared contracts should move into `provider_ops/` or `work_items/`.

## Risks / Trade-offs

- [Risk] Jira may not have native equivalents for every HSD-ES execution or efficiency panel -> Mitigation: represent missing mappings as unsupported or configuration-required states, not fake zero data.
- [Risk] A discovered HSD-ES saved query could be mistaken for the whole product model -> Mitigation: treat saved queries as provider-specific seeds, while dashboard scope, canonical fields and chart recipes remain provider-neutral.
- [Risk] Project-specific Jira custom fields or HSD-ES article fields drift over time -> Mitigation: version ProjectProviderProfile mappings, retain raw provider fields, and require aggregate runs to record mapping_version.
- [Risk] Query ownership differs between providers and creates two ingestion models -> Mitigation: normalize provider-owned saved queries and Metrics-managed native queries into one source population provenance contract.
- [Risk] Stock Grafana may not support same-page evidence UX well enough -> Mitigation: run C-stock evidence gates and upgrade to Grafana App/Scenes if needed.
- [Risk] AI-generated chart specs could drift into ungoverned query generation -> Mitigation: AI returns intent/spec draft only; Metrics validator owns datasource/query/evidence approval.
- [Risk] A copied dashboard can become another semantic truth system -> Mitigation: store dashboard semantics in Metrics chart catalog and approved aggregate contracts, not Grafana panel-local scripts.

## Migration Plan

1. Freeze this OpenSpec change as the architecture target.
2. Implement Jira-first quality facts, Metrics-managed JQL profiles, daily/WW aggregates and approved Grafana data surfaces.
3. Add HSD-ES quality facts using `NVU All Bugs` (`queryId=15017652869`) as the first base seed, with static profile scope labels where item-level field mappings are not yet confirmed.
4. Release the first Grafana dashboard contract as a selected-profile dashboard for supported quality charts; render execution, automation, shift-left and escaped bug panels as deferred/configuration-required/unsupported, and reserve Jira/HSD-ES side-by-side comparison for explicit comparison/correlation surfaces.
5. Add AI read/explain/chart-draft support over the same facts and chart contracts, with Grafana App/Scenes and Metrics UI sidebar as preferred entry points.
6. Add richer HSD-ES field mappings, Jira-HSD-ES correlation and cross-provider AI explanations.
7. Re-evaluate stock Grafana after evidence/event and AI layout gates; upgrade to Grafana App/Scenes or split AI into a separate surface if required.

Rollback for implementation waves should keep existing Django reference pages and existing Jira sync/history untouched until the Grafana path passes parity and evidence gates.

## Deferred Post-First-Wave Questions

- Which provider-specific fields should later unlock execution, automation, shift-left and escaped bug charts after the first wave? This remains TBD and does not block first-wave quality chart implementation.
