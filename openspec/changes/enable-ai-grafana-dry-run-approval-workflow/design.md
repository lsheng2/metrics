## Context

Dashboard owns Metrics semantics, render config validation and gcx precondition. AI Base owns orchestration, CLI runtime, gcx tool execution, durable dry-run proof storage and human approval mechanics. Existing AI Base `StandardCliRunner` already records `JsonDryRunProofStore` entries and blocks write commands unless a matching proof exists.

## Goals / Non-Goals

**Goals:**
- Add an AI Base helper that calls Dashboard `workflow.run`, then records a dry-run proof summary when the workflow is ready.
- Expose proof id, proof status and approval requirement in AI Base Dashboard Query Agent UI.
- Keep Dashboard runbook documentation current for human E2E use.

**Non-Goals:**
- Do not execute real Grafana import/publish in this change.
- Do not add a Dashboard-owned approval database.
- Do not allow AI to bypass Metrics precondition or render validation.

## Decisions

1. **AI Base owns dry-run proof.**
   - Rationale: the CLI runner and durable proof store already live in AI Base.
   - Alternative: Dashboard records proof. Rejected because Dashboard does not execute gcx.

2. **Dashboard remains validation/precondition authority.**
   - Rationale: Metrics must own chart semantics and publication gate.
   - Alternative: AI Base revalidates chart semantics. Rejected because it would duplicate and drift from Metrics.

3. **First implementation uses connector-level proof summary.**
   - Rationale: gives the user a visible dry-run proof flow quickly, while real gcx command execution remains governed by existing CLI runner tooling.

## Risks / Trade-offs

- [Risk] Proof summary could be mistaken for final publication → Mitigation: UI labels approval as required and mutation as not executed.
- [Risk] Real gcx integration varies by local install → Mitigation: use existing CLI runner proof semantics and keep full mutation disabled until explicit approval workflow is added.
