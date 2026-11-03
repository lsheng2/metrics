# W3 Capture Archive Packet

Status: proposed implementation detail; entry requires full W3.CREDENTIALS and this packet's review.
Goal: durable provider-neutral source observations and complete raw history before any analysis.
Canonical ledger: [tasks](tasks.md). Design dependencies: [provider-access](provider-access.md),
[integration-execution](integration-execution.md), [migration-catalog](migration-catalog.md).
This packet defines W3.ARCHIVE only; accepted summaries/index rebuild/import remain W4/W5.

## 1. Ownership And Layout

`project_management` owns its stage archives. `CaptureArchiveService` consumes only the public
Project API for owner/stage checks. All source I/O is a caller responsibility; no network under archive locks.
An archive is an independent ordinary Git repository, not a child worktree or remote of the code repo.
Source byte blobs and raw page manifests are append-only; SQLite projections are never raw authority.

```text
<configured-data-root>/
  archive-root.json
  budget.lock
  projects/<project-uuid>/stages/<stage-uuid>/
    archive/                 # independent .git and readable committed JSON
    objects/sha256/<hash>/payload
    runtime/empty-hooks/
    runtime/archive.lock
    runtime/pending/<capture-id>/
```

Object stores are stage-local, preventing an object hash from bypassing owner/stage boundaries.
Root identity binds schema version and storage configuration, not a named business project.
Stage bootstrap binds project/stage/owner, frozen descriptor/hash and explicit Git author/branch.
No secret, source credential path, `.env` or code-repository remote is copied.
`archive-root.json` immutably records schema_version, root_id UUID, canonical root path,
author_name/email and branch. Opening with different identity/path/author/branch returns
ARCHIVE_IDENTITY_MISMATCH; do not adopt an arbitrary preexisting root.
Limits are versioned configuration, not immutable historical identity: each new capture intent records
the exact admitted limit values/hash. Tightening configuration blocks new allocation if current usage
exceeds it, but does not rewrite old intent limits or prevent authorized history reads/partial sealing.

Settings: `METRICS_PROJECT_ARCHIVE_ROOT=""` (unconfigured), author name/email explicitly supplied on
initialization, branch=`main`. Empty root refuses writes. Root must be an absolute local external path,
not inside the code checkout, an existing Git repo, or an unknown nonempty directory.
Tests use `tempfile.TemporaryDirectory` outside the checkout; no implicit production root creation.

Add `portalocker==4.4.1`; local wheel available. Limits are configurable positive integers:
root50GiB/1000000files, stage10GiB/200000files, capture256MiB/100000files,
single raw page16MiB, object32MiB. Defaults are capacity policy, not available disk measurements.
No disk-free APIs, threshold or enable switch.

## 2. Exact Values And API

Frozen slots DTOs in `project_management/app/domain/captures.py`, finite JSON handled by
`capture_values.py` using deterministic UTF8/sorted compact keys/allow_nan=false.

