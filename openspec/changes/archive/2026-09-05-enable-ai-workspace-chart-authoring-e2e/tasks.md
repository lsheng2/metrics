## 1. Dashboard Artifact Contract

- [x] 1.1 Define Dashboard AI workspace artifact request/response contracts for chart intent, artifact metadata, validation findings and normalized render config preview; verify with focused API contract tests.
- [x] 1.2 Add Dashboard artifact validation API that accepts artifact content plus `artifact_ref`, `artifact_version`, `workspace_key`, `correlation_id` and validates profile boundary, approved chart recipe/series, canonical fields, range and secret safety; verify pass/fail tests.
- [x] 1.3 Ensure unsupported semantics such as `new_critical` return `needs_metric_recipe` or structured findings without publishing; verify focused unsupported-series test.

## 2. Dashboard Publish Contract

- [x] 2.1 Extend publish request path to carry artifact metadata and require matching dry-run proof plus approval id; verify missing proof/approval tests block before Grafana import.
- [x] 2.2 Record artifact id/version/correlation id in publish audit/history; verify publish history API includes artifact metadata.
- [x] 2.3 Keep generated Grafana JSON derived from Dashboard-normalized render config rather than arbitrary AI JSON; verify import mock receives Dashboard-generated payload.

## 3. AI Base Companion Integration

- [x] 3.1 Create companion AI Base OpenSpec change for `dashboard_query_agent` workspace-grounded chat and artifact-first chart authoring; verify AI Base OpenSpec validates.
- [x] 3.2 Implement AI Base workspace context Q&A so chat can answer boundary/data-block/canonical-field questions from synced Metrics context; verify focused chat/runtime test.
- [x] 3.3 Implement AI Base dashboard chart artifact creation and versioned workspace storage; verify artifact API/service tests.
- [x] 3.4 Implement AI Base Metrics connector calls for artifact validation, dry-run proof and approval/publish handoff; verify mocked connector tests.

## 4. E2E Try Run

- [x] 4.1 Update local E2E scripts/demo instructions to sync context, create a chart artifact, validate it, request approval and publish; verify script dry-run path succeeds.
- [x] 4.2 Run a deterministic HSD-ES or fixture-backed E2E where AI Base chat creates an approved `open_bug_trend` chart artifact and Dashboard returns a Grafana URL; verify the Grafana chart page loads.
- [x] 4.3 Run negative E2E for unsupported `new_critical` semantics; verify no dry-run proof, approval-ready state or Grafana mutation is created.
