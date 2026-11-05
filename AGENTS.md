# Dashboard Agent Entry

Before design, coding, testing, review or development-document changes, read and follow
[AI_CONTRACT.md](AI_CONTRACT.md). It is the single repository development contract.

Use the current OpenSpec change and its one `tasks.md`; do not keep a second skill ledger.
Current product context is in [README.md](README.md) and [repo context](.github/ai-governance/repo-context.md).
Load only the relevant module, specification, tests and BKM after the contract.

For structural discovery use the installed `codebase-memory` skill, verify coverage/freshness,
and fall back to focused source reads when the index misses current work. Never silently rebuild an index.
Codex subagents use explicit `gpt-5.5` and `xhigh`; preserve unrelated work and runtime credentials.
