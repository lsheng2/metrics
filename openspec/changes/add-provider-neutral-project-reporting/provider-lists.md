# W3.LISTS Provider List Packet

Status: draft under coordinator reconciliation; independent packet signoff is still required.
Canonical task status remains `tasks.md`. No source code is implemented by this document.

## 1. Boundary

W3.LISTS adds safe spreadsheet fixed-list selection for Project Stages. It owns
the minimal provider-sync extension needed to resolve Jira keys before a Stage
exists. It does not reopen W3.GATEWAY scope, create fake Stages, or run live
providers during planning.

Accepted rulings:

- Add scoped optional `ScopeSelection.frozen_list_id`.
- Make catalog resolution actor-aware.
- Add a project-owned immutable frozen-list table.
- Pin `openpyxl==3.1.5`.
- Parser preparation installed the approved openpyxl3.1.5/et-xmlfile2.0.0
  wheels on2026-11-02; `pip check` passed. The full list workflow is not implemented.
- HSD saved-query Stages use neither `scope_id` nor `frozen_list_id`; list is
  mutually exclusive with Jira scope and optional per provider.

## 2. Selection Compatibility

Target:

```text
ScopeSelection(profile_id: str, scope_id: int | None = None,
               frozen_list_id: str | None = None)
```

Serialization contract:

- Existing rows keep their byte/semantic layout: `{"profile_id": "...",
  "scope_id": <int|null>}`. Old HSD rows with `scope_id: null` remain exactly
  representable.
- `selection_from_json` defaults missing `frozen_list_id` to `None`.
- `selection_to_json` always writes `profile_id` and `scope_id`; it omits only
  the new `frozen_list_id` when `None`.
- Tests must prove exact existing Jira and HSD Stage idempotence and descriptor
  hashes are unchanged.

Affected consumers: `ProjectManagementService.preview_stage/add_stage/
_source_status`, `DashboardScopeCatalog`, `ProjectManagementFacade`,
`project_catalog`, new `project_lists`, fakes and source-status tests.

## 3. Parser Reuse

Copy/adapt actual donor parser functions, not a rewrite:

- From `spreadsheet_archive.py`: `WorkbookLimits` as `SpreadsheetBounds`,
  `selected_limits`, `check_now`, `validate_archive`, XML parser and worksheet
  order checks.
- From `spreadsheet.py`: `inspect_workbook`, `extract_workbook`, `_workbook`,
  `_selection`, `_token`, `_diagnostic`, `_rows`.

Adapt only imports, error names and Jira-only token validation. Keep ZIP/XML
guards before `openpyxl.load_workbook`, formula/error-cell refusal, row order
validation, duplicate diagnostics, source SHA behavior and the donor
`worksheets=32` bound.

Keep the parser files split:

- `project_management/out/spreadsheet_archive.py` should remain the bounded
  archive/XML guard layer, roughly the donor file size/shape (~170 lines).
- `project_management/out/spreadsheet.py` should remain workbook inspection and
  selected-column extraction, roughly the donor file size/shape (~160 lines).
- Do not combine both parser files plus provider/list service logic into a
  large `spreadsheet_source.py`.

No shell disk-free check is added.

### Executable Parser Slice

W3.LISTS.A owns only `app/domain/spreadsheet.py`, `out/spreadsheet_archive.py`,
`out/spreadsheet.py`, public `app/api/spreadsheet.py`, parser tests and the
openpyxl dependency pin. It has no DB, credential, network or Stage mutation.
W3.LISTS.B/C/D consume this public API for request resolution, list approval
and production commands/capture. Their unfinished status does not make the
parser's independent semantics speculative.

The limits preserve donor field names to avoid two sets of limit authorities:

```text
SpreadsheetBounds(input_bytes=524288, expanded_bytes=8388608,
                  archive_entries=128, xml_elements=100000, xml_depth=64,
                  scan_rows=10000, diagnostics=500, worksheets=32)
SpreadsheetError(code: str, message: str | None = None)
inspect_workbook(data: bytes, *, limits=None, check=None) -> dict
extract_workbook(data: bytes, *, provider_id: str, sheet: str, column: str,
                 first_row=2, max_items=500, limits=None, check=None) -> dict
```

