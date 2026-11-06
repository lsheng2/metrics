from dataclasses import asdict
from uuid import UUID, uuid5

from project_management.app.domain.report_authoring_hashes import (
    authored_create_template_use_request_hash,
    pinned_template_use_hash,
)
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.report_contracts import ReportError, ReportSelection
from project_management.app.domain.report_continuity import PublicationRef
from project_management.app.domain.report_preparation import PreparationResult
from project_management.app.domain.report_preparation_validation import request_payload_from_intent
from project_management.app.domain.run_contracts import DailyRunRequest, DailyRunTarget, RunError
from project_management.app.domain.run_values import capture_id as run_capture_id
from project_management.app.domain.run_values import draft_command_id as run_draft_command_id
from project_management.app.domain.run_values import operation_id as run_operation_id
from project_management.app.domain.run_values import request_hash as run_request_hash
from project_management.app.domain.report_draft_values import validate_uuid_text
from project_management.services.report_continuity_preview import build_baseline_preview_from_repository
from project_management.services.report_preservation import reprepare_parent_draft
from project_management.services.report_historical_references import HistoricalReferenceResolver
from project_management.services.report_reprepare_replay import existing_reprepare_replay
from project_management.services.report_reprepare_parent_cas import verify_parent_cas
from project_management.storage.report_preparations import ReportPreparationStore


def preparation_runtime_options(service):
    run = service.run_service
    refresh = run is not None and callable(run.notifier)
    analysis = None if run is None else run.analysis_service
    available = refresh and callable(getattr(run, 'backend_resolver', None))
    available = available and all(callable(getattr(analysis, name, None)) for name in ('prepare', 'advance', 'cancel'))
    return {'refresh': bool(refresh), 'analysis': bool(available)}


def require_preparation_runtime(service, request):
    if request['source_mode'] != 'refresh':
        return
    options = preparation_runtime_options(service)
    if not options['refresh']:
        raise RunError('RUN_UNAVAILABLE')
    if request['analysis_mode'] == 'changed_items' and not options['analysis']:
        raise ReportError('REPORT_AI_UNAVAILABLE')


def prepare_worker_context(service, actor, project_id, stage_id, operation, request):
    target = getattr(request, 'target', None)
    if target is None or target.source_mode != 'refresh':
        raise ReportError('REPORT_INVALID')
    intent = stored_intent(service, actor, project_id, stage_id, target.preparation_id)
    if (
        intent['preparation_intent_hash'] != target.preparation_intent_hash
        or intent['effective_selection_hash'] != target.effective_selection_hash
        or intent['run_request_hash'] != run_request_hash(request)
        or intent['draft_id'] != target.draft_id
        or intent['derived_operation_id'] != operation.operation_id
        or intent['operation_id'] != operation.operation_id
        or intent['capture_id'] != operation.capture_id
        or intent['analysis_mode'] != target.analysis_mode
    ):
        raise ReportError('REPORT_REVISION_CONFLICT')
    validate_active_preparation(service, actor, project_id, stage_id, target)
    selection = ReportSelection(operation.capture_id, None, None, 'standup', intent['timezone'])
    template = service._template_from_intent(intent)
    parent_draft = reprepare_parent_draft(service.draft_service, actor, project_id, stage_id, intent)
    pinned = service.template_service.use(
        actor,
        project_id,
        command_id=intent['template_use_command_id'],
        draft_id=intent['draft_id'],
        request_hash=authored_create_template_use_request_hash(selection, template, intent['preparation_id']),
        selection=template,
        use_mode='continuity_prepare',
    )
    ref = service.continuity.prepare_context(
        actor,
        project_id,
        stage_id,
        preparation_id=intent['preparation_id'],
        create_command_id=intent['draft_command_id'],
        series_id=intent['series_id'],
        series_policy_hash=intent['series_policy_hash'],
        meeting_date=intent['meeting_date'],
        expected_baseline_ref=service._baseline_ref(intent['expected_baseline_ref']),
        selection=selection,
        template_use_hash=pinned_template_use_hash(pinned),
        acknowledge_gap_draft_ids=tuple(intent['acknowledge_gap_draft_ids']),
        authority=_authority_from_intent(service, intent),
        preservation_parent_draft=parent_draft,
        historical_reference_resolver=HistoricalReferenceResolver(service.draft_service, actor, project_id, stage_id),
    )
    return intent, selection, template, ref


