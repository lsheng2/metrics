from pathlib import Path

from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError, ArchiveLimits
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import ReportDraftLimits, bytes_hash, read_json
from project_management.app.domain.report_publication_contracts import (
    MANIFEST_HASHED_FILES,
    PUBLICATION_FILES,
    finalization_from_mapping,
    manifest_from_mapping,
    publication_path,
)
from project_management.app.domain.report_publication_validation import (
    PublicationValidationContext,
    validate_publication_files,
)
from project_management.storage.admission import GrowthEstimate, admit, finalize_growth
from project_management.storage.paths import read_bytes, validate_uuid, write_bytes


SNAPSHOT_READ_LIMIT = 8_388_608


class ReportFinalizationPacketStore:
    def __init__(self, repository, archive_root: Path, archive_limits: ArchiveLimits, limits: ReportDraftLimits):
        self.repository = repository
        self.archive_root = archive_root
        self.archive_limits = archive_limits
        self.limits = limits

    def root(self, draft_id: str) -> Path:
        return self.repository.runtime / 'report-drafts' / validate_uuid(draft_id)

    def intent_exists(self, draft_id: str) -> bool:
        return (self.root(draft_id) / 'finalization.json').exists()

    def write_files(self, draft_id: str, publication_id: str, files) -> None:
        root = self.root(draft_id)
        self._admit(root, GrowthEstimate(sum(len(data) for data in files.values()) + 8192, len(files) * 2))
        for name in PUBLICATION_FILES:
            write_bytes(root, f'finalization-files/{validate_uuid(publication_id)}/{name}', files[name],
                        immutable=True, conflict_code='ARCHIVE_CAPTURE_CONFLICT')

    def write_intent(self, draft_id: str, payload) -> None:
        root = self.root(draft_id)
        self._admit(root, GrowthEstimate(len(canonical_bytes(payload)) + 4096, 2))
        write_bytes(root, 'finalization.json', canonical_bytes(payload), immutable=True,
                    conflict_code='ARCHIVE_CAPTURE_CONFLICT')

    def admit_new(self, draft_id: str, files, payload) -> None:
        git_growth = finalize_growth(len(files), sum(len(data) for data in files.values()))
        local_bytes = sum(len(data) for data in files.values()) + len(canonical_bytes(payload)) + 12288
        local_files = len(files) * 2 + 2
        self._admit(self.root(draft_id), GrowthEstimate(local_bytes + git_growth.bytes, local_files + git_growth.files))

    def admit_commit(self, draft_id: str, files) -> None:
        self._admit(self.root(draft_id), finalize_growth(len(files), sum(len(data) for data in files.values())))

    def packet(self, draft_id: str):
        return self._verified(self.root(draft_id), draft_id)

    def state(self, draft_id: str) -> str:
        root = self.root(draft_id)
        if (root / 'finalized.json').exists():
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if not self.intent_exists(draft_id):
            return 'draft'
        payload, files = self._verified(root, draft_id)
        return 'finalized' if self._committed(payload, files) else 'finalizing'

    def _verified(self, root: Path, draft_id: str):
        try:
            payload = finalization_from_mapping(read_json(read_bytes(root, 'finalization.json')))
        except ReportError as error:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from error
        if payload['draft_id'] != draft_id:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        files = {}
        for name in PUBLICATION_FILES:
            data = read_bytes(root, f"finalization-files/{payload['publication_id']}/{name}",
                              limit=self.limits.max_edit_history_bytes + SNAPSHOT_READ_LIMIT)
            if len(data) != payload['file_sizes'][name] or bytes_hash(data) != payload['file_hashes'][name]:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
            files[name] = data
        try:
            manifest = manifest_from_mapping(read_json(files['manifest.json']))
        except ReportError as error:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from error
        if (manifest.publication_id != payload['publication_id'] or manifest.draft_id != payload['draft_id']
                or manifest.draft_revision != payload['draft_revision']
                or manifest.draft_revision_hash != payload['draft_revision_hash']
                or manifest.purpose != payload['purpose'] or manifest.snapshot_hash != payload['snapshot_hash']
                or manifest.template_hash != payload['template_hash']
                or manifest.finalized_at != payload['finalized_at'] or manifest.finalized_by != payload['finalized_by']
                or bytes_hash(files['manifest.json']) != payload['file_hashes']['manifest.json']):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        if manifest.schema_version != payload['schema_version']:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        self._verify_authored_fields(manifest, payload)
        if any(manifest.file_hashes[name] != payload['file_hashes'][name] for name in MANIFEST_HASHED_FILES):
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        try:
            validate_publication_files(payload['publication_id'], files, self._context(), payload['finalized_by'])
        except ReportError as error:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from error
        return payload, files

    def _verify_authored_fields(self, manifest, payload) -> None:
        if manifest.schema_version == 1:
            return
        fields = (
            'authoring_schema',
            'template_snapshot_hash',
            'template_document_hash',
            'fill_policy_hash',
            'edits_hash',
            'series_id',
            'report_role',
            'meeting_key',
            'period_key',
            'continuity_hash',
        )
        for field in fields:
            if getattr(manifest, field) != payload[field]:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')

    def _committed(self, payload, files) -> bool:
        try:
            commit = self.repository.find_commit_for_path(publication_path(payload['publication_id'], 'manifest.json'))
        except ReportError as error:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from error
        if commit is None:
            return False
        for name in PUBLICATION_FILES:
            try:
                data = self.repository.read_file(publication_path(payload['publication_id'], name), commit)
            except (ArchiveError, ReportError):
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None
            if data != files[name]:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return True

    def _admit(self, draft_root: Path, growth: GrowthEstimate) -> None:
        admit(self.archive_root, self.repository.stage_root, draft_root, self.archive_limits, growth)

    def _context(self):
        return PublicationValidationContext(
            self.repository.project.id,
            self.repository.stage.id,
            self.repository.owner_subject,
            self.repository.stage.definition_hash,
        )