Each bound is a positive integer no larger than that field's supported default.
`max_items` is independently1..500. `check`, when supplied by the application,
is a synchronous deadline/cancellation check; its failure propagates without
returning a success-shaped result. No model or HTTP caller supplies a callback.

Inspection keys: `schema_version=1,source_sha256,file_bytes,sheets`.
Extraction adds `provider_id,sheet,column,first_row,rows_scanned,blank_rows,
duplicate_rows,tokens,selected_rows,diagnostics,resolved=false,can_confirm`.
Tokens are ordered unique strings. Each selected row is
`{row,cell,raw_value,token}` for a valid nonblank token, including duplicate
rows; raw_value retains its finite string/int/float type. Invalid cells stay
in bounded diagnostics, and never create confirmable subset scope.
Diagnostics retain the donor shape
`{row,cell,code,severity,value,value_truncated,duplicate_of}`.
`can_confirm` here means syntactically eligible, not source approval; the
application preview still requires provider identity rules and authorization.

Jira syntax accepts positive numeric strings of at most64digits or the existing
Jira-key grammar. HSD syntax accepts only the same bounded positive numeric
article-ID syntax; neither provider is qualified online by syntax validation.
Excel numeric cells retain the donor15-digit exactness bound. Strings are not
rounded or coerced into floating point. Unknown providers fail before parsing.

| Parser case | Fixture / operation | Required result |
| --- | --- | --- |
| PA01 | Scope B2:B5 has Jira key, numeric ID, blank, duplicate; another sheet has unrelated data | only selected tokens; original row values and duplicate warning; original SHA |
| PA02 | formula, cell error, bool/date, fractional or over-precision number | error diagnostic; can_confirm=false; no valid-subset approval |
| PA03 | HSD numeric article IDs and a Jira key | numeric IDs retained; Jira key rejected, no Jira fallback |
| PA04 | unsafe/duplicate/encrypted/symlink ZIP member, unsupported compression | refusal before workbook materialization |
| PA05 | DTD/entity, excessive depth/elements, ambiguous row/cell order | typed XML/workbook refusal |
| PA06 | input/expanded/entry/sheet/row/item/diagnostic limits | exact bound accepted where valid, excess rejected, no silent truncation |
| PA07 | cancellation while streaming/reading cells | original error propagates; actual workbook and row iterator close; no success result |
| PA08 | invalid sheet/column/row, empty range, malformed workbook | safe typed errors or EMPTY_SCOPE diagnostic |

First RED imports `project_management.app.api.spreadsheet` and extracts a
synthetic two-provider workbook. Run
`.venv/Scripts/python.exe -m pytest project_management/tests/test_provider_lists_parser.py project_management/tests/test_provider_lists_archive.py --ds=provider_sync.tests.connection_test_settings -q`.
Port the two pinned donor files after observing RED, then run these tests plus
the existing project catalog tests. Parser review does not approve list
creation, HSD online qualification, CLI deployment or the full W3.LISTS leaf.

## 4. Approval Projection

`preview_hash` from earlier drafts is replaced by a semantic
`approval_hash = sha256(canonical(ApprovalProjection))`.

```text
ApprovalProjection(
  schema_version=1,
  provider_id: str,
  profile_id: str,
  endpoint_url: str,
  safe_profile_projection_hash: str,
  principal_id: str | None,
  endpoint_id: str,
  workbook_sha256: str,
  workbook_size: int,
  archive_fingerprint: str,
  parser_policy_hash: str,
  selection: WorkbookSelection,
  selected_rows: tuple[SelectedRawRow, ...],
  identities: tuple[ApprovedIdentity, ...],
)
```

Included:

- source bytes hash/size and selected sheet/column/first row;
- parser policy: `openpyxl==3.1.5`, `SpreadsheetBounds`, parser revision;
- safe profile projection, provider, endpoint and verified principal;
- stable-ID mapping: stable ID, display key, row and cell.

