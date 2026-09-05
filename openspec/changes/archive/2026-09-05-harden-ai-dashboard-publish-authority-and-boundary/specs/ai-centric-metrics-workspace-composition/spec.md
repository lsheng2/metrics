## MODIFIED Requirements

### Requirement: Workspace boundary is provider and project scoped
Metrics SHALL define workspace boundaries that prevent AI sessions and connector invocations from crossing the selected provider/project/profile.

#### Scenario: Workspace boundary is included
- **WHEN** a context bundle is produced
- **THEN** it SHALL include allowed provider ids, profile ids, project labels, range modes and permitted data-block ids
- **THEN** AI Base SHALL bind chats, generated artifacts and model-visible connector operations to that boundary

#### Scenario: Connector invocation crosses workspace boundary
- **WHEN** a model-visible connector operation attempts to use a provider/profile/project outside the active workspace boundary
- **THEN** AI Base SHALL block the invocation before calling Metrics Dashboard
