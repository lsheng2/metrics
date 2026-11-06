from dataclasses import asdict, dataclass
from typing import Mapping
from uuid import UUID, uuid5

from project_management.app.domain.capture_values import canonical_bytes, decode_json, sha256_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_authoring_hashes import (
    authored_create_request_hash,
    authored_create_template_use_request_hash,
    pinned_template_use_hash,
)
from project_management.app.domain.report_authoring import authored_edit_from_mapping
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_uuid_text
from project_management.app.domain.report_templates import UserTemplateSelection
from project_management.app.domain.report_continuity import MAX_CONTEXT_BYTES
from project_management.services.report_preparation_seed import validate_prepared_context_seed
from project_management.storage.paths import read_bytes


@dataclass(frozen=True, slots=True)
class PreparedDraftContext:
    draft_id: str
    request_hash: str
    context: Mapping
    context_hash: str
    snapshot_hash: str
    pinned_template_use: object
    authority: Mapping | None
    initial_authored_edits: tuple
    preservation_hash: str | None
    preservation_review_issues: tuple


class PreparedContextReader:
    def __init__(self, archive, template_service):
        self.archive = archive
        self.template_service = template_service

    def read_for_create(self, actor, project_id, stage_id, *, command_id, selection, template, preparation_id):
        command_id = validate_uuid_text(command_id)
        preparation_id = validate_uuid_text(preparation_id)
        draft_id = str(uuid5(UUID(validate_uuid_text(str(stage_id))), f'draft:{command_id}'))
        with self.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
            seed = self._read_seed(repository, preparation_id)
            context = validate_prepared_context_seed(seed)
            self._verify_seed_binding(repository, actor, project_id, stage_id, preparation_id, command_id, draft_id, seed)
        preservation = seed.get('preservation')
        preservation_hash = None if preservation is None else preservation['preservation_hash']
        self._verify_selection(seed, selection)
        pinned = self.template_service.read_use(
            actor,
            project_id,
            draft_id=draft_id,
            template_use_hash=seed['template_use_hash'],
        )
        self._verify_template_binding(seed, selection, template, preparation_id, pinned)
        return PreparedDraftContext(
            draft_id,
            authored_create_request_hash(selection, template, preparation_id, seed['context_hash'], preservation_hash),
            context,
            seed['context_hash'],
            seed['snapshot_hash'],
            pinned,
            seed.get('authority'),
            () if preservation is None else tuple(authored_edit_from_mapping(item) for item in preservation['initial_authored_edits']),
            preservation_hash,
            () if preservation is None else tuple(preservation['review_issues']),
        )

    def _read_seed(self, repository, preparation_id):
        try:
            return decode_json(read_bytes(repository.runtime, f'report-preparations/{preparation_id}/context.json', limit=MAX_CONTEXT_BYTES + 8192))
        except ArchiveError as error:
            if error.code == 'ARCHIVE_RAW_PAGE_MISSING':
                raise ReportError('REPORT_NOT_FOUND') from None
            raise ReportError('REPORT_ARTIFACT_INVALID') from None

    def _verify_seed_binding(self, repository, actor, project_id, stage_id, preparation_id, command_id, draft_id, seed):
        expected = {
            'preparation_id': preparation_id,
            'create_command_id': command_id,
            'draft_id': draft_id,
            'project_id': validate_uuid_text(str(project_id)),
            'stage_id': validate_uuid_text(str(stage_id)),
            'owner_subject': actor.subject,
            'stage_hash': repository.stage.definition_hash,
        }
        if any(seed[key] != value for key, value in expected.items()):
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _verify_selection(self, seed, selection):
        expected = sha256_bytes(canonical_bytes({
            'selection': selection,
            'baseline': seed['expected_baseline_ref'],
        }))
        if seed['effective_selection_hash'] != expected:
            raise ReportError('REPORT_REVISION_CONFLICT')

    def _verify_template_binding(self, seed, selection, template, preparation_id, pinned):
        if not isinstance(template, UserTemplateSelection):
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
        expected_request = authored_create_template_use_request_hash(selection, template, preparation_id)
        if pinned.request_hash != expected_request or seed['template_request_hash'] != expected_request:
            raise ReportError('REPORT_REVISION_CONFLICT')
        if pinned_template_use_hash(pinned) != seed['template_use_hash']:
            raise ReportError('REPORT_ARTIFACT_INVALID')
        if pinned.template_snapshot.get('selection') != asdict(template):
            raise ReportError('REPORT_TEMPLATE_UNSUPPORTED')
