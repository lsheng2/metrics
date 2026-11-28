# Project Authority Boundary Review Overlay

This project-local overlay customizes `authority-boundary-review` for this repository. Keep cross-project authority-boundary mechanics in the skill-level base rule asset; put only project-specific authorities, forbidden degradations, fixtures, and validation commands here.

## Project-Specific Authorities

- Runtime code authority stays in the modular monolith boundaries from `AGENTS.md`: domain modules communicate through public APIs in `app/api/`, and `ui_web` is the federation gateway.
- Local service lifecycle authority is owned by `scripts/service_lifecycle_engine/`. For launcher work, wrapper PID, listener PID, process group, command identity, process start marker, listener identity, lifecycle state, readiness endpoint, and termination ledger are separate authorities and must not be substituted for one another without an explicit capability downgrade.
- Skill authority: shared skills live once in user-level `~/.agents/skills/` (read by Copilot and Codex); project skills live once in `.agents/skills/` with byte-identical `.claude/skills/` copies; OpenSpec-managed per-tool copies and the Copilot-facing `drawio` skill live under `.github/skills/`. The layout and its exceptions are in `.github/skills/README.md`. Codex-only role adapters stay under `.agents/skills/`, say they are for Codex only, and are turned off for Copilot in `.github/copilot/settings.json`.
- The lsheng2 skills have canonical user-level sources under `~/.agents/skills/`. This repository holds only their project overlays (`.github/skills/lsheng2-coding/`); a project `SKILL.md` or script wrapper that forwards to a personal path is a second authority.
- Agent routing authority is `.github/custom-agents.md` and `.github/agents/*.agent.md`; lanes and the R2 loop come from `AI_CONTRACT.md` §1 and the `r2-change-loop` skill. Codex role adapters may map to these roles but must not redefine them incompatibly.
- Forbidden degradations: copying canonical workflow scripts into a divergent implementation, adding Codex adapter hooks that Copilot can accidentally invoke, restoring removed `port_lifecycle` compatibility during zero-compatibility work, treating process existence as service ownership, treating a non-ready persisted endpoint as live, conflating caller force request with kill escalation, or documenting a dual-agent path that only works for one agent.

## Project-Specific Surface Matrix Requirements

- Skill layout reviews must include `.github/skills/README.md`, `.agents/skills/README.md`, `.github/copilot/settings.json`, every touched `SKILL.md` under `.github/skills/`, `.agents/skills/` and `.claude/skills/`, and `scripts/tests/test_skill_copies.py`.
- For script-capable skills, review the scripts at their single canonical location; a project copy or forwarding wrapper of a canonical script is a finding.
- For routing-sensitive skills, include `.github/custom-agents.md`, `.github/agents/*.agent.md`, and any Codex role adapter SKILL files that claim to map those roles.
- For documentation truth sync, include `AGENTS.md`, `.github/copilot-instructions.md` when present, `openspec/docs/backlog/README.md`, and any handoff or guide files changed in the same dirty tree.
- Generated receipt files and review gate state are local process artifacts; review them for protocol health only when they are touched, not as product source authority.
- For `service_lifecycle_engine` work, include `scripts/service_lifecycle_engine/*.py`, launcher scripts such as `scripts/e2e_bug_trend.py` and `scripts/e2e_provider_parity.py`, runtime helpers such as `scripts/e2e_grafana_runtime.py`, OpenSpec lifecycle docs, CLI entry points, resolver/start/stop/state-store paths, and all lifecycle tests.
- Product/source changed-file counts must exclude `.review/` process evidence unless the task is explicitly reviewing the review process itself.

## Project-Specific Negative Fixtures

