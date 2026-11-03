# W3 Provider Connection Foundation

Status: implementation refinement for W2.REPLAN; not approved for coding until that gate passes.
Goal: one endpoint-bound credential resolver and safe local credential adoption, consumed by existing
Jira/HSD clients and the new reporting pipeline. Status remains only in [tasks](tasks.md).
Authority: [provider-access](provider-access.md); this appendix replaces the temporary W3 draft,
not the public task-run/1 contract. Profile source is repo-local; one implementation writer.

## 1. Scope And Evidence

Current credential helpers in `bug_metrics/provider_profile_connection.py` resolve endpoint and token
independently, and treat any `settings:` text as fallback. `create_jira_client` consumes those helpers.
HSD sync/probe clients repeat this resolution. Tasks uses its explicit `TasksConfig.jira`.
These are concrete migration consumers, not alternative runtime authorities.

Existing `ProviderProfileConfig.mapping_version_hash` excludes secret values; it cannot detect
an inline token change. Existing managed rows have `updated_at`; full profile saves update it.
Adoption must compare the actual observed row and credential reference, not only the mapping hash.
`select_for_update()` is not used as a SQLite correctness guarantee.

Constructor probe on installed `atlassian-python-api==5.0.3` accepted an injected requests.Session,
`backoff_and_retry=False`, `retry_with_header=False`, with zero Session.send calls.
This proves factory injection exists, not that redirect behavior is already safe.
`pywin32==312` cp313/win_amd64 wheel is available in the owned W3 wheelhouse; not installed in main env yet.
No actual source credentials or `.env` values were read for this design.

Donor behavior is read at commit `3d06b7a4a25434ee2fa133c9b4bef5f9c7c1366d`, primarily
`src/standup/adapters/jira_credentials.py`. Full donor configuration/runtime is not imported.
The exact blob/dependency mapping accompanies this packet in `provider-foundation-source.json`.

## 2. Files And Consumers

| Owner files | Responsibility / consumer |
| --- | --- |
| `bug_metrics/app/api/provider_connections.py` | Public DTO/resolver facade and safe errors; imported by clients |
| `bug_metrics/provider_connections/{__init__,contracts,normalization,resolver,handle,request_session,hsd_opener}.py` | Pure normalization, selected-source resolution, opaque handle and requests/urllib boundaries |
| `bug_metrics/provider_connections/{protected_store,windows_files,adoption}.py` | Protected source/target files and adoption application service |
| `bug_metrics/app/api/provider_credentials.py` | Public adoption API, calls owned profile persistence internally |
| `bug_metrics/app/api/provider_profile_config.py`, `provider_profile_config_persistence.py` | Keep secret reference metadata and avoid stale writes during adoption |
| `bug_metrics/provider_profile_security.py` | Export/redaction policy for protected references; no token/path disclosure |
| `jira_sync/out/jira_scope_issue_adapter.py` | Compatibility create_jira_client delegates, does not choose credentials |
| `jira_sync/management/commands/{sync_jira_scope,dump_real_jira_bug_trend_fixture}.py` | Explicit selected profile or legacy deployment config |
| `jira_sync/container.py` | Metadata client consumes legacy resolver; no new source selection |
| `provider_sync/management/commands/sync_{provider,hsdes}_profile.py` | HSD client consumes public resolved handle |
| `provider_sync/app/api/hsdes.py` | Injectable bound opener; integrated transport refuses redirects |
| `bug_metrics/app/api/provider_profile_connection_test.py` | Draft/saved connection test uses same resolver and safe errors |
| `tasks/out/jira_task_repository.py` | Explicit TasksConfig adapter, no replacement by global settings |
| `provider_sync/management/commands/provider_credentials.py` | Preview/apply JSON CLI over public adoption API |
| `metrics/settings/defaults_metrics.py`, `.env.example`, `requirements.txt` | Protected root and size limit, pinned Windows dependency |

W3 source does not edit W2 views/templates, unrelated Scope Config work, old repositories or real
provider data. No new DB model is required: managed profile row, its exact connection JSON,
mapping/source hashes and updated_at supply the conditional update boundary.
If implementation discovers a new data model is necessary, amend this packet before writing it.

