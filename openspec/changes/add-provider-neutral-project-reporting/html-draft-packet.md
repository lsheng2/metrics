# HTML Draft And Finalization Packet

Status: execution detail for W6.HTML.EDIT / FINALIZE, dependent on SOURCE/RENDER.
Parent: [HTML authoring](html-report-authoring.md).
No new Git writer, worker or source authority. State only in tasks.md.

Version boundary: this packet describes implemented schema1. The proposed
[Authoring V2 contracts](report-authoring-contracts.md) add exact schema2 readers,
overlays, template snapshots and finalization packets. Old bytes/hash rules here remain;
do not reinterpret schema1 text or accept schema2 via a relaxed schema1 parser.

## Construction And Boundaries

```text
ReportDraftService(archive, source_reader, renderer, *,
                   limits=None, clock=None)
```

`archive` is the existing CaptureArchiveService. `source_reader` and `renderer`
are the SOURCE/RENDER public services. `clock` supplies aware UTC instants,
default now; never use it to change source cutoff. ReportDraft/ReportPublication
DTOs and public methods are as defined in the parent.
Use new `ReportDraftStore` inside `project_management/storage/report_drafts.py`
for controlled runtime files. It gets the already authorized stage repository,
not arbitrary paths from a user. Reuse storage.paths canonical read/write/link
guards and root-budget/stage locks. No test-only factory branches in production.

New public `ReportDraft` exact field order:
`draft_id, revision, revision_hash, selection, snapshot_hash, snapshot,
template, template_definition, edits, created_at, updated_at,
parent_publication_id, state`.
`template` is normalized TemplateSelection; `template_definition` is the
resolved hash/renderer/version/options descriptor; `edits` is a tuple of
server-attributed ReportEdit. `state` is derived, not in the hashed immutable
revision payload. `revision_hash` hashes the exact revision JSON bytes excluding
itself; snapshot_hash hashes its separate canonical snapshot bytes.

`app/domain/report_draft_values.py` supplies explicit schema1 deserialization
for these DTOs and the SOURCE snapshot (SourceChainKey, WorkItemIdentity,
SummaryReference, ReportRow/Message/Event/Day). Only defined fields/types accepted,
including bool-vs-int, UUID/hash, string/None and bounded collection checks.
No pickle/eval/dynamic class names or ad hoc repr parsing. Re-encoded bytes/hash
must match the stored canonical values before a saved draft is used.
ReportService implementations never expose the private store to W7/UI.

The archive exposes an internal `_report_repository(actor, project, stage,
write=False)` context from a new `services/report_archive.py` mixin:
owner first, root identity, shared locks for mutations, recheck owner/lifecycle/
stage under lock, then existing repository factory and identity checks.
Writes reject archived/noncurrent sources and active capture; reads do not
allocate lock paths or initialize anything. Source generation/render happens
outside write locks; install their results only after a fresh state check.
No public arbitrary file/namespace write API is introduced.

## Create And Save

Create payload: canonical `{selection, template}` plus command_id supplied by
trusted route form/CLI. `draft_id=UUID5(stage_id, "draft:"+command_id)`.
Same command identical original payload replays its original revision, independent
of later draft revisions. Different payload with same ID -> REPORT_REVISION_CONFLICT.
Replay reads saved selected template/snapshot, not current config or current source.

Storage refinement of parent layout:

```text
runtime/report-drafts/<draft-id>/
  intent.json
  snapshot.json
  revisions/<8-digit-revision>.json
  commands/<command-id>.json
  current.json
```

Snapshot is saved once with its immutable hash; revisions reference it.
The returned ReportDraft still includes the full verified snapshot. Avoid copying
the entire source into every note revision. It exposes `revision_hash` from the
verified immutable revision bytes in create/get/save responses; W7 records that
public value without accessing storage internals. `intent.json` binds original
command/payload hash/project/stage/owner/snapshot_hash/created_at.
Revision contains version/revision/selection/template definition/active edits/
created_at/updated_at/parent-publication, not a second source authority.
Each command intent stores canonical request hash, expected/prior revision,
complete intended next revision and its hash before atomic current.json publish.
`current.json` has revision+revision_hash only; derived finalizing/finalized state
comes from finalization packet and verified Git receipt, not an editable boolean.

