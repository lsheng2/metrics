- [x] 1. Add explicit scope-provider binding persistence
  - [x] 1.1 Add `BugTrendScopeProviderBinding` model and migration with one active binding per `JiraScopeConfig`.
  - [x] 1.2 Add binding status/provenance/blockers fields and model-level helpers for explicit vs compatibility/configuration-required states.
  - [x] 1.3 Add seed/backfill path for existing sample scopes and registry-backed scopes.

- [x] 2. Add binding resolver service
  - [x] 2.1 Implement `ScopeProviderBindingResolver` that resolves explicit binding first.
  - [x] 2.2 Move legacy matching out of Workbench-specific facade code into resolver compatibility mode.
  - [x] 2.3 Return structured binding DTO with `scope_id`, `profile_id`, `provider_id`, `status`, `provenance`, and `blockers`.
  - [x] 2.4 Reject or flag ambiguous/missing bindings without reusing stale profile/provider hints.

- [x] 3. Wire Workbench to canonical binding state
  - [x] 3.1 Update Workbench state normalization to consume binding resolver output.
  - [x] 3.2 Keep toolbar profile/provider as readonly derived fields without primary form names.
  - [x] 3.3 Ensure scope change pushes canonical URL without derived `profile_id/provider_id`.
  - [x] 3.4 Ensure AI context, Grafana panel URL and evidence forms consume normalized binding state.

- [x] 4. Add validation coverage
  - [x] 4.1 Add resolver unit tests for explicit binding, stale query hints, display-name rename, compatibility backfill and ambiguous/missing binding.
  - [x] 4.2 Add Workbench view/browser tests for canonical URL, derived field rendering and AI/evidence binding projection.
  - [x] 4.3 Run focused Workbench/provider tests, `manage.py check`, `git diff --check`, and `openspec validate --specs --strict`.

- [x] 5. Validate live UI
  - [x] 5.1 Restart the Dashboard/Grafana/AI Base stack.
  - [x] 5.2 Inspect real Workbench scope switching in a browser viewport.
  - [x] 5.3 Save screenshot/DOM metrics showing canonical URL, resolved profile/provider and synced AI context.
