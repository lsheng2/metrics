## 1. Baseline Documentation

- [x] 1.1 Commit and push existing AI Grafana publish case study documentation.

## 2. Jira Publish Readiness

- [x] 2.1 Add tests proving `chiplet-2a-jira` readiness returns a clear blocker before aggregate coverage exists.
- [x] 2.2 Add tests proving Jira aggregate coverage for `open_bug_trend` returns non-empty `grafana_rows` after deterministic sync/fixture materialization.
- [x] 2.3 Implement or harden readiness API/path so AI publish checks data readiness before Grafana import.
- [x] 2.4 Run Jira profile sync or deterministic Jira fixture materialization and verify `26WW32` to `26WW35` can render nonblank chart data.

## 3. Approval State

- [x] 3.1 Add tests for AI publish approval state transitions: pending, approved, rejected, published.
- [x] 3.2 Implement Dashboard-owned approval record/service/API or equivalent persisted state.
- [x] 3.3 Wire `publish-demo` to require matching approval state, preserving local demo auto-approval as explicit policy.

## 4. Recipe-Driven AI Authoring

- [x] 4.1 Add tests for catalog-driven chart id and series selection beyond fixed literal parsing.
- [x] 4.2 Update Dashboard workflow/publish response to include chart recipe provenance in publish metadata.
- [x] 4.3 Update AI Base integration prompt/contract notes if connector request shape changes are required.

## 5. Grafana Publish History

- [x] 5.1 Add tests for recording AI-generated Grafana publish artifact history.
- [x] 5.2 Implement publish history API and minimal operator-readable surface.
- [x] 5.3 Verify repeated publishes preserve prior audit metadata and mark latest status.

## 6. Validation And E2E

- [x] 6.1 Run `openspec validate productionize-jira-first-ai-chart-publish-workflow --strict` and `openspec validate --all --strict`.
- [x] 6.2 Run focused Dashboard tests for provider sync/readiness, AI workflow/publish, approval and history.
- [x] 6.3 Run AI Base focused tests if connector/chat behavior changes.
- [x] 6.4 Run E2E: Jira-first Chat publish prompt returns a Grafana URL and the Grafana chart canvas is nonblank.
