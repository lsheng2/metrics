## 1. Dashboard publish authority

- [x] 1.1 Add tests proving forged `approval_chat_demo_*` ids and arbitrary `dry_run_proof_id` cannot publish.
- [x] 1.2 Add a bound publish authorization service/model using `BugTrendAuditEvent` or a dedicated persistence layer.
- [x] 1.3 Require publish authorization to match profile/provider/workspace/range/chart/series/artifact/version/hash/proof/operation before Grafana import.
- [x] 1.4 Remove local-demo prefix auto-approval from the publish path.
- [x] 1.5 Update Dashboard publish approval APIs/tests/history to surface authorization metadata.

## 2. Dashboard artifact and workspace boundary validation

- [x] 2.1 Add negative tests for `workspace_key` mismatching artifact `profile_id/provider_id`.
- [x] 2.2 Enforce expected `workspace_key = metrics.{provider_id}.{profile_id}` from Metrics readiness during artifact validation.
- [x] 2.3 Extend unsafe artifact checks to include `nativeQuery` and any missing sensitive aliases.

## 3. AI Base artifact platform

- [x] 3.1 Add append-only artifact revision records with content hash.
- [x] 3.2 Add version-addressed artifact retrieval or summary fields sufficient for proof/approval binding.
- [x] 3.3 Replace Dashboard-specific artifact kind/source policy hardcode with a generic artifact authority registry or manifest-backed policy.

## 4. AI Base connector boundary and permission policy

- [x] 4.1 Add connector operation sensitivity/approval metadata and fail-closed model-visible exposure rules.
- [x] 4.2 Pass session/workspace context to connector runtime tool handlers.
- [x] 4.3 Enforce Metrics workspace boundary on model-visible connector operation arguments.
- [x] 4.4 Add tests for model-visible connector calls crossing provider/profile/workspace boundaries.

## 5. AI Base connector identity and transport safety

- [x] 5.1 Add Dashboard connector identity expectations to connector definition/config.
- [x] 5.2 Verify Dashboard sidecar identity before first connector invocation.
- [x] 5.3 Disable environment proxy trust for loopback connector base URLs.
- [x] 5.4 Add tests for wrong-service rejection and loopback proxy bypass.

## 6. E2E, docs, and cleanup

- [x] 6.1 Update Dashboard AI runbook to distinguish model-visible tools from internal governed workflow operations.
- [x] 6.2 Extend e2e stack script with non-mutating dry-run proof and approval-authority checks.
- [x] 6.3 Decide whether AI Base `.vscode/settings.json` and `pyrightconfig.json` are committed project policy or local config; remove or document accordingly.
- [x] 6.4 Run focused Dashboard and AI Base tests, OpenSpec validation, and the dual-app e2e smoke.
