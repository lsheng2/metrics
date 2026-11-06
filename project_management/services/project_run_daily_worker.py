from dataclasses import replace

from project_management.app.domain.capture_values import content_hash
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.run_contracts import ItemRunResult, RunError


def is_daily_manual_request(request):
    target = getattr(request, 'target', None)
    return target is not None and target.source_mode == 'refresh' and target.analysis_mode == 'manual_only'


def record_manual_items(worker, actor, project_id, stage_id, operation, manifest):
    existing = {item.source_key_hash: item for item in operation.item_results}
    results = []
    for identity in manifest.membership.items:
        source_key = worker.run_service.archive._source_key(manifest.intent, identity)
        key_hash = content_hash(source_key)
        results.append(existing.pop(key_hash, ItemRunResult(key_hash, 'pending', error_code='ANALYSIS_MANUAL_ONLY')))
    if existing:
        raise RunError('RUN_STORAGE_INVALID')
    return worker._transition(
        actor,
        project_id,
        stage_id,
        operation.operation_id,
        lambda current: replace(current, item_results=tuple(results), revision=current.revision + 1),
    )


def draft_daily(worker, actor, project_id, stage_id, operation, request):
    if worker.daily_preparation_service is None:
        return worker._partial(actor, project_id, stage_id, operation.operation_id,
                               'RUN_STORAGE_INVALID', operation.item_results)
    try:
        intent, selection, template, ref = worker.daily_preparation_service.prepare_worker_context(
            actor, project_id, stage_id, operation, request,
        )
        worker.daily_preparation_service.validate_active_preparation(actor, project_id, stage_id, request.target)
        payload = _draft_selection_payload(intent, selection, template, ref.context_hash)
        worker.run_service.write_draft_selection(actor, project_id, stage_id, operation.operation_id, payload)
        worker.daily_preparation_service.validate_active_preparation(actor, project_id, stage_id, request.target)
        draft = worker.run_service.draft_service.create_authored(
            actor,
            project_id,
            stage_id,
            command_id=intent['draft_command_id'],
            selection=selection,
            template=template,
            preparation_id=intent['preparation_id'],
        )
        worker.daily_preparation_service.validate_active_preparation(actor, project_id, stage_id, request.target)
    except ReportError as error:
        return worker._partial(actor, project_id, stage_id, operation.operation_id,
                               worker._report_error(error), operation.item_results)
    final_state = 'draft_ready'
    if any(item.state not in {'accepted', 'no_work'} for item in operation.item_results):
        final_state = 'partial'
    return worker._transition(
        actor,
        project_id,
        stage_id,
        operation.operation_id,
        lambda current: replace(
            current,
            state=final_state,
            revision=current.revision + 1,
            draft_id=draft.draft_id,
            draft_revision=draft.revision,
            draft_revision_hash=draft.revision_hash,
            snapshot_hash=draft.snapshot_hash,
            template_hash=draft.template_definition.template_hash,
            error_code=None,
        ),
    )


def _draft_selection_payload(intent, selection, template, context_hash):
    return {
        'schema_version': 2,
        'kind': 'daily_preparation',
        'preparation_id': intent['preparation_id'],
        'context_hash': context_hash,
        'selection': selection,
        'template': template,
        'draft_id': intent['draft_id'],
        'command_id': intent['draft_command_id'],
        'payload_hash': content_hash({
            'preparation_id': intent['preparation_id'],
            'context_hash': context_hash,
            'selection': selection,
            'template': template,
            'draft_id': intent['draft_id'],
            'command_id': intent['draft_command_id'],
        }),
    }
