## 1. Query Builder Metadata View Model

- [x] 1.1 Add a facade-level Query Builder control projection that maps current builder state plus `ScopeConfigOptions` into selectable source controls, and verify with facade tests covering selected values, metadata options and no-metadata fallback.
- [x] 1.2 Extend Query Builder POST parsing to merge metadata-selected values with `*_manual` fallback values without duplicates, and verify with facade tests for common fields and repeated custom field rows.

## 2. Scope Config UI

- [x] 2.1 Replace Query Builder free-text source fields with metadata-backed checkbox/select controls plus manual fallback textareas, and verify rendered Scope Config HTML shows selected metadata values and manual fallback controls.
- [x] 2.2 Update metadata refresh partial rendering so htmx refresh returns refreshed Query Builder controls and discovered metadata summary together, and verify metadata view tests cover the partial output without saving the scope.
- [x] 2.3 Update Query Builder preview JavaScript to read checkbox/select/manual controls after initial load and htmx swaps, and verify browser smoke covers desktop and mobile Source population preview behavior.

## 3. Source Authority Safeguards

- [x] 3.1 Verify Query Builder save persists generated JQL from metadata-selected plus manual values and round-trips the builder state.
- [x] 3.2 Verify Custom JQL save ignores metadata-backed Query Builder selections and does not persist active builder state.

## 4. Validation

- [x] 4.1 Run focused Django tests for Scope Config facade, Scope Config views, metadata views, Jira metadata API and query builder.
- [x] 4.2 Run `python manage.py check`, `python manage.py makemigrations --check --dry-run`, `openspec validate metadata-backed-query-builder-controls --strict`, and `git diff --check`.
- [x] 4.3 Run an end-to-end local demo/smoke against `/bug-trend/scope-config/?scope_id=20` or an available synthetic scope, and verify no horizontal overflow and metadata-backed source controls can generate a preview.
