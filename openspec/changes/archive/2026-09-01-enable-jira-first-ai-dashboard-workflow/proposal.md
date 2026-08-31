## Why

Jira-first dashboard data already has durable sync and aggregate primitives, but the operator path is still scope-id oriented while the new AI workflow is profile-id oriented. The next step is to make `chiplet-2a-jira` a first-class provider profile workflow: sync by profile, verify readiness from the same dashboard/AI surface, and let AI Base call one workflow endpoint instead of stitching individual validation calls together.

## What Changes

- Extend generic provider-profile sync so Jira profiles can be synced by `profile_id`, reusing the existing durable `sync_jira_scope` behavior.
- Add tests proving `chiplet-2a-jira` syncs durable Jira history/calculation runs and then returns supported provider aggregates through the same profile contract as HSD-ES.
- Polish the AI workflow output/page so operators and AI Base can see the exact workflow endpoint, profile/provider, supported/unsupported status, and next action.
- Update AI Base connector contract to include `workflow.run` and prefer it for Dashboard try-runs while preserving unsupported-series handling.

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `provider-facts-and-sync`: 增加 Jira profile-driven sync path and readiness contract for `chiplet-2a-jira`.
- `dashboard-ai-sidecar-integration`: 增加 AI Base use of Dashboard `workflow.run` as the preferred end-to-end connector operation.
- `provider-ai-dashboard-composition`: 增加 workflow result as the preferred composition envelope for supported/unsupported chart requests.

## Impact

- Dashboard: `provider_sync` management commands/tests, Jira sync command reuse, AI workflow result/page, OpenSpec specs.
- AI Base: dashboard connector operation fixture, try-run helper/tests, Dashboard Query Agent page copy/operation list.
- External systems: no new provider write behavior; Jira sync still uses existing read-only Jira sync credentials and durable history/calculation run storage.
