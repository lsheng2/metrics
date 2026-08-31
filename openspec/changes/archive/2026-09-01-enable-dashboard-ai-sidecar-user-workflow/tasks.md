## 1. Planning And Contracts

- [x] 1.1 Validate the new OpenSpec proposal/spec/design/task artifacts with `openspec validate enable-dashboard-ai-sidecar-user-workflow --strict`.
- [x] 1.2 Add focused tests for the Dashboard AI workflow envelope and verify they fail before implementation.

## 2. Dashboard Workflow Implementation

- [x] 2.1 Add a Metrics-owned AI workflow request/result contract and verify supported HSD-ES requests return `draft_validated` plus precondition metadata.
- [x] 2.2 Verify unsupported HSD-ES semantic requests return `needs_metric_recipe` while preserving the exact requested series.
- [x] 2.3 Verify Jira `chiplet-2a-jira` uses the same workflow envelope as HSD-ES for supported requests.
- [x] 2.4 Add a Dashboard page and route for the AI sidecar workflow and verify the page renders readiness, profile/range/chart inputs, result status, draft preview and gcx precondition guidance.

## 3. Validation And Integration

- [x] 3.1 Run focused Dashboard AI, provider chart and query surface tests and verify they pass.
- [x] 3.2 Run `python manage.py check`, `openspec validate --all --strict`, whitespace checks and verify no failures.
- [x] 3.3 Run or document the two-app smoke path against AI Base at `METRICS_AI_BASE_URL` and verify Dashboard still reports sidecar readiness without requiring AI Base for local validation.
- [x] 3.4 Commit and push scoped Dashboard changes on the feature branch.
