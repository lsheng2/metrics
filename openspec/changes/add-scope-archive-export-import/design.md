## Context

See `proposal.md` - Why. `JiraScopeConfig.enabled` already controls whether a saved scope participates in normal dashboard selectors. Existing foreign keys from calculations, bucket evidence, Jira history, sync cursor, provider binding and audit use cascade semantics, so physical deletion has a large blast radius.

## Goals / Non-Goals

**Goals:**

- Use Archive as the normal removal workflow and keep it reversible through existing edit/save-and-enable behavior.
- Add portable JSON export/import for saved scope configuration without moving historical fact data.
- Protect hard delete so it is available only for archived scopes with explicit confirmation.
- Keep Scope Library high-density and avoid hiding destructive operations behind clipped UI.

**Non-Goals:**

- Bulk archive/delete is not included in this phase.
- Import does not merge into an existing scope or overwrite existing history.
- Export does not include calculation runs, Jira raw payloads, bucket evidence, sync cursors or audit history.

## Decisions

- Archive maps to the existing `enabled=False` model state.
  - Rationale: Dashboard selectors already use enabled-only scope lists, so the existing state gives reversible archive semantics without migration.
  - Alternative considered: add a new `archived_at` field. Deferred because it would require a migration and the current first-order user need is safe removal from active selection.

- Hard delete is allowed only after archive.
  - Rationale: Current cascade relationships make direct delete too dangerous as a primary action.
  - Alternative considered: no hard delete at all. Rejected because operators need a way to clean imported mistakes or abandoned archived scopes.

- Export/import uses a versioned JSON package.
  - Rationale: JSON keeps semantic config portable and reviewable, and avoids provider-specific binary or database dump coupling.
  - Alternative considered: CSV. Rejected because semantic list fields, binding metadata and package metadata are nested structures.

- Imported scopes are archived/draft by default.
  - Rationale: Imported config must be reviewed, synced and recalculated before entering normal Dashboard/AI use.
  - Alternative considered: preserve enabled state. Rejected because cross-environment imports can point at stale projects, provider bindings or mappings.

- Deployment is an explicit lifecycle step, not a side effect of import.
  - Rationale: new users need a clear path from draft config to validated scope, source sync, calculation, Workbench evidence, and AI/Grafana usage.
  - Alternative considered: automatically enable imported valid scopes. Rejected because provider binding and freshness can still be missing.

- Validation uses layered readiness.
  - Rationale: a scope can be valid enough to save, valid enough to appear in Dashboard, but not yet ready for AI/Grafana because binding, sync or calculation is missing.
  - The first implementation strengthens config validation and exposes the product matrix in docs/UI copy; later work can add a richer persisted readiness object.

## Risks / Trade-offs

- [Risk] Operators may still expect Delete to be reversible. → Mitigation: show Delete only for archived scopes and require a confirmation token.
- [Risk] Exported binding profile may not exist in the target environment. → Mitigation: import preserves metadata as editable binding only when present; imported scope remains archived until reviewed.
- [Risk] Existing `enabled=False` mixes draft and archived language. → Mitigation: UI uses Archive wording for library actions while preserving existing draft/save behavior for new scopes.

## Migration Plan

1. Add scope config service methods for export package, import package, impact summary and archived-only hard delete.
2. Wire Scope Library POST/GET actions for import/export/delete and update row actions.
3. Strengthen scope validation and deployment checks so invalid scopes cannot be enabled.
4. Add tests for non-destructive archive, export/import round-trip, protected delete and validation/deployment blocking.
5. Validate with focused Django/browser tests and `openspec validate`.
