## Why

Dashboard AI workflow currently stops at `ready_for_dry_run`: Metrics validates the chart draft and precondition, but the operator cannot yet see a durable gcx dry-run proof or distinguish “ready to dry-run” from “approved to mutate.” Before AI can safely change Grafana, the workflow needs a visible dry-run proof and approval gate.

## What Changes

- Add a Dashboard/AI Base workflow contract for `workflow.run -> gcx dry-run -> dry_run_proof_id -> approval required`.
- Keep real Grafana import/publish mutation disabled unless a matching dry-run proof and explicit human approval id exist.
- Extend AI Base Dashboard try-run to produce a dry-run proof summary when Metrics returns `ready_for_dry_run`.
- Show dry-run proof status and approval requirement in the AI Base Dashboard Query Agent page.
- Add a short human runbook for E2E dashboard AI dry-run workflow usage.

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `dashboard-ai-sidecar-integration`: add visible dry-run proof and approval-gated mutation workflow behavior.
- `provider-ai-dashboard-composition`: clarify that workflow result can proceed to dry-run proof, but not mutation, without human approval.

## Impact

- Dashboard specs/docs/runbook.
- AI Base connector try-run helper, tests, and Dashboard Query Agent UI.
- Existing gcx CLI runner dry-run proof store and approval checks are reused; no direct Grafana mutation is enabled by this change.