def validate_active_preparation(service, actor, project_id, stage_id, target):
    intent = stored_intent(service, actor, project_id, stage_id, target.preparation_id)
    if (
            intent['preparation_id'] != target.preparation_id
            or intent.get('preparation_intent_hash') != target.preparation_intent_hash
            or intent['effective_selection_hash'] != target.effective_selection_hash
            or intent['draft_id'] != target.draft_id):
        raise ReportError('REPORT_REVISION_CONFLICT')
    with service.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
        store = ReportPreparationStore(repository, service.archive.config.root, service.archive.config.limits)
        slot = store.slot(intent['slot_id'])
        if (slot is None
                or slot['preparation_id'] != intent['preparation_id']
                or slot['intent_hash'] != service._hash(intent)):
            raise ReportError('REPORT_REVISION_CONFLICT')
    return intent


def reprepare(service, actor, project_id, stage_id, *, command_id, preparation_id,
              expected_operation_revision, expected_draft_revision,
              expected_draft_revision_hash, expected_baseline_ref, template_selection,
              source_mode, capture_id, analysis_mode):
    intent = stored_intent(service, actor, project_id, stage_id, preparation_id)
    replay = existing_reprepare_replay(
        service, actor, project_id, stage_id, command_id, intent,
        expected_operation_revision, expected_draft_revision, expected_draft_revision_hash,
        expected_baseline_ref, template_selection, source_mode, capture_id, analysis_mode,
    )
    if replay is not None:
        return replay
    if service._baseline_payload(expected_baseline_ref) != intent['expected_baseline_ref']:
        raise ReportError('REPORT_BASELINE_CONFLICT')
    if intent['operation_id'] is None:
        if expected_operation_revision is not None:
            raise ReportError('REPORT_REVISION_CONFLICT')
        operation = None
    else:
        if service.run_service is None:
            raise ReportError('REPORT_INVALID')
        operation = service.run_service.get(actor, project_id, stage_id, intent['operation_id'])
        if operation.revision != expected_operation_revision:
            raise ReportError('REPORT_REVISION_CONFLICT')
        if operation.state not in {'draft_ready', 'partial', 'canceled', 'failed'}:
            raise ReportError('REPORT_REVISION_CONFLICT')
    if operation is not None and operation.draft_id is None:
        if expected_draft_revision is not None or expected_draft_revision_hash is not None:
            raise ReportError('REPORT_REVISION_CONFLICT')
        draft = None
    else:
        draft = service.draft_service.get(actor, project_id, stage_id, intent['draft_id'])
    if draft is not None and (draft.revision != expected_draft_revision or draft.revision_hash != expected_draft_revision_hash):
        raise ReportError('REPORT_REVISION_CONFLICT')
    status = None if draft is None else service.draft_service.finalization_status(actor, project_id, stage_id, draft.draft_id)
    if status is not None and status.state == 'finalizing':
        raise ReportError('REPORT_FINALIZING')
    if status is None:
        return _reprepare_unfinalized(
            service, actor, project_id, stage_id, command_id, intent, operation, draft,
            expected_baseline_ref, template_selection, source_mode, capture_id, analysis_mode,
        )
    if status.state != 'finalized':
        raise ReportError('REPORT_INVALID')
    if (source_mode != 'saved_capture' or analysis_mode != 'manual_only'
            or capture_id != intent['capture_id']
            or asdict(template_selection) != intent['template_selection']):
        raise ReportError('REPORT_FINALIZED')
    publication = service.draft_service.get_publication(actor, project_id, stage_id, status.publication_id)
    linked = service.draft_service.create_linked_revision(
        actor,
        project_id,
        stage_id,
        command_id=command_id,
        publication_ref=PublicationRef(
            publication.manifest.publication_id,
            publication.manifest_sha256,
            publication.commit_id,
        ),
    )
    return PreparationResult(
        'created',
        intent['preparation_id'],
        None if operation is None else operation.operation_id,
        linked.draft_id,
        linked.revision,
        None,
        service._public_selection(intent['effective_selection']),
        (),
        linked.state,
        service.link_builder.links(project_id, stage_id, linked.draft_id, None),
        linked.preservation_review_issues,
    )


