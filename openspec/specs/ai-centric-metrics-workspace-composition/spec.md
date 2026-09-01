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
Metrics SHALL define workspace boundaries that prevent AI sessions from crossing the selected provider/project/profile.

#### Scenario: Workspace boundary is included
- **WHEN** a context bundle is produced
- **THEN** it SHALL include allowed provider ids, profile ids, project labels, range modes and permitted data-block ids
- **THEN** AI Base SHALL be able to bind chats and generated artifacts to that boundary
