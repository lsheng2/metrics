# W3 Gateway And Capture Packet

Status: ready for implementation after W3.ARCHIVE closure and Poincare's independent plan/validation
review, with the reported API gaps resolved. Canonical ledger is tasks.md. W3.GATEWAY -> W3.CLI ->
W3.CAPTURE are serial checkpoints of this packet. Lists/grants/attachments/HSD have later exact packets.

## 1. Boundary

Project owner/stage -> frozen descriptor -> selected resolved connection -> verified provider principal ->
bounded membership/raw pages -> CaptureArchiveService -> immutable snapshots/coverage.
Neither metadata views nor legacy metrics cursor is a complete reporting capture authority.
Legacy sync consumers keep their existing protocol; no raw-query option is added to a bound stage.
Raw response bytes go to the archive callback before JSON decoding, even if the response later fails
validation. Never put token/auth headers/cookies or private credential paths into a raw page descriptor.

Sources and product differences are recorded in [provider-api-evidence](provider-api-evidence.md).
Jira Data Center is the first full capture adapter. HSD remains its own adapter with truthful coverage;
do not infer comment/history capability from Jira or claim unsupported APIs are nonexistent.

## 2. Public Contracts

New `provider_sync/app/api/access_contracts.py` contains frozen slots values:

```text
CaptureLimits(max_requests=256, max_download_bytes=268435456, max_response_bytes=16777216,
              max_members=500, max_details=100, max_comments_per_item=10000,
              max_history_per_item=20000, page_size=100)
AccessContext(actor: ProjectActor, project_id: str, stage_id: str,
              capture_id: str, request_id: str, deadline_at: datetime, limits: CaptureLimits)
ProviderPrincipal(provider_id, endpoint_id, principal_id, verified_at, evidence_page_id: str | None)
RequestUsage(requests: int, downloaded_bytes: int)
WorkItemMarker(identity: WorkItemIdentity, updated: str, fields_hash: str, fields: Mapping)
MembershipObservation(members: tuple[WorkItemMarker,...], coverage: PartCoverage,
                      raw_page_ids: tuple[str,...], definition_hash, usage: RequestUsage)
ItemObservation(snapshot: SnapshotInput | None, identity, marker: WorkItemMarker,
                coverage: CaptureCoverage, failures: tuple[str,...], usage: RequestUsage)
AccessStatus(profile_id, provider_id, readiness, principal_verified: bool, blockers: tuple[str,...])
```

Current fields and updated string preserve provider precision; comparison markers from search and
detail endpoints have different domains and are never compared as interchangeable timestamps.
All IDs and capture/source DTOs reuse `project_management.app.api.capture_archive` public exports.
Provider implementation never imports a project private storage class.

`provider_sync/app/api/access.py`:

```text
ProviderAccessService(project_api, connection_resolver, adapter_registry, archive)
  .profiles(*, provider_id=None) -> tuple[PublicProfile,...]
  .status(profile_id) -> AccessStatus
  .scope(actor, project_id, stage_id) -> FrozenScopeStatus
  .verify(context, *, online=False) -> ProviderPrincipal
  .enumerate(lease: ProviderCaptureLease) -> MembershipObservation
  .capture_item(lease: ProviderCaptureLease, marker) -> ItemObservation
  .read_item(actor, project_id, stage_id, capture_id, source_key) -> SnapshotInput
  .open_capture(context, *, online=False) -> ProviderCaptureLease
ProviderCaptureLease(principal, resolved_scope, usage)
  .attach_archive_sink(sink) -> None
  .enumerate() -> MembershipObservation
  .capture_item(marker) -> ItemObservation
  .verify_final() -> None
  .close() -> None
```

