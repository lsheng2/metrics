## 1. OpenSpec And Reuse Baseline

- [x] 1.1 Validate `add-provider-setup-profile-management` with `openspec validate add-provider-setup-profile-management --strict`.
- [x] 1.2 Inventory reusable Scope management code paths for archive/delete/import/export/audit/help-tip/dirty-form/provider colors and document chosen shared abstractions in implementation notes or code comments only where needed; verify with a targeted diff review.

## 2. Provider Profile Store And Contracts

- [x] 2.1 Add managed provider profile persistence that preserves the current registry profile contract and verify registry tests cover bundled JSON plus managed profiles.
- [x] 2.2 Add profile lifecycle states and version fingerprints for source/mapping changes, and verify archived profiles resolve as unavailable/configuration_required.
- [x] 2.3 Add create/edit/duplicate/archive/restore/delete-impact/delete service operations and verify domain/API tests cover safe lifecycle behavior.
- [x] 2.4 Add versioned non-secret profile export/import packages and verify round-trip, conflict policy, and secret exclusion tests.
- [x] 2.5 Add audit events for profile create/edit/archive/restore/delete/import/export and verify audit payload tests include before/after fingerprints and destructive confirmation evidence.

## 3. Provider Setup Template And Metadata Workflow

- [x] 3.1 Generalize provider setup template registry for Provider Setup and Scope Config reuse, and verify Jira green, HSD-ES blue, GitHub purple and future-provider neutral styling data is emitted from templates.
- [x] 3.2 Implement provider-specific setup projections for Jira, HSD-ES and GitHub-template providers, and verify each renders source labels, detail rows, metadata support and readiness guidance.
- [x] 3.3 Add metadata discovery and mapping validation orchestration that respects provider capability state, and verify unsupported HSD-ES/GitHub metadata paths do not call Jira adapters.

## 4. Provider Setup UI

- [x] 4.1 Add Provider Setup menu/list page with high-density profile inventory and verify navigation/sidebar tests show the entry.
- [x] 4.2 Add provider-first create/edit UI with progressive sections for source, metadata, field mappings, value mappings and readiness, and verify low-context copy and required markers render.
- [x] 4.3 Add archive/delete/import/export/duplicate controls matching Scope Library safety semantics and verify view tests cover protected delete, archived defaults and package download/upload.
- [x] 4.4 Add dirty-form guard, help tips, responsive admin table styling and provider color consistency, and verify browser smoke covers desktop/mobile layout without text overlap.
- [x] 4.5 Split Provider Setup inventory from the dedicated Provider Profile Config editor, and verify New Profile/Edit no longer render the inventory table on the active edit screen.
- [x] 4.6 Extend the provider-colored editor frame to include advanced JSON and bottom actions, and verify nested detail panels do not repeat provider-color left rails.

## 5. Scope Handoff

- [x] 5.1 Add Create Scope from Profile handoff to Scope Config with provider/profile preselected and safe defaults prefilled; verify handoff view tests.
- [x] 5.2 Add Bind Existing Scope flow from Provider Setup using explicit scope-provider binding authority; verify binding does not mutate profile source/mapping data.
- [x] 5.3 Update Scope Config/Scope Library/Data Health blockers for archived or invalid provider profiles and verify provider-backed consumers do not silently use archived profiles.

## 6. Validation

- [x] 6.1 Run focused provider setup, provider registry, scope handoff and data health tests.
- [x] 6.2 Run `python manage.py check`, migration dry-run, OpenSpec strict validation and diff whitespace validation.
- [x] 6.3 Run a browser smoke for Provider Setup and Scope Config provider handoff at desktop and mobile widths.
