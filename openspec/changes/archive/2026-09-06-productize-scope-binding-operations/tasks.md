- [x] 1. Add backend scope binding operations
  - [x] 1.1 Add explicit save operation that validates provider profile and resolves provider id.
  - [x] 1.2 Add provider profile choices for UI.
  - [x] 1.3 Add binding summary/detail projection for Data Health.

- [x] 2. Add Scope Library binding editor
  - [x] 2.1 Render compact binding status/profile/provider/provenance/blockers.
  - [x] 2.2 Add profile selector and save action for missing/ambiguous/compatibility bindings.
  - [x] 2.3 Keep Confirm compatibility and existing Edit/Duplicate/Disable actions.
  - [x] 2.4 Reduce action row height with compact controls.

- [x] 3. Add Data Health binding section
  - [x] 3.1 Show status counts.
  - [x] 3.2 Show detail rows with repair links.
  - [x] 3.3 Make non-explicit bindings visually distinct.

- [x] 4. Add Workbench AI binding diagnostics
  - [x] 4.1 Include scope binding status/profile/provider in AI context.
  - [x] 4.2 Show Scope Library repair link before AI workspace sync hint when binding is unresolved.

- [x] 5. Validate and inspect
  - [x] 5.1 Add focused tests for backend, Scope Library, Data Health and AI diagnostics.
  - [x] 5.2 Run OpenSpec, Django, migration and diff checks.
  - [x] 5.3 Restart full stack and capture Scope Library/Data Health/Workbench evidence.