```text
ArchiveStorageConfig(root: Path, author_name: str, author_email: str, limits: ArchiveLimits)
ArchiveLimits(max_root_bytes, max_root_files, max_stage_bytes, max_stage_files,
              max_capture_bytes, max_capture_files, max_raw_page_bytes, max_object_bytes)
CaptureSourceIdentity(provider_id, endpoint_id, endpoint_url, principal_id, credential_revision, rule_hash)
WorkItemIdentity(provider_id, endpoint_id, stable_id, display_key)
SourceChainKey(provider_id, endpoint_id, stable_id, principal_id, rule_hash)
PartCoverage(state, source_version: str | None, observed_count: int | None,
             total_count: int | None, reason_code: str | None)
CaptureCoverage(facts, comments, history, attachments, dependencies: PartCoverage)
CaptureIntent(project_id, stage_id, capture_id, request_id, source: CaptureSourceIdentity,
              original_input_hash, required_parts: tuple[str,...], deadline_at: datetime)
RawPageInput(page_key, item: WorkItemIdentity | None, content_type, payload: bytes,
             request_fingerprint)
RawPageRef(page_id, sha256, size_bytes, content_type, request_fingerprint)
SnapshotInput(identity: WorkItemIdentity, facts: Mapping, comments_by_id: Mapping,
              history_by_id: Mapping, attachments_by_id: Mapping, dependencies_by_id: Mapping,
              coverage: CaptureCoverage, raw_page_ids: tuple[str,...], consistent: bool)
StoredSnapshotRef(identity, capture_id, sequence, previous_capture_id, source_hash, git_path)
MembershipInput(items: tuple[WorkItemIdentity,...], coverage: PartCoverage,
                raw_page_ids: tuple[str,...])
CaptureReceipt(capture_id, commit_id, manifest_sha256, parent_commit,
               membership_complete, complete, failure_code: str | None,
               snapshots: tuple[StoredSnapshotRef,...], checkout_state)
ArchiveIdentity(root_id, project_id, stage_id, owner_subject, descriptor_hash,
                head_commit: str)
PreparedCapture(capture_id, intent_hash, state: Literal["prepared","replayed"])
CaptureManifest(schema_version: Literal[1], intent: CaptureIntent,
                membership: MembershipInput, snapshots: tuple[StoredSnapshotRef,...],
                pages: tuple[RawPageRef,...], complete: bool, failure_code: str | None,
                prepared_at: str, finalized_at: str)
CapturePage(items: tuple[CaptureReceipt,...], next_cursor: str | None)
SourceChainPage(items: tuple[StoredSnapshotRef,...], next_cursor: str | None)
ArchiveError(code: str)  # message is fixed by a code-to-safe-English dictionary
```

Part states: complete/partial/unsupported/access_lost/not_requested.
Display key is not identity; chain key is provider/endpoint/stable_id/principal/rule. Credential revision
is observed metadata and may be unknown, not a verified principal or proof of unchanged visibility.
Project/stage UUIDs, generated request/capture IDs and page IDs use strict allowlisted syntax.
Use UUID for capture/request, SHA256 for page IDs; raw caller page keys are hashed, never path segments.
Stage rule remains W1's immutable descriptor hash. Endpoint ID must match the selected endpoint/provider,
but no independent endpoint normalization implementation may disagree with the connection owner.

Public facade `project_management/app/api/capture_archive.py` exposes:

```text
CaptureArchiveService(project_api, repository_factory, config)
  .initialize_stage(actor, project_id, stage_id) -> ArchiveIdentity
  .prepare(actor, intent: CaptureIntent) -> PreparedCapture
  .append_page(actor, intent, page: RawPageInput) -> RawPageRef
  .append_snapshot(actor, intent, snapshot: SnapshotInput) -> StoredSnapshotRef
  .finalize(actor, intent, membership: MembershipInput,
            *, complete: bool, failure_code: str | None = None) -> CaptureReceipt
  .finalize_partial(actor, project_id, stage_id, capture_id, *, failure_code,
                    membership: MembershipInput | None = None) -> CaptureReceipt
  .read_capture(actor, project_id, stage_id, capture_id) -> CaptureManifest
  .read_page(actor, project_id, stage_id, capture_id, page_id) -> bytes
  .read_snapshot(actor, project_id, stage_id, capture_id, source_key: SourceChainKey) -> SnapshotInput
  .list_captures(actor, project_id, stage_id, *, limit=100, after=None) -> CapturePage
  .source_chain(actor, project_id, stage_id, source_key: SourceChainKey,
                *, after_capture_id=None, limit=100) -> SourceChainPage
```