For numeric IDs explicitly confirmed offline, `principal_id=None` means only
the selected identities were approved; it is not a fabricated verified source
identity. Jira-key confirmation requires a real verified principal. The first
capture always verifies its own principal and binds it in the archive. When
approval already has a principal, that principal must match.

Excluded volatile observations:

- `verified_at`;
- request usage/counts/deadlines;
- credential revision and token hashes;
- runtime receipt IDs;
- issue `updated`, fields hash and lightweight/current facts.

No model-visible value may contain token hashes or credential source hashes.

Stage descriptor:

- `source_version = approval_hash`.
- `query_kind = "frozen_work_items"`.
- `query` is compact reference metadata only:

```json
{
  "schema_version": 1,
  "source_kind": "frozen_work_items",
  "frozen_list_id": "...",
  "approval_hash": "...",
  "population_hash": "...",
  "count": 500
}
```

Full population and row audit are read from `ProjectFrozenList`, not embedded in
`ScopeDescriptor.query`. This keeps `validate_descriptor`'s 16384 JQL/query
bound unchanged and supports 500 long IDs.

Audit may record volatile resolution receipt fields (`verified_at`, usage,
credential revision, lightweight issue markers) as local operator evidence, but
they are not part of Stage rule identity.

Required replay test: same workbook/profile/principal/stable IDs but different
`verified_at`, usage counts and issue `updated` markers produces the same
`approval_hash` and confirms/replays successfully.

## 5. Safe Profile Projection

`ProfileListContext` is built from existing safe APIs:

- `ProjectProviderProfileRegistry.resolve_profile(profile_id)` for profile
  identity/provider/enabled/source-population metadata;
- `connection_resolver.describe_profile(profile_id, expected_provider_id=...)`
  for normalized endpoint metadata without opening credentials.

Safe projection contains:

```text
ProfileListContext(project_id, profile_id, provider_id, display_name,
                   enabled, endpoint_url, endpoint_id,
                   safe_profile_projection_hash)
```

`safe_profile_projection_hash` canonicalizes only non-secret fields:
profile ID, provider ID, enabled state, normalized endpoint URL, endpoint ID,
and the selected provider's decoding policy revision. It excludes PATs, tokens,
cookies, credential revision, private paths and mutable saved-query membership
definitions. Frozen membership must not change or become a different rule when
an unrelated saved query on the same profile is edited. Disabling the profile
still refuses new access; changing endpoint/provider/decoding policy requires
new approval.

## 6. Public DTOs And Services

```text
WorkbookSelection(sheet: str, column: str, first_row: int = 2)
WorkbookInspection(schema_version, project_id, profile_id, provider_id,
                   endpoint_url, source_sha256, file_bytes,
                   archive_fingerprint, sheets, bounds)
WorkbookSourceIdentity(source_sha256, file_bytes, archive_fingerprint,
                       parser_policy_hash)
SelectedRawRow(row, cell, raw_token, normalized_token, provider_id)
SpreadsheetRowDiagnostic(row, cell, code, severity, value,
                         value_truncated, duplicate_of)
ApprovedIdentity(provider_id, endpoint_id, stable_id, display_key, row, cell)
ResolutionObservation(verified_at, usage, credential_revision,
                      lightweight_markers)
OnlineResolutionRequest(deadline_at: datetime, limits: CaptureLimits)
StableIdResolutionInput(project_id: str, profile: ProfileListContext,
                        source_identity: WorkbookSourceIdentity,
                        selection: WorkbookSelection,
                        tokens: tuple[SelectedRawRow, ...],
                        online_request: OnlineResolutionRequest)
StableIdResolutionReceipt(identities: tuple[ApprovedIdentity, ...],
                          principal_id: str | None,
                          observation: ResolutionObservation | None,
                          complete: bool,
                          diagnostics: tuple[SpreadsheetRowDiagnostic, ...])
SpreadsheetListPreview(inspection, selection, selected_rows, diagnostics,
                       candidate_identities, resolution_observation,
                       approval_projection, approval_hash, can_confirm)
FrozenListRecord(id, project_id, owner_subject, stage_key, stage_name,
                 provider_id, profile_id, endpoint_url, endpoint_id,
                 principal_id, approval_hash, population_hash,
                 safe_profile_projection_hash, selection_json,
                 identities_json, selected_rows_json, diagnostics_json,
                 workbook_sha256, workbook_size, created_at)
```

