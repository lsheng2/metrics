from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.run_contracts import RunError
from project_management.storage.project_operations import ProjectOperationRepository
from project_management.storage.report_drafts import ReportDraftStore


def verify_parent_cas(repository, archive_root, archive_limits, draft_limits, intent):
    if intent['parent_operation_id'] is not None:
        operation = _operation(repository, archive_root, archive_limits, intent['parent_operation_id'])
        if (operation.revision != intent['expected_parent_operation_revision']
                or operation.state != intent['expected_parent_operation_state']):
            raise ReportError('REPORT_REVISION_CONFLICT')
    if intent['parent_draft_id'] is not None:
        try:
            draft = ReportDraftStore(repository, archive_root, archive_limits, draft_limits).read_draft(intent['parent_draft_id'])
        except ArchiveError:
            raise ReportError('REPORT_REVISION_CONFLICT') from None
        if (draft.revision != intent['expected_parent_draft_revision']
                or draft.revision_hash != intent['expected_parent_draft_revision_hash']
                or draft.state != 'draft'):
            raise ReportError('REPORT_REVISION_CONFLICT')


def _operation(repository, archive_root, archive_limits, operation_id):
    try:
        operations = ProjectOperationRepository(
            archive_root,
            repository.stage_root,
            repository.runtime,
            archive_root / 'budget.lock',
            repository.runtime / 'archive.lock',
            archive_limits,
        )
        return operations.current(operation_id)
    except (ArchiveError, RunError):
        raise ReportError('REPORT_REVISION_CONFLICT') from None
