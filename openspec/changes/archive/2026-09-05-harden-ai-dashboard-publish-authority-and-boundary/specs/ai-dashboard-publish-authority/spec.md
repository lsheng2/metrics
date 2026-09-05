## ADDED Requirements

### Requirement: Publish authorization is a bound authority object
Dashboard SHALL NOT publish an AI-generated Grafana dashboard from independently supplied approval/proof strings.

#### Scenario: Publish authorization is requested
- **WHEN** AI Base or an operator requests publish authorization
- **THEN** Dashboard SHALL create an authorization record containing profile id, provider id, workspace key, dashboard uid, chart id, requested series, range mode, range bounds, artifact ref, artifact version, artifact content hash, dry-run proof id, actor, status, created time and expiry
- **THEN** the initial status SHALL be `pending_approval`

#### Scenario: Human approval is granted
- **WHEN** a human approves the authorization record
- **THEN** Dashboard SHALL mark only that exact authorization id as `approved`
- **THEN** Dashboard SHALL retain the original bound tuple and SHALL NOT let the approval mutate scope, artifact, proof or range

#### Scenario: Publish is requested
- **WHEN** publish is requested for a Grafana mutation
- **THEN** Dashboard SHALL require an approved, non-expired authorization whose bound tuple matches the publish request
- **THEN** Dashboard SHALL reject forged, missing, pending, rejected, expired, or mismatched authorization ids before Grafana import
- **THEN** Dashboard SHALL regenerate and validate the render config before import

#### Scenario: Local demo approval prefix is supplied
- **WHEN** a caller supplies an approval id using a local demo prefix without a persisted approved authorization
- **THEN** Dashboard SHALL reject the publish request
- **THEN** Dashboard SHALL NOT auto-create approval records from approval id prefixes or chat text

### Requirement: Dry-run proof is bound to artifact version
Dashboard and AI Base SHALL treat dry-run proof as evidence for one immutable artifact version and scope tuple.

#### Scenario: Dry-run proof is checked
- **WHEN** a publish authorization or publish request references a dry-run proof id
- **THEN** the proof id SHALL be associated with artifact ref, artifact version, content hash, workspace key, profile id, range and operation
- **THEN** mismatched proof scope SHALL block publish

### Requirement: Publish history remains auditable
Dashboard SHALL record approved publish transitions with enough metadata to reconstruct the authorization decision.

#### Scenario: Publish succeeds
- **WHEN** Grafana import succeeds
- **THEN** Dashboard SHALL record publish history with authorization id, artifact ref/version/hash, dry-run proof id, actor, profile/provider, range, chart id, series, dashboard uid, Grafana URL and correlation id
