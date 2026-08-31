## ADDED Requirements

### Requirement: AI workflow envelope is provider neutral
Metrics SHALL expose a workflow envelope for AI dashboard requests that describes profile、range、chart recipe、requested series、validation、draft preview、precondition and audit state without embedding provider-native query language.

#### Scenario: Workflow envelope is returned
- **WHEN** a user submits an AI chart request through the dashboard workflow
- **THEN** Metrics SHALL return a structured envelope containing profile id, provider id, dashboard uid, chart id, requested series, range mode, range bounds, intent validation result, render config preview summary, gcx precondition result and safe user-facing guidance

#### Scenario: Provider-native secrets are present in source configuration
- **WHEN** the selected profile contains Jira JQL、HSD-ES saved query metadata、credentials、tokens、private paths or native field mappings
- **THEN** the workflow envelope SHALL omit or redact those values and SHALL expose only approved catalog/profile provenance, canonical metric names and safe artifact references

### Requirement: AI generated chart workflow is preview-first
AI dashboard workflow SHALL treat generated render configs as drafts until validation and precondition checks complete.

#### Scenario: Draft render config is valid
- **WHEN** intent validation produces a render config draft and Metrics render-config validation passes
- **THEN** the workflow SHALL show the draft as previewable and eligible for gcx dry-run or import precondition, not as already published

#### Scenario: Draft render config is invalid
- **WHEN** render-config validation fails
- **THEN** the workflow SHALL show structured findings and SHALL NOT expose a publish-ready state

### Requirement: Jira and HSD-ES profiles share the same AI composition surface
Metrics SHALL use the same AI dashboard composition workflow for Jira and HSD-ES profiles, with provider differences handled by profile registry、fact adapters、chart recipes and render config validation rather than separate UI logic.

#### Scenario: Jira first provider uses the workflow
- **WHEN** profile `chiplet-2a-jira` is selected for an AI dashboard request
- **THEN** Metrics SHALL validate the request through the same catalog, intent and render-config endpoints used for HSD-ES

#### Scenario: HSD-ES second provider uses the workflow
- **WHEN** profile `nvu-ttl-hsdes` is selected for an AI dashboard request
- **THEN** Metrics SHALL validate the request through the same catalog, intent and render-config endpoints used for Jira
