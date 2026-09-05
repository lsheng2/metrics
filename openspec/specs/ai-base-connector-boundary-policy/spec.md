# ai-base-connector-boundary-policy Specification

## Purpose
TBD - created by archiving change harden-ai-dashboard-publish-authority-and-boundary. Update Purpose after archive.

## Requirements

### Requirement: Connector model-visible tools are workspace-bound
AI Base SHALL enforce the active app workspace boundary before invoking model-visible connector operations.

#### Scenario: Model supplies a matching profile
- **WHEN** a chat session is bound to a Metrics workspace context
- **AND** the model calls a Metrics connector operation with profile/provider/workspace arguments matching the active workspace boundary
- **THEN** AI Base MAY invoke the connector operation

#### Scenario: Model supplies a different profile
- **WHEN** a chat session is bound to one Metrics workspace context
- **AND** the model calls a connector operation with a different provider id, profile id, workspace key or project scope
- **THEN** AI Base SHALL block the operation before sending an HTTP request to Dashboard

#### Scenario: Chat session has no Metrics workspace binding
- **WHEN** the model calls a Metrics connector operation that requires provider/project context
- **THEN** AI Base SHALL block the operation and instruct the user to sync/select a Metrics workspace context first

### Requirement: Connector operations declare sensitivity
AI Base SHALL require connector operation policy metadata before exposing operations as runtime tools.

#### Scenario: Operation can mutate or publish
- **WHEN** a connector operation can publish, mutate, callback, approve or import external resources
- **THEN** it SHALL NOT be model-visible
- **THEN** it SHALL require explicit governed workflow execution and approval policy

#### Scenario: Model-visible operation lacks safe policy
- **WHEN** a connector operation is marked model-visible without declaring read/validate-only sensitivity
- **THEN** AI Base SHALL fail closed and not expose it as a runtime tool

### Requirement: Connector transport verifies local sidecar identity
AI Base SHALL verify configured Dashboard connector identity before sending app context, user prompts, artifact refs or mutation requests.

#### Scenario: Expected Dashboard service responds
- **WHEN** AI Base initializes or first invokes the Dashboard connector
- **THEN** it SHALL verify the expected service id, profile/capability summary and optional instance token before enabling connector calls

#### Scenario: Wrong service responds on the port
- **WHEN** the configured base URL responds but identity does not match the Dashboard connector contract
- **THEN** AI Base SHALL block the connector call

### Requirement: Loopback connector calls bypass environment proxies
AI Base SHALL avoid leaking local connector payloads through environment HTTP proxies.

#### Scenario: Connector base URL is loopback
- **WHEN** connector base URL uses `127.0.0.1`, `localhost` or `[::1]`
- **THEN** AI Base SHALL create HTTP clients with environment proxy trust disabled
