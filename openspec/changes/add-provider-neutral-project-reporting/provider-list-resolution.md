# W3.LISTS.B Request And Identity Resolution

Status: CODE_READY after independent design/validation check by Newton
(`01a19a14-0fc9-70c2-a37e-6071aaec132b`). The three requested precision checks
cover failed_index, final connection-metadata drift and direct key-path reads.
This refines provider-lists.md sections8/9; tasks.md is the sole execution ledger.
No Stage, workbook, capture or approval is persisted by this packet.

## Interfaces

Provider-owned values in `provider_sync/app/api/access_contracts.py`:

```text
ProviderRequestContext(actor: ProjectActor, project_id: str, request_id: str,
                       deadline_at: datetime, limits: CaptureLimits)
validate_request_context(context: ProviderRequestContext) -> None
```

IDs are canonical lowercase UUIDs, actor is a nonblank bounded subject and
deadline is timezone-aware. `AccessContext` remains separate and still requires
valid project/stage/capture/request IDs. No optional/fabricated Stage IDs.

`provider_sync/services/capture_session.py`:

```text
ProviderReadSession(context: ProviderRequestContext | AccessContext, reader, *,
                    timeout_seconds, authorize=None, clock=None, monotonic=None)
  .get_json(relative_path, params, *, item=None, page_key) -> CapturedJson
  .usage -> RequestUsage
  .remaining_seconds() -> float
  .close() -> None
CaptureSession(ProviderReadSession)
  .attach_archive_sink(ArchivePageSink) -> None
```

Refactor the existing request/count/deadline/strict-JSON path once into the base
class. A protected `_retain_response(HeldRawPage)` hook lets CaptureSession keep
its existing hold/flush/append behavior. The base session returns parsed data
but does not offer an archive sink or retain raw pages between requests.
The base class must not expose inherited capture attachment by accident.
Only CaptureSession accepts AccessContext and archive intent matching.
Existing capture page IDs, raw bytes, deadlines and accounting must not change.

`provider_sync/app/api/list_identity.py` public API:

```text
IdentifierBinding(requested: str, identity: WorkItemIdentity, updated: str)
IdentityResolution(profile_id: str, provider_id: str, endpoint_id: str,
                    principal: ProviderPrincipal,
                    bindings: tuple[IdentifierBinding,...], usage: RequestUsage)
ResolutionFailure(AccessError)
  .usage: RequestUsage
  .failed_index: int | None

ProviderListIdentityResolver(project_api, registry_loader, resolver_factory, *,
                             reader_factory=BoundCaptureReader, clock=None)
  .resolve(context: ProviderRequestContext, *, profile_id: str,
            provider_id: str, expected_endpoint_url: str,
            identifiers: tuple[str,...], online=False) -> IdentityResolution
```

`registry_loader()` returns a current ProjectProviderProfileRegistry.
`resolver_factory(registry)` returns a ProviderConnectionResolver for that
exact registry snapshot. Default composition uses the existing public factories,
not another credential store. Reload only metadata for final/current-source
checks; never change credentials halfway through the owned session.

This transport API deliberately accepts identifiers, not workbook DTOs. The
W3.LISTS.C application service binds the returned requested-token/identity map
to its stored worksheet/row provenance and semantic ApprovalProjection.
ProviderPrincipal.verified_at, IdentifierBinding.updated and usage are observations,
not approval-hash inputs. No raw body, token, cookie or credential path is returned.

## Admission And Flow

1. Require explicit online=True and validate context, explicit profile/provider,
   nonempty ordered tuple of unique identifiers, and configured max_members.
   Jira tokens use the already qualified numeric ID/key grammar, bounded256chars;
   no JQL, URLs or escaped path fragments. Unqualified HSD online resolution
   returns PART_CONTRACT_UNQUALIFIED before credential lookup. Offline numeric
   syntax remains the parser/application responsibility.
2. Check owner via the public Project API, and require nonarchived Project.
3. Load current selected profile, require enabled matching provider, then call
   describe_profile and compare expected URL through source_endpoint_matches.
   Jira Data Center server_pat is the currently qualified online combination.
4. Resolve the one selected connection. Its endpoint and opaque credential
   selection metadata must match the description. Open one BoundCaptureReader
   and one ProviderReadSession with the original context.