Page responses contain `items` and explicit `next_cursor`; no silently bounded complete-list claim.
`checkout_state` is `current` or `stale`, independent of complete capture coverage.
Cursor is base64url of strict canonical JSON `{v:1,head_commit,last_capture_id,source_key_hash}`.
It is an untrusted selector, not authorization: decode bounded<=1024bytes, verify schema, pinned
head exists in this stage history and last ID belongs to it. Project ownership is rechecked.
Source key hash is null for list_captures; source_chain verifies it against its supplied key.
Order is oldest to newest committed source sequence; limit1..100. A newer head does not silently
change a cursor's snapshot. Unknown/cross-stage/incorrect source cursor is ARCHIVE_MANIFEST_INVALID.
`after_capture_id` must resolve to the same source chain; missing predecessor is an integrity error.
Reads resolve pages/snapshots from the committed capture manifest, never caller-supplied paths/hashes.
All public calls check Project ownership before filesystem access. Archived projects reject prepare/
append/new initialize; existing authorized reads remain, and finalize_partial may seal already captured
material without adding provider data or advancing a successful watermark.
W4 must use these public queries and the same underlying commit owner, not read mutable cache as truth.
Use the existing public `get_project(actor,project_id)`, locate the exact stage UUID in returned stages,
check archived/source status as required, compare definition_hash and descriptor immediately before
filesystem writes. Missing stage is PROJECT_NOT_FOUND. Do not import Project ORM in archive code.
Authorization linearizes at that check; a concurrent archive after an in-flight local append's check
does not retroactively erase captured evidence, but the next append fails and only partial sealing remains.

`PreparedCapture` returns only capture_id, intent_hash and state prepared/replayed.
`ArchiveIdentity` returns project/stage, descriptor hash and current commit; no private secrets.
`CaptureManifest` contains serialized intent, membership, snapshot refs, raw page refs, complete/failure
and immutable timestamps. Receipt fields are derived from actual Git commit and manifest bytes.

## 3. Validation Before Writes

Source identity must equal the frozen stage's provider/full endpoint/rule; principal_id must be nonempty
and supplied by a qualified capture layer, not substituted from BasicAuth owner.
Archive records a supplied principal; it does not itself prove upstream login.
W3.ARCHIVE tests use an explicit synthetic principal through the same CaptureSourceIdentity.
Real principal qualification is W3.GATEWAY/CAPTURE, not an unmet dependency on a model or live login.
The archive compares full endpoint URL/provider/rule with the frozen stage and treats endpoint_id as
gateway-owned opaque identity; it requires exact equality within a stored source chain but never
recomputes a competing endpoint normalization/hash. Gateway verifies it using the connection owner.
One prepared capture per stage is allowed until finalized, preventing competing sequence derivations.
Same capture_id plus exact intent is replay; different bytes are ARCHIVE_CAPTURE_CONFLICT.
Request/capture IDs do not renew deadline, identity or quotas on retry.

Membership coverage is independent of detail coverage: complete membership with only some item snapshots
is a valid partial capture. Snapshot identities must be a subset of declared membership (or explicitly
granted dependency records in their own part); `complete=true` requires a snapshot for every member.
Do not reject honest partial detail merely because the full membership set is larger.
For successful complete captures every required part is complete and each snapshot is consistent.
If complete is false, failure_code/coverage truth explains outstanding parts; no complete watermark.

`decode_snapshot(payload: bytes) -> SnapshotInput` is the canonical byte-entry parser, rejecting duplicate
JSON keys with object_pairs_hook before Mapping construction. Trusted Python adapters may construct
SnapshotInput directly, where mapping keys are intrinsically unique; that path does not claim to
detect duplicates already discarded by an earlier parser. Gateway must reject duplicate record IDs
before converting lists to maps and preserve raw bytes; source IDs in stored records must match map keys.
No NaN/infinity/coercion.
For collection parts observed_count equals actual record count, complete requires equal known total;
partial known total may be larger, never smaller. Unsupported/not_requested/access_lost cannot claim
newly fetched records. Attachments metadata has its own explicit metadata-only coverage; body not_requested
does not imply all bodies are read. Adapter owns raw-to-canonical extraction but archive checks actual
record IDs, counts and same-intent raw refs. It cannot infer semantic truth from a caller's complete flag.

Source hash excludes fetched_at/capture ID and includes identity plus facts, full preserved comment/history/
attachment/dependency values. Comments map keeps the entire provider raw record alongside normalized
fields when provided; raw original byte pages remain separate. No Unicode/English conversion.
Archive derives sequence/predecessor from committed same-principal/rule source history under the stage lock.
Snapshot references returned during prepare are provisional until final commit and cannot be accepted by AI.

