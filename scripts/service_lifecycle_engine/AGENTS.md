# service_lifecycle_engine AI Contract

This package is a generic, cross-project local service lifecycle engine. Changes in this directory must preserve that boundary.

## Generic Boundary

- Keep project-specific service names, launcher layouts, environment variables, UI links, endpoint binding stores, health routes, and domain-specific status interpretation outside this package.
- Expose reusable primitives here: service specs, lifecycle state, provenance, live service resolution, launch metadata, process/PID helpers, health snapshots, diagnostics, conformance checks, and display-safe live snapshots.
- Keep endpoint selection separate from diagnostics and display metadata. A live snapshot may describe a URL; it must not become runtime endpoint authority unless an outer adapter maps it that way.
- Keep canonical health statuses small and stable. Project-specific states should use `reason`, `special_state`, or diagnostics instead of expanding the core enum.
- Prefer provider protocols for external facts so tests and consumers do not require real ports, real processes, platform-specific process files, or a specific filesystem layout.

## Change Requirements

- Public reusable APIs must be exported from `service_lifecycle_engine.__init__`.
- New public APIs should have neutral tests using names such as `api`, `worker`, or `dashboard`.
- Health-related APIs must preserve startup-blocking, live-status, optional observability, and advisory probe semantics.
- Production code in this package should stay free of app-specific comments and examples.
