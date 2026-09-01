# dashboard-ai-sidecar-integration Specification

## Purpose
Dashboard AI Sidecar Integration 定义 Metrics dashboard 如何把 AI Base 作为可选 AI platform 使用，让用户通过 sidecar/chat 请求 dashboard insight、chart draft、Grafana operation，同时保持 Metrics 对 provider data、chart semantics、validator 和 publication audit 的所有权。

## Requirements

### Requirement: Dashboard sidecar uses AI Base as optional platform
Metrics dashboard SHALL integrate AI Base as an optional sidecar/platform dependency, not as a required runtime component for provider sync、cache、Grafana rendering or approved dashboard APIs.

#### Scenario: AI Base is unavailable
- **WHEN** AI Base is not installed, not running, disabled, or fails handshake
- **THEN** Metrics dashboard SHALL continue to support provider profile selection, provider sync/cache, approved chart APIs, Grafana render config generation, evidence APIs and non-AI dashboard usage

#### Scenario: AI Base is available
- **WHEN** AI Base handshake succeeds for the configured dashboard profile
- **THEN** Metrics dashboard MAY expose AI entry points that call AI Base with bounded context and SHALL keep all non-AI paths source-compatible

### Requirement: Sidecar handshake is identity-checked
Dashboard SHALL verify AI Base sidecar identity before treating any local service as the active sidecar.

#### Scenario: Expected sidecar responds
- **WHEN** Dashboard probes AI Base
- **THEN** Dashboard SHALL verify `serviceId`, optional `instanceToken`, profile id, health path and app capability summary before enabling AI UI

#### Scenario: Wrong sidecar responds on the port
- **WHEN** a local HTTP service responds but service identity or instance token does not match the configured sidecar
- **THEN** Dashboard SHALL treat AI as unavailable and SHALL NOT send dashboard context, user prompts or artifact references to that service

### Requirement: Dashboard-to-AI request context is bounded
Dashboard SHALL send AI Base a structured context envelope instead of raw database access, raw provider credentials, raw Jira/HSD-ES native query text, or unrestricted filesystem paths.

#### Scenario: User asks from dashboard page
- **WHEN** a user asks the sidecar to explain, modify, or create a chart from an active dashboard
- **THEN** Dashboard SHALL include selected `profile_id`, dashboard uid, range mode, WW/date range, selected panel context, allowed operation mode, correlation id and Metrics catalog URLs

#### Scenario: Context includes sensitive fields
- **WHEN** source profile metadata contains native queries, credentials, tokens, private paths or provider auth details
- **THEN** Dashboard SHALL redact or omit those fields before sending the context to AI Base

### Requirement: AI Base calls Metrics contracts before generating outputs
AI Base SHALL use Metrics-provided catalog、intent validation、draft render validation、evidence and precondition APIs before returning chart or dashboard operation outputs.

#### Scenario: Metrics connector routes are published
- **WHEN** AI Base profile `dashboard_query_agent` is configured with the Metrics connector
- **THEN** it SHALL call Dashboard-owned HTTP contracts:
  - `GET /api/ai-dashboard/catalog/`
  - `POST /api/ai-dashboard/intent/validate/`
  - `POST /api/ai-dashboard/render-config/validate/`
  - `POST /api/ai-dashboard/gcx/precondition/`
  - `POST /api/ai-dashboard/gcx/publication-callback/`
  - `GET /api/ai-dashboard/context/`
- **AND** Dashboard SHALL keep these routes provider/profile neutral and backed by Metrics-owned profile registry、chart recipes、Grafana render config validator、provider facts and aggregate artifacts

#### Scenario: AI creates a chart draft
- **WHEN** user requests a chart change
- **THEN** AI Base SHALL call Metrics catalog/intent validation and SHALL return either a validated draft render config, structured validation findings, or `needs_metric_recipe`

#### Scenario: User requests unsupported semantics
- **WHEN** user asks for a series such as `new_critical` but Metrics only approves `new_critical_high`
- **THEN** AI Base SHALL preserve the exact series identity, return `needs_metric_recipe`, and SHALL NOT rename, filter, relabel or synthesize unsupported Metrics semantics

### Requirement: gcx operations are Metrics-preconditioned
AI Base/gcx SHALL NOT mutate Grafana resources for Metrics dashboards unless Metrics precondition validation has passed for the exact artifact and operation.

#### Scenario: Draft render config is invalid
- **WHEN** gcx import or push is requested for an invalid render config or generated dashboard
- **THEN** AI Base SHALL call Metrics precondition validation and SHALL block the gcx mutation before any Grafana mutation command runs

