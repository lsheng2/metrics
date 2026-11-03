from datetime import UTC, datetime
from dataclasses import replace

from project_management.app.domain.capture_values import (
    canonical_bytes,
    content_hash,
    decode_json,
    decode_snapshot,
    intent_from_mapping,
    manifest_from_bytes,
    membership_from_mapping,
    sha256_bytes,
    work_item_from_mapping,
)
from project_management.app.domain.captures import (
    ArchiveError,
    ArchiveIdentity,
    ArchiveLimits,
    CaptureIntent,
    CaptureManifest,
    CaptureReceipt,
    MembershipInput,
    PartCoverage,
    PreparedCapture,
    RawPageInput,
    RawPageRef,
    SnapshotInput,
    StoredSnapshotRef,
)
from project_management.app.domain.contracts import ProjectError
from project_management.storage.admission import GrowthEstimate, admit, finalize_growth, page_growth, write_reservation
from project_management.storage.locks import CombinedLocks
from project_management.storage.objects import ObjectStore
from project_management.storage.paths import ensure_configured_archive_root, read_bytes, validate_uuid, write_bytes
from project_management.storage.staging import PendingCaptureStore, active_capture_path, active_payload
from project_management.services.archive_reads import ArchiveReads
from project_management.services.archive_material import ArchiveMaterial
from project_management.services.report_archive import ReportArchiveRepositoryAccess
from project_management.services.report_archive_reads import ReportArchiveReads
from project_management.services.project_operation_archive import ProjectOperationArchive
from project_management.services.source_resolution import SourceResolutionArchive
from project_management.services.summary_journal import SummaryJournal
from project_management.app.domain.capture_validation import (
    item_key, text, validate_limits, validate_membership, validate_page, validate_snapshot,
)