`ProjectListInputService`:

```text
inspect_workbook(actor, project_id, profile_id, load_bytes, *,
                 bounds=SpreadsheetBounds()) -> WorkbookInspection

preview_spreadsheet_list(actor, project_id, profile_id, load_bytes, *,
                         selection: WorkbookSelection,
                         source_sha256: str | None,
                         online_resolution: OnlineResolutionRequest | None,
                         bounds=SpreadsheetBounds()) -> SpreadsheetListPreview

confirm_spreadsheet_stage(actor, project_id, *,
                          key: str, name: str, profile_id: str,
                          load_bytes, selection: WorkbookSelection,
                          expected_source_sha256: str,
                          expected_approval_hash: str,
                          online_resolution: OnlineResolutionRequest | None,
                          bounds=SpreadsheetBounds()) -> StageSummary
```

`load_bytes` is adapter-supplied, called at most once per new parse path, and is
never provided by HTTP/model input.

`FrozenListRepository`:

```text
metadata(actor, frozen_list_id) -> FrozenListRecord
read_artifact(actor, frozen_list_id) -> bytes
read_population(actor, frozen_list_id) -> tuple[ApprovedIdentity, ...]
find_existing_stage_projection(actor, project_id, stage_key)
    -> FrozenListRecord | None
commit_list_stage(actor, project_id, *, key, name,
                  approval: ApprovalProjection,
                  preview: SpreadsheetListPreview,
                  workbook_bytes: bytes) -> StageSummary
```

`metadata` and `read_population` must work even if workbook bytes are corrupt or
missing. `read_artifact` verifies `workbook_sha256` and may raise
`SOURCE_ARTIFACT_CORRUPT` without making authorized Stage identities unreadable.
Both metadata/population reads also validate the stored approval projection
and `population_hash`; corrupt approved identities cannot fall back to workbook
contents or a current saved query. List lookup is project-bound: callers must
match `record.project_id` to the current Project before using its descriptor.
Catalog resolution therefore takes `(actor, project_id, selection)` for all
providers; saved-query paths keep their old descriptor bytes.

Population hash is SHA256 of canonical ordered ApprovedIdentity values.
`FrozenListRecord` persists the complete ApprovalProjection and parser policy
revision needed to reproduce its hash; it is not reconstructed from volatile
resolution observations. The repository stores original bytes only through
`commit_list_stage`, which verifies actual byte length, workbook SHA, selected
metadata and approval/population hashes before any mutation.

## 7. Confirmation Ordering And Idempotence

One service owns list+stage+audit transaction: `ProjectListInputService` with
`FrozenListRepository`.

Order:

1. Validate actor/project ownership, key/name, and the shape of supplied hashes.
2. Look up existing Stage/list by `project_id + stage_key` before generating a
   new list UUID.
3. If existing Stage exists:
   - compare stage name, profile ID, WorkbookSelection, supplied source SHA and
     `expected_approval_hash` against the stored list;
   - if they match, return the original Stage as a historical replay, even when
     the current source/file or a new network deadline is unavailable;
   - no workbook read, provider call, new deadline or new budget is consumed;
   - if name or approval differs, return `STAGE_RULE_IMMUTABLE`.
4. If Stage is absent, require a nonarchived project and enabled matching
   profile, then read workbook bytes once, parse and run required online
   resolution using this command's explicit deadline/budget.
5. Compare source SHA and `approval_hash`.
6. Inside one DB transaction, lock project, recheck archived/profile projection,
   insert one frozen-list record and Stage, and write audit. List ID is generated
   only after the existing-stage comparison; descriptor generation uses that
   chosen ID. An existing saved-query Stage under the same key conflicts.