#### Scenario: Draft render config is valid
- **WHEN** Metrics precondition validation passes for the draft artifact
- **THEN** AI Base MAY run approved gcx validate/dry-run operations and SHALL require configured approval before any write/import/push mutation

### Requirement: AI Base exposes reusable platform surfaces
AI Base SHALL expose reusable platform primitives for application-owned AI enablement instead of hardcoding Dashboard-specific logic into shared runtime.

#### Scenario: Dashboard registers as fourth app profile
- **WHEN** Dashboard uses AI Base as `dashboard_query_agent`
- **THEN** AI Base SHALL load the profile through the same manifest/profile mechanism used by Sample、Report Creator and SoC AI Driver

#### Scenario: Dashboard needs app-specific tools
- **WHEN** Dashboard enables Metrics connector、gcx CLI tools or dashboard workflow adapters
- **THEN** AI Base SHALL register them through profile-scoped extension lanes and SHALL NOT expose them to other profiles unless those profiles explicitly opt in

### Requirement: Sidecar results are auditable and replayable
Dashboard/AI Base interactions SHALL carry structured correlation, result envelope, approval and artifact metadata.

#### Scenario: AI returns insight or draft
- **WHEN** AI Base completes a dashboard request
- **THEN** the response SHALL include status, correlation id, selected profile/range, used Metrics catalog versions, validation findings, generated artifact refs and safe user-facing summary

#### Scenario: AI/gcx mutation succeeds
- **WHEN** gcx mutates Grafana after approval
- **THEN** AI Base SHALL emit a structured operation result and Dashboard/Metrics SHALL record publication/audit metadata without exposing raw secrets or provider credentials

### Requirement: Dashboard exposes an operator-facing AI sidecar workflow
Metrics dashboard SHALL expose an operator-facing workflow that lets a user run the AI dashboard composition contract from a selected provider profile without requiring direct API calls.

#### Scenario: Sidecar workflow page opens
- **WHEN** a user opens the AI sidecar workflow surface
- **THEN** the system SHALL show AI sidecar readiness, configured AI Base profile, supported capabilities, selected provider profile, range, chart recipe, requested series, validation result, draft preview status and gcx precondition status

#### Scenario: Sidecar is unavailable
- **WHEN** AI Base is disabled, unavailable, identity-mismatched or missing required dashboard capabilities
- **THEN** the workflow SHALL still allow Metrics-local validation of catalog、intent、render config and gcx precondition, while clearly showing that external AI Base orchestration is not ready

### Requirement: Workflow validates supported and unsupported requests explicitly
Metrics dashboard SHALL provide deterministic try-run scenarios for supported and unsupported AI chart requests so operators can understand whether a request is ready to publish or requires Metrics-owned semantic work.

#### Scenario: Supported HSD-ES request produces draft
- **WHEN** the workflow validates profile `nvu-ttl-hsdes` for chart `open_bug_trend` with requested series `new_critical_high`
- **THEN** the result SHALL be `draft_validated` with a safe render config preview and SHALL NOT expose native HSD-ES query text, credentials or private paths

#### Scenario: Unsupported HSD-ES semantic is blocked
- **WHEN** the workflow validates profile `nvu-ttl-hsdes` for chart `open_bug_trend` with requested series `new_critical`
- **THEN** the result SHALL be `needs_metric_recipe`, SHALL preserve the exact requested series identity and SHALL NOT silently map it to `new_critical_high`

#### Scenario: Jira profile uses same workflow
- **WHEN** the workflow validates profile `chiplet-2a-jira` for chart `open_bug_trend` with requested series `new_critical_high`
- **THEN** the result SHALL use the same workflow envelope and validation statuses as HSD-ES without requiring provider-specific UI branches

### Requirement: gcx precondition is visible before any mutation
Metrics dashboard SHALL make the gcx mutation gate visible in the sidecar workflow before any Grafana import, push or publish action can be treated as executable.

#### Scenario: Draft passes precondition
- **WHEN** a validated draft render config is checked for `grafana_import`
- **THEN** the workflow SHALL show `precondition_passed`, mutation eligibility, approval policy and correlation metadata without performing a write mutation

#### Scenario: Draft fails precondition
- **WHEN** a draft render config fails Metrics validation
- **THEN** the workflow SHALL show `blocked`, structured findings and mutation disallowed before any gcx mutation command is run

### Requirement: AI Base prefers Dashboard workflow operation
AI Base Dashboard Query Agent SHALL use Dashboard `workflow.run` as the preferred end-to-end operation for chart try-runs when the connector contract exposes it.

#### Scenario: Workflow operation is available
- **WHEN** AI Base executes an open bug trend try-run and the Metrics connector exposes `workflow.run`
- **THEN** AI Base SHALL call `POST /api/ai-dashboard/workflow/` with profile id, dashboard uid, chart id, requested series, range and gcx operation, and SHALL display the returned intent/render/precondition states

