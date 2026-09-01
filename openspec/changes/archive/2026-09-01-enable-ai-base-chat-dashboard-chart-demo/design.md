## Context

AI Base already has generic Chat, connector, and Dashboard Query Agent profile support. Dashboard already exposes `workflow.run`. The new requirement is a deterministic demo path in Chat so users can manually test the workflow without relying on arbitrary LLM behavior.

## Goals / Non-Goals

**Goals:**
- Recognize a narrow Dashboard chart request in AI Base Chat.
- Call the existing Metrics connector try-run helper.
- Return a readable chat response containing proof and approval state.

**Non-Goals:**
- Do not execute real Grafana mutation.
- Do not build a broad natural-language parser.
- Do not add new chart semantics beyond `open_bug_trend` and approved series.

## Decisions

1. **Use chat shortcut infrastructure.**
   - Rationale: it already bypasses runtime LLM calls for deterministic app-owned commands.

2. **Keep parsing conservative.**
   - Rationale: only a demo request should trigger the shortcut; general chat remains routed to the model runtime.

## Risks / Trade-offs

- [Risk] Users may expect broad natural language understanding → Mitigation: first version documents the supported phrasing and keeps fallback to normal chat.
