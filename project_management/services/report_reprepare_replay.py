from dataclasses import asdict

from project_management.app.domain.report_contracts import ReportError
from project_management.storage.report_preparations import ReportPreparationStore


def existing_reprepare_replay(service, actor, project_id, stage_id, command_id, parent,
                              expected_operation_revision, expected_draft_revision,
                              expected_draft_revision_hash, expected_baseline_ref,
                              template_selection, source_mode, capture_id, analysis_mode):
    with service.archive._report_repository(actor, project_id, stage_id, write=False) as repository:
        store = ReportPreparationStore(repository, service.archive.config.root, service.archive.config.limits)
        command = store.command(command_id)
        if command is None:
            return None
        replacement = store.intent(command['preparation_id'])
        _verify_call(
            service, command, replacement, parent, expected_operation_revision,
            expected_draft_revision, expected_draft_revision_hash, expected_baseline_ref,
            template_selection, source_mode, capture_id, analysis_mode,
        )
    return _result(service, actor, project_id, stage_id, replacement, command['disposition'])


def _verify_call(service, command, replacement, parent, expected_operation_revision,
                 expected_draft_revision, expected_draft_revision_hash, expected_baseline_ref,
                 template_selection, source_mode, capture_id, analysis_mode):
    if command['request_hash'] != replacement['request_hash']:
        raise ReportError('REPORT_ARTIFACT_INVALID')
    expected = {
        'parent_preparation_id': parent['preparation_id'],
        'parent_intent_hash': service._hash(parent),
        'expected_parent_operation_revision': expected_operation_revision,
        'parent_draft_id': None if expected_draft_revision is None else parent['draft_id'],
        'expected_parent_draft_revision': expected_draft_revision,
        'expected_parent_draft_revision_hash': expected_draft_revision_hash,
        'expected_baseline_ref': service._baseline_payload(expected_baseline_ref),
        'template_selection': asdict(template_selection),
        'source_mode': source_mode,
        'capture_id': None if source_mode == 'refresh' else capture_id,
        'analysis_mode': analysis_mode,
    }
    actual = {
        'parent_preparation_id': replacement['parent_preparation_id'],
        'parent_intent_hash': replacement['parent_intent_hash'],
        'expected_parent_operation_revision': replacement['expected_parent_operation_revision'],
        'parent_draft_id': replacement['parent_draft_id'],
        'expected_parent_draft_revision': replacement['expected_parent_draft_revision'],
        'expected_parent_draft_revision_hash': replacement['expected_parent_draft_revision_hash'],
        'expected_baseline_ref': replacement['expected_baseline_ref'],
        'template_selection': replacement['template_selection'],
        'source_mode': replacement['source_mode'],
        'capture_id': None if replacement['source_mode'] == 'refresh' else replacement['capture_id'],
        'analysis_mode': replacement['analysis_mode'],
    }
    if actual != expected:
        raise ReportError('REPORT_PREPARATION_COMMAND_CONFLICT')


def _result(service, actor, project_id, stage_id, intent, disposition):
    if intent['source_mode'] == 'refresh':
        return service._operation_result(actor, project_id, stage_id, intent, disposition, {'source_mode': 'refresh'})
    return service._draft_result(actor, project_id, stage_id, intent, disposition, {
        'template_selection': service._template_from_intent(intent),
        'source_mode': intent['source_mode'],
        'capture_id': intent['capture_id'],
        'analysis_mode': intent['analysis_mode'],
        'expected_baseline_ref': service._baseline_ref(intent['expected_baseline_ref']),
        'expected_series_policy_hash': intent['series_policy_hash'],
    })
