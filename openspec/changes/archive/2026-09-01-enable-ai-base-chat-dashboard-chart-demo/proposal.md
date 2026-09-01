## Why

The Dashboard and AI Base workflow contracts now validate chart drafts and expose dry-run proof state, but a human still needs a direct way to exercise this from the AI Base Chat page. A deterministic chat shortcut gives a reliable E2E demo path before depending on model-specific tool-call behavior.

## What Changes

- Add an AI Base chat shortcut for Dashboard chart authoring requests such as “Create a weekly open bug trend chart for chiplet Jira from 26WW32 to 26WW35, only new critical/high.”
- The shortcut calls the existing Metrics connector `workflow.run` path and returns provider/profile, validation, gcx precondition, dry-run proof and approval-required summary in the chat response.
- Unsupported series continue to return `needs_metric_recipe` and do not create a proof.
- Update the Dashboard human runbook with the AI Base Chat demo steps.

## Capabilities

### New Capabilities

- 无。

### Modified Capabilities

- `dashboard-ai-sidecar-integration`: add deterministic AI Base Chat demo path for Dashboard chart authoring workflow.

## Impact

- AI Base chat shortcut handling and tests.
- Dashboard validation runbook.
- No new provider writes or Grafana mutations.
