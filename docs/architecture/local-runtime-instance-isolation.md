# Local Runtime Instance Isolation

## Purpose

Scrum Dashboard local development needs one runtime identity for each local workspace instance. Port allocation alone is not enough: two starts can use different ports and still collide through lifecycle state, PID files, logs, Grafana runtime files, endpoint settings, Redis queues, DB names, Docker compose projects, telemetry attributes, browser caches, or stop authority.

`state/local/runtime-instance.json` is the durable authority for the local
Dashboard runtime instance. Schema 2 names only Dashboard, Grafana and the
external model gateway. Generated `state/local/worktree-runtime.env` is an
operator projection, not another configuration authority.

## Authority Order

1. Explicit CLI arguments or process environment selected by the operator.
2. Durable `state/local/runtime-instance.json`.
3. Built-in single-workspace defaults.

The launcher may accept explicit overrides for one invocation, but normal start/restart/stop behavior should resolve the same durable runtime identity every time.
Explicit requested ports take precedence over profile ports. Merely generating
an env projection does not load it; an operator who explicitly loads it selects
those values as process-environment inputs.

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

The E2E service config keeps alternative port lists. When ports are not
explicitly selected, the profile chooses the first preference; an available
declared alternative may be selected when another process holds it. A caller's
explicit port is not replaced by the built-in profile default. Normal launchers
never adopt or force-kill a listener selected only by port.

## External Service Mode

Default local Dashboard-owned services use `dedicated` mode:

- `django`
- `grafana`

Cross-project services use `shared_consumed` unless Dashboard is explicitly made the owner:

- external LiteLLM gateway

A shared-consumed binding may clear local Dashboard binding/projection state, but it must not stop the external listener. Dedicated and shared-managed services require the actor identity to match the owner unless the operator explicitly requests force.

## Start Flow

1. The launcher resolves the workspace.
2. It reads `state/local/runtime-instance.json` when present.
3. If no profile exists, it creates one using the workspace path as the stable seed and `default` as the port profile.
4. It refreshes `state/local/worktree-runtime.env`.
5. It starts Dashboard services using the profile instance id, profile state root and profile primary ports.
6. The E2E flow writes `state/e2e/bug_trend_ports.json` for the stack tools.

Local backend start/stop manages only Dashboard. It does not migrate the
database, initialize demo data or import dashboards into Grafana. Those actions
belong to the explicit E2E workflow. Launchers use the selected
`METRICS_DASHBOARD_PYTHON` or `.venv-embedded/Scripts/python.exe`; a missing
interpreter fails instead of choosing another environment.

## Stop Flow

1. Stop resolves the same runtime profile.
2. The lifecycle engine stops each registered Dashboard-owned service with that service's configured grace period.
3. The Dashboard service uses `manage.py serve --host 127.0.0.1 --port <owned> --stop-file <owned>` and its stop command creates only that owned stop-file.
4. Shared-consumed external services are not stopped by Dashboard lifecycle.

Grafana's stop command uses SLE's controlled-stop helper with its persisted PID,
start marker and command identity. The helper sends a targeted Windows control
event; missing/mismatched identity or unsupported events are errors.

SLE retains an existing child handle or a Windows process handle while stopping
the service. Termination records include the service's `exit_code`, separately
from the helper or outer script's exit code. A normal stop requires an observed
service exit of zero, no force and the cooperative stop path. Unknown/nonzero
service exits and terminate/kill escalation produce a failed launcher result;
an unregistered or already stopped service is an idempotent no-op. The latter
does not rewrite its prior exit and permits an explicit later restart.
An abnormal stop in the current restart attempt blocks subsequent setup/start.
Identity is rechecked after
waits before destructive escalation. No second process registry is introduced.
If PID lookup disappears just after a wait, only the retained original process
observation may confirm a late exit. A live changed identity remains protected
from follow-up kill. A newly observed nonzero exit before any stop action is
`exited_before_terminate`, not a normal already-stopped no-op.
Normal startup prepares only its selected registered services; it does not
implicitly recover or terminate processes from orphan PID files. The generic
engine still accepts an explicit grace override, while Dashboard leaves that
unset to use each service's own grace.

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
The task registry calls the canonical stack script with its action directly.
Cross-worktree stop uses the current launcher code and each selected workspace's
registered state, never an older script copied into that workspace. Enumeration
or stop failures are nonzero; a failure in one workspace does not hide the
remaining results. There is no ordinary port-force task.

## Validation

Focused checks include:

- runtime isolation unit tests for generic identity, namespace, stop authority and conflict detection;
- conformance checks exported by `service_lifecycle_engine`;
- Dashboard profile adapter tests for schema 2 durable JSON, generated env projection, service bindings and state roots;
- launcher tests proving E2E uses the profile-derived instance, preferred primary ports and owned stop-file;
- Windows launcher tests proving PowerShell entrypoints call the real lifecycle owner and reject retired force-by-port/AI Base parameters;
- Dashboard stack script tests proving lifecycle state path is profile-derived.

The native PowerShell tests under `scripts/tests/test_windows_launcher_*paths.py`
run current source copies with synthetic settings, isolated databases and copied
plugin code. Copies contain tracked source and explicitly planned new files,
not arbitrary workspace contents. Runtime and final Windows qualification
remain tracked separately in the MDB-2 OpenSpec ledger.