7. If insert races with an identical projection, reload and return existing.
8. If list insert succeeds but Stage/audit fails, rollback removes the list.

There is no implicit repeated grant reset. A new command may have a new explicit
deadline/budget, but exact replay of an existing Stage does not consume it.

## 8. Pre-Stage Provider Read Session

W3.LISTS adds a minimal provider-sync extension:

```text
ProviderRequestContext(actor, project_id, request_id,
                       deadline_at, limits: CaptureLimits)
ProviderReadSession(context: ProviderRequestContext | AccessContext, reader,
                    timeout_seconds, authorize=None, clock=None, monotonic=None)
CaptureSession(ProviderReadSession)
```

Rules:

- `AccessContext` stays strict: stage/capture/request/project UUIDs remain
  mandatory for capture.
- `ProviderReadSession` owns request/download/deadline/page-key accounting and
  strict JSON.
- Only `CaptureSession` accepts `ArchivePageSink`.
- `ProviderRequestContext` has no stage/capture ID and cannot attach archive
  sinks.
- Caller permission and selected-profile checks are owned by
  `ProjectListInputService` and `ProviderListIdentityResolver`.

Reader change: allow Jira key paths only for the safe issue-read endpoint:

```text
/rest/api/2/issue/<positive-int-or-jira-key>
```

Keep refusing absolute URLs, path escapes, worklog, attachment body, writes,
redirect following and arbitrary endpoints before sending credentials.

Owner paths added by W3.LISTS:

- `provider_sync/app/api/access_contracts.py`
- `provider_sync/services/capture_session.py`
- `provider_sync/out/capture_reader.py`
- `provider_sync/tests/test_provider_request_session.py`
- `provider_sync/tests/test_capture_reader.py`
- `provider_sync/tests/test_provider_capture_gateway.py`

## 9. Pre-Stage Stable-ID Resolution

The exact provider API, owned files and RB/ID tests are in
[provider-list-resolution](provider-list-resolution.md). That packet supersedes
the rough provider transport signature below: workbook/row DTOs stay in the
application service; provider_sync receives only the explicit bounded identifiers.

```text
ProviderListIdentityResolver.resolve(actor, request: StableIdResolutionInput,
                                     *, online: bool)
    -> StableIdResolutionReceipt
```

Flow:

1. Project owner/profile checks happen before credential lookup.
2. `online=True` is mandatory for Jira keys.
3. Build one `ProviderRequestContext` and one `ProviderReadSession`.
4. Verify principal, resolve all keys, then recheck same principal/profile/
   endpoint/safe profile projection.
5. Return complete stable-ID mapping. Partial resolution is diagnostics only
   and cannot confirm.

Jira numeric IDs may be stable offline. Jira keys must resolve online to stable
issue IDs and display keys. HSD article IDs may be accepted as stable IDs when
the HSD strategy qualifies them; partial HSD qualification must be explicit.

## 10. Frozen Source Resolution And Lease Dispatch

`JiraCaptureAdapter.resolve` currently rejects non-JQL. W3.LISTS must add
dispatch for `query_kind="frozen_work_items"`.

Frozen `SourceResolutionInput`:

```text
SourceResolutionInput(
  original_rule_hash = stage.definition_hash,
  provider_id = descriptor.provider_id,
  endpoint_id = frozen_list.endpoint_id,
   principal_id = current verified lease principal,
  effective_query = descriptor.query,
  dependencies = (),
  resolver_revision = "frozen-list-v1:<parser_policy_hash>"
)
```

This satisfies the existing archive rule that `effective_query == Stage.query`
while keeping full population outside the descriptor.
If `frozen_list.principal_id` is non-null, require equality with the current
verified principal. If null, the archive's first source resolution provides the
first verified principal binding; later captures must match it.

`ProviderCaptureLease` dispatch:

- For `jql`, keep current `adapter.enumerate/verify_final`.
- For `frozen_work_items`, read frozen-list metadata/population by
  `frozen_list_id` from descriptor/source_ref and actor owner.
