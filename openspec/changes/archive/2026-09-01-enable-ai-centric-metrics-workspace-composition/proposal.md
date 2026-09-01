## Why

The current AI dashboard flow is safe but chart-recipe centric: AI can only select an approved chart recipe and minor render options. The next architecture step is to make AI Base workspaces the interaction boundary for Metrics projects, so AI can reason from Metrics-published provider/project context, canonical data blocks and Grafana constraints without guessing or leaving the selected provider/project boundary.

## What Changes

- Add a Metrics workspace context bundle contract for one provider/project/profile.
- Expose low-level canonical data-block metadata that is close to provider raw facts but uses Metrics canonical field names.
- Include workspace boundary, provider profile, data-block catalog, Grafana render contract and Metrics help files in the bundle.
- Define AI Base workspace synchronization as the preferred communication model for future AI chart composition.

## Capabilities

### New Capabilities

- `ai-centric-metrics-workspace-composition`: Defines Metrics-owned workspace context bundles, canonical data blocks and AI Base workspace boundaries for AI-centric dashboard composition.

### Modified Capabilities

- `dashboard-ai-sidecar-integration`: Adds workspace-context synchronization as the preferred AI Base integration surface beyond stateless connector calls.
- `provider-ai-dashboard-composition`: Adds canonical low-level data blocks as the composition input for future AI-generated Grafana artifacts.

## Impact

- Dashboard API/docs/specs for context bundle generation.
- AI Base workspace/catalog integration in a paired change.
- No provider write actions, no raw provider credentials and no arbitrary Grafana publish in this slice.
