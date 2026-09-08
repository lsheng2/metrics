## Context

Current profile records include `source_population`, `field_bindings`, `value_mappings`, `chart_bindings`, `sync_policy`, and `readiness_policy`. These are used by provider sync, chart support, AI/Grafana context and export/import. However the user-facing workflow should not require one profile per project query. Provider onboarding belongs above project scope.

## Goals / Non-Goals

**Goals:**

- Make provider profile mean provider-level connection/onboarding, not a required per-scope source.
- Add a `connection_settings` contract with base URL, auth mode, internal credential reference, system-derived onboarding status and optional profile-local temporary credentials.
- Allow local temporary credentials in `ProviderProfileConfig` for the current phase, while excluding them from exported packages, readiness payloads, audit details and hidden form state.
- Move source-specific thinking into Scope Config: Jira JQL and HSD-ES saved query are scope/range inputs.
- Keep Scope Library as a scope inventory only; do not use it as a secondary provider profile inventory.
- Preserve existing source-heavy profiles for compatibility while new UI copy and defaults guide users toward provider-level profiles.

**Non-Goals:**

- No raw tokens/passwords in exported profile packages or non-editing diagnostic payloads.
- No breaking migration that deletes existing `chiplet-2a-jira` or `nvu-ttl-hsdes` records.
- No full replacement of HSD-ES aggregate APIs with scope-id based APIs in this pass.

## Decisions

- Add `connection_settings` to the profile contract.
  - Contains keys such as `base_url`, `auth_mode`, `credential_ref`, `credential_storage`, `onboarding_status`, `transport`, and `timeout_seconds`.
  - May contain a nested `credentials` object for temporary local onboarding values, limited by the selected provider authentication method.
  - `credential_ref` remains a pointer such as `settings:METRICS_HSDES_*` or `vault:hsdes/default` so future vault migration has a stable target.

- Resolve runtime credentials from profile first and deployment settings second.
  - Jira may use profile-local `credentials.email` and `credentials.api_token` before `METRICS_JIRA_*`.
  - HSD-ES may use profile-local `credentials.username`, `credentials.password`, or `credentials.token` before `METRICS_HSDES_*`.
  - Windows integrated auth and settings-backed references remain supported.
  - Secret values must not participate in exported payloads or public readiness payloads.

- UI should expose connection/onboarding fields first.
  - Users select the provider first, then one authentication method; the editor renders only the credential fields used by that provider/method.
  - Temporary credential inputs appear beside connection fields; saved token values render as stars, while non-token identity fields remain readable.
  - `credential_ref` is treated as an internal compatibility pointer and `onboarding_status` is represented by a read-only system status in the primary UI.
  - Provider-specific source/mapping JSON remains available under Advanced for compatibility/debugging.
  - Display-only or legacy source-heavy values should not dominate the main editor.

- Provider profile inventory belongs to Provider Setup.
  - Provider Setup is the only profile-management surface for profile creation, editing, connection tests, export/import, archive/restore and hard deletion.
  - Scope Library lists saved scopes and their binding state only.
  - Scope Library must not append unbound provider profiles as read-only rows; users choose available provider profiles from the New/Edit Scope binding controls.

- Scope owns concrete project/range source.
  - Existing `JiraScopeConfig.jql` remains the current scope source field for Jira and HSD-ES compatibility.
  - Full scope-owned HSD-ES source JSON can be added later; this pass keeps existing compatibility stable.

## Validation Plan

- Unit tests for profile config save/export/import with `connection_settings`, temporary credential storage and secret filtering.
- Registry tests for default connection settings on bundled profiles.
- Command tests proving Jira/HSD-ES sync can read profile-local credentials while retaining settings fallback.
- Browser layout tests for Provider Profile Config and Scope Config tabs on desktop/mobile.
- `manage.py check`, migration dry-run, OpenSpec strict validation and `git diff --check`.