## 4. Local Transaction Protocol

Lock order always root budget lock -> stage lock, using nonblocking portalocker.
Locks cover local mutation only. Network fetches happen between calls, never while a lock is held.
Root lock serializes admissions across stages; stage lock serializes raw/manifest/ref mutation.
All measured current bytes/files under the data root include Git, staging, objects and incomplete writes.
No cache counter is sufficient on its own: measure bounded local tree usage under root lock for admission.
This first implementation favors correct accounting; optimize only from later measurements.

Use an emergency sealing reserve of max(1MiB,64KiB per admitted page up to capture file limit)
within configured app quota, not outside it. Before append admit payload, raw manifest, canonical
staging peak and conservative Git object/tree/commit overhead (uncompressed new content plus8KiB/file,
1MiB transaction allowance). Reject before accepting another page if finalizing it could not fit.
Exact reservation counters bind capture intent and count alongside current actual usage. On recovery
reconstruct from pending intents/pages; never clear unknown allocation to gain capacity.
Filesystem write failure may still occur; report it, retain pending evidence, and do not return success.

Persist `runtime/pending/<capture>/reservation.json` by atomic replacement:
schema_version, intent_hash, limits_hash, admitted_page_count, actual_stage_bytes/files,
actual_root_bytes/files, remaining_git_bytes/files, sealing_reserve_bytes/files, state reserved/settled.
The actual fields are measured observations, not an alternative byte authority.
For admission, root charge is measured root usage plus the sum of every unresolved capture's remaining
Git and sealing reservations; stage charge is measured stage usage plus that stage's unresolved reserve.
Charge candidate payload/staging growth before the write, then remeasure it while still holding root lock.
Persist remaining future Git growth as the uncompressed not-yet-committed content bound plus8KiB/file
and1MiB transaction allowance; already written payload is counted only in measured usage, not twice.
At commit, actual Git growth is measured and remaining_git becomes0 only after verifying published ref.
Sealing reserve becomes0 only after durable capture receipt/closed active reference. A torn/missing record
is rebuilt conservatively from the immutable intents and current bytes; ambiguous state refuses allocation.
Capture charge differs from physical deduplication: sum original bytes for every accepted logical page
(same page_id counts once), each snapshot staging record, membership/final manifest and capture-specific
coordination files plus its remaining Git/sealing reservation. Two page IDs referencing the same object
count twice for capture bytes, once physically for root/stage, preventing unlimited logical inputs via dedup.
Capture files charge each logical page/object reference, page intent, receipt and snapshot record, plus
actual capture coordination files and reserved future files. Root/stage use actual file counts.
For N durable/admitted pages and S snapshots, reserve sealing_files=`8+4*N+2*S`; Git loose file reserve
is `2*new_manifest_file_count+4` (blob+tree upper allowance and commit/index/ref state).
sealing_bytes=`max(1MiB,64KiB*N)`; remaining_git_bytes as the bound above. Each append updates N/S and
checks all three quotas before data acceptance. These conservative defaults may be calibrated only
with measured evidence and a new limits version; no silent negative/zero unknown usage.

Prepare writes exclusive immutable intent then records active capture reference atomically.
Active reference is recoverable coordination state, not history; its content must resolve to exact intent.
If either already exists unexpectedly, refuse rather than overwrite.

Append page:

1. Check owner/stage/intent/deadline, safe paths, limits and budget.
2. Write an immutable page intent with expected hash/size/item/request/page identity before bytes.
3. Exclusively store bytes by SHA256 or verify existing same bytes; flush.
4. Mark page durable by exclusive retained receipt; missing receipt on recovery can be reconstructed only
   after verifying the expected payload bytes. A missing/truncated object stays a partial failure.
5. Return RawPageRef only after durable receipt. A repeated page_key with changed content conflicts.

`page_id = SHA256(canonical JSON(intent_hash, item identity or null, page_key))`.
Payload hash is deliberately excluded from that ID, so changed bytes under the same page key cannot
masquerade as a new page. Repeated identical page IDs compare payload hash/size/content type/request hash.

