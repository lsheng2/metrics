from datetime import date
from uuid import UUID, uuid5

from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.contracts import ProjectError
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.report_draft_values import validate_uuid_text
from project_management.app.domain.report_preparation import PreparationDetails, PreparationResult
from project_management.app.domain.run_contracts import RunError
from project_management.storage.report_preparations import ReportPreparationStore


def preparation_for_meeting(service, actor, project_id, stage_id, series_id, meeting_date, *, _read_view=None):
    series_id = validate_uuid_text(series_id)
    try:
        if type(meeting_date) is not str or date.fromisoformat(meeting_date).isoformat() != meeting_date:
            raise ValueError
    except ValueError:
        raise ReportError('REPORT_INVALID') from None
    slot_id = str(uuid5(UUID(series_id), f'daily:{meeting_date}'))
    try:
        scope = (service.archive._report_read_view(actor, project_id, stage_id, allow_absent=True) if _read_view is None
                 else service.archive._report_repository(actor, project_id, stage_id, _read_view=_read_view))
        with scope as repository:
            if repository is None:
                return None
            intent = _store(service, repository).active_intent(slot_id)
            if intent is None:
                return None
            return get_preparation(service, actor, project_id, stage_id, intent['preparation_id'], _read_view=repository)
    except (ArchiveError, ProjectError) as error:
        raise service.draft_service._report_error(error, missing_as_not_found=True) from None


def get_preparation(service, actor, project_id, stage_id, preparation_id, *, _read_view=None):
    preparation_id = validate_uuid_text(preparation_id)
    try:
        with service.archive._report_repository(actor, project_id, stage_id, write=False, _read_view=_read_view) as repository:
            store = _store(service, repository)
            intent = store.find_intent(preparation_id)
            if intent is None:
                raise ReportError('REPORT_NOT_FOUND')
            active = store.active_intent(intent['slot_id'])
            operation = _operation(service, actor, project_id, stage_id, intent, repository)
            draft = _draft(service, actor, project_id, stage_id, intent, operation, repository)
            return _details(service, actor, project_id, stage_id, intent, active, operation, draft, repository)
    except (ArchiveError, ProjectError) as error:
        raise service.draft_service._report_error(error, missing_as_not_found=True) from None


def _store(service, repository):
    return ReportPreparationStore(repository, service.archive.config.root, service.archive.config.limits)


def _operation(service, actor, project_id, stage_id, intent, repository):
    if intent['operation_id'] is None:
        return None
    try:
        store = service.archive._project_operation_store(repository)
        operation = store.current(intent['operation_id'])
    except RunError as error:
        if error.code == 'RUN_NOT_FOUND':
            return None
        raise
    if operation.actor_subject != actor.subject:
        raise ReportError('REPORT_NOT_FOUND')
    return operation


def _draft(service, actor, project_id, stage_id, intent, operation, repository):
    try:
        return service.draft_service.get(actor, project_id, stage_id, intent['draft_id'], _read_view=repository)
    except ReportError as error:
        if error.code != 'REPORT_NOT_FOUND':
            raise
        if operation is not None and operation.draft_revision is not None:
            raise ReportError('REPORT_ARTIFACT_INVALID') from None
        return None


def _details(service, actor, project_id, stage_id, intent, active, operation, draft, repository):
    publication, links = ((None, {}) if draft is None else
                          service._links(actor, project_id, stage_id, draft, _read_view=repository))
    state = operation.state if operation is not None else 'prepared'
    if draft is not None and (operation is None or draft.state != 'draft'):
        state = draft.state
    result = PreparationResult(
        'existing', intent['preparation_id'], None if operation is None else operation.operation_id,
        None if draft is None else draft.draft_id, None if draft is None else draft.revision,
        publication, service._public_selection(intent['effective_selection']), (), state, links,
        () if draft is None else draft.preservation_review_issues,
    )
    return PreparationDetails(
        result,
        None if operation is None else operation.revision,
        None if draft is None else draft.revision_hash,
        None if active is None else active['preparation_id'],
        intent.get('parent_preparation_id'),
    )