#### Scenario: Workflow operation is unavailable
- **WHEN** AI Base runs against an older Dashboard connector contract without `workflow.run`
- **THEN** AI Base MAY fall back to catalog and intent validation operations without losing unsupported-series safety

### Requirement: Dashboard workflow page explains profile-driven Jira and HSD-ES paths
Dashboard AI workflow page SHALL make profile selection, provider identity, supported/unsupported status and next action visible for both Jira and HSD-ES profiles.

#### Scenario: Operator runs Jira workflow
- **WHEN** the operator selects `chiplet-2a-jira` and runs the workflow
- **THEN** the page SHALL show provider `jira`, validation status, render preview status, gcx precondition status and a next action without showing raw Jira credentials

#### Scenario: Operator runs unsupported series workflow
- **WHEN** the operator requests an unapproved series such as `new_critical`
- **THEN** the page SHALL show `needs_metric_recipe` and SHALL preserve the exact requested series

### Requirement: AI Grafana workflow records dry-run proof before mutation
AI Base Dashboard Query Agent SHALL create or surface a durable dry-run proof before any Grafana import, publish or push mutation is considered eligible.

#### Scenario: Workflow reaches dry-run state
- **WHEN** Dashboard `workflow.run` returns `ready_for_dry_run`
- **THEN** AI Base SHALL run or simulate the configured gcx dry-run path through the governed CLI runner, record a `dry_run_proof_id`, and show the proof status to the operator

#### Scenario: Workflow does not reach dry-run state
- **WHEN** Dashboard `workflow.run` returns `needs_metric_recipe`, `blocked`, validation failed, or precondition not checked
- **THEN** AI Base SHALL NOT create a dry-run proof and SHALL surface the blocking status instead

### Requirement: Human approval is required after dry-run proof
AI Base SHALL NOT execute Grafana mutation after dry-run proof unless an explicit human approval id is attached to the mutation request and the proof still matches.

#### Scenario: Dry-run proof exists without approval
- **WHEN** a valid dry-run proof exists but no approval id exists
- **THEN** UI SHALL show approval required and mutation SHALL remain unavailable

#### Scenario: Mutation is requested without matching proof
- **WHEN** a mutation request lacks a matching dry-run proof, matching scope, or matching artifact reference
- **THEN** AI Base SHALL block mutation before running gcx and SHALL NOT call Dashboard publication callback

### Requirement: AI Base chat can trigger Dashboard chart workflow demo
AI Base Dashboard Query Agent SHALL provide a deterministic chat path that can trigger a supported Dashboard chart workflow and return dry-run proof guidance.

#### Scenario: User asks for an approved Jira chart in chat
- **WHEN** a user asks AI Base Chat to create a weekly open bug trend chart for Jira `chiplet-2a-jira` from `26WW32` to `26WW35` with `new_critical_high`
- **THEN** AI Base SHALL call the Metrics connector workflow, return the validation and precondition states, include dry-run proof id when available, and state that human approval is required before Grafana mutation

#### Scenario: User asks for unsupported chart semantics in chat
- **WHEN** a user asks AI Base Chat for a series not approved by Metrics
- **THEN** AI Base SHALL return the `needs_metric_recipe` state and SHALL NOT create a dry-run proof

### Requirement: Approved AI chart publish demo creates a visible Grafana dashboard
Dashboard SHALL expose a local operator-approved publish step for AI-generated chart demos after dry-run proof is available.

#### Scenario: Approved publish imports a validated draft
- **WHEN** AI Base submits a publish request for `chiplet-2a-jira` with an approved `open_bug_trend` series, a dry-run proof id, and an explicit approval id
- **THEN** Dashboard SHALL regenerate and validate the Metrics-owned render config before import
- **THEN** Dashboard SHALL import the generated Grafana dashboard into the configured local Grafana instance
- **THEN** Dashboard SHALL return a visible Grafana URL for the imported dashboard
- **THEN** Dashboard SHALL record publication callback audit containing operation, actor, dashboard uid, correlation id and dry-run proof id

#### Scenario: Publish request lacks approval
- **WHEN** a publish request omits approval id or dry-run proof id
- **THEN** Dashboard SHALL reject the request before Grafana import
- **THEN** Dashboard SHALL NOT record a successful publication callback

#### Scenario: Publish request uses unsupported semantics
- **WHEN** a publish request asks for a series not approved by the Metrics chart recipe catalog
- **THEN** Dashboard SHALL return `needs_metric_recipe` or validation failure
- **THEN** Dashboard SHALL NOT import a Grafana dashboard