Create first validates only request shape and actor/project ownership, derives
draft_id and checks for a persisted create command/intent under the shared locks.
An existing matching command replays/repairs its saved snapshot/template/revision
without current-source or current-template resolution; a changed request
fingerprint conflicts. Current access/lifecycle checks still apply.
Only an absent command releases locks to resolve the new source/template.
It then reacquires shared locks, checks the command again to close the race,
rechecks source freshness, admits snapshot/revision/intent/write overhead,
writes immutable snapshot/create intent/revision/command then publishes head.
Same command repairs an incomplete matching create; conflicting retained material
is preserved and refused. Never flush a draft directory to make create succeed.

Save accepts the complete desired active edits list plus template selection.
Under lock, first replay matching existing command; otherwise compare expected
revision, check not finalizing, validate original target hashes and bounds.
Existing unchanged edit content retains its verified author/time; new or changed
edits receive the current verified actor/time. Removed notes disappear only from
the new active list, remaining in old revisions. Browser-posted author/time ignored
or refused, never used as evidence. Same-source/template changes require no model.

Before saving, enforce per-note/all-edit limits and cumulative saved edit-history
size <=8MiB (initial configurable limit). This is additional to the1000revision
guard and existing physical stage/root quota. Refuse with original revisions
retained. No automatic cleanup of notes.

After a command intent exists, that original intended revision/timestamps are
the only repair candidate. Write revision then atomic head. A crash before head
is recoverable by original command; any conflicting later head refuses rather
than moving backward. A command replay never reapplies edits as another revision.

`ReportDraftStore.publish_current(revision, revision_hash, *, expected_revision)`
is the only mutable-head writer. Called under the existing shared locks, it
rechecks the old head and exact immutable revision hash, then invokes existing
`storage.paths.write_bytes(..., "current.json", canonical_bytes(head),
immutable=False)`. That helper already uses a flushed temp file and os.replace
with containment/link checks. Use immutable=True for all snapshot/revision/
command/finalization payloads; no second generic atomic-file implementation.

## Reads And Current Source

`get` and `render(revision=N)` authorize owner and validate draft identity/
snapshot/revision bytes. Render accepts any retained saved revision, not only
the mutable latest, and never writes a cache on GET. Returned content binds the
exact requested draft/revision/hash. Wrong owner or missing draft ->404 semantics.
No current source network call is required to view a permitted historical draft.
Current configured source visibility/lifecycle rules remain enforced.

New draft creation/finalization uses current source selection or explicit
historical_export. Parent publication lineage is checked by the report archive
resolver. Until FINALIZE installs the resolver, non-null parent/baseline values
remain explicitly unsupported instead of faked.

Finalization requires current source/candidate and selected baseline to remain
the same as the draft, but an unrelated Git append is not semantic source drift.
Compare capture/source/accepted refs and versioned policy, not only global HEAD.
Actual Git append still uses current HEAD CAS. Existing original snapshot's
source_commit remains unchanged in the edition.

## Finalization

1. Reauthorize and read exact expected draft revision. If already committed for
   that revision/purpose, verify the manifest/request and replay original receipt.
2. Validate/produce final renderer output outside locks. Only edition metadata
   may differ from a draft preview; content, notes, cutoff and template match
   the selected saved revision. Final preview/copy must bind its explicit state.
3. Reacquire shared locks and check revision/not-finalizing/source/baseline/
   lifecycle. Admit retained packet plus conservative Git growth before writing.
4. Persist all six exact packet files, hashes and command payload hash according
   to parent section7. Cumulative saved edit revisions go into edits.json.
   Persist original timestamp and publication ID before marking finalizing.
5. Append only `report_publications/<publication-id>/` and exactly
   snapshot.json/template.json/edits.json/report.html/report.txt/manifest.json
   through existing StageRepository.append_record. Manifest hashes other5files;
   finalization packet hashes all6. No arbitrary namespace/file value from Web.
6. Verify committed files/manifest/reference and return ReportPublication.
   Materialization state is separate. Do not delete retained packet on success.

`resume_finalization` reads exact durable bytes, never rerenders. Before a new
ref update it rechecks current authorization and source/baseline guards. If a
commit already exists, verify/replay even when source later advanced; it cannot
overwrite the later live display or claim a new publication time.
Committed receipt may be reconstructed from Git when the local final state
was lost. Missing/corrupt packet or mismatched intent refuses safely.

