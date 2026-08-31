## 1. Dashboard Sidecar Configuration

- [x] 1.1 Add dashboard-side AI sidecar config with enable/disable knob, AI Base base URL, expected `serviceId`, optional `instanceToken`, timeout and profile id; verify non-AI dashboard behavior is unchanged when disabled.
- [x] 1.2 Add sidecar handshake/probe client that verifies AI Base identity and profile capability before enabling AI UI; verify wrong service id/token leaves AI unavailable.
- [x] 1.3 Add Data Health or diagnostics surface for AI sidecar status, including unavailable, degraded, ready and blocked states; verify no source credentials or private paths are shown.

## 2. Metrics Connector Contract

- [x] 2.1 Publish a dashboard AI catalog endpoint or service facade that exposes profiles, chart recipes, allowed series, range modes, support status, limits and schema version without provider credentials/native query text.
- [x] 2.2 Publish a `DashboardCompositionIntent` validation endpoint for AI Base; verify `new_critical` returns `needs_metric_recipe` while `new_critical_high` render-only intent returns a validated draft.
- [x] 2.3 Publish draft render config validation/preview endpoint that uses the same Grafana render config and generated dashboard validators as developer-authored artifacts.
- [x] 2.4 Publish a Metrics gcx precondition endpoint that blocks invalid render config/dashboard artifacts before AI Base can run gcx mutation.
- [x] 2.5 Publish evidence/explanation context endpoint for selected profile/range/chart/panel; verify provenance includes profile mapping version, chart recipe version, fact snapshot and freshness.

## 3. AI Base Profile And Connector Integration

- [x] 3.1 Propose AI Base `dashboard_query_agent` profile manifest entry with Dashboard-specific ports, app identity, docs delta, feature gates and `dashboardQuery` capability.
- [x] 3.2 Define AI Base Metrics connector lane models for service base URL, auth ref, health path, contract version, request schemas, response envelopes and redaction policy.
- [x] 3.3 Add Dashboard-owned connector tool declarations for catalog lookup, intent validation, draft preview, evidence lookup and precondition validation; verify they are profile-scoped and not visible to Sample/RCA/SoC by default.
- [x] 3.4 Add cross-repo contract fixtures/snapshots so AI Base tests can mock Metrics responses and Metrics tests can validate AI Base request envelopes.

## 4. gcx Operation Safety

- [x] 4.1 Wire `StandardCliRunner` activation with a durable dry-run proof store, precondition executor and callback executor for Dashboard profile gcx tools.
- [x] 4.2 Make successful `write_preview` dry-run commands record proof with command id, artifact path, executable fingerprint, env policy, session/correlation/approval scope and expiry.
- [x] 4.3 Require matching proof plus approval before `grafana_push_resources` or equivalent mutation; verify mismatched path/profile/env/executable blocks mutation.
- [x] 4.4 Keep `grafana_gcx_command_catalog` operator/debug-visible by default, not model-facing; verify model-visible tool list excludes it unless explicitly enabled for diagnostics.
- [x] 4.5 Add Metrics publication/audit post-success callback after gcx mutation; verify callback failure is surfaced without hiding that Grafana mutation already occurred.

## 5. First HSD-ES AI Try Run

- [x] 5.1 With AI Base available, run a supported HSD-ES request: “show only `new_critical_high` for `open_bug_trend` from WW10 to WW35”; verify AI returns Metrics-validated draft render config.
- [x] 5.2 Run an unsupported semantic request: “only show `new_critical`”; verify AI returns `needs_metric_recipe` and does not generate a fake series.
- [x] 5.3 Run gcx precondition pass/fail dry-run against generated artifacts; verify invalid artifact blocks before gcx mutation and valid artifact proceeds only to approved dry-run.
- [x] 5.4 Record sidecar run evidence with request envelope, Metrics validation response, AI result, gcx precondition result and any user approval state.

## 6. Validation And Rollout

- [x] 6.1 Run Metrics focused tests for AI catalog, intent validation, precondition validation, provider chart API and Grafana artifact validator.
- [x] 6.2 Run AI Base focused tests for profile manifest, connector registration, cli runner activation, preconditions, callbacks, dry-run proof and gcx registry.
- [x] 6.3 Run smoke test with AI Base absent/disabled and verify dashboard remains fully usable.
- [x] 6.4 Run OpenSpec validation and update implementation review with evidence, residual risks and rollback path.