Tests: `provider_sync/tests/test_provider_connections.py`,
`test_provider_credentials_adoption.py`, `test_provider_credentials_native.py`,
`test_provider_access_consumers.py`, `test_provider_credentials_command.py`.
Shared synthetic settings/fixtures may live beside those tests, not production modules.
Use `provider_sync/tests/connection_test_settings.py` with `.env` loading suppressed, known synthetic
credential/settings values and temporary test storage, selected explicitly through pytest `--ds`.
It must not initialize production data or fall back to the real developer .env during test collection.

## 3. Public Contracts

All values use frozen slots dataclasses. Only runtime handles retain credentials privately.
Error messages are fixed English text, never provider exception text; exception chaining is suppressed
at CLI/HTTP boundaries. No user-supplied factory, URL or arbitrary settings key is accepted by a command.

```text
ConnectionError(code: str)
TlsTrust(verification: bool, source: str, reference: str, readiness_id: str)
ProviderEndpoint(provider_id, base_url, endpoint_id, auth_mode,
                 timeout_seconds, tls: TlsTrust, transport)
CredentialSource(kind, reference, revision)
ConnectionInfo(profile_id, endpoint, credential, principal_id: str | None,
               principal_verified: bool, readiness, blocker_codes)

ProviderConnectionResolver(settings_source, profile_registry, protected_store)
  .resolve_profile(profile_id, *, expected_provider_id=None) -> ResolvedConnection
  .resolve_record(profile_record) -> ResolvedConnection
  .resolve_jira_settings(settings_source) -> ResolvedConnection
  .resolve_jira_config(jira_config) -> ResolvedConnection
  .status(profile_id) -> ConnectionInfo

ResolvedConnection.info -> ConnectionInfo
ResolvedConnection.open_jira_client(factory) -> Jira-compatible client
ResolvedConnection.open_hsdes_client(factory) -> HSD-compatible client
```

`resolve_jira_config` uses only its supplied object: jira_server_url, auth_mode,
jira_email, jira_api_token, verify_ssl, ca_bundle. No lookup of global settings or
registered profile is allowed on this path. Its nonsecret source is `explicit_config`.
`resolve_record` handles an explicitly supplied saved or draft provider profile, using the same
binding rules; it does not merge credentials from a different endpoint's saved record.

`ResolvedConnection` is not a dataclass, refuses pickling, has no token/header/kwargs getter and
its repr is safe. Concrete factories are trusted composition dependencies; the handle supplies their
credentials only after endpoint validation. It imports no `provider_sync` implementation.
Consumers pass the existing Jira/HsdesHttpClient factories. This is not a sandbox against malicious
Python code in the same process.

Internal file-store SPI (not exported by the public connections module):

```text
SourceFileReceipt(file_identity: str, last_write: str, owner_class: str)
read_source_toml(path: Path, *, max_bytes: int) -> (token: str, receipt: SourceFileReceipt)
ProtectedCredentialStore(root: Path, max_bytes: int)
  .create_candidate(*, provider_id, profile_id, endpoint_id, auth_mode,
                    token: str) -> CredentialSource
  .read_selected(*, reference, revision, provider_id, profile_id,
                 endpoint_id, auth_mode) -> str
  .list_unreferenced(profile_references: frozenset[tuple[str,str]]) -> tuple[PendingCredential,...]
PendingCredential(reference: str, revision: str, status="pending_cleanup")
```

Secret-returning SPI calls are confined to resolver/adoption internals, never public DTO/CLI paths.
An injected store must implement all three methods; missing protected capability is a safe error,
not a reason to reinterpret a protected reference as an inline/settings secret.

Public principal is `None`, verified=false for offline status, including Windows integrated auth.
Successful server-info/saved-query connectivity alone cannot invent a verified user identity.
Verified principal acquisition belongs to W3.GATEWAY's explicitly online operation.
Credential revisions are `unknown:settings`, `unknown:inline`, `unknown:explicit_config`,
`unknown:windows_integrated`, or the actual protected revision. Unknown is not evidence no rotation occurred.

