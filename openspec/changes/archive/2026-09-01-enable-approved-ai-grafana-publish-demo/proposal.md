## Why

AI Base Chat can now produce a governed Dashboard dry-run proof, but the local E2E demo still stops before the operator can see the generated chart in Grafana. The next step is a bounded local publish path that keeps Metrics validation and audit ownership while making the generated dashboard visible.

## What Changes

- Add a Metrics-owned AI Grafana publish demo endpoint that accepts the same chart workflow request plus an explicit approval id and dry-run proof id.
- Regenerate the render config through the existing workflow, validate it, import the generated Grafana dashboard into the local E2E Grafana instance, record publication callback audit, and return the visible Grafana URL.
- Update the AI Dashboard workflow/runbook surfaces so the operator can understand the dry-run to approved publish path.
- Keep unsupported series and invalid drafts blocked; keep provider credentials and native provider queries out of all responses.

## Capabilities

### New Capabilities

- None.

### Modified Capabilities

- `dashboard-ai-sidecar-integration`: Adds the local operator-approved publish step after dry-run proof for the AI Dashboard demo.
- `provider-ai-dashboard-composition`: Adds a Metrics-owned publish envelope that turns a validated draft into a visible Grafana dashboard URL after explicit approval.

## Impact

- Affected Dashboard backend: AI dashboard composition service/contracts, API view/URL, focused tests, E2E runbook.
- Affected external runtime: local Grafana E2E instance only.
- Security impact: publish remains Metrics-generated and Metrics-validated; no raw Grafana JSON from AI, provider credentials, native queries, raw SQL, or arbitrary filesystem paths are accepted.
