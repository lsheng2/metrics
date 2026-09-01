## ADDED Requirements

### Requirement: AI Base chat can produce publishable Dashboard artifacts
Dashboard sidecar integration SHALL support a chat-triggered flow where AI Base creates a validated chart artifact and Dashboard remains the authority for validation, approval and Grafana publication.

#### Scenario: Chat request creates validated draft
- **WHEN** a user asks AI Base chat to create a supported Grafana chart for a synced Metrics workspace
- **THEN** AI Base SHALL use workspace context and Metrics validation contracts to produce a draft artifact
- **THEN** Dashboard SHALL return validation status, precondition status, correlation id and next action

#### Scenario: Chat request cannot be validated
- **WHEN** user asks for unsupported semantics, missing profile, missing range or unavailable data
- **THEN** the flow SHALL return a clear blocked state and SHALL NOT create a dry-run proof or approval-ready publish action

### Requirement: Human-approved publish is end-to-end auditable
Dashboard sidecar integration SHALL require dry-run proof and human approval before AI-generated chart artifacts mutate Grafana.

#### Scenario: Human-approved publish succeeds
- **WHEN** a validated artifact has matching dry-run proof and approval id
- **THEN** AI Base MAY request Dashboard publish
- **THEN** Dashboard SHALL regenerate or normalize the Grafana payload from the validated artifact, import it to Grafana, and return a visible dashboard URL
- **THEN** Dashboard SHALL record publish history with profile id, provider id, artifact id, correlation id, approval id, dry-run proof id, dashboard uid and status

#### Scenario: Publish lacks proof or approval
- **WHEN** publish is requested without matching dry-run proof or approval id
- **THEN** Dashboard SHALL reject the mutation before Grafana import
- **THEN** Dashboard SHALL return a structured blocking reason
