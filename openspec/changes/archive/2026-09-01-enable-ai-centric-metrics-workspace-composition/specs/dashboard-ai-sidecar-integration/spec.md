## ADDED Requirements

### Requirement: Dashboard can synchronize Metrics context into AI Base workspaces
Dashboard SHALL support AI Base workspace synchronization as an integration surface in addition to stateless connector operations.

#### Scenario: Workspace context is synchronized
- **WHEN** Dashboard connects to AI Base for a selected provider/profile
- **THEN** Dashboard SHALL be able to push a Metrics context bundle into an AI Base workspace
- **THEN** the workspace SHALL remain bounded to the selected provider/project/profile for subsequent chat sessions
