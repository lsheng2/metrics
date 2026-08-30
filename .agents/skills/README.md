# Cross-Agent Skill Bridge

This directory is the Codex-facing project skill entrypoint. Copilot-facing project skills live under `.github/skills/`.

## Codex-Only Agent Adapter Layer

The role adapters in this directory are for Codex only. They let Codex discover and use the existing Copilot custom-agent role definitions without changing Copilot behavior.

Copilot continues to use `.github/agents/*.agent.md` and `.github/custom-agents.md` as its custom-agent source. Do not point Copilot at the Codex-only adapters, and do not duplicate role definitions here.

Use thin adapter `SKILL.md` files when a skill's canonical source already lives elsewhere. Do not duplicate large manuals or scripts unless the project intentionally vendors the skill.

Current convention:

- `.agents/skills/<skill>/SKILL.md` exposes a skill to Codex.
- `.github/skills/<skill>/SKILL.md` exposes the same skill to Copilot.
- `.agents/skills/<role-adapter>/SKILL.md` exposes a Codex-only adapter for an existing `.github/agents/*.agent.md` role.
- Shared personal skills use `%USERPROFILE%/.copilot/skills/<skill>/SKILL.md` as the canonical source.
- Project-specific overrides and profiles stay in this repository.

If a canonical personal skill is missing on another machine, report the missing source and fall back to the repository-local profile/config only when that is enough for the requested task.

## Codex-Only Script Wrappers

Some Codex adapters expose `scripts/` wrappers. These wrappers are for Codex only and forward to the canonical user-level skill scripts in `%USERPROFILE%/.copilot/skills/`. They exist so instructions that say `python scripts/...` still work from a Codex skill directory.

Do not mirror these wrappers into `.github/skills/`, and do not treat them as Copilot custom-agent setup.
