## Context

Dashboard already exposes provider/profile catalog, AI workflow validation and approved publish demo endpoints. AI Base already has a workspace catalog and chat sessions can bind to workspaces. The missing architecture layer is a durable context bundle pushed from Metrics into an AI Base workspace so the agent can answer and draft from project-specific context rather than guessing.

## Goals / Non-Goals

**Goals:**
- Define a Metrics context bundle shape for `provider + project + profile`.
- Expose canonical low-level data blocks close to provider facts.
- Keep provider-native fields as provenance, not AI-facing field names.
- Let AI Base store the bundle under an existing workspace.

**Non-Goals:**
- Do not implement arbitrary AI-generated Grafana JSON validation in this first slice.
- Do not add production artifact publish governance beyond the already implemented approved demo.
- Do not expose provider credentials or native provider query editing to AI.

## Decisions

1. **Use workspace as the AI interaction boundary.**
   A Metrics workspace maps to one provider/project/profile boundary. Multiple chat sessions can use the workspace, but generated artifacts and context stay inside the same boundary.

2. **Publish files, not only API responses.**
   Metrics context is represented as named files such as `metrics-context/workspace-boundary.json`, `data-block-catalog.json` and `grafana-render-contract.json`. This makes the context usable by AI Base source import, retrieval and future custom agents.

3. **Expose canonical lego blocks first.**
   The first catalog includes item-level quality facts and weekly quality buckets. The shape is intentionally close to raw provider facts but remapped to canonical names.

## Risks / Trade-offs

- [Risk] Workspace context can become stale. -> Mitigation: include bundle version, generated timestamp and profile mapping hash.
- [Risk] AI may over-trust canonical fields. -> Mitigation: every artifact still needs Metrics validation before publish.
- [Risk] Two repos must stay in sync. -> Mitigation: use shared contract examples and focused tests on both sides.