`PublicProfile(profile_id,provider_id,display_name,enabled)` and
`FrozenScopeStatus(project_id,stage_id,definition_hash,source_status,descriptor,
first_resolution_hash=None,first_principal_id=None)` contain no credentials.
The optional fields identify the first stored verification, not a claim of current online permission.
`verify(...online=False)` refuses CAPABILITY_UNAVAILABLE and makes no connection. Online caller must
have exact stage owner, unchanged source, nonarchived project and remaining deadline/budget.
`status`, `scope`, stored `read_item` are offline; missing data returns explicit unavailable, no fetch.
No default project/stage/profile or first enabled scope on these reporting APIs.
`open_capture` creates exactly one bound connection and counter/deadline session for this capture.
The lease is an in-process closeable context, not a durable authority or public serializable object.
Other public online methods delegate to that same caller-supplied lease for a running capture; they never
reset a counter by constructing another reader. ProjectCaptureService uses one lease end to end.
Attempted requests, identity probes, filter reads and final validation all debit that same budget.
Counters from returned observations are cumulative receipts, not grants for additional requests.

Shared adapter SPI in `provider_sync/app/spi/capture.py`:

```text
ProviderCaptureAdapter.verify(connection, session) -> ProviderPrincipal
ProviderCaptureAdapter.resolve(descriptor, principal, session) -> SourceResolutionInput
ProviderCaptureAdapter.enumerate(descriptor, principal, session) -> MembershipObservation
ProviderCaptureAdapter.capture(marker, descriptor, principal, session) -> ItemObservation
CaptureSession.get_json(relative_path, params, *, item=None, page_key) -> CapturedJson
HeldRawPage(page_key, item: WorkItemIdentity | None, content_type, body: bytes,
            request_fingerprint, partial: bool, error_code: str | None)
CapturedJson(value: Mapping, raw_page_id: str | None, page_key, request_fingerprint)
ArchivePageSink(intent: CaptureIntent, append_page: Callable[[RawPageInput], RawPageRef])
```

`CaptureSession` owns counters and original monotonic/UTC deadline; every failed or successful request
counts before send. Its archive sink is `append_page(actor,intent,RawPageInput)` supplied after prepare.
The sink returns a page ID. This is a bounded source-session object, not a second operation scheduler.
The sink's intent must match the lease project/stage/capture/request/source/deadline before attachment.
`RawPageInput` adds optional `partial=False,error_code=None`; nondefault values are persisted in the
page intent, leaving prior raw bytes and the existing RawPageRef/manifest format unchanged.
They cannot turn an incomplete transport response into a decoded complete document.
The lease uses SourceResolutionInput directly for resolved_scope; its canonical hash is the resolution
hash, not another mutable copy of the source rule. Dependency source_hash is SHA256 of exact UTF-8 JQL.

`project_management/services/capture.py`:

```text
ProjectCaptureService(project_api, provider_access, archive, clock)
  .capture(context: AccessContext) -> CaptureReceipt
```

This internal synchronous application method is not invoked on page GET or public capture CLI before W7.
It verifies source/principal, creates the immutable capture intent, enumerates full membership,
captures at most max_details with all remaining members pending, finalizes complete or partial.
W3 internal synthetic integration is a real service test, not a fake public operation ID.
Policy changes or drift refuse new observations without rewriting already retained evidence.
On a post-prepare failure the archive's `finalize_partial` accepts the last known MembershipInput.
It recovers any durable page intent first and retains that membership even when no item detail has
completed; the older default without membership is still available when membership is genuinely unknown.
Commit/publication errors are not reclassified as a different partial candidate after a commit attempt.

## 3. Request And Raw-Byte Boundary

Expose a narrow `ResolvedConnection.open_capture_reader(factory)` composition hook.
It uses the same credential source/TLS/proxy/endpoint validation as CREDENTIALS and returns only a reader,
not a token or raw header getter. Jira reader reuses BoundProviderSession; HSD reader uses bound
opener/integrated runner. Normalized endpoints are not independently recomputed in the project domain.
`source_endpoint_matches(ConnectionInfo, source_endpoint)` belongs to the connection public API.
It compares through that owner's normalizer; the capture retains the original frozen descriptor URL
alongside the normalized opaque endpoint ID, so equivalent case/default-port/trailing-slash spelling
neither breaks archive identity nor rewrites an existing Stage hash.

