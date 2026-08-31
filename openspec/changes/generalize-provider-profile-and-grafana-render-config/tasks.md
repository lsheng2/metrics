## 1. Profile Registry Foundation

- [x] 1.1 Define `ProjectProviderProfile` schema and sample YAML/config files for `chiplet-2a-jira` and `nvu-ttl-hsdes`; verify loader tests cover provider id, source population, static scope labels, field bindings, chart bindings, mapping version and disabled profile handling.
- [x] 1.2 Replace first-profile constants and hardcoded static scope labels with registry lookups in provider chart/readiness paths; verify existing Jira and HSD-ES profile API tests still pass and unknown profile returns structured unsupported/unavailable state.
- [x] 1.3 Add chart support resolution from provider capability, profile field bindings and chart recipe requirements; verify supported, deferred, unsupported and configuration-required states with focused registry tests.
- [x] 1.4 Replace `sync_hsdes_profile` single-profile guard with a generic provider/profile sync dispatch command while preserving HSD-ES command compatibility if needed; verify `nvu-ttl-hsdes` sync still works and unsupported profile/provider returns a safe error.

## 2. Canonical Facts And Aggregate Generalization

- [x] 2.1 Define a canonical fact input contract for chart calculators and a compatibility adapter for current Jira calculation runs; verify Jira-backed `open_bug_trend` produces the same series/counts as before.
- [x] 2.2 Move HSD-ES normalized fact aggregation onto the same canonical calculator interface where practical; verify HSD-ES live/seed facts produce unchanged Grafana rows for supported quality charts.
- [x] 2.3 Replace provider-specific supported chart sets with chart recipe catalog compatibility checks; verify unconfigured execution/automation/shift-left/escaped charts remain deferred/configuration-required rather than empty supported charts.
- [x] 2.4 Extend aggregate artifact/cache identity with `range_mode`, normalized `range_start`, `range_end`, `range_grain` and display labels while keeping backward-compatible WW fields; verify WW and date mode artifacts do not collide.
- [x] 2.5 Update provider readiness/Data Health payloads to expose registry-derived source population, chart support, mapping version and freshness; verify Grafana readiness tests cover both Jira and HSD-ES profiles.

## 3. Grafana Render Config And Generator

- [x] 3.1 Define render config schema for dashboard variables, control text, sections, panels, chart recipe refs, category fields, value fields, evidence links and layout; verify schema validation rejects missing recipe refs and unapproved fields.
- [x] 3.2 Build generator that converts render config to deterministic Grafana JSON for `ip-quality-dashboard`; verify generated JSON contains the same approved Metrics API targets and profile-first variable model as the current dashboard.
- [x] 3.3 Update Grafana artifact validator to validate both render config and generated JSON, including category-axis checks, daily metric ownership, provider-native literal bans, secret bans and evidence-link contract.
- [x] 3.4 Treat `ops/grafana/provider_parity_dashboard.json` or its successor as generated artifact and document the regeneration command; verify `python scripts/validate_grafana_artifacts.py` or current equivalent passes on generated output.

## 4. AI Dashboard Composition Contract

- [x] 4.1 Define Metrics-side DTO/schema for `DashboardCompositionIntent`, catalog response, draft render config, validation findings, `needs_metric_recipe` and publication/audit metadata; verify schema snapshot tests cover valid and invalid examples.
- [x] 4.2 Add read-only catalog/validation services or endpoints for AI base consumption; verify AI client can list profiles, chart recipes, allowed series, range modes, support status and row/time limits without provider credentials.
- [x] 4.3 Implement draft validator rule for exact series identity; verify request for `new_critical` fails when only `new_critical_high` exists, while a visibility-only request for `new_critical_high` can pass.
- [x] 4.4 Add Metrics precondition validator contract for AI base/gcx Grafana operations; verify invalid render config blocks gcx publication before any Grafana mutation command can run.
- [x] 4.5 Document optional AI base integration path for `dashboard_query_agent` and `gcx`, including no direct Metrics code edits, no source credentials, no arbitrary SQL, and approval-gated publish; verify docs mention AI base absence does not break non-AI dashboard.

## 5. Validation And Review

- [x] 5.1 Run focused tests for profile registry, chart support, aggregate compatibility, range identity, render config validation and AI draft validation; verify commands and results are recorded in the apply summary.
- [x] 5.2 Run existing Grafana dashboard validator against generated artifacts; verify no unapproved datasource, provider-native query literal, secret-shaped field or panel-local business calculation is reported.
- [x] 5.3 Run `python manage.py check` and the relevant provider/Grafana/API focused pytest suite; verify no regression in current HSD-ES offline/live dashboard behavior.
- [x] 5.4 Run `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked` before review; record any unavailable gate explicitly.
  - 2026-08-31: `check_file_size_limits.py --include-untracked` passed with 37 checked files; `check_diff_whitespace.py --include-untracked` passed.
- [x] 5.5 Perform architecture review against module boundaries, public API contracts, AI/gcx ownership, secret handling and rollback path; verify remaining risks are documented before closing the change.