def _authority_from_intent(service, intent):
    return {
        'schema_version': 1,
        'kind': 'daily_preparation_active_slot',
        'preparation_id': intent['preparation_id'],
        'preparation_intent_hash': intent.get('preparation_intent_hash') or intent.get('reprepare_intent_hash') or service._hash(intent),
        'slot_id': intent['slot_id'],
        'slot_key': intent['slot_key'],
        'draft_id': intent['draft_id'],
        'create_command_id': intent['draft_command_id'],
        'series_id': intent['series_id'],
        'meeting_date': intent['meeting_date'],
    }


def _reprepare_unfinalized(service, actor, project_id, stage_id, command_id, parent, operation, draft,
                           expected_baseline_ref, template_selection, source_mode, capture_id, analysis_mode):
    request = service._request(
        command_id,
        parent['series_id'],
        parent['meeting_date'],
        parent['series_policy_hash'],
        expected_baseline_ref,
        template_selection,
        source_mode,
        capture_id,
        analysis_mode,
        tuple(parent['acknowledge_gap_draft_ids']),
    )
    require_preparation_runtime(service, request)
    _, stage, policy = service.continuity._read_policy_for_prepare(
        actor, project_id, stage_id, request['series_id'], request['expected_series_policy_hash'],
    )
    preview = service.continuity.preview(
        actor, project_id, stage_id, series_id=request['series_id'],
        meeting_date=request['meeting_date'], template_selection=request['template_selection'],
    )
    service._validate_preview(preview, request)
    ids = derived_ids(stage.id, request['slot_id']) if request['source_mode'] == 'refresh' else None
    capture_id = request['capture_id'] if request['source_mode'] == 'saved_capture' else ids['capture_id']
    selection = ReportSelection(capture_id=capture_id, timezone=policy.calendar.timezone)
    if request['source_mode'] == 'saved_capture':
        service._validate_saved_capture(actor, project_id, stage_id, selection)
    effective = service._effective_selection(request, preview, policy, request['capture_id'])
    effective = {**effective, 'capture_id': capture_id}
    replacement = _replacement_intent(
        service, actor, project_id, stage.id, stage.definition_hash, request, preview, effective, selection,
        parent, operation, draft,
    )
    try:
        with service.archive._report_repository(actor, project_id, stage_id, write=True) as repository:
            locked = build_baseline_preview_from_repository(service.archive, repository, policy, request['meeting_date'])
            service._validate_preview(locked, request)
            store = ReportPreparationStore(repository, service.archive.config.root, service.archive.config.limits)
            verify_parent_cas(repository, service.archive.config.root, service.archive.config.limits, service.draft_service.limits, replacement)
            stored, disposition = store.reserve_replacement(request['command_id'], replacement['request_hash'], parent, replacement)
    except ArchiveError as error:
        raise service.draft_service._report_error(error) from None
    return service._compose_or_result(actor, project_id, stage_id, stored, disposition, request)


