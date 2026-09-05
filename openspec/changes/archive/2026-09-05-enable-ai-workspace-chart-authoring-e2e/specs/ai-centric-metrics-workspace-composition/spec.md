## ADDED Requirements

### Requirement: AI Base chat is grounded by Metrics workspace context
Metrics SHALL publish enough workspace context for AI Base chat sessions to answer project boundary、canonical field、data block 和 Grafana constraint questions without guessing provider-native details.

#### Scenario: User asks available data blocks
- **WHEN** a chat session is bound to a Metrics-synchronized AI Base workspace
- **THEN** the AI answer SHALL use the workspace context bundle data-block catalog to list available block ids, grain, canonical dimensions, measures, allowed transforms and evidence capability
- **THEN** the answer SHALL NOT introduce provider-native fields as chart-authoring fields unless the context bundle marks them as provenance examples only

#### Scenario: User asks workspace boundary
- **WHEN** a user asks what provider/project/profile the workspace represents
- **THEN** the AI answer SHALL cite the workspace boundary context and identify allowed provider ids, profile ids, project labels, range modes and permitted data blocks
- **THEN** the answer SHALL not claim access outside that workspace boundary

#### Scenario: Context is incomplete
- **WHEN** the workspace context does not include data-block catalog, canonical field map or boundary metadata
- **THEN** AI Base SHALL report the missing context and request a workspace sync instead of inventing chart fields or provider semantics
