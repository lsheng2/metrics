# Local Runtime Instance Isolation

## Purpose

Scrum Dashboard local development needs one runtime identity for each local workspace instance. Port allocation alone is not enough: two starts can use different ports and still collide through lifecycle state, PID files, logs, Grafana runtime files, endpoint settings, Redis queues, DB names, Docker compose projects, telemetry attributes, browser caches, or stop authority.

This design makes `state/local/runtime-instance.json` the durable authority for the local Dashboard runtime instance. Generated files such as `state/local/worktree-runtime.env` are compatibility projections, not the source of truth.

## Authority Order

1. Explicit CLI arguments or process environment selected by the operator.
2. Durable `state/local/runtime-instance.json`.
3. Generated `state/local/worktree-runtime.env` projection.
4. Built-in single-workspace defaults.

The launcher may accept explicit overrides for one invocation, but normal start/restart/stop behavior should resolve the same durable runtime identity every time.

## Generic Lifecycle Engine Role

`scripts/service_lifecycle_engine` owns the project-neutral primitives:

- `RuntimeInstanceIdentity`
- `RuntimeResourceNamespace`
- `ExternalServiceMode`
- `ExternalServiceBinding`
- `StopAuthorityDecision`
- `detect_runtime_isolation_conflicts(...)`
- runtime isolation conformance checks

The generic engine does not know Dashboard service names, VS Code task labels, Grafana config paths, AI Base endpoints, Jira profiles, Docker compose files, or local browser behavior.

## Dashboard Adapter Role

`scripts/dashboard_runtime_instance_profile.py` maps one Dashboard instance id to Dashboard-specific projections:

| Projection | Derived From |
| --- | --- |
| Lifecycle instance name | runtime instance id |
| Lifecycle state root | `state/local/instances/<instance_id>/service-lifecycle-engine` |
| Runtime logs and PID files | lifecycle state root |
| Dashboard primary port | profile `django` port |
| Grafana primary port | profile `grafana` port |
| Generated env projection | durable runtime profile |
| Dashboard service namespace | runtime identity plus `dashboard` service group |
| External service bindings | runtime identity plus declared service mode |

The E2E service config keeps fallback port lists. The profile only chooses the primary preferred port; fallback remains available when a foreign process blocks the preferred port or when the operator explicitly requests force-by-port cleanup.

## External Service Mode

Default local Dashboard-owned services use `dedicated` mode:

- `django`
- `grafana`

Cross-project services use `shared_consumed` unless Dashboard is explicitly made the owner:

- AI Base backend
- AI Base frontend
- external LiteLLM gateway

A shared-consumed binding may clear local Dashboard binding/projection state, but it must not stop the external listener. Dedicated and shared-managed services require the actor identity to match the owner unless the operator explicitly requests force.

## Start Flow

1. The launcher resolves the workspace.
2. It reads `state/local/runtime-instance.json` when present.
3. If no profile exists, it creates one using the workspace path as the stable seed and `default` as the port profile.
4. It refreshes `state/local/worktree-runtime.env`.
5. It starts Dashboard services using the profile instance id, profile state root and profile primary ports.
6. It still writes `state/e2e/bug_trend_ports.json` as the compatibility summary consumed by existing Dashboard AI stack tooling.

## Stop Flow

1. Stop resolves the same runtime profile.
2. The lifecycle engine stops services registered under the profile-derived state root.
3. Shared-consumed external services are not stopped by Dashboard lifecycle.
4. Explicit force-by-port remains an operator action and is reported separately from kill escalation.

## Why This Also Helps The Main Worktree

The main worktree can accidentally start one logical service on multiple ports when each launcher invocation re-derives a different identity or only knows the last registered port. A durable runtime profile makes repeated starts use the same instance id and state root, so restart/stop first targets the previously registered service before selecting fallback ports.

This does not remove the need for inventory. The follow-up all-worktree inventory should scan sibling profiles, live listeners and Docker-published ports, then call `detect_runtime_isolation_conflicts(...)` before starting a new stack.

## VS Code Task Naming

Task labels should make scope visible:

- `Current Worktree: Dashboard AI Stack: Start`
- `Current Worktree: Dashboard AI Stack: Stop`
- `Current Worktree: Dashboard AI Stack: Restart`
- `All Worktrees: Dashboard Ports Inventory`
- `All Worktrees: Stop Dashboard Project Services`

Current-worktree tasks only operate on the selected runtime profile. All-worktree tasks scan Git-registered Dashboard worktrees and make destructive cleanup explicit.

## Validation

The first implementation pass is covered by:

- runtime isolation unit tests for generic identity, namespace, stop authority and conflict detection;
- conformance checks exported by `service_lifecycle_engine`;
- Dashboard profile adapter tests for durable JSON, generated env projection, service bindings and state roots;
- launcher tests proving E2E uses the profile-derived instance and preferred primary ports;
- Dashboard AI stack script tests proving lifecycle state path is profile-derived.