Append snapshot validates current durable page receipts, computes normalized snapshot/hash/sequence and
writes an exclusive staging record. No accepted or publication state is touched.

Finalize constructs all deterministic capture files solely from verified pending records.
Read current branch HEAD; write an alternate index from HEAD; hash-object files; update-index with
mode100644; write-tree; commit-tree with explicit author/committer; publish using update-ref old/new CAS.
Store the candidate tree/commit in an immutable finalize intent before ref update, so a crash after update
can discover the original commit rather than build another commit with a different clock.
At most one ref update per exact capture. No automatic repeat on CAS failure; reread and either recognize
the already committed candidate or return ARCHIVE_CHAIN_CONFLICT.
All previously committed files remain in the next tree; capture paths are never overwritten.

The main checkout/index is read-only to consumers and maintained only by the archive materializer.
Every capture commit is append-only, so materialization adds only the new manifest-declared paths.
Before doing so, verify the ordinary index exactly matches the recorded checkout head and every existing
tracked file matches its old blob; unexpected staged changes or human edits stop materialization.
Previously materialized new paths after a crash may be reused only if their bytes equal the known new blob.
Create the missing declared paths with exclusive or same-byte semantics; never delete/overwrite other files.
Only after all declared files match the new tree run `git read-tree <new_commit>` for the ordinary index,
then atomically record the new checkout head. This full index replacement is allowed only by those
old-index/old-content checks, not as a general repair operation.
If materialization cannot proceed, return the committed receipt with checkout_state=stale, retain all
history, and future writes require explicit successful repair. Reads use git cat-file, not stale files.
No reset --hard/checkout --/clean command. A stale checkout is not a lost commit or failed AI acceptance.

The single internal commit owner is `StageRepository.append_record(record_id, namespace,
files: Mapping[str,bytes], *, expected_head, record_fingerprint) -> CommitReceipt`,
declared in `app/spi/archive.py` and implemented by `storage/repository.py`.
`namespace` has an internal registered allowlist; W3 registers only captures/bootstrap.
Caller is the authorized application service holding root/stage locks, never an HTTP raw file request.
Paths are validated inside the namespace, existing content cannot change, fingerprint binds exact file
set and bytes, and the owner performs the same finalize intent/ref-CAS/materialization sequence.
W4/W5/W6 extend the registered record types with their own semantic validators; they do not add another
Git writer or expose arbitrary namespace writes. W3 tests only captures/bootstrap, not future acceptance.
`CommitReceipt` has commit_id, parent_commit, tree_id, record_fingerprint and checkout_state.

After commit verify manifest/hash/parent/pages, then atomically close active capture coordination and settle
reservation using actual usage. Crash before settlement leaves reservation unresolved until same-intent
recovery proves ref commit. Never declare ordinary successful finalize from a partial recovery.
`finalize_partial` can operate after deadline using existing intents/objects only, no new source bytes,
new IDs, deadline extension or provider/model call.

## 5. Git, Paths And Errors

Git environment strips inherited GIT_*; disable system/global config, prompting/replacement objects,
autocrlf, filters, hooks, signing, automatic maintenance. Explicit Git timeout30s/output limit16MiB,
bounded stdout/stderr drain, cleanup only the spawned process. Reuse donor Git runner policy.
`* -text -filter` is the only attributes file. Validate regular independent .git, branch, local allowlisted
config, no remotes/alternates/grafts/shallow/replace refs/submodules/unresolved main index.
No arbitrary user Git arguments; branch/author values validated before invocation.

Validate lexical and resolved roots/children, regular files, no links/reparse/hardlinks or path traversal,
including Windows reserved names. Public page identifiers resolve only through committed manifest.
Git output/error text is not leaked into domain errors.

