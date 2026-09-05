# ai-centric-metrics-workspace-composition Specification

## Purpose
Defines the AI-centric workspace model where Metrics publishes bounded provider/project context into AI Base workspaces so AI can reason over canonical data blocks and create draft artifacts without guessing provider-specific fields.

## Requirements

### Requirement: Metrics exposes workspace context bundles
Metrics SHALL expose a context bundle for a selected provider/project/profile that AI Base can store in a workspace.

#### Scenario: HSD-ES workspace context is requested
- **WHEN** AI Base or an operator requests the context bundle for profile `nvu-ttl-hsdes`
- **THEN** Metrics SHALL return workspace boundary metadata, provider profile metadata, canonical field mappings, data-block catalog, Grafana render constraints and Metrics help content
- **THEN** the bundle SHALL identify `provider_id=hsdes`, `profile_id=nvu-ttl-hsdes` and project labels for NVU
- **THEN** the bundle SHALL include generic app-workspace fields `source_app_id`, `workspace_key`, `workspace_name`, `bundle_version`, `boundary` and `files`

#### Scenario: Jira workspace context is requested
- **WHEN** AI Base or an operator requests the context bundle for profile `chiplet-2a-jira`
- **THEN** Metrics SHALL return the same bundle shape with `provider_id=jira` and Jira project labels
- **THEN** AI-facing fields SHALL use Metrics canonical names rather than Jira custom field ids

### Requirement: Data blocks are close to provider facts but canonicalized
Metrics SHALL describe low-level lego blocks close to provider raw facts while exposing only canonical field names to AI and Grafana.

#### Scenario: Quality facts data block is listed
- **WHEN** the bundle includes quality work-item facts
- **THEN** the data block SHALL expose canonical fields such as `work_item_id`, `title`, `status`, `severity`, `owner`, `component`, `created_at`, `updated_at`, `closed_at`, `milestone`, `project`, `ip` and `source_url`
- **THEN** the data block SHALL include provider-native provenance separately from AI-facing field names

#### Scenario: AI requests provider-native fields
- **WHEN** a generated artifact references provider-native field names such as Jira custom fields or HSD-ES article paths
- **THEN** Metrics SHALL reject the artifact validation rather than treating those names as approved canonical fields

### Requirement: Workspace boundary is provider and project scoped
Metrics SHALL define workspace boundaries that prevent AI sessions and connector invocations from crossing the selected provider/project/profile.

#### Scenario: Workspace boundary is included
- **WHEN** a context bundle is produced
- **THEN** it SHALL include allowed provider ids, profile ids, project labels, range modes and permitted data-block ids
- **THEN** AI Base SHALL bind chats, generated artifacts and model-visible connector operations to that boundary

#### Scenario: Connector invocation crosses workspace boundary
- **WHEN** a model-visible connector operation attempts to use a provider/profile/project outside the active workspace boundary
- **THEN** AI Base SHALL block the invocation before calling Metrics Dashboard

### Requirement: Context files declare role and visibility
Metrics SHALL label every context file with role and visibility so AI Base can decide whether the file is model context, catalog-only context, or internal context.

#### Scenario: Context file metadata is included
- **WHEN** Metrics produces a workspace context bundle
- **THEN** every file SHALL include path, content type, role and visibility
- **THEN** files intended for model grounding SHALL use `model_context`
- **THEN** files intended for discovery but not automatic prompt injection SHALL use `catalog_only`

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