Report-publication path validation extends `storage/repository.py` only for this
exact UUID namespace/file allowlist, keeping old namespace semantics intact.
One publication ID maps to one draft/revision/purpose. Missing original bytes
cannot cause regeneration under a new template or a second publication ID.
No push, remote changes, global Git config, user branch switch or unrelated add.

## Publication Queries And Baselines

Add read-only archive helpers `list_report_publications(...)` and
`read_report_publication(...)` in the same new report archive owner. Sort by
verified finalization time and publication ID; query exact files at pinned HEAD,
validate all hashes/owner/stage/rule/lineage. The returned manifest has no own
commit hash. Resolve commit separately from the verified publication path.

Latest standup publication is the prior finalized source baseline, not latest
draft/export. Parent amendment links must be same owner/stage and acyclic.
Historical exports preserve original snapshot and never become the latest
standup. Permit selection of old same-stage publication data for new drafts
without re-running the initial-source selection as though it were current.
First authoring slice may compare exact same-source baseline as no changes;
changed-source timeline/events remain W4.DELTA/EVIDENCE rather than dropping
changes. The full pipeline must continue to surface pending delta honestly.

## Tests And Files

EDIT: `services/report_drafts.py`, `storage/report_drafts.py`,
`services/report_archive.py`, `app/domain/report_draft_values.py`,
`tests/test_report_drafts.py`, `tests/report_draft_fixtures.py`.
FINALIZE: `services/report_publication.py`, `services/report_publication_reads.py`,
bounded additions in report_archive.py/storage/repository.py/source resolver,
`tests/test_report_publication.py`, `test_report_publication_security.py`.
Modify CaptureArchiveService mixin/public reports exports and parent DTO additions
only as required for these public services. No other source/SDK behavior changes.

HT15-19: fast controlled store SPI tests for conflict and failure branches, plus
real safe-path temporary storage for immutable file/atomic-head behavior.
HT20-24/31: one representative real temporary Git scenario with sequential
save/no-commit -> finalize -> replay -> amendment -> original download.
Fault cases use injected storage/Git SPI failure at actual declared boundaries;
never mock final success or assert only mock calls. Corruption cases verify
the service refuses output, not merely that a hash helper differs.
Snapshot/accepted source/candidate remain byte-identical after all operations.
The source fixture can be reused read-only; every mutating scenario owns its
draft/publication path and never modifies prior validation evidence.

First EDIT RED checks note save yields revision2 but unchanged archive HEAD.
First FINALIZE RED checks explicit finalize produces one real commit and old
record hashes remain equal. Failed/duplicate commits and pre-append crash must
retain the same original packet/ID. Run only affected tests before stable-candidate
browser qualification, not the entire old T12 suite.

### FINALIZE Integration Details

Keep ReportDraftService as the public service. Put finalization/read methods in
a mixin or composed ReportPublicationService in services/report_publication.py,
sharing existing `_store` and archive `_report_repository`; never subclass a
test fixture or expose arbitrary storage callbacks to HTTP.
Draft-store state now requires a validated resolver: a valid durable local
finalization packet means finalizing; finalized requires matching committed
manifest/files. Mere finalized.json existence remains invalid.

The publication ID/paths are derived, and the finalization payload contains
draft revision hash as well as snapshot/template hashes. Check original
rendered.revision_hash matches selected draft. Every file hash/size in the
packet is verified before append; manifest links back to selected draft.
Replay returns the exact prior commit using its path/manifest fingerprint,
never the current HEAD as a substitute for publication commit.

Historical publication reads verify original bytes/provenance and current
authorization but need not rerender or construct a model/summary service.
Current report finalization takes a fresh report source read outside the write
lock and compares semantic capture/summary identity under the write lock using
its pinned HEAD; ordinary report/Git appends alone must not count as source
drift. A new actual capture or accepted revision does count as source drift.

Lineage source resolution can be a focused collaborator in
services/report_publication_reads.py consumed by ReportSourceReader. For a
parent publication, decode its exact stored snapshot and selected template
without passing the old capture to the current-only SOURCE selection. New
draft retains original snapshot plus parent ID; current standup finalization
still checks freshness, historical_export never advances the latest baseline.
For a baseline publication with exactly equal retained source identities and
hashes across every intermediate complete capture, set comparison_state=no_change
and events=(). If changed-source delta is unavailable, explicitly refuse that
comparison rather than making up a no-change or silently omitting it.
The unchanged full-stack path is thereby executable while W4 remains open.