Errors are fixed English codes: ARCHIVE_ROOT_UNCONFIGURED, ARCHIVE_CONFIG_INVALID, ARCHIVE_BUSY,
ARCHIVE_DEADLINE_EXPIRED, ARCHIVE_QUOTA_EXCEEDED, ARCHIVE_CAPTURE_CONFLICT,
ARCHIVE_COVERAGE_INCOMPLETE, ARCHIVE_IDENTITY_MISMATCH, ARCHIVE_CHAIN_CONFLICT,
ARCHIVE_RAW_PAGE_MISSING, ARCHIVE_RAW_PAGE_INTEGRITY_FAILED, ARCHIVE_MANIFEST_INVALID,
ARCHIVE_GIT_DIRTY, ARCHIVE_STORAGE_UNAVAILABLE, UNSAFE_PATH plus ProjectError for owner/lifecycle.

## 6. Files And Test Cases

Create `app/domain/{captures,capture_values}.py`, `app/spi/archive.py`,
`app/api/capture_archive.py`, `out/capture_archive.py`,
`storage/{git,paths,objects,repository,staging,admission,locks}.py`.
Modify `project_management/container.py` for explicit configured construction only,
`metrics/settings/defaults_metrics.py`, `.env.example`, `requirements.txt` and current guide.
Keep helpers small; split a responsibility before any configured limit is exceeded.
No Django schema needed in W3.ARCHIVE.

| IDs / file | Layer and discriminating behavior |
| --- | --- |
| AR01-04 `test_capture_archive.py` | L1/L2 owner/empty root/inside code repo/wrong stage rule rejected before files; unknown total not complete |
| AR05-08 same | L2 raw Unicode bytes retained; duplicate page same bytes replay/different bytes reject; subset details with complete membership stays partial |
| AR09-12 `test_capture_archive_recovery.py` | L2 interruption after page intent/object/receipt; old deadline refuses append but allows partial sealing; commit-before-return replay original commit |
| AR13-16 `test_capture_archive_git_native.py` | L3 real Git hostile env/hooks ignored; branch/ref/CAS; main checkout human edit never overwritten; committed reads independent of checkout |
| AR17-20 `test_capture_archive_budget.py` | L2/L3 stage/root/capture limits and two-process different-stage race; write failure retains intent; unresolved reservation not zero |
| AR21-23 `test_capture_archive_security.py` | L2/L3 path/link/corrupt object/forged page read refused; same display key wrong site/principal never crosses source chain |
| AR24 same | L2 three captures A/B/C remain separately queryable with paginated source_chain; no W4 accepted-baseline claim |

Use synthetic temporary external data root and real Git for commit assertions; stubbing Git success is
not acceptance. Test cache counters cannot bypass actual quota. Simulated write errors at exact boundaries,
real subprocess lock/CAS tests and bounded cleanup. Zero files/empty selection/skip are not a pass.
Run with explicit synthetic Django settings from provider connection tests, never real .env or captures.

```powershell
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_capture_archive.py --ds=provider_sync.tests.connection_test_settings -q
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_capture_archive_recovery.py project_management/tests/test_capture_archive_budget.py --ds=provider_sync.tests.connection_test_settings -q
.\.venv\Scripts\python.exe -m pytest project_management/tests/test_capture_archive_git_native.py project_management/tests/test_capture_archive_security.py --ds=provider_sync.tests.connection_test_settings -q
```

No test probes whole-volume free capacity. Native Git/source-boundary tests are local, not permission
to migrate old archives or enable a data remote. Final W3.R will review actual consumers after W3.CAPTURE.

## 7. Exit And Later Consumers

W3.ARCHIVE exits with real append/read/replay/recovery APIs and quota/path/Git tests; no report or AI call.
W3.CAPTURE must consume it for actual retained pages/snapshots, never keep another unarchived payload cache.
W4 indexes source chains and accepted pointers using committed manifests; model input is cumulative since
last accepted summary. W4.IMPORT must preserve original hashes and declare any transformed projection.
W5/W6 use the same commit owner for accepted summaries/publications, separate from capture completion.
Source migration mapping is fixed from the donor blob inventory, with code/license notices preserved.
The machine-produced inventory is [capture-archive-source.json](capture-archive-source.json);
41 source/test/resource blob IDs were checked against the pinned donor commit before inclusion.
Its temporary authoring paths are historical provenance, not runtime paths or another task ledger.
