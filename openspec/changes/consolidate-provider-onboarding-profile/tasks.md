## 1. OpenSpec Contract

- [x] 1.1 Define provider onboarding profile vs scope source ownership.

## 2. Profile Contract

- [x] 2.1 Add `connection_settings` to provider profile persistence, registry and export/import contracts.
- [x] 2.2 Preserve export/readiness boundary: allow `credential_ref` and profile-local temporary credentials while excluding token/password/secret material from packages and public payloads.
- [x] 2.3 Allow Jira and HSD-ES sync commands to use profile connection settings and profile-local credentials while retaining settings fallback.

## 3. UI

- [x] 3.1 Refocus Provider Profile Config main editor on connection/onboarding fields.
- [x] 3.2 Demote source/mapping JSON to Advanced compatibility/debug fields.
- [x] 3.3 Keep Scope Config as the scope-owned place for concrete project/range/source query.

## 4. Validation

- [x] 4.1 Add focused domain/view/browser tests for connection settings and UI boundaries.
- [x] 4.2 Run focused regression tests for provider profile, scope config, data health and workbench.
- [x] 4.3 Run `python manage.py check`, migration dry-run, OpenSpec strict validation and diff whitespace validation.