- Verify descriptor approval hash, profile ID, endpoint, principal and source
  version match the frozen list.
- Enumerate by metadata/lightweight lookup for each fixed identity, never by
  live JQL.
- `verify_final` re-reads the frozen-list metadata and principal/profile, then
  repeats lightweight lookup only for completion checks within the same lease
  budget. Missing identities keep capture partial.

Metadata-only lookup failure for an ID yields missing member coverage; it does
not delete the ID or fabricate current facts.

## 11. Membership And Capture Conversion

Extend `MembershipObservation`:

```text
MissingMember(identity: WorkItemIdentity, reason_code: str)

MembershipObservation(...,
  fixed_population: tuple[WorkItemIdentity, ...] | None = None,
  missing_members: tuple[MissingMember, ...] = ())
```

Dynamic JQL/HSD observations use `fixed_population=None`. Frozen-list
observations set `fixed_population` to all approved identities.

`members` contains only real `WorkItemMarker(identity, updated, fields_hash,
fields)` observations. Missing IDs never get fake timestamps/current fields.

`ProjectCaptureService` conversion:

- archive `MembershipInput.items = fixed_population` when it is not None,
  otherwise `tuple(marker.identity for marker in members)`;
- for an intact approved frozen list, membership coverage is complete with
  `observed_count = total_count = len(fixed_population)`. This coverage proves
  the fixed population, not successful current reads;
- current-read failures are represented separately by `missing_members`.
  The observed `members` plus missing identities must partition the fixed
  population exactly, without duplicates or fabricated markers;
- capture the observed markers within the detail budget, retain the entire
  approved population, and seal partial whenever a missing member or pending
  detail remains. Complete finalize still requires a complete required-parts
  snapshot for every approved identity;
- one missing item does not invalidate valid per-item snapshots/summaries for
  observed identities, but it prevents stage-level complete/unchanged summary.

Stage-level complete reporting requires zero missing members and all required
details/summaries. Per-item reuse checks that item's current access, marker,
approved source identity and accepted baseline; another item's absence does
not force a model call for an unchanged valid item. Missing items remain
explicitly pending, not deleted or closed.

Final verification uses the same lease budget. Re-read immutable population
metadata and principal/profile; they must match the initial binding. Re-read
lightweight markers for observed identities and report changed/missing current
observations without changing population. An identity/principal/rule change
blocks acceptance; failed marker reads keep the affected item pending.

## 12. Artifact Disposition

Retained in `ProjectFrozenList`:

- original workbook bytes, bounded at 512 KiB by service and model validation;
- workbook SHA/size, archive fingerprint, parser policy hash;
- selected raw rows and diagnostics;
- approved identity population.

Not model-visible: local file path, unselected cells/sheets, token hashes,
credentials, raw provider response bodies.

Workbook artifact read/verify is separate from metadata/population reads. A
corrupt or missing workbook artifact cannot make authorized Stage identities
unreadable.
The 512 KiB bound applies to runtime bytes before transaction and artifact
storage, not the source-file line-count checker. Selected rows and approved
identities have independent count/serialized-size bounds; metadata-only readers
do not load the BLOB merely to obtain the approved population.

## 13. Descriptor Size

Do not store all 500 identities in `ScopeDescriptor.query`. Store only compact
reference metadata and hashes. Full population comes from `ProjectFrozenList`.

Tests must include 500 long IDs and assert:

- descriptor query remains under 16384 bytes;
- `validate_descriptor` JQL bound remains unchanged;
- capture can read population through the frozen-list repository;
- caller cannot forge descriptor JSON to bypass repository ownership.

## 14. CLI

```text
manage.py project_lists inspect --project-id <uuid> --profile-id <profile> --file <path>
manage.py project_lists preview --project-id <uuid> --profile-id <profile> --file <path>
  --sheet <sheet> --column <column> [--first-row <n>] [--source-sha256 <sha256>]
  [--online-resolve --deadline-at <UTC ISO8601>] [lowering-only max options]
manage.py project_lists confirm-stage --project-id <uuid> --profile-id <profile>
  --key <stage-key> --name <stage-name> --file <path>
  --sheet <sheet> --column <column> [--first-row <n>]
  --source-sha256 <sha256> --approval-hash <sha256>
  [--online-resolve --deadline-at <UTC ISO8601>] [lowering-only max options]
```

