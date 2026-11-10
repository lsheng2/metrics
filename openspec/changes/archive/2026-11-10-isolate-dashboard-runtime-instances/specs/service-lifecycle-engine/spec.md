## ADDED Requirements

### Requirement: Runtime instance identity is the local runtime authority
系统 SHALL expose an app-neutral runtime instance identity containing a project namespace and an instance id safe for lifecycle keys, filenames, local namespaces, telemetry attributes, and generated runtime projections.

#### Scenario: Stable identity derivation
- **WHEN** a local launcher derives an identity from the same project name, seed, and label
- **THEN** the derived instance id SHALL be stable across repeated invocations
- **AND** a different seed SHALL produce a different instance id

#### Scenario: Unsafe identity is rejected
- **WHEN** a caller supplies an identity containing path traversal, whitespace, or shell-unsafe characters
- **THEN** the lifecycle engine SHALL reject the identity before it can be used in state paths, namespace keys, or stop authority decisions

### Requirement: Runtime resource namespaces isolate local projections
系统 SHALL derive resource namespaces from a runtime instance identity so local services can isolate ports, state directories, database names, compose project names, queue/key prefixes, and telemetry attributes without embedding project-specific service topology in the generic engine.

#### Scenario: Namespace includes instance identity
- **WHEN** a project adapter asks the engine to derive a namespace for a service group
- **THEN** the namespace SHALL include the runtime project name, instance id, service group, safe state directory name, safe database name, safe compose project name, telemetry attributes, and declared ports

#### Scenario: Invalid port is rejected
- **WHEN** a namespace declares a port outside the TCP port range
- **THEN** the lifecycle engine SHALL reject the namespace

### Requirement: External service mode controls stop authority
系统 SHALL model external services as `dedicated`, `shared_consumed`, or `shared_managed`, and SHALL return explicit stop authority decisions for an actor identity.

#### Scenario: Dedicated owner may stop service
- **WHEN** a runtime instance owns a dedicated service
- **THEN** the owner actor SHALL be allowed to stop the service
- **AND** a different actor SHALL be denied unless force is explicitly requested

#### Scenario: Shared consumer cannot stop external service
- **WHEN** a runtime instance consumes a shared external service managed by another owner
- **THEN** the consumer SHALL NOT be allowed to stop the external service
- **AND** the decision SHALL allow clearing only the local binding when appropriate

### Requirement: Runtime isolation conflicts are detected before launch
系统 SHALL expose a generic conflict detector that reports duplicate instance/service declarations, duplicate namespaces, and duplicate ports across runtime bindings.

#### Scenario: Duplicate service instance is detected
- **WHEN** two bindings claim the same project instance and service name
- **THEN** the conflict detector SHALL report a duplicate instance/service conflict

#### Scenario: Duplicate namespace is detected
- **WHEN** two bindings use the same namespace prefix
- **THEN** the conflict detector SHALL report a duplicate namespace conflict

#### Scenario: Duplicate port is detected
- **WHEN** two bindings declare the same local port
- **THEN** the conflict detector SHALL report a duplicate port conflict

### Requirement: Dashboard launcher consumes one durable runtime profile
Scrum Dashboard SHALL use one durable runtime profile per local workspace as the authority for profile-managed E2E service identity, lifecycle state root, and primary local ports.

#### Scenario: Profile is created once and reused
- **WHEN** the Dashboard E2E launcher starts without an explicit runtime instance id
- **THEN** it SHALL create `state/local/runtime-instance.json` when absent
- **AND** later starts in the same workspace SHALL reuse the stored instance id

#### Scenario: Generated env is not authority
- **WHEN** Dashboard writes `state/local/worktree-runtime.env`
- **THEN** the file SHALL be a generated compatibility projection of `runtime-instance.json`
- **AND** launcher code SHALL NOT treat the env projection as more authoritative than explicit CLI/env values or the durable JSON profile

#### Scenario: Repeated worktree start reuses lifecycle state root
- **WHEN** the same Dashboard worktree is started repeatedly
- **THEN** the launcher SHALL use the same lifecycle instance name and state root
- **AND** restart/stop SHALL target the previously registered services for that runtime instance before selecting fallback ports
