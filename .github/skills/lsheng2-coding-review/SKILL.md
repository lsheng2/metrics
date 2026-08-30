---
name: lsheng2-coding-review
description: Use for lsheng2 coding review, architectural code review, dirty code review, exact-pass iteration review, and P0-P3 review fix loops.
argument-hint: review target and exact pass count, e.g. review dirty code in 2 exact-pass iterations
---

# Lsheng2 Coding Review Adapter

Canonical source for this skill is the user-level Copilot skill:

`%USERPROFILE%/.copilot/skills/lsheng2-coding-review/SKILL.md`

Load that file first. Then load this repository's project-local config and overlays as directed by the canonical skill:

- `.github/skills/lsheng2-coding/config.json`
- `.github/skills/lsheng2-coding/review-rules/dag-plan-doc-review.md`
- `.github/skills/lsheng2-coding/review-rules/authority-boundary-review.md`

This project file exists only to expose the same review workflow through the repository-level Copilot skill surface.