## 4. Resolution And Transport

Normalize endpoint as HTTPS origin plus optional base path; lower-case host, normalize default443,
remove terminal slash, reject userinfo/query/fragment/backslash/control/whitespace/dot segments,
encoded path separators and ambiguous escaping. Do not drop an enterprise `/jira` or HSD `/rest` base.
`endpoint_id = SHA256(canonical JSON(provider_id, normalized_base_url, auth_mode))`.
TLS trust configuration is separately compared for transport readiness; verify_ssl=false is rejected
for reporting/credential adoption. Corporate CA bundle remains supported.

`TlsTrust.source` is `system` or `custom_ca`; verification is always true for admitted connections.
Public reference is `system-ca` or `configured-ca`; it contains no filesystem path.
The handle privately holds the configured CA path (absolute normalized local file, no URI) or `True`,
and passes that same value to the session.verify and Jira factory without a global fallback.
`readiness_id = SHA256(canonical JSON(verification,source,normalized private CA configuration))`;
this identifies configuration, not a claim that a mutable certificate file's bytes never changed.
Offline status may check path shape/readability but does not claim a live TLS handshake.
Requests owns CA parsing/verification at request time; malformed/missing trust returns a safe
connection failure without retry using verify=false or a different CA source.
Adoption preview includes tls.readiness_id, so changing trust configuration invalidates it.
PC06 separately tests a supplied TasksConfig custom CA against deliberately conflicting globals,
system CA with no custom file, rejected false verification, and no private CA path in public status.

Allowlisted settings references are exact provider field names, including the documented provider-wide
`settings:METRICS_JIRA_*` or `settings:METRICS_HSDES_*` credential marker. Unknown references fail;
they are not arbitrary environment/vault lookups.

Selection order:

1. Explicit protected reference: require its exact revision and endpoint/provider/profile/auth binding;
   invalid/missing material fails, never fallback.
2. Explicit inline legacy credential: use only the selected credential family and report unknown revision;
   do not merge credential members from other sources.
3. Explicit settings reference, or legacy empty credential selection: use deployment credentials only
   if normalized profile endpoint and auth mode match the deployment endpoint/auth mode.
4. HSD integrated auth: no token is read; report unknown principal/revision.

Conflicting top-level and nested secret values or multiple conflicting credential aliases fail rather
than choosing insertion order. Empty/malformed selected values fail, not fall back.
Draft connection tests must not borrow a saved profile credential after changing its endpoint/auth.

Jira factory creates a `BoundProviderSession(requests.Session)` from the validated endpoint.
At the send boundary, require same normalized origin and allowed base path, force
allow_redirects=false, reject every3xx, allow GET/HEAD and only the Jira read-search POST paths
`<base>/rest/api/{2,3,latest}/search` used by the existing client. All other POST/PUT/PATCH/DELETE fail
before send. The allowlist does not authorize a new CLI raw-query surface.
Clear cookies and use only selected service auth.
Atlassian backoff/retry-with-header are disabled; failed auth never re-resolves another source.
Do not allow Requests netrc to replace selected Bearer credentials. Preserve corporate proxies by
explicitly resolving applicable proxy settings at construction and assigning them to the session;
then set trust_env=false. Proxy values remain private, never exported.
Transport tests drive a real requests.Session with a synthetic HTTPAdapter, not merely factory kwargs.

HSD urllib factory uses a bound opener rejecting redirects and wrong origins before sending auth.
Existing integrated Windows request path must set maximum redirection0 and preserve default credentials;
the chosen endpoint/path is validated before subprocess creation. No browser cookies or fallback auth.
Tests inspect and run synthetic transport behavior; actual Kerberos remains separate qualification.

## 5. Protected Files

Add `pywin32==312; sys_platform == "win32"`. No permission-check opt-out.
New settings are `METRICS_PROVIDER_SECRET_DIR` (default existing state_dir/provider-secrets) and
`METRICS_PROVIDER_SECRET_MAX_BYTES` (default65536). Do not create directories at module import.
Non-Windows native adoption reports unsupported unless an equivalent platform policy is separately
implemented; ordinary settings/inline resolution remains portable.

