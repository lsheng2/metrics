## 1. Scope Management Contracts

- [x] 1.1 Add OpenSpec delta for Archive/Delete/Export/Import behavior and verify `openspec validate add-scope-archive-export-import --strict` passes.
- [x] 1.2 Add scope config export/import/delete/impact service methods and verify focused API tests pass.
- [x] 1.3 Strengthen scope validation/deployment readiness checks and verify invalid scopes cannot be enabled.

## 2. Scope Library UI

- [x] 2.1 Add Scope Library Export and Import controls and verify rendered HTML includes safe archive/delete wording.
- [x] 2.2 Add archived-only Delete action with confirmation token and verify enabled scopes cannot be deleted.
- [x] 2.3 Keep status tags and row menus visually consistent and verify browser tests cover visible Archive/Delete actions.
- [x] 2.4 Add user-facing scope lifecycle/readiness guidance and verify new-user path is visible from Scope Library.

## 3. Validation

- [x] 3.1 Run focused Scope Library and Data Health tests.
- [x] 3.2 Run Django system check and diff whitespace validation.
