## 1. Persistence And Source Authority

- [x] 1.1 Add persisted source mode and query-builder state to saved Jira scope config, and verify migration defaults keep existing scopes in Custom JQL mode with unchanged final JQL.
- [x] 1.2 Extend scope config dataclass, normalization, duplicate, import/export and config hash handling for source mode and builder state, and verify existing scope config tests plus new hash tests pass.
- [x] 1.3 Implement a Jira query builder helper that generates stable JQL from project/type/common field filters and generic custom field filters, and verify quoting, list values, empty filters and deterministic ordering with unit tests.

## 2. Metadata Discovery

- [x] 2.1 Fix Jira metadata adapter wrapper parsing for issue type `values` payloads and custom field `options` payloads, and verify tests cover `Story` and real option names instead of wrapper keys.
- [x] 2.2 Add facade/view projections that separate source mode context, metadata discovery context, semantic mappings and optional display fields, and verify metadata context does not change persisted runtime query in Custom JQL mode.

## 3. Scope Config UI

- [x] 3.1 Redesign Scope Config source section with mutually exclusive Custom JQL and Query Builder controls, and verify rendered HTML exposes one selected source authority and labels inactive controls as ignored.
- [x] 3.2 Add Query Builder controls for project, issue type, component, affected version, fix version, priority, resolution, security level, labels and generic custom field filters, and verify generated JQL preview renders from submitted selections.
- [x] 3.3 Separate metadata discovery, semantic mapping and optional display fields into distinct high-density Bulma sections, and verify user-facing copy says metadata refresh is advisory unless selected in Query Builder.
- [x] 3.4 Preserve provider/profile panel semantics and Jira/HSD-ES/GitHub provider styling while adding source mode UI, and verify existing provider setup and scope config view tests still pass.

## 4. Save And Runtime Behavior

- [x] 4.1 Update save handling so Custom JQL persists the user-authored query and ignores query-builder-only filters, and verify a regression test proves builder values are not appended as hidden filters.
- [x] 4.2 Update save handling so Query Builder persists generated JQL and round-trips builder selections, and verify sync-facing scope JQL matches the preview.
- [x] 4.3 Verify Jira sync continues to consume the persisted final source query plus field mappings only, with no dependency on metadata refresh context.

## 5. Validation

- [x] 5.1 Run focused Django tests for scope config, scope metadata, provider setup, scope binding and sync query materialization.
- [x] 5.2 Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, OpenSpec strict validation for this change, and whitespace checks.
- [x] 5.3 Run a browser/UI smoke for Scope Config in Custom JQL and Query Builder modes at desktop and mobile widths, and verify text does not overlap and the source authority is visually unambiguous.