Adoption input is one explicitly selected TOML file with `[jira] token="..."`, not a raw token file,
whole config import or implicit environment fallback. Token is1..8192 ASCII printable non-whitespace chars.
Source path appears only in trusted CLI argv; never profile/audit/result/error/model input.
This source format is qualified only for a Jira server_pat target. Reject HSD, cloud_basic or other
auth modes before reading the source; do not install a Jira PAT as a differently shaped credential.
Future source formats may extend the public service with separately validated provider adapters.

Open source via Win32 handle with read/control access, OPEN_EXISTING and OPEN_REPARSE_POINT,
no write/delete sharing. Validate same-handle file identity, regular-file attributes, size, protected DACL
and owner. Allowed owner/allow ACE SIDs: current user, SYSTEM, Administrators. Reject null/unprotected DACL,
unrecognized ACEs and other allow principals. Read from that handle; no path validate/reopen race.
All ancestor paths are checked for reparse/ambiguous targets; source bytes never change.

Target paths use generated IDs only:
`<root>/<provider>/<profile>/<secret-id>/<revision>.secret` plus `.meta.json`.
Metadata binds schema_version, secret-id, revision, provider, profile, endpoint_id, auth_mode, created_at.
Neither metadata nor public outputs contain token/hash/length/source path.
Use atomic CREATE_NEW with protected security attributes, flush bytes, verify through protected handle,
then create metadata. Parent directories are application-owned/protected, never recursively reset ACLs
on an existing unowned directory. Read rechecks protection and metadata binding every time.
Before writing either final file, create a protected exclusive intent file
`<root>/<provider>/<profile>/<secret-id>/<revision>.intent.json` containing that same nonsecret
metadata and `kind=credential_candidate`. The immutable intent is the durable inventory authority
for both partial and completed candidate files; no post-rollback write is required to remember them.
The currently committed profile reference is the only active selection authority.
`ProtectedCredentialStore.list_unreferenced(profile_references)` scans these owned intents and returns
secret-id/revision and `pending_cleanup` for any reference absent from the committed profile set;
an active reference is never labeled disposable. It never returns paths/bytes or deletes anything.
Intent write failure means no later secret-file write. Crashes after intent/token/metadata leave an
inventory entry; resolve requires complete protected metadata and a currently selected exact reference.
Incomplete/unreferenced revisions stay protected and are not automatically deleted.

## 6. Preview And Apply

Preview is read-only, including zero DB/profile/audit writes.
It reports the nonsecret current source class/revision, profile mapping/source hashes,
profile updated_at if managed, endpoint_id/auth_mode, and a source file identity receipt
(volume/file ID/last-write marker, not source path or token attributes).
It does not generate a random target revision, because recomputing preview must yield the same receipt.
The public AdoptionPreview has only the declared nonsecret fields below. Do not hide raw connection
JSON in an extra field and rely on to_dict redaction: repr/asdict/serialization must also remain safe.
Apply keeps its immediately observed old connection JSON in a private local transaction input for CAS,
never accepts that value from the public preview document. A metadata-only resolver operation supplies
endpoint/source/trust information without fabricating dummy credentials or requiring existing auth.

```text
AdoptionPreview(profile_id, provider_id, endpoint_id, auth_mode, profile_kind,
                tls_readiness_id,
                expected_mapping_hash, expected_source_hash, expected_updated_at,
                expected_credential_reference, expected_credential_revision,
                source_identity, source_last_write, adoption_id, conflict)

adoption_id = SHA256(canonical JSON(all preceding nonsecret preview fields))

CredentialAdoptionService.preview(profile_id, source_file) -> AdoptionPreview
CredentialAdoptionService.apply(profile_id, source_file, *, expected_preview,
                                replace=False) -> AdoptionResult
AdoptionResult(status="applied", adoption_id, profile_id, credential_reference,
               credential_revision, mapping_hash, source_hash, updated_at)
```