- The same skill name appears in more than one project skill directory outside the exceptions listed in `.github/skills/README.md`.
- A project `SKILL.md` or script wrapper forwards to a personal skill path (`~/.agents/skills/`, `~/.copilot/skills/` or `%USERPROFILE%`).
- A `.claude/skills/<skill>` entry differs from `.agents/skills/<skill>`.
- A Codex-only role adapter is missing from the Copilot `disabledSkills` list in `.github/copilot/settings.json`, or states role content that differs from its `.github/agents/*.agent.md` source.
- README instructions describe dual-agent compatibility but omit where the canonical source lives, how sync is maintained, or which directories are intentionally agent-specific.
- A registered wrapper PID no longer exists while an owned listener is still alive.
- A persisted listener PID exists but is not currently listening on the service host/port.
- A persisted endpoint exists with lifecycle state other than `ready`.
- A registered PID exists but its command identity does not match the service command.
- A path-qualified expected executable matches a same-basename process from another path, or `./python.exe` matches unqualified `python.exe`.
- `force_requested` or stop source is recorded as `forced` kill escalation when graceful stop succeeded.

## Project-Specific Validation Rules

- Run `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked` before review when available.
- Run `scripts/tests/test_skill_copies.py` through the no-dotenv test entry when `.agents/skills/` or `.claude/skills/` changes.
- Static review must search for forwarding `SKILL.md` files, duplicate skill names across project skill directories, routing references to retired skills (`dag-based-planning`, `lsheng2-dag-based-planning`, `lsheng2-multiagent-creation`) in current guides, and duplicated script logic.
- Documentation-only changes do not require Django runtime tests unless they alter application code, configuration defaults, templates, or scripts executed by the application.
- For `service_lifecycle_engine`, Tier 1 should run the targeted tests for the failure class first, especially `scripts/tests/test_service_lifecycle_platform_ops.py`, `test_service_lifecycle_provenance.py`, `test_service_lifecycle_stopping.py`, `test_service_lifecycle_resolver.py`, and `test_service_lifecycle_state_store.py` as applicable.
- For `service_lifecycle_engine`, Tier 2 should run the focused lifecycle/launcher bundle: `python -m pytest scripts/tests/test_service_lifecycle_engine.py scripts/tests/test_service_lifecycle_stopping.py scripts/tests/test_service_lifecycle_state_store.py scripts/tests/test_service_lifecycle_provenance.py scripts/tests/test_service_lifecycle_platform_ops.py scripts/tests/test_service_lifecycle_resolver.py scripts/tests/test_service_lifecycle_process.py scripts/tests/test_service_lifecycle_cli.py scripts/tests/test_e2e_bug_trend_launcher.py scripts/tests/test_e2e_provider_parity_launcher.py -q`.
- For `service_lifecycle_engine`, Tier 3 should run `openspec validate generalize-service-lifecycle-engine --strict`, `python scripts/check_file_size_limits.py --include-untracked`, and `python scripts/check_diff_whitespace.py --include-untracked`.
- For `service_lifecycle_engine`, Tier 4 follows the trigger rules in the shared review skill. Use the isolated native launcher tests in `scripts/tests/test_windows_launcher_real_paths.py`, `test_windows_launcher_sle_paths.py` and `test_windows_launcher_stack_real_paths.py` through the selected runtime interpreter. They exercise the real entrypoints on owned synthetic source/data copies; do not start or stop the operator's existing service as a review step.

## Reviewer Prompt Additions

- Require the reviewer to inspect all three tool entry trees (`.github/skills/`, `.agents/skills/`, `.claude/skills/`) and to state whether any surface is intentionally one-tool-only.
- Require every clean pass to state which skill, README and settings surfaces were covered and which file each tool resolves for every touched skill name.
- Treat unclear ownership between `.agents/skills/`, `.github/skills/`, `.claude/skills/` and user-level `~/.agents/skills/` as an authority-boundary finding.
- For `service_lifecycle_engine`, require each reviewer prompt after a process/identity finding to bundle sibling checks for wrapper PID, listener PID, process group, command executable identity, command arguments, listener endpoint identity, persisted lifecycle readiness, and force/kill semantics.