`BoundCaptureReader.read(relative_path, params, *, timeout, max_bytes) -> RawResponse`
where `RawResponse(status_code,content_type,body: bytes,partial: bool,error_code: str | None)`
has no request/response credential headers. Partial indicates bounded/truncated/interrupted transport,
not a full JSON document. Such bytes are retained as partial raw evidence and cannot enter the decoder.
Paths come only from provider adapter allowlists; queries are serialized with structured URL APIs.
Use streaming response iteration and stop before storing >max_bytes; close response in all paths.
Requests include identity+purpose only in private session. No redirects/retries/provider-write methods.
Handle failed HTTP responses with bounded body as raw evidence, then safe error code; never raw exception.
Duplicate JSON keys/NaN/nonobject responses are rejected with the original page preserved.

The source callback must not acquire archive locks while network is in progress; it is called only after
bounded response bytes are obtained. A read failure before any bytes may record request error metadata;
partial network bytes are saved explicitly partial and never parsed as a full response.
Remaining request/download budget zero or deadline reached stops before the next send.
No implicit sleep/retry after429/401/403; usage and pending work remain.

Readiness/principal verification has one small metadata probe before capture prepare. Its raw evidence is
temporarily held within response-size budget, then archived as the first page after principal-bound intent.
If identity cannot be verified, no principal-bound capture is created and no model input can use it.
This is not permission to label an unknown identity verified merely to archive data.
The lease attaches its archive sink only once after prepare, then flushes the bounded held identity/
definition pages with their original request keys. A second attachment or another capture identity fails.
Explicit standalone verify returns identity/usage but does not claim those pages already have archive IDs.

## 4. Jira Adapter

Jira API paths appended to the selected enterprise base path, including `/jira` when configured.
Identity: GET `/rest/api/2/myself`; stable principal is response.key when present, else response.name
only for a contract declaring that name as stable. Missing/wrong shape means PRINCIPAL_UNVERIFIED.
No Cloud accountId fallback unless that adapter is explicitly selected.

Membership: validate approved JQL with `validateQuery=true`, read lightweight id/key/updated/summary/
status/resolution/assignee/issuelinks. Require startAt=requested offset, nonnegative total,
unique stable IDs and keys, no error/warningMessages, complete pages. Start at0; next adds actual
returned length. Total changing, empty page before total, duplicate ID, overlimit fail completeness.
Repeat lightweight enumeration once at end and compare the stable ID/marker set; inconsistency retains
partial capture, never declares an immutable transactional Jira snapshot.

For saved-filter dependencies in JQL, use the donor proven parser/recursive filter resolution strategy,
pin parser bundle and filter-definition hashes. A changed nested filter is source drift, not ordinary
membership update. Until the parser/closure can prove the chosen rule, refuse it with SCOPE_UNVERIFIABLE;
do not use substring/regex parsing of arbitrary JQL to authorize queries.
Node22.18.0 is installed and matches the donor tested version. Pin the donor parser.cjs/manifest/license
resources rather than invoking npm during capture; bounded utility process uses its fixed input/output
and no inherited developer tools. Parser failure is a source-admission failure, not an empty valid query.

`ResolvedScope(original_rule_hash, effective_query, dependency_definitions, resolution_hash)` is
produced by the adapter. First source admission appends one immutable resolution binding for this Stage;
later captures must match it, including nested saved filter definitions. A changed definition returns
SOURCE_CHANGED and requires a new Stage; it cannot overwrite the prior rule binding.
This is a derived source-definition guard, not a second editable scope configuration.
Archive exposes a narrow `bind_source_resolution(actor,project_id,stage_id,definition) -> str`
at the same StageRepository owner, with a registered `source_resolution` record type.
It is added/tested with this gateway packet, not claimed present in W3.ARCHIVE.
Exact archive DTOs:
`SourceDependencyDefinition(filter_id: str, query: str, source_hash: str)`;
`SourceResolutionInput(original_rule_hash, provider_id, endpoint_id, principal_id, effective_query,
dependencies: tuple[SourceDependencyDefinition,...], resolver_revision: str)`;
`SourceResolutionRef(resolution_hash: str, commit_id: str)`.
Hash is canonical input JSON; dependencies sorted by stable filter ID and duplicate/cyclic references
rejected. Only source_resolution/first.json is written under the new registered namespace.
Repeated identical definition returns original ref; differing definition returns SOURCE_CHANGED.
Public `read_source_resolution(actor,project_id,stage_id)` returns that immutable value or explicit
absence. Raw source-definition response bytes are held until capture sink attachment, then archived;
the resolution record is a derived rule guard, not a replacement for those raw pages.
The first binding is accepted only after existing frozen rule/owner/principal checks and complete
server validation; it is shown as first verified source definition in stored scope status.
Re-read dependency definitions at the end of capture; drift makes current capture partial and does
not update the immutable first binding.