CLI `provider_credentials preview --profile-id --source-file` prints the preview JSON.
CLI `provider_credentials apply --profile-id --source-file --preview-file --apply [--replace]`
accepts the locally saved nonsecret preview document, strictly validates its schema/size and recomputes
all fields. `--preview-file` is a file path, not arbitrary code or credentials. It is not itself
authentication: this command is a trusted local operation. New secret IDs/revisions are generated only
after the preview has been revalidated.
The CLI accepts either the raw preview DTO or its exact successful schema_version1 stdout envelope.
This permits saving preview stdout and passing it back without hand-editing JSON. Failed envelopes,
unknown fields, duplicate keys and documents over65536bytes are rejected before apply.

Settings/inline revision remains explicitly unknown. Replacement authorizes changing the selected
profile reference, not deleting/revoking the old environment value or proving it never rotated.
Apply re-reads current source and compares file identity/last-write metadata; online verification is
separate. If this cannot establish a stable selected source read, fail and require a new preview.

Transaction:

1. Validate expected preview against current profile/source with no mutations. If conflict and
   replace=false, fail before writing. Construct only a whitelist public result.
2. Begin transaction.atomic. For a managed profile, perform a conditional no-op UPDATE matching PK,
   mapping_version_hash, source_version_hash, updated_at AND exact old connection_settings JSON.
   This obtains SQLite's write lock and detects inline secret or reference races without exporting a hash.
   Zero rows means CAS mismatch. Locked/busy means safe retryable PROVIDER_BUSY, no blind retry.
3. For a bundled profile, compare the immutable selected record and require no managed row.
   Create the managed row inside the same transaction, before secret files, under unique profile_id.
   Use a nested savepoint for unique conflict; never query inside a broken transaction.
   Revalidate the managed row/expected public source before proceeding. Failed later work rolls it back.
4. Write an exclusive protected intent, then new secret plus metadata. No existing file is overwritten.
5. Under the held write transaction, update the selected row connection_settings to protected reference,
   remove all inline secret aliases, preserve unrelated source/mapping fields. Recalculate and persist
   both hashes and updated_at using the existing owner helpers. Add safe audit in the same transaction.
6. Commit. Only then return applied. Old secret files/settings are untouched.

If file write, CAS, DB or audit fails, profile/audit transaction rolls back; any new file remains
unreferenced/protected, inventoried by its immutable intent, and is returned as pending local cleanup
by the owner scanner. Failure has no AdoptionResult; safe error contains only the adoption ID if available.
Existing profile editor saves must use the same owned conditional connection write boundary when a
protected reference is present: a stale form must not silently resurrect inline values or discard a
concurrently adopted reference. This affected consumer gets a concrete race test.

New CLI success: stdout one schema_version/result/error JSON. Business/argument/internal failure:
stdout empty, stderr one safe envelope, nonzero. Help remains standard. Avoid CommandError prefix
for machine protocol; suppress raw traceback/source paths in public diagnostics.

Error set for this leaf: PROVIDER_PROFILE_UNAVAILABLE, PROVIDER_UNSUPPORTED,
PROVIDER_ENDPOINT_INVALID, PROVIDER_ENDPOINT_CREDENTIAL_MISMATCH, PROVIDER_TRUST_INVALID,
PROVIDER_CREDENTIAL_UNAVAILABLE, PROVIDER_CREDENTIAL_INVALID, PROVIDER_CREDENTIAL_UNPROTECTED,
PROVIDER_CREDENTIAL_PLATFORM_UNSUPPORTED, PROVIDER_CREDENTIAL_CONFLICT,
PROVIDER_CREDENTIAL_CAS_MISMATCH, PROVIDER_REDIRECT_UNSUPPORTED, PROVIDER_METHOD_FORBIDDEN,
PROVIDER_AUTH_FAILED, PROVIDER_PERMISSION_DENIED, PROVIDER_NETWORK_ERROR, PROVIDER_BUSY,
INVALID_ARGUMENTS and INTERNAL_ERROR. Codes have a fixed safe English message dictionary.

## 7. Tests And Sequence