def _replacement_intent(service, actor, project_id, stage_id, stage_hash, request, preview, effective, selection,
                        parent, operation, draft):
    preparation_id = str(uuid5(UUID(parent['preparation_id']), f"reprepare:{request['command_id']}"))
    operation_command_id = str(uuid5(UUID(preparation_id), 'operation-command'))
    derived_operation_id = run_operation_id(validate_uuid_text(str(stage_id)), operation_command_id)
    replacement_capture_id = run_capture_id(derived_operation_id) if request['source_mode'] == 'refresh' else selection.capture_id
    draft_command_id = run_draft_command_id(derived_operation_id)
    draft_id = str(uuid5(UUID(validate_uuid_text(str(stage_id))), f'draft:{draft_command_id}'))
    public_selection = service._public_selection({**effective, 'capture_id': replacement_capture_id})
    intent = {
        'schema_version': 3,
        'kind': 'daily_reprepare',
        'preparation_id': preparation_id,
        'slot_id': request['slot_id'],
        'slot_key': {'series_id': request['series_id'], 'local_date': request['meeting_date']},
        'project_id': validate_uuid_text(str(project_id)),
        'stage_id': validate_uuid_text(str(stage_id)),
        'owner_subject': actor.subject,
        'command_id': request['command_id'],
        'request_hash': '',
        'series_id': request['series_id'],
        'series_policy_hash': request['expected_series_policy_hash'],
        'meeting_date': request['meeting_date'],
        'meeting_key': preview.meeting_key,
        'period_key': preview.period_key,
        'timezone': selection.timezone,
        'expected_baseline_ref': service._baseline_payload(preview.baseline_ref),
        'template_selection': asdict(effective['template_selection']),
        'source_mode': request['source_mode'],
        'capture_id': replacement_capture_id,
        'analysis_mode': request['analysis_mode'],
        'acknowledge_gap_draft_ids': tuple(effective['acknowledge_gap_draft_ids']),
        'effective_selection': public_selection,
        'effective_selection_hash': service._hash(public_selection),
        'operation_command_id': operation_command_id,
        'derived_operation_id': derived_operation_id,
        'operation_id': None if request['source_mode'] == 'saved_capture' else derived_operation_id,
        'draft_command_id': draft_command_id,
        'draft_id': draft_id,
        'template_use_command_id': str(uuid5(UUID(preparation_id), 'template-use')),
        'created_at': service.continuity._now(),
        'parent_preparation_id': parent['preparation_id'],
        'parent_intent_hash': service._hash(parent),
        'parent_operation_id': None if operation is None else operation.operation_id,
        'expected_parent_operation_revision': None if operation is None else operation.revision,
        'expected_parent_operation_state': None if operation is None else operation.state,
        'parent_draft_id': None if draft is None else draft.draft_id,
        'expected_parent_draft_revision': None if draft is None else draft.revision,
        'expected_parent_draft_revision_hash': None if draft is None else draft.revision_hash,
        'stage_hash': stage_hash,
        'preparation_intent_hash': None,
        'run_request_hash': None,
        'reprepare_intent_hash': '',
    }
    intent['request_hash'] = service._hash(request_payload_from_intent(intent))
    if request['source_mode'] == 'refresh':
        intent['preparation_intent_hash'] = service._hash({
            key: item for key, item in intent.items()
            if key not in {'preparation_intent_hash', 'run_request_hash', 'reprepare_intent_hash'}
        })
        intent['run_request_hash'] = run_request_hash(daily_run_request(service, intent))
    intent['reprepare_intent_hash'] = service._hash({
        key: item for key, item in intent.items()
        if key not in {'preparation_intent_hash', 'run_request_hash', 'reprepare_intent_hash'}
    })
    return intent


def stored_intent(service, actor, project_id, stage_id, preparation_id):
    with service.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
        return ReportPreparationStore(repository, service.archive.config.root, service.archive.config.limits).intent(preparation_id)


def derived_ids(stage_id, slot_id):
    preparation_id = str(uuid5(UUID(validate_uuid_text(str(stage_id))), f"preparation:{slot_id}"))
    operation_command_id = str(uuid5(UUID(preparation_id), 'operation-command'))
    operation_id = run_operation_id(validate_uuid_text(str(stage_id)), operation_command_id)
    return {
        'operation_command_id': operation_command_id,
        'operation_id': operation_id,
        'capture_id': run_capture_id(operation_id),
    }


def original_request_payload(service, request):
    return {
        'series_id': request['series_id'],
        'meeting_date': request['meeting_date'],
        'expected_series_policy_hash': request['expected_series_policy_hash'],
        'expected_baseline_ref': service._baseline_payload(request['expected_baseline_ref']),
        'template_selection': asdict(request['template_selection']),
        'source_mode': request['source_mode'],
        'capture_id': request['capture_id'],
        'analysis_mode': request['analysis_mode'],
        'acknowledge_gap_draft_ids': tuple(request['acknowledge_gap_draft_ids']),
    }


def daily_run_request(service, intent):
    return DailyRunRequest(
        intent['operation_command_id'],
        intent['stage_hash'],
        service._template_from_intent(intent),
        intent['timezone'],
        DailyRunTarget(
            intent['preparation_id'],
            intent['preparation_intent_hash'],
            intent['draft_id'],
            intent['effective_selection_hash'],
            'refresh',
            intent['analysis_mode'],
        ),
    )