class CaptureArchiveService(ProjectOperationArchive, ArchiveReads, ReportArchiveRepositoryAccess, ReportArchiveReads, ArchiveMaterial, SourceResolutionArchive, SummaryJournal):
    def __init__(self, project_api, repository_factory, config):
        self.project_api = project_api
        self.repository_factory = repository_factory
        self.config = config
        validate_limits(config.limits)
        text(config.author_name, 160)
        text(config.author_email, 256)

    def initialize_stage(self, actor, project_id, stage_id) -> ArchiveIdentity:
        project, stage = self._stage_for_write(actor, project_id, stage_id)
        self._validate_root_before_lock()
        with self._locks(project, stage):
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            head = repository.initialize()
            return ArchiveIdentity(
                root_id=self._root_id(),
                project_id=project.id,
                stage_id=stage.id,
                owner_subject=actor.subject,
                descriptor_hash=stage.definition_hash,
                head_commit=head,
            )

    def prepare(self, actor, intent: CaptureIntent) -> PreparedCapture:
        project, stage = self._validate_intent_for_write(actor, intent)
        intent_hash = content_hash(intent)
        self._validate_root_before_lock()
        with self._locks(project, stage):
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.initialize()
            pending = self._pending(intent)
            if (pending.root / 'receipt.json').exists():
                if pending.read_intent()[1] != intent:
                    raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
                return PreparedCapture(intent.capture_id, intent_hash, 'replayed')
            active = pending.runtime_root / active_capture_path(pending.runtime_root)
            if active.exists() and decode_json(read_bytes(pending.runtime_root, active.name)) != active_payload(intent_hash, intent.capture_id):
                raise ArchiveError('ARCHIVE_BUSY')
            admit(
                self.config.root,
                repository.stage_root,
                pending.root,
                self.config.limits,
                GrowthEstimate(len(canonical_bytes(intent)) + 2 * 1024**2 + 8192, 16),
            )
            state = self._prepare_intent(pending, intent, intent_hash)
            self._write_active(pending.runtime_root, intent.capture_id, intent_hash)
            write_reservation(pending.root, self.config.limits, 'reserved', len(pending.pages()), 1024 * 1024, 4)
            return PreparedCapture(intent.capture_id, intent_hash, state)

    def append_page(self, actor, intent: CaptureIntent, page: RawPageInput) -> RawPageRef:
        project, stage = self._validate_intent_for_write(actor, intent)
        self._validate_deadline(intent)
        validate_page(page)
        if page.item is not None and (page.item.provider_id != intent.source.provider_id
                                      or page.item.endpoint_id != intent.source.endpoint_id):
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        if len(page.payload) > self.config.limits.max_raw_page_bytes:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        self._validate_root_before_lock()
        with self._locks(project, stage):
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.initialize()
            pending = self._pending(intent)
            intent_hash = self._require_prepared(pending, intent)
            page_id = self._page_id(intent_hash, page)
            page_intent = self._page_intent(intent_hash, page_id, page)
            path = pending.root / 'pages' / page_id / 'receipt.json'
            store = ObjectStore(repository.objects, self.config.limits.max_object_bytes)
            if path.exists():
                old_intent = decode_json(read_bytes(pending.root, f'pages/{page_id}/intent.json'))
                comparable = dict(page_intent)
                comparable['item'] = old_intent.get('item')
                old_item = work_item_from_mapping(old_intent['item']) if old_intent.get('item') else None
                if self._item_key(old_item) != self._item_key(page.item) or canonical_bytes(old_intent) != canonical_bytes(comparable):
                    raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
                ref = pending.read_page(page_id).reference
                if store.read(ref) != page.payload:
                    raise ArchiveError('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED')
                return ref
            admit(self.config.root, repository.stage_root, pending.root, self.config.limits, page_growth(len(page.payload)))
            pending.write_page_intent(page_id, page_intent)
            reference = store.put(page.payload, page.content_type, page.request_fingerprint, page_id)
            pending.write_page_receipt(page_id, reference, self._item_key(page.item), page.page_key)
            write_reservation(pending.root, self.config.limits, 'reserved', len(pending.pages()), 1024 * 1024, 4)
            return pending.read_page(page_id).reference

    def append_snapshot(self, actor, intent: CaptureIntent, snapshot: SnapshotInput) -> StoredSnapshotRef:
        project, stage = self._validate_intent_for_write(actor, intent)
        self._validate_deadline(intent)
        decode_snapshot(canonical_bytes(snapshot))
        self._validate_snapshot_identity(intent, snapshot)
        validate_snapshot(snapshot)
        if len(canonical_bytes(snapshot)) > self.config.limits.max_raw_page_bytes:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        self._validate_root_before_lock()
        with self._locks(project, stage):
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.initialize()
            pending = self._pending(intent)
            self._require_prepared(pending, intent)
            self._validate_snapshot_pages(pending, snapshot)
            for old, ref in pending.snapshots():
                if item_key(old.identity) == item_key(snapshot.identity):
                    if canonical_bytes(old) != canonical_bytes(snapshot):
                        raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
                    return ref
            admit(self.config.root, repository.stage_root, pending.root, self.config.limits,
                  finalize_growth(1, len(canonical_bytes(snapshot))))
            source_hash = self._source_hash(snapshot)
            source_key = self._source_key(intent, snapshot.identity)
            history = self._source_chain(repository, source_key)
            reference = StoredSnapshotRef(
                identity=snapshot.identity,
                capture_id=intent.capture_id,
                sequence=len(history) + 1,
                previous_capture_id=history[-1].capture_id if history else None,
                source_hash=source_hash,
                git_path=f'captures/{intent.capture_id}/snapshots/{source_hash}.json',
            )
            pending.write_snapshot(source_hash, snapshot, reference)
            write_reservation(pending.root, self.config.limits, 'reserved', len(pending.pages()), 1024 * 1024, 4)
            return reference

    def finalize(self, actor, intent: CaptureIntent, membership: MembershipInput, *, complete: bool, failure_code: str | None = None) -> CaptureReceipt:
        project, stage = self._validate_intent_owner(actor, intent)
        validate_membership(membership_from_mapping(decode_json(canonical_bytes(membership))))
        if failure_code is not None:
            text(failure_code)
        self._validate_root_before_lock()
        with self._locks(project, stage):
            repository = self.repository_factory.open(self.config, project, stage, actor.subject)
            repository.initialize()
            pending = self._pending(intent)
            replay = self._finalize_replay(repository, intent, membership, complete, failure_code)
            if replay is not None:
                return replay
            if complete and project.archived:
                raise ProjectError('PROJECT_ARCHIVED')
            if complete and stage.source_status != 'current':
                raise ProjectError('SOURCE_CHANGED')
            if complete:
                self._validate_deadline(intent)
            self._require_prepared(pending, intent)
            pages = pending.pages()
            snapshots = pending.snapshots()
            self._validate_finalize(intent, membership, pages, snapshots, complete, failure_code)
            prepared_at = pending.prepared_at()
            finalized_at = datetime.now(UTC).isoformat()
            refs = tuple(reference for _, reference in snapshots)
            manifest = CaptureManifest(1, intent, membership, refs, pages, complete, failure_code, prepared_at, finalized_at)
            frozen = pending.finalize_manifest(manifest)
            candidate = manifest_from_bytes(canonical_bytes(frozen))
            if (candidate.intent != intent or candidate.membership != membership
                    or candidate.complete != complete or candidate.failure_code != failure_code
                    or candidate.snapshots != refs or candidate.pages != pages):
                raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
            manifest = candidate
            manifest_bytes = canonical_bytes(candidate)
            files = {
                f'captures/{intent.capture_id}/manifest.json': manifest_bytes,
                f'captures/{intent.capture_id}/pages.json': canonical_bytes(pages),
                f'captures/{intent.capture_id}/page-intents.json': canonical_bytes(pending.page_intents()),
                f'captures/{intent.capture_id}/admission.json': read_bytes(pending.root, 'intent.json'),
            }
            for snapshot, reference in snapshots:
                self._validate_snapshot_pages(pending, snapshot)
                files[reference.git_path] = canonical_bytes(snapshot)
            objects = ObjectStore(repository.objects, self.config.limits.max_object_bytes)
            for page in pages:
                objects.read(page)
            growth_bytes = sum(len(data) for data in files.values())
            admit(self.config.root, repository.stage_root, pending.root, self.config.limits,
                  finalize_growth(len(files), growth_bytes), consume_reserved=True)
            pending.freeze_manifest(candidate)
            receipt = repository.append_record(
                intent.capture_id,
                'captures',
                files,
                expected_head=repository.head(),
                record_fingerprint=sha256_bytes(manifest_bytes),
            )
            capture_receipt = CaptureReceipt(
                capture_id=intent.capture_id,
                commit_id=receipt.commit_id,
                manifest_sha256=sha256_bytes(manifest_bytes),
                parent_commit=receipt.parent_commit,
                membership_complete=membership.coverage.state == 'complete',
                complete=complete,
                failure_code=failure_code,
                snapshots=refs,
                checkout_state=receipt.checkout_state,
            )
            pending.write_receipt(capture_receipt)
            write_reservation(pending.root, self.config.limits, 'settled', len(pages), 0, 0)
            self._clear_active(pending.runtime_root)
            return capture_receipt

    def finalize_partial(self, actor, project_id, stage_id, capture_id, *, failure_code, membership=None) -> CaptureReceipt:
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        if membership is not None:
            validate_membership(membership_from_mapping(decode_json(canonical_bytes(membership))))
        self._validate_root_before_lock()
        repository = self.repository_factory.open(self.config, project, stage, actor.subject)
        repository.verify_identity()
        pending = PendingCaptureStore(repository.runtime, capture_id)
        _, intent = pending.read_intent()
        stored_limits = decode_json(read_bytes(pending.root, 'intent.json'))['limits']
        if stored_limits != decode_json(canonical_bytes(self.config.limits)):
            original = ArchiveLimits(**stored_limits)
            validate_limits(original)
            resumed = type(self)(self.project_api, self.repository_factory, replace(self.config, limits=original))
            return resumed.finalize_partial(actor, project_id, stage_id, capture_id, failure_code=failure_code,
                                            membership=membership)
        with self._locks(project, stage):
            pending.recover_pages(ObjectStore(repository.objects, self.config.limits.max_object_bytes))
        pages = pending.pages()
        snapshots = pending.snapshots()
        if membership is None:
            membership = MembershipInput(
                tuple(snapshot.identity for snapshot, _ in snapshots),
                self._partial_coverage(failure_code, len(snapshots)),
                tuple(page.page_id for page in pages),
            )
        return self.finalize(actor, intent, membership, complete=False, failure_code=failure_code)

    def _stage_for_write(self, actor, project_id, stage_id):
        project, stage = self._stage_for_read(actor, project_id, stage_id)
        if project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        if stage.source_status != 'current':
            raise ProjectError('SOURCE_CHANGED')
        return project, stage

    def _stage_for_read(self, actor, project_id, stage_id):
        validate_uuid(project_id)
        validate_uuid(stage_id)
        detail = self.project_api.get_project(actor, project_id)
        for stage in detail.stages:
            if stage.id == stage_id:
                return detail.project, stage
        raise ProjectError('PROJECT_NOT_FOUND')

    def _validate_intent_for_write(self, actor, intent: CaptureIntent):
        project, stage = self._validate_intent_owner(actor, intent)
        if project.archived:
            raise ProjectError('PROJECT_ARCHIVED')
        if stage.source_status != 'current':
            raise ProjectError('SOURCE_CHANGED')
        return project, stage

    def _validate_intent_owner(self, actor, intent: CaptureIntent):
        intent_from_mapping(decode_json(canonical_bytes(intent)))
        validate_uuid(intent.project_id)
        validate_uuid(intent.stage_id)
        validate_uuid(intent.capture_id)
        validate_uuid(intent.request_id)
        project, stage = self._stage_for_read(actor, intent.project_id, intent.stage_id)
        descriptor = stage.descriptor
        if (
            intent.source.provider_id != descriptor.provider_id
            or intent.source.endpoint_url != descriptor.endpoint
            or intent.source.rule_hash != stage.definition_hash
            or not intent.source.principal_id
            or not intent.source.endpoint_id
        ):
            raise ArchiveError('ARCHIVE_IDENTITY_MISMATCH')
        return project, stage

    def _validate_deadline(self, intent: CaptureIntent) -> None:
        if datetime.now(UTC) > intent.deadline_at.astimezone(UTC):
            raise ArchiveError('ARCHIVE_DEADLINE_EXPIRED')

    def _prepare_intent(self, pending: PendingCaptureStore, intent: CaptureIntent, intent_hash: str) -> str:
        try:
            existing_hash, existing = pending.read_intent()
        except ArchiveError as error:
            if error.code != 'ARCHIVE_RAW_PAGE_MISSING':
                raise
            pending.write_intent(intent, intent_hash, self.config.limits)
            return 'prepared'
        if existing_hash != intent_hash or existing != intent:
            raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
        return 'replayed'

    def _require_prepared(self, pending: PendingCaptureStore, intent: CaptureIntent) -> str:
        existing_hash, existing = pending.read_intent()
        if existing != intent:
            raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
        if (pending.root / 'receipt.json').exists():
            raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
        active = decode_json(read_bytes(pending.runtime_root, active_capture_path(pending.runtime_root)))
        if active != active_payload(existing_hash, intent.capture_id):
            raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
        wrapper = decode_json(read_bytes(pending.root, 'intent.json'))
        if wrapper.get('limits') != decode_json(canonical_bytes(self.config.limits)):
            raise ArchiveError('ARCHIVE_CONFIG_INVALID')
        return existing_hash

    def _finalize_replay(self, repository, intent, membership, complete, failure_code):
        manifest_path = f'captures/{intent.capture_id}/manifest.json'
        if manifest_path not in repository.list_files(f'captures/{intent.capture_id}'):
            return None
        manifest = manifest_from_bytes(repository.read_file(manifest_path))
        if (
            manifest.intent != intent
            or manifest.membership != membership
            or manifest.complete != complete
            or manifest.failure_code != failure_code
        ):
            raise ArchiveError('ARCHIVE_CAPTURE_CONFLICT')
        receipt = self._receipt_from_manifest(repository, manifest)
        pending = self._pending(intent)
        pending.write_receipt(receipt)
        write_reservation(pending.root, self.config.limits, 'settled', len(manifest.pages), 0, 0)
        active = pending.runtime_root / active_capture_path(pending.runtime_root)
        if active.exists():
            if decode_json(read_bytes(pending.runtime_root, active.name)) == active_payload(content_hash(intent), intent.capture_id):
                self._clear_active(pending.runtime_root)
        return receipt

    def _pending(self, intent: CaptureIntent) -> PendingCaptureStore:
        return PendingCaptureStore(self.config.root / 'projects' / intent.project_id / 'stages' / intent.stage_id / 'runtime', intent.capture_id)

    def _locks(self, project, stage):
        stage_lock = self.config.root / 'projects' / project.id / 'stages' / stage.id / 'runtime' / 'archive.lock'
        return CombinedLocks(self.config.root / 'budget.lock', stage_lock)

    def _validate_root_before_lock(self) -> None:
        ensure_configured_archive_root(self.config.root)

    def _write_active(self, runtime, capture_id: str, intent_hash: str) -> None:
        write_bytes(runtime, active_capture_path(runtime), canonical_bytes(active_payload(intent_hash, capture_id)), immutable=True)

    def _clear_active(self, runtime) -> None:
        active = runtime / active_capture_path(runtime)
        try:
            if active.exists():
                active.unlink()
        except OSError:
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE') from None

    def _item_key(self, item) -> str | None:
        if item is None:
            return None
        return content_hash(item_key(item))

    def _root_id(self):
        return str(decode_json(read_bytes(self.config.root, 'archive-root.json'))['root_id'])

    def _partial_coverage(self, failure_code: str, count=0):
        return PartCoverage('partial', None, count, None, failure_code)
