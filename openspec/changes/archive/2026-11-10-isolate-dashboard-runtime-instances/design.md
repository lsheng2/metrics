## Context

See `proposal.md` for motivation. Scrum Dashboard already has a generic `service_lifecycle_engine` with safe stop, provenance, state store, live resolution, startup orchestration and conformance checks. The missing piece is a single durable runtime identity that all local projections share. Today `scripts/e2e_bug_trend.py` accepts `--instance`, but the default is always `default`, while ports and runtime paths remain partly derived by each launcher. `scripts/e2e_dashboard_ai_stack.ps1` also hardcodes the old lifecycle state path.

The related `system_integration_agent_ai` implementation proves a reusable pattern: keep generic identity/namespace/stop semantics in `service_lifecycle_engine`, then let each project own an adapter mapping the identity to ports, state dirs, env projection and external service contracts.

## Goals / Non-Goals

**Goals:**

- Add app-neutral runtime isolation primitives to `service_lifecycle_engine`.
- Add a Dashboard-owned runtime profile adapter that maps one instance id to Dashboard local projections.
- Make Dashboard E2E start/stop consume that durable profile for lifecycle instance name, state root and primary ports.
- Keep external shared services, such as AI Base and LiteLLM, represented as consumed services unless Dashboard explicitly owns them.
- Preserve the existing compatibility summary `state/e2e/bug_trend_ports.json` during the first implementation pass.

**Non-Goals:**

- Do not copy Aegra-specific names, Docker topology, endpoint binding stores, or Linux shell launchers.
- Do not make `service_lifecycle_engine` know Dashboard, Grafana, AI Base, Jira, or VS Code task names.
- Do not implement all-worktree inventory/cleanup in this first pass; the new primitives and profile adapter are the foundation for that follow-up.
- Do not change unrelated Scope Config UI work already dirty in this worktree.

## Decisions

### 1. Generic module first, project adapter second

`service_lifecycle_engine.runtime_instance` owns `RuntimeInstanceIdentity`, `RuntimeResourceNamespace`, `ExternalServiceMode`, `ExternalServiceBinding`, `StopAuthorityDecision`, and conflict detection. `scripts/dashboard_runtime_instance_profile.py` owns Dashboard ports, state directories, generated env names and shared service contracts.

Alternative considered: put Dashboard profile fields directly into the lifecycle engine. Rejected because the engine is deliberately cross-project and already has an `AGENTS.md` boundary forbidding project-specific service names.

### 2. Durable JSON profile is the local authority

Dashboard creates or reuses `state/local/runtime-instance.json`. The generated env file is a compatibility projection for scripts and future tasks. Explicit CLI/env values can override one invocation, but a normal restart uses the durable profile.

Alternative considered: derive identity from workspace path on every run without persisting it. Rejected because durable state makes operator inspection, profile migration, VS Code tasks and stale process diagnosis clearer.

### 3. Preferred primary ports are profile-derived

The Dashboard adapter maps default local services to primary ports. The E2E service config still supplies fallback port lists. The launcher reorders preferred ports so the profile port is tried first and existing fallback behavior remains available when a port is unavailable or explicitly force-cleaned.

Alternative considered: replace preferred port lists with a single fixed port. Rejected because the current E2E workflow intentionally supports fallback ports when a foreign process blocks the default.

### 4. State root moves under instance scope

Profile-managed lifecycle state uses `state/local/instances/<instance_id>/service-lifecycle-engine`. This keeps PID files, authority files, logs, termination ledgers and startup ledgers under one runtime identity. The Dashboard AI stack reads this path through the profile instead of hardcoding `metrics-bug-trend-default.json`.

Alternative considered: keep `state/e2e/service-lifecycle-engine` and only change `instance_name`. Rejected because the user’s issue is broader than ports; state/log/provenance isolation needs the same identity boundary.

### 5. Shared services are consumed by default

Dashboard profile models AI Base backend/frontend and external LiteLLM as shared-consumed bindings. Dashboard can read or pass endpoints to AI Base, but it must not stop those services as part of Dashboard-owned lifecycle unless a future explicit shared-managed contract is added.

Alternative considered: let Dashboard stack stop any process on known external ports. Rejected because cross-project stop authority was the original class of failure.

## Risks / Trade-offs

- [Old unprofiled services may still exist] -> VS Code E2E tasks already pass `ForceByPort`; the first profiled run can clear old preferred-port listeners, and old state remains ignored rather than trusted.
- [Existing tests assume old state path] -> update focused launcher tests and stack script assertions to require profile-derived state path while preserving the compatibility summary path.
- [Multiple worktrees still need inventory] -> this pass adds conflict primitives and profile projection; all-worktree inventory/task naming is a follow-up built on these APIs.
- [Port fallback can still choose another port if the preferred one is foreign-owned] -> conflict detection and future inventory should make that visible; force-by-port remains an explicit operator action.

## Migration Plan

1. Add generic runtime isolation primitives and conformance exports.
2. Add Dashboard runtime profile adapter and focused tests.
3. Update `e2e_bug_trend.py` to load/create the profile and use profile-derived lifecycle state root and primary ports.
4. Update Dashboard AI stack script to read profile-derived lifecycle state path.
5. Add architecture doc and OpenSpec delta.
6. Run focused lifecycle/profile/launcher tests plus OpenSpec validation and hygiene checks.
