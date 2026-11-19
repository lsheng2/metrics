# Historical SDK 0.2 Integration

Status: superseded by MDB-2 embedded runtime integration.

This page is a historical pointer, not an installation or runtime contract.
Dashboard now consumes the pinned `ai-base-runtime` wheel through `ai_host`,
with App-owned task-run ports and task profiles. It does not select the former
HTTP client or contract pack as an alternative execution path.

Current behavior and commands:

- [Project reporting](project-reporting.md)
- [Reporting development and validation](../../../docs/development/reporting-delivery.md)
- [MDB-2 design and task ledger](../../changes/embed-ai-base-runtime-in-process/tasks.md)
- [Runtime artifact identity](../../../ai_host/runtime_artifact.json)

The former selection, review and joined-run results remain in
[the historical integration specification](../../changes/add-provider-neutral-project-reporting/sdk-020-integration.md)
and [its delivery receipt](../../changes/add-provider-neutral-project-reporting/sdk-020-join-delivery.json).
Those results describe their original versions and do not qualify the current
runtime, real models/providers or production deployment.