Final sequence: owner/project/stage -> lifecycle/descriptor -> enabled profile -> connection material ->
one lease `/myself` -> JQL/filter closure and strict server validation -> bind source resolution ->
prepare principal-bound capture -> attach sink/flush held raw -> complete membership -> bounded details ->
final membership/filter reread -> final `/myself` -> complete or partial finalize.
Any refusal before prepare makes no principal-bound capture; after prepare, successful prior pages
are sealed partial. No step substitutes another identity or renews the original lease budget.

Details by stable issue ID:

1. GET issue fields=*all and expand=changelog,names,schema. Check returned ID and key/updated fields.
2. GET every comments page; validate exact IDs/total/startAt and retain every body/raw record.
3. Expanded field history must startAt0 and total match actual unique records; otherwise history partial.
   Do not call the unavailable Data Center issue/changelog pagination endpoint.
4. Attachments metadata preserved; body not_requested. Linked records listed as metadata, no out-of-scope GET.
5. Re-read issue fields/expansion and compare with the initial content using the donor approved comparison
   policy; keep both raw versions. Any inconsistent marker/field/history observation prevents complete.
6. Verify principal remains the same at the end of the capture before finalization.

Closed/Fixed is display status only. No-change decisions require same provider/site/principal/rule/marker
plus a prior complete source and valid accepted summary; W3 itself may reuse a prior complete source
observation as an explicit reference, never manufacture a new complete raw snapshot.
Initial W3.CAPTURE may fetch selected details each time; W4 adds deterministic no-change/accepted reuse.
Model input optimization is separate from source download, never implemented by dropping comments.

## 5. HSD Boundary

Reuse explicit profile saved-query/tenant/subject configuration and its own identity endpoint `/rest/user`.
Official query paging is1-based with end-row semantics; fixture/decoder must reflect that, not legacy0/count.
Raw records/comments/history use documented article/children/history endpoints with explicit field lists.
Missing documented response schema means the adapter selects only a qualified decoder revision backed
by a captured approved sample, or reports PART_CONTRACT_UNQUALIFIED; arbitrary dict coercion is forbidden.
Current canonical facts from the existing HSD provider are usable only with honest part coverage.
If principal response cannot establish identity, strict capture/summary is blocked, not assigned a
hardcoded principal. HSD live qualification is separate from implementing synthetic decoding.

This packet does not mark HSD comments/history complete merely because the endpoints exist.
W3.HSD must return a truthful provider result on same project pipeline and cover the required-part
refusal in W5; changing from facts-only to complete requires actual adapter qualification.

## 6. CLI Checkpoint

`manage.py provider_access profiles [--provider-id]`, `status --profile-id`,
`scope --project-id --stage-id`, `item --project-id --stage-id --capture-id --item-id`
use trusted `local_operator` and the public service. No actor/token/URL/JQL/path option.
`verify` and scope `--online` explicitly select context/deadline/budget and refuse if not qualified.
`capture` and `operation` return CAPABILITY_UNAVAILABLE until W7 runtime owns their durable execution;
zero fabricated operation ID, zero new raw writes/upstream requests.
New command follows the credential CLI's safe argument/error envelope implementation pattern,
not subprocess text scraping or domain duplication. Legacy sync output stays unchanged.
Exact online CLI arguments are `verify --project-id --stage-id --online --deadline-at <UTC ISO8601>`
and `scope --project-id --stage-id --online --deadline-at <UTC ISO8601>`.
Optional integer `--max-requests/--max-download-bytes/--max-members` may lower the configured limits,
not silently exceed them. Request/capture IDs are newly generated only for explicit online operations;
the result reports request usage and source verification, not a completed capture or durable run.
`verify --profile-id` is not sufficient for stage-scoped reporting access and is rejected.
Standalone online scope uses one short-lived lease and returns membership coverage without initializing
an archive; capture service supplies the archive sink during its internal run. No command exposes token
or filesystem input except the separately qualified credential-adoption command.

