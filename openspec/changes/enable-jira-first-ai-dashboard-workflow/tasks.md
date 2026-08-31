## 1. Planning

- [x] 1.1 Validate OpenSpec artifacts with `openspec validate enable-jira-first-ai-dashboard-workflow --strict`.

## 2. Dashboard Jira Profile Sync

- [x] 2.1 Add failing tests for `sync_provider_profile --profile-id chiplet-2a-jira` delegating to durable Jira sync and returning JSON.
- [x] 2.2 Implement Jira dispatch in generic provider profile sync and verify Jira sync command tests pass.
- [x] 2.3 Add readiness/workflow UX refinements for Jira profile guidance and verify AI workflow page/API tests pass.

## 3. AI Base Workflow Operation

- [x] 3.1 Add `workflow.run` to AI Base Metrics connector contract and verify connector operation tests fail before implementation.
- [x] 3.2 Update AI Base dashboard try-run to prefer `workflow.run` with fallback and verify backend tests pass.
- [x] 3.3 Update AI Base Dashboard Query Agent page to show workflow operation availability and verify desktop route/build tests pass where practical.

## 4. Validation And Delivery

- [x] 4.1 Run focused Dashboard tests for provider sync, Jira sync, AI workflow and provider charts.
- [x] 4.2 Run focused AI Base tests for Dashboard connector and try-run.
- [x] 4.3 Run `manage.py check`, `openspec validate --all --strict`, whitespace/file-size checks and applicable AI Base build checks.
- [x] 4.4 Commit and push scoped Dashboard changes, and commit AI Base changes separately if remote permissions allow.
