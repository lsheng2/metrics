# Project Authority Boundary Review Overlay

This project-local overlay customizes `authority-boundary-review` for this repository. Keep cross-project authority-boundary mechanics in the skill-level base rule asset; put only project-specific authorities, forbidden degradations, fixtures, and validation commands here.

## Project-Specific Authorities

- Runtime code authority stays in the modular monolith boundaries from `AGENTS.md`: domain modules communicate through public APIs in `app/api/`, and `ui_web` is the federation gateway.
- Local service lifecycle authority is owned by `scripts/service_lifecycle_engine/`. For launcher work, wrapper PID, listener PID, process group, command identity, process start marker, listener identity, lifecycle state, readiness endpoint, and termination ledger are separate authorities and must not be substituted for one another without an explicit capability downgrade.
- Copilot skill authority stays under `.github/skills/` and user-level `.copilot/skills/`; Codex-only adapters stay under `.agents/skills/` and must clearly say they are for Codex only.
- The three lsheng2 skills have canonical user-level Copilot sources. Project-local Codex adapters may forward to canonical scripts, but must not create a second script authority or silently change Copilot behavior.
- Agent routing authority for DAG work is `.github/custom-agents.md`, `.github/agents/*.agent.md`, and the DAG project profile routing section. Codex role adapters may map to these roles but must not redefine them incompatibly.
- Forbidden degradations: copying canonical workflow scripts into a divergent implementation, adding Codex adapter hooks that Copilot can accidentally invoke, restoring removed `port_lifecycle` compatibility during zero-compatibility work, treating process existence as service ownership, treating a non-ready persisted endpoint as live, conflating caller force request with kill escalation, or documenting a dual-agent path that only works for one agent.

## Project-Specific Surface Matrix Requirements

- Skill adapter reviews must include `.agents/skills/README.md`, every touched `.agents/skills/*/SKILL.md`, any `.agents/skills/*/scripts/*.py` wrapper, `.github/skills/README.md`, every touched `.github/skills/*/SKILL.md`, and `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md`.
- For script-capable skills, include both the Codex wrapper and the canonical user-level target named by the wrapper. The review must verify that wrapper behavior is pure forwarding plus clear failure reporting.
- For routing-sensitive skills, include `.github/custom-agents.md`, `.github/agents/*.agent.md`, and any Codex role adapter SKILL files that claim to map those roles.
- For documentation truth sync, include `AGENTS.md`, `.github/copilot-instructions.md` when present, `openspec/docs/backlog/README.md`, and any handoff or guide files changed in the same dirty tree.
- Generated receipt files and review gate state are local process artifacts; review them for protocol health only when they are touched, not as product source authority.
- For `service_lifecycle_engine` work, include `scripts/service_lifecycle_engine/*.py`, launcher scripts such as `scripts/e2e_bug_trend.py` and `scripts/e2e_provider_parity.py`, runtime helpers such as `scripts/e2e_grafana_runtime.py`, OpenSpec lifecycle docs, CLI entry points, resolver/start/stop/state-store paths, and all lifecycle tests.
- Product/source changed-file counts must exclude `.review/` process evidence unless the task is explicitly reviewing the review process itself.

## Project-Specific Negative Fixtures

- A Copilot-only skill path exists but no `.agents/skills/<skill>/SKILL.md` Codex adapter exists for the same skill.
- A `.agents/skills/<skill>/SKILL.md` exists but does not state that it is Codex-only and must not be pointed to by Copilot.
- A wrapper script exists in `.agents/skills/*/scripts/` but does not forward to the canonical user-level script path or cannot fail clearly when the canonical source is missing.
- A legacy alias such as `dag-based-planning` exists but does not point to the renamed `lsheng2-dag-based-planning` skill.
- README instructions describe dual-agent compatibility but omit where the canonical source lives, how sync is maintained, or which directories are intentionally agent-specific.
- A registered wrapper PID no longer exists while an owned listener is still alive.
- A persisted listener PID exists but is not currently listening on the service host/port.
- A persisted endpoint exists with lifecycle state other than `ready`.
- A registered PID exists but its command identity does not match the service command.
- A path-qualified expected executable matches a same-basename process from another path, or `./python.exe` matches unqualified `python.exe`.
- `force_requested` or stop source is recorded as `forced` kill escalation when graceful stop succeeded.

## Project-Specific Validation Rules

- Run `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked` before review when available.
- Run the lsheng2 adapter maintenance checks when lsheng2 scripts or READMEs are touched: `.agents/skills/lsheng2-dag-based-planning/scripts/dag_setup_doctor.py`, `.agents/skills/lsheng2-dag-based-planning/scripts/lint_project_profile.py`, and `.agents/skills/lsheng2-dag-based-planning/scripts/run_maintainer_checks.py` when those wrappers exist and their canonical scripts are installed.
- Static review must search for accidental Copilot entry points into `.agents/skills/`, accidental Codex entry points into `.github/skills/` where not intended, stale `dag-based-planning` canonical references, and non-forwarding duplicate script logic.
- Documentation-only changes do not require Django runtime tests unless they alter application code, configuration defaults, templates, or scripts executed by the application.
- For `service_lifecycle_engine`, Tier 1 should run the targeted tests for the failure class first, especially `scripts/tests/test_service_lifecycle_platform_ops.py`, `test_service_lifecycle_provenance.py`, `test_service_lifecycle_stopping.py`, `test_service_lifecycle_resolver.py`, and `test_service_lifecycle_state_store.py` as applicable.
- For `service_lifecycle_engine`, Tier 2 should run the focused lifecycle/launcher bundle: `python -m pytest scripts/tests/test_service_lifecycle_engine.py scripts/tests/test_service_lifecycle_stopping.py scripts/tests/test_service_lifecycle_state_store.py scripts/tests/test_service_lifecycle_provenance.py scripts/tests/test_service_lifecycle_platform_ops.py scripts/tests/test_service_lifecycle_resolver.py scripts/tests/test_service_lifecycle_process.py scripts/tests/test_service_lifecycle_cli.py scripts/tests/test_e2e_bug_trend_launcher.py scripts/tests/test_e2e_provider_parity_launcher.py -q`.
- For `service_lifecycle_engine`, Tier 3 should run `openspec validate generalize-service-lifecycle-engine --strict`, `python scripts/check_file_size_limits.py --include-untracked`, and `python scripts/check_diff_whitespace.py --include-untracked`.
- For `service_lifecycle_engine`, Tier 4 should run real launcher E2E only after Tier 1-3 are green or when launcher/process ownership changed: `python scripts/e2e_bug_trend.py restart`, `python scripts/e2e_bug_trend.py stop --force-by-port`, and `python scripts/e2e_provider_parity.py restart --skip-browser`.

## Reviewer Prompt Additions

- Require the reviewer to inspect both agent entry trees and to state whether any surface is intentionally one-agent-only.
- Require every clean pass to state which adapter/script/README surfaces were covered and whether Copilot behavior remains unchanged.
- Treat unclear ownership between `.agents/skills/`, `.github/skills/`, and user-level `.copilot/skills/` as an authority-boundary finding.
- For `service_lifecycle_engine`, require each reviewer prompt after a process/identity finding to bundle sibling checks for wrapper PID, listener PID, process group, command executable identity, command arguments, listener endpoint identity, persisted lifecycle readiness, and force/kill semantics.
