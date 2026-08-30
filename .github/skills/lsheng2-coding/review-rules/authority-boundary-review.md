# Project Authority Boundary Review Overlay

This project-local overlay customizes `authority-boundary-review` for this repository. Keep cross-project authority-boundary mechanics in the skill-level base rule asset; put only project-specific authorities, forbidden degradations, fixtures, and validation commands here.

## Project-Specific Authorities

- Runtime code authority stays in the modular monolith boundaries from `AGENTS.md`: domain modules communicate through public APIs in `app/api/`, and `ui_web` is the federation gateway.
- Copilot skill authority stays under `.github/skills/` and user-level `.copilot/skills/`; Codex-only adapters stay under `.agents/skills/` and must clearly say they are for Codex only.
- The three lsheng2 skills have canonical user-level Copilot sources. Project-local Codex adapters may forward to canonical scripts, but must not create a second script authority or silently change Copilot behavior.
- Agent routing authority for DAG work is `.github/custom-agents.md`, `.github/agents/*.agent.md`, and the DAG project profile routing section. Codex role adapters may map to these roles but must not redefine them incompatibly.
- Forbidden degradations: copying canonical workflow scripts into a divergent implementation, adding Codex adapter hooks that Copilot can accidentally invoke, removing legacy compatibility aliases without migration notes, or documenting a dual-agent path that only works for one agent.

## Project-Specific Surface Matrix Requirements

- Skill adapter reviews must include `.agents/skills/README.md`, every touched `.agents/skills/*/SKILL.md`, any `.agents/skills/*/scripts/*.py` wrapper, `.github/skills/README.md`, every touched `.github/skills/*/SKILL.md`, and `.github/skills/lsheng2-dag-based-planning/templates/project-profile.md`.
- For script-capable skills, include both the Codex wrapper and the canonical user-level target named by the wrapper. The review must verify that wrapper behavior is pure forwarding plus clear failure reporting.
- For routing-sensitive skills, include `.github/custom-agents.md`, `.github/agents/*.agent.md`, and any Codex role adapter SKILL files that claim to map those roles.
- For documentation truth sync, include `AGENTS.md`, `.github/copilot-instructions.md` when present, `openspec/docs/backlog/README.md`, and any handoff or guide files changed in the same dirty tree.
- Generated receipt files and review gate state are local process artifacts; review them for protocol health only when they are touched, not as product source authority.

## Project-Specific Negative Fixtures

- A Copilot-only skill path exists but no `.agents/skills/<skill>/SKILL.md` Codex adapter exists for the same skill.
- A `.agents/skills/<skill>/SKILL.md` exists but does not state that it is Codex-only and must not be pointed to by Copilot.
- A wrapper script exists in `.agents/skills/*/scripts/` but does not forward to the canonical user-level script path or cannot fail clearly when the canonical source is missing.
- A legacy alias such as `dag-based-planning` exists but does not point to the renamed `lsheng2-dag-based-planning` skill.
- README instructions describe dual-agent compatibility but omit where the canonical source lives, how sync is maintained, or which directories are intentionally agent-specific.

## Project-Specific Validation Rules

- Run `python scripts/check_file_size_limits.py --include-untracked` and `python scripts/check_diff_whitespace.py --include-untracked` before review when available.
- Run the lsheng2 adapter maintenance checks when lsheng2 scripts or READMEs are touched: `.agents/skills/lsheng2-dag-based-planning/scripts/dag_setup_doctor.py`, `.agents/skills/lsheng2-dag-based-planning/scripts/lint_project_profile.py`, and `.agents/skills/lsheng2-dag-based-planning/scripts/run_maintainer_checks.py` when those wrappers exist and their canonical scripts are installed.
- Static review must search for accidental Copilot entry points into `.agents/skills/`, accidental Codex entry points into `.github/skills/` where not intended, stale `dag-based-planning` canonical references, and non-forwarding duplicate script logic.
- Documentation-only changes do not require Django runtime tests unless they alter application code, configuration defaults, templates, or scripts executed by the application.

## Reviewer Prompt Additions

- Require the reviewer to inspect both agent entry trees and to state whether any surface is intentionally one-agent-only.
- Require every clean pass to state which adapter/script/README surfaces were covered and whether Copilot behavior remains unchanged.
- Treat unclear ownership between `.agents/skills/`, `.github/skills/`, and user-level `.copilot/skills/` as an authority-boundary finding.
