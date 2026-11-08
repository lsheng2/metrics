# Retire The Legacy Standup Workspace

Status: accepted for reversible execution by the user's 2026-11-08 request.
Implementation: completed; deletion-ready, original directory retained.
Docs impact: migration, operations.
Human guide: `docs/migration/legacy-workspace-retirement.md`.

## Why

Dashboard is the active product, but the old working directory still holds
34 commits absent from its remote, dirty source, research, credentials and
ignored historical evidence. A porting catalog is not proof that these bytes
can be deleted. The user explicitly requested a plan and execution until the
old directory can be removed without losing useful material.

## What Changes

- Preserve the complete ordinary-file working tree, including `.git`, dirty,
  untracked, ignored, binary and generated files, in an owner-restricted
  local archive outside both code repositories.
- Preserve Git refs in an additional self-contained bundle and prove recovery.
- Record junctions/symlinks without following them or copying shared targets.
- Make Dashboard's current documentation and future porting source independent
  of the old path. Retain immutable provenance instead of changing old hashes.
- Validate Dashboard with old-root access forbidden; issue a deletion-readiness
  receipt only after archive verification and an independent review.

## Non-Goals

This is not resuming legacy T12, implementing every remaining Dashboard feature,
importing old records as new accepted business data, or activating a deployment.
W4.IMPORT and W7.PROTECTION remain separate product work. A protected local
archive is not an off-machine backup. Do not delete the original directory,
export secrets/data to a code remote, change global agent configuration, stop
other agents, call providers/models, send mail, or enable scheduling.

## Ownership

Dashboard owns the plan, maintenance utility, tests, current guide and receipt.
The legacy tree is read-only. The private archive owns preserved payload and
machine-specific inventories. Existing unrelated Dashboard changes are protected.
