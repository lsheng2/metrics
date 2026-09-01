## 1. Planning

- [x] 1.1 Validate OpenSpec artifacts with `openspec validate enable-ai-grafana-dry-run-approval-workflow --strict`.

## 2. AI Base Dry-run Proof Flow

- [x] 2.1 Add failing AI Base tests for Dashboard try-run proof summary after `workflow.run`.
- [x] 2.2 Implement dry-run proof summary generation in the Dashboard try-run helper and verify focused connector tests pass.
- [x] 2.3 Show dry-run proof id/status/approval requirement in Dashboard Query Agent UI and verify desktop build/e2e pass.

## 3. Dashboard Runbook

- [x] 3.1 Add human E2E runbook covering start/stop/restart scripts, Jira/HSD-ES workflow checks, and dry-run proof expectations.

## 4. Validation And Delivery

- [x] 4.1 Run Dashboard OpenSpec validation and applicable script checks.
- [x] 4.2 Run AI Base focused connector tests, full backend tests where practical, desktop build and dashboard route e2e.
- [x] 4.3 Commit and push Dashboard docs/specs and AI Base implementation in separate scoped commits.