| IDs | Layer / actual boundary | Required negative evidence |
| --- | --- | --- |
| PC01-PC06 | L1 resolver with synthetic settings/registry | exact settings binding; endpoint/auth drift; conflicting aliases; malformed explicit ref; unknown principal/revision; explicit TasksConfig despite different globals |
| PC07 | L1 real requests.Session with synthetic HTTPAdapter | wrong origin/base path zero send;3xx one send/no redirect;401 one credential/no re-resolve |
| PC08 | L1 same requests boundary | POST/PUT/PATCH/DELETE rejected except exact read-search POST allowlist; no netrc/cookie replacement; retry flags disabled; synthetic HTTPS proxy retained with trust_env=false |
| PC09 | L1 actual HSD urllib opener with synthetic handler | wrong origin/base path before auth/send;302/307 rejected with zero second endpoint calls; selected auth only |
| PC10 | L1 HSD integrated request builder with synthetic process runner | validated endpoint and encoded safe request; MaximumRedirection0 present at consuming PowerShell boundary; redirect/error returns safe failure and no alternate transport invocation |
| PA01-PA05 | L2 real ORM + synthetic protected store | preview zero writes; apply/ref CAS; stale updated_at/secret-only update; two same-preview applies at most one accepted; DB/audit failure retains old reference and intent-scanner reports new revision pending_cleanup |
| PA06-PA09 | L3 actual Win32 handles/temp files | actual protected DACL owner/access; unprotected/null DACL/link/directory rejected; same-handle read; new intent/token/metadata permissions and original source unchanged; partial write remains inventoried |
| PA10 | L3 two local processes/temp SQLite | concurrent apply/store write claim, unique successful reference/audit, no lost update; stale editor cannot overwrite adopted ref |
| PC11 | L2 affected consumers | each row in section2 delegates same resolver; legacy CLI outputs preserved; status/metadata do not auto-sync |
| PA11 | L2 subprocess CLI | invalid args/read failure/conflict safe single JSON stderr; source/token canaries absent; help and valid preview behavior |

PA06-PA10 are native tests, not mocked ACL tests renamed native. Keep pure parser/ACL-decision unit
tests separate. Run native once on a stable candidate; no actual personal credentials.
W3.CREDENTIALS has three internal checkpoints: resolver/factory -> consumer migration -> adoption.
They do not bypass the parent dependency; W3.ARCHIVE waits for the full leaf.

First RED:

```powershell
.\.venv\Scripts\python.exe -m pytest provider_sync/tests/test_provider_connections.py --ds=provider_sync.tests.connection_test_settings -q
```

Then run `test_provider_access_consumers.py`, `test_provider_credentials_adoption.py`,
`test_provider_credentials_command.py` with explicit paths. Final native command selects
`provider_sync/tests/test_provider_credentials_native.py`; it cannot silently skip on this Windows host.
Use real temporary DB under a guarded fixture root and subprocess timeout/cleanup ownership;
exact native fixture names/commands are fixed before invocation.

Affected existing tests: `tasks/tests/test_unit_jira_task_repository_auth.py`,
`jira_sync/tests/test_sync_jira_scope_command.py`, `jira_sync/tests/test_api_scope_metadata.py`,
`provider_sync/tests/test_sync_provider_profile_command.py`,
`provider_sync/tests/test_api_hsdes_live_sync.py`, `bug_metrics/tests/test_api_provider_profile_config.py`.
Validate Django check, migration drift, OpenSpec and byte-matched candidate hygiene.
Do not execute existing live-marked tests just because their filename is in this consumer list.

## 8. Propagation And Exit

PM-CONNECTION: resolver -> bound factories -> legacy sync/metadata/task/probe + future gateway.
PM-CREDENTIAL: protected files -> resolver -> all the same consumers; profile adoption/CAS -> profile
editor/export/audit. No credential getter or secondary resolution path.
CLI, audit, serialized references, caches, tests and operator docs all consume the new identity;
UI reporting itself stays offline. Unknown revisions never become reusable permission evidence.

Independent review must verify actual paths, not merely the facade exists.
Exit is a usable single connection authority and protected local adoption with negative/native tests,
no source credentials migrated unless explicitly invoked, and every affected existing consumer mapped.
Not a claim of complete capture, Jira/HSD live identity, AI Base integration or formal deployment.