5. Verify `/myself`, resolve each supplied token via
   `/rest/api/2/issue/{token}?fields=id,key,updated`, then verify `/myself` again.
   Every HTTP request shares the same budget. No JQL/filter enumeration,
   comment/detail capture, retries, redirects or credential fallback.
6. Numeric requested ID must equal returned stable ID. A Jira key may resolve
   to a newer display key, but the response must have valid stable ID/key and
   updated fields. Repeated resolved stable IDs fail, even for different tokens.
7. An authorize callback reloads Project and public profile/connection metadata
   before each HTTP send. Compare provider/profile/enabled state and endpoint
   including auth/TLS/transport plus opaque credential kind/reference/revision.
   Recheck that metadata once more after the final identity response.
   A change refuses completion; no provider source-population query fields are
   part of this fixed-list identity operation.
8. Only complete, same-principal, same-connection resolution returns success.
   A source HTTP/shape/duplicate/limit failure raises ResolutionFailure with
   cumulative usage and failing input index (or None for identity/final check),
   not partial success. Owner/Project failures remain ProjectError and disclose
   no resolved bindings. All paths close the reader; nothing is persisted.

`ResolutionFailure` is a typed local observation. Missing usage on a pre-session
refusal is not a refund or evidence of zero prior runs; no durable operation
or billing ledger is introduced here.

## Reader Boundary

Extend the existing Jira allowlist only for
`/rest/api/2/issue/<positive-id-or-qualified-jira-key>`.
`/comment` remains a numeric-ID capture path. Requests for absolute URLs,
path escapes, worklog, attachments or write methods remain forbidden.
Keep normalized URL/TLS/proxy handling in the connection owner.

## Files And Tests

Owner files: `provider_sync/app/api/{access_contracts,list_identity}.py`,
`services/{capture_session,list_identity}.py`, `out/capture_reader.py`,
`tests/{test_provider_request_session,test_provider_list_identity,test_capture_reader}.py`.
Shared fixtures may extend `tests/capture_gateway_fixtures.py` with key lookup
without changing existing numeric capture responses. Current capture tests and
one real temporary-Git pipeline case are consumers of the refactored session.

| Case | Initial data / action | Expected result |
| --- | --- | --- |
| RB01 | stage-less request context, two reads, max_requests1 | first read succeeds, next denied before send; no sink capability |
| RB02 | request context passed to CaptureSession, malformed capture IDs | INVALID_ARGUMENTS, no reader use |
| RB03 | bad JSON, oversized/interrupted/403 response, expired monotonic deadline | same typed refusal/accounting as capture; reader closes |
| RB04 | existing capture attaches held identity and reads comments | original raw/ref/flush behavior and sink matching preserved |
| ID01 | owner mismatch/archive/offline/unqualified HSD/wrong endpoint | zero credential resolution/HTTP requests |
| ID02 | Jira key and numeric ID on a two-item profile | four requests total, correct map/current principal, closed responses |
| ID03 | two keys resolve same stable ID, numeric ID returns another ID | typed failure, no partial result |
| ID04 | final principal/profile/endpoint changes | completion refused, original budget, no fallback |
| ID05 | max_requests2 for two inputs or limit reached after a failed lookup | counter includes probes/failures; no extra request or success |
| ID06 | key path versus worklog/escaped/absolute paths | only the safe key lookup expands the reader allowlist |

Steps: first add RED tests for ProviderRequestContext/ProviderReadSession and
resolver admission/success; refactor the shared session; implement selected
identity resolution; add negative/final-check tests; run direct and affected
consumers, then update current docs. No new command or Stage approval in B.

```text
.venv/Scripts/python.exe -m pytest provider_sync/tests/test_provider_request_session.py provider_sync/tests/test_provider_list_identity.py provider_sync/tests/test_provider_capture_gateway.py provider_sync/tests/test_jira_capture_contract.py provider_sync/tests/test_capture_reader.py --ds=provider_sync.tests.connection_test_settings -q
.venv/Scripts/python.exe -m pytest project_management/tests/test_capture_pipeline.py::TestProjectCapturePipeline::test_shouldCommitCompleteSourceAndReadItThroughPublicProviderApi --ds=provider_sync.tests.connection_test_settings -q
```
