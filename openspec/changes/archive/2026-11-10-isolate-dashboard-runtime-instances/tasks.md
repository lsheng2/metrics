## 1. OpenSpec And Architecture

- [x] 1.1 Create OpenSpec proposal/design/spec/tasks for Dashboard runtime instance isolation and verify `openspec validate isolate-dashboard-runtime-instances --strict` passes.
- [x] 1.2 Add architecture documentation for Dashboard local runtime instance isolation and verify it names durable authority, generated projection, explicit override precedence, state roots, ports, external service mode, and follow-up inventory work.

## 2. Generic Lifecycle Engine

- [x] 2.1 Add runtime identity, namespace, external service mode, stop authority and conflict detection primitives to `service_lifecycle_engine`, and verify focused runtime isolation tests pass.
- [x] 2.2 Add runtime isolation conformance checks and export them from the package, and verify existing lifecycle conformance tests still pass.

## 3. Dashboard Runtime Profile

- [x] 3.1 Add `ScrumDashboardRuntimeInstanceProfile` adapter that writes/reads `state/local/runtime-instance.json` and renders `state/local/worktree-runtime.env`, and verify profile tests cover stable identity reuse, primary ports, state dirs, bindings and env projection.
- [x] 3.2 Update Dashboard E2E launcher to consume the profile for lifecycle instance name, state directory and preferred primary ports, and verify launcher unit tests cover profile creation and port ordering.
- [x] 3.3 Update Dashboard AI stack script to resolve lifecycle state path from the profile, and verify script contract tests cover the new path logic.
- [x] 3.4 Rename existing VS Code tasks with `Current Worktree:` scope labels and verify task dependencies still resolve to existing labels.
- [x] 3.5 Add `All Worktrees:` VS Code tasks for Dashboard port inventory and explicit project service stop, and verify task labels and scripts are covered by focused tests.

## 4. Validation

- [x] 4.1 Run focused pytest for service lifecycle, Dashboard runtime profile, E2E bug trend launcher and Dashboard AI stack launcher.
- [x] 4.2 Run `python manage.py check`, OpenSpec strict validation, file-size and whitespace checks, and report any blocked checks.