## 7. Validation And Files

Files: `provider_sync/app/api/{access,access_contracts}.py`, `app/spi/capture.py`,
`out/{capture_reader,jira_capture,jira_pages,jira_scope,hsdes_capture}.py`,
`management/commands/provider_access.py`, `project_management/services/capture.py`,
the narrow handle factory and consumer tests. Preserve old metrics calculation/history ownership.
The copied `_jql` resources are protected by `.gitattributes` with `-text -filter`;
normal Git hashing under Windows autocrlf must match their pinned donor blobs.
Donor source/resource/test exact closure for Jira parser/capture/consistency must be fixed before code.

| Case | Exact behavior to disprove |
| --- | --- |
| GA01 | Owner/stage mismatch or archived/source_changed refuses before connection/secret lookup |
| GA02 | Wrong principal/schema/endpoint has no complete capture/model input |
| GA03 | Pagination duplicate/total drift/empty middle page/max members keeps raw pages but not complete |
| GA04 |100detail limit with500members yields full membership+pending400, never silently omits scope |
| GA05 | Comments added B/C are both retained; old comment edit retains full new snapshot, no last-comment-only shortcut |
| GA06 | Request/download/deadline limit stops before next request; interrupted bytes remain partial |
| GA07 | Required history/comment coverage failure blocks complete, retains raw error pages and successful earlier pages |
| GA08 | Changed nested filter/JQL definition cannot continue under frozen rule |
| GA09 | Closed/reopened items still observed; no status-based skip |
| GA10 | Safe CLI profiles/status/item offline; verify requires online; capture/operation unavailable without IDs |
| GA11 | Source lost/403 remains access_lost and pending, not closed or deleted |
| GA12 | HSD distinct auth/paging/decoder/coverage, no fake Jira data/identity |

Test modules: `test_provider_capture_gateway.py`, `test_jira_capture_contract.py`,
`test_provider_access_command.py`, `test_hsdes_capture_contract.py` under provider_sync/tests,
and `project_management/tests/test_capture_pipeline.py` using real temporary Git archive + synthetic
HTTP adapter. Test actual public services and raw bytes/coverage/request counts, not accepting mock objects.
No real Jira/HSD/model calls for this packet's coding acceptance. Exact live prerequisites stay separate.

Implementation order within the named ledger nodes:

1. W3.GATEWAY first creates reader/session/lease and strict source guards, pinned JQL bundle/wrapper,
   source-resolution DTO/namespace and Jira adapter. First RED imports the missing public service and
   asserts wrong-owner zero resolver invocations. Then real synthetic transport asserts raw bytes, safe
   errors, cumulative counters and comments pagination.
2. W3.CLI adds offline profiles/status/scope/item and guarded online diagnostics plus explicit unavailable
   capture/operation. Standalone subprocess tests assert exact stdout/stderr/exit, not direct handle only.
3. W3.CAPTURE connects the public services and archive through one internally invoked application method.
   Real temporary Git+synthetic requests test one valid item, failed later page, no privilege fallback,
   detail cap with retained complete membership and final identity/source drift.

Commands after files exist use `.venv/Scripts/python.exe -m pytest` with exact
`provider_sync/tests/test_provider_capture_gateway.py`, `test_jira_capture_contract.py`,
`test_provider_access_command.py` and `project_management/tests/test_capture_pipeline.py`,
all with `--ds=provider_sync.tests.connection_test_settings -q`.
HSD-specific richer decoder remains W3.HSD; only the explicit unsupported/partial route belongs here.
No placeholder complete coverage, fake history or default principal is permitted.
