# Cross-Agent Skill Bridge

This directory is the Copilot-facing project skill entrypoint. Codex-facing project skills live under `.agents/skills/`.

Use thin adapter `SKILL.md` files when a skill's canonical source already lives elsewhere. Do not duplicate large manuals or scripts unless the project intentionally vendors the skill.

Current convention:

- `.github/skills/<skill>/SKILL.md` exposes a skill to Copilot.
- `.agents/skills/<skill>/SKILL.md` exposes the same skill to Codex.
- Shared personal skills use `%USERPROFILE%/.copilot/skills/<skill>/SKILL.md` as the canonical source.
- Project-specific overrides and profiles stay in this repository.

If a canonical personal skill is missing on another machine, report the missing source and fall back to the repository-local profile/config only when that is enough for the requested task.
