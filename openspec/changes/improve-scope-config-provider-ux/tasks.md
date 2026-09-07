## 1. OpenSpec Contract

- [x] 1.1 Validate proposal/spec/design/tasks with `openspec validate improve-scope-config-provider-ux --strict`.

## 2. Scope Config Provider Context

- [x] 2.1 Add a facade/view projection for a single scope's provider binding and profile choices, and verify focused Scope Config tests can assert provider/profile visibility.
- [x] 2.2 Render provider/profile context and unavailable/new-scope guidance on Scope Config, and verify existing/new scope pages show the right provider boundary.
- [x] 2.3 Add provider setup template registry for Jira, HSD-ES and future providers, and verify provider pillars are generated from template/profile data.
- [x] 2.4 Save selected provider profile as explicit binding after new or edited scope save, and verify scope semantic fields remain separate from binding state.

## 3. Readiness And Metadata Mapping UX

- [x] 3.1 Add Save Draft, Enable Scope, Provider Metadata, and Dashboard/AI readiness guidance to Scope Config, and verify required-field copy renders.
- [x] 3.2 Group metadata options by type with count and mapping-purpose text, and verify the metadata partial no longer presents only an unstructured tag list.
- [x] 3.3 Add non-saving mapping links for common metadata options, and verify links append values to Dashboard semantic fields through existing query parameters.
- [x] 3.4 Render provider-first selection with Jira green and HSD-ES blue visual markers, and verify new scope page exposes the provider choice before detail fields.
- [x] 3.5 Render provider-specific detail guidance from templates, and verify HSD-ES does not display as Jira metadata-supported.
- [x] 3.6 Render provider choices as folder-style card tabs with selected-state check, Jira green, HSD-ES blue and GitHub purple, and verify the selected tab attaches to the provider context/profile/detail content panel.

## 4. Validation

- [x] 4.1 Run focused Scope Config tests and verify they pass.
- [x] 4.2 Run `python manage.py check`, OpenSpec strict validation, and diff whitespace validation.
