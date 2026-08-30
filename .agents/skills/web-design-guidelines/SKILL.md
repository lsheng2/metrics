---
name: web-design-guidelines
description: Review UI code for Web Interface Guidelines compliance. Use when asked to "review my UI", "check accessibility", "audit design", "review UX", or "check my site against best practices".
metadata:
  author: vercel
  version: "1.0.0"
  argument-hint: <file-or-pattern>
---

# Web Design Guidelines Adapter

## Codex-Facing Project Skill

This file is the Codex-facing project entrypoint. It must not be copied into `.github/skills/` as the Copilot source of truth.

For this project, both the Codex-facing and Copilot-facing skill entries use the same upstream Web Interface Guidelines URL below. Keep the two project entrypoints behaviorally aligned, but do not make one agent surface depend on the other.

## How It Works

1. Fetch the latest guidelines from the source URL below.
2. Read the specified files or prompt the user for a file or pattern.
3. Check the selected files against all fetched rules.
4. Output findings using the terse format required by the fetched guidelines.

## Guidelines Source

Fetch fresh guidelines before each review:

```
https://raw.githubusercontent.com/vercel-labs/web-interface-guidelines/main/command.md
```

Use the available web fetch/search capability to retrieve the latest rules. The fetched content contains all rules and output format instructions.
