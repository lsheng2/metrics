## Context

Dashboard already validates AI chart intent, render config and gcx precondition through `workflow.run`. The local E2E stack already imports Grafana dashboards through the Grafana HTTP API using the built-in admin credentials. The current AI Base Chat demo records a proof summary but does not execute a visible publish.

## Goals / Non-Goals

**Goals:**
- Add a local-only demo publish endpoint that can make an approved AI chart visible in the E2E Grafana instance.
- Preserve Metrics ownership of render config generation, validation, import target and audit.
- Return a user-facing dashboard URL suitable for manual verification.

**Non-Goals:**
- No cloud/shared Grafana production publishing.
- No arbitrary AI-authored Grafana JSON import.
- No full enterprise approval workflow UI.
- No provider write action.

## Decisions

1. **Dashboard owns local publish.**
   AI Base should not generate or import arbitrary dashboard JSON. It calls a Dashboard endpoint, and Dashboard reruns the same workflow validation before import.

2. **Use explicit approval id and dry-run proof id as request gates.**
   This keeps the existing approval boundary observable even though the local E2E demo does not yet have a full approval UI.

3. **Use local Grafana HTTP API for the demo.**
   The current E2E stack already configures a local Grafana datasource and dashboard import path. The publish endpoint reuses that pattern via a configurable Grafana base URL, defaulting to `http://127.0.0.1:3001`.

## Risks / Trade-offs

- [Risk] Local demo publish could be mistaken for production governance. -> Mitigation: endpoint name and response state identify it as a local approved demo.
- [Risk] Grafana may run on a non-default port. -> Mitigation: add an environment knob and have the stack script set it.
- [Risk] Revalidating workflow changes the generated correlation id. -> Mitigation: caller supplies correlation id for audit and response.
