# service_lifecycle_engine AI Contract

This package is a generic, cross-project local service lifecycle engine. Changes in this directory must preserve that boundary.

## Generic Boundary

- Keep project-specific service names, launcher layouts, environment variables, UI links, endpoint binding stores, health routes, and domain-specific status interpretation outside this package.
- Expose reusable primitives here: service specs, lifecycle state, provenance, live service resolution, launch metadata, process/PID helpers, health snapshots, startup orchestration, diagnostics, conformance checks, and display-safe live snapshots.
- Keep endpoint selection separate from diagnostics and display metadata. A live snapshot may describe a URL; it must not become runtime endpoint authority unless an outer adapter maps it that way.
- Keep canonical health statuses small and stable. Project-specific states should use `reason`, `special_state`, or diagnostics instead of expanding the core enum.
- Startup orchestration APIs must model generic dependency graphs, activation policies, restart policy metadata, launch attempts, timings, and diagnostics only. Do not encode a project's service topology, shell script phases, runtime endpoint binding semantics, or UI policy in core.
- Lazy startup and restart policy belong here only as declarations and reusable execution hooks. Project adapters decide which external event triggers a lazy service or restart.
- Prefer provider protocols for external facts so tests and consumers do not require real ports, real processes, platform-specific process files, or a specific filesystem layout.

## Change Requirements

- Public reusable APIs must be exported from `service_lifecycle_engine.__init__`.
- New public APIs should have neutral tests using names such as `api`, `worker`, or `dashboard`.
- Health-related APIs must preserve startup-blocking, live-status, optional observability, and advisory probe semantics.
- Startup orchestration APIs must include generic tests for dependency sorting, cycle/unknown dependency rejection, required versus optional dependency failure behavior, max parallelism, lazy/manual activation, and serializable launch timing/error records.
- Production code in this package should stay free of app-specific comments and examples.
