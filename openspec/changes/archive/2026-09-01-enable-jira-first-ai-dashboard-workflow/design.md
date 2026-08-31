## Context

Dashboard has two provider families:
- Jira already has durable scope sync through `sync_jira_scope`, local `JiraIssue`/transition history, calculation runs and provider chart aggregates.
- HSD-ES has provider-profile sync through `sync_provider_profile`/`sync_hsdes_profile` and provider_sync cache artifacts.

The AI workflow is now profile-based, so Jira must be accessible through the same profile-driven operator path. AI Base also has a Metrics connector contract, but it still models the workflow as separate catalog/intent/render/precondition calls; Dashboard now has a single workflow endpoint.

## Goals / Non-Goals

**Goals:**
- Make generic `sync_provider_profile --profile-id chiplet-2a-jira` run the existing Jira scope sync and return JSON.
- Keep Jira dashboard render path durable: sync first, render from local history/calculation runs.
- Add tests for supported Jira sync, missing Jira scope, and HSD-ES dispatch preservation.
- Update Dashboard workflow page/API to expose provider identity and workflow endpoint clearly.
- Update AI Base connector contract and try-run to use `workflow.run` when available.

**Non-Goals:**
- Do not add Jira write behavior.
- Do not replace `sync_jira_scope`; generic profile sync delegates to it.
- Do not implement new chart semantics beyond existing first-wave quality charts.
- Do not require AI Base for Dashboard validation.

## Decisions

1. **Reuse `sync_jira_scope` instead of duplicating Jira sync logic.**
   - Rationale: it already handles cursor locking, full vs incremental, durable history materialization and recalculation.
   - Alternative: create a parallel provider_sync Jira service. Rejected because it would duplicate cursor/calculation behavior.

2. **Generic profile sync returns JSON for both supported and blocked paths.**
   - Rationale: operators, tests and AI tools need machine-readable status.
   - Alternative: keep human-only management output. Rejected because AI Base cannot reliably parse styled text.

3. **AI Base connector adds `workflow.run` but keeps fallback operations.**
   - Rationale: new Dashboard versions can use the richer envelope; old Dashboard versions remain usable.
   - Alternative: remove individual operations. Rejected because they are still useful for diagnostics and compatibility.

## Risks / Trade-offs

- [Risk] `sync_provider_profile` calling another command hides some low-level Jira sync output → Mitigation: return profile/scope/status/coverage JSON and leave `sync_jira_scope` available for low-level diagnosis.
- [Risk] Real Jira live sync depends on local credentials/network → Mitigation: implementation tests use mocked existing Jira adapter; live smoke is optional and reports configuration/auth state.
- [Risk] AI Base and Dashboard commits must stay compatible → Mitigation: Dashboard keeps existing individual operations; AI Base only prefers `workflow.run` when present.
