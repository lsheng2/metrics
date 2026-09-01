## 1. Dashboard Publish API

- [x] 1.1 Add a failing API test proving approved publish imports a validated draft and returns a Grafana URL.
- [x] 1.2 Add a failing API test proving missing approval id or dry-run proof id blocks import and audit.
- [x] 1.3 Implement the Dashboard publish request/response contract, service method and API route.
- [x] 1.4 Update the local E2E stack environment and runbook to expose the Grafana base URL to Dashboard.

## 2. Validation

- [x] 2.1 Run focused Dashboard AI API tests and verify they pass.
- [x] 2.2 Run `openspec validate enable-approved-ai-grafana-publish-demo --strict` and `openspec validate --all --strict`.
- [x] 2.3 Verify the running local E2E stack can import the approved AI chart and return an accessible Grafana URL.