No `--actor`, raw descriptor, URL, token or path echo. Local path must be an
ordinary local file, no UNC/network/device/reparse path.
Online options are required only for a new Jira-key resolution. Numeric-ID
offline approval is explicitly unverified until capture. An existing exact
stage replay needs neither current file bytes nor a new network budget.
The concrete lowering-only flags are `--max-requests`, `--max-download-bytes`,
`--max-response-bytes` and `--max-items`; none may exceed its configured bound.

## 15. Focused Tests

Required additions include:

- exact Jira and HSD old selection JSON/idempotence;
- parser ZIP/XML/formula/row diagnostics from donor cases;
- `SpreadsheetBounds.worksheets=32` and rejection of 33 worksheets;
- ApprovalProjection replay with different `verified_at`, usage and issue
  `updated` but same stable IDs;
- confirm exact existing Stage before reading file or using provider budget;
- race rollback with no orphan list/audit;
- corrupt workbook artifact does not block metadata/population reads;
- pre-stage `ProviderReadSession` cannot attach archive sink and old
  `AccessContext` validation still rejects malformed stage/capture UUIDs;
- Jira key issue path allowed, worklog/absolute/path escape refused;
- frozen `SourceResolutionInput` effective query equals descriptor query;
- frozen enumeration preserves `fixed_population` and reports missing member
  reason without fake `WorkItemMarker`;
- 500 long-ID descriptor-size case.

## 16. Focused Commands

Use synthetic provider settings; no ambient defaults:

```powershell
$python = Join-Path (Get-Location) '.venv/Scripts/python.exe'
& $python -m pytest project_management/tests/test_provider_lists_parser.py project_management/tests/test_provider_lists_archive.py -q --ds=provider_sync.tests.connection_test_settings
& $python -m pytest project_management/tests/test_provider_lists_service.py project_management/tests/test_provider_list_resolution.py -q --ds=provider_sync.tests.connection_test_settings
& $python -m pytest project_management/tests/test_provider_lists_repository.py project_management/tests/test_provider_lists_catalog.py -q --ds=provider_sync.tests.connection_test_settings
& $python -m pytest project_management/tests/test_project_lists_command.py -q --ds=provider_sync.tests.connection_test_settings
& $python -m pytest provider_sync/tests/test_provider_request_session.py provider_sync/tests/test_capture_reader.py -q --ds=provider_sync.tests.connection_test_settings
& $python -m pytest provider_sync/tests/test_provider_access_consumers.py provider_sync/tests/test_provider_capture_gateway.py -q --ds=provider_sync.tests.connection_test_settings
& $python manage.py makemigrations project_management --check --dry-run --settings=provider_sync.tests.connection_test_settings
& $python manage.py check --settings=provider_sync.tests.connection_test_settings
& $python scripts/check_file_size_limits.py --include-untracked
& $python scripts/check_diff_whitespace.py --include-untracked
openspec validate add-provider-neutral-project-reporting --strict --no-interactive
```

## 17. Remaining Concrete Gaps

These are the only remaining packet-level gaps before implementation signoff:

- HSD online article-ID qualification may stay partial, but the HSD strategy
  must expose that partial status explicitly.
- Implementation must prove the exact old Jira and HSD selection JSON layouts
  still replay and hash as before.
- Capture/report consumers must use `fixed_population is None` to distinguish
  dynamic membership from frozen population. Missing members prevent a complete
  stage report, not reuse of other independently valid item summaries.
- Coordinator amendments still need source-map/DTO/test-matrix reconciliation
  and independent packet review. This draft is not CODE_READY.

## 18. Source Map

Donor blob map and copy-vs-rewrite ownership are in
`provider-lists-source.json`. Do not import the donor package or add the donor
repo to `PYTHONPATH`.
