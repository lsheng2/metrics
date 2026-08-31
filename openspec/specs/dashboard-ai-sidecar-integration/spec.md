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
