from types import SimpleNamespace
from uuid import UUID, uuid5

import pytest

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_contracts import ReportError
from project_management.app.domain.run_values import capture_id as run_capture_id
from project_management.app.domain.run_values import draft_command_id as run_draft_command_id
from project_management.app.domain.run_values import operation_id as run_operation_id
from project_management.storage.report_preparations import ReportPreparationStore
from project_management.tests.history_persistence_fixtures import archive_limits


def fake_store(tmp_path):
    project = SimpleNamespace(id='70000000-0000-4000-8000-000000000001')
    stage = SimpleNamespace(id='70000000-0000-4000-8000-000000000002')
    repository = SimpleNamespace(
        project=project,
        stage=stage,
        owner_subject='archive-owner',
        runtime=tmp_path / 'runtime',
        stage_root=tmp_path,
    )
    repository.runtime.mkdir()
    return ReportPreparationStore(repository, tmp_path, archive_limits())


def v2_intent():
    project_id = '70000000-0000-4000-8000-000000000001'
    stage_id = '70000000-0000-4000-8000-000000000002'
    series_id = '75000000-0000-4000-8000-000000000001'
    meeting_date = '2026-11-02'
    slot_id = str(uuid5(UUID(series_id), f'daily:{meeting_date}'))
    preparation_id = str(uuid5(UUID(stage_id), f'preparation:{slot_id}'))
    operation_command_id = str(uuid5(UUID(preparation_id), 'operation-command'))
    operation_id = run_operation_id(stage_id, operation_command_id)
    capture_id = run_capture_id(operation_id)
    draft_command_id = run_draft_command_id(operation_id)
    template = {'template_id': '76000000-0000-4000-8000-000000000001', 'revision': 1, 'revision_hash': 'a' * 64, 'origin': 'user'}
    original = {
        'series_id': series_id,
        'meeting_date': meeting_date,
        'expected_series_policy_hash': 'b' * 64,
        'expected_baseline_ref': None,
        'template_selection': template,
        'source_mode': 'refresh',
        'capture_id': None,
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
    }
    effective = {
        'series_id': series_id,
        'series_policy_hash': original['expected_series_policy_hash'],
        'meeting_date': meeting_date,
        'meeting_key': f'intel-workweek:7:{meeting_date}',
        'period_key': 'intel-workweek:7:2026:ww45',
        'calendar_id': 'intel-workweek',
        'calendar_revision': 7,
        'timezone': 'Asia/Shanghai',
        'expected_baseline_ref': None,
        'template_selection': template,
        'source_mode': 'refresh',
        'capture_id': capture_id,
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
    }
    return sync_v2({
        'schema_version': 2,
        'preparation_id': preparation_id,
        'slot_id': slot_id,
        'slot_key': {'series_id': series_id, 'local_date': meeting_date},
        'project_id': project_id,
        'stage_id': stage_id,
        'owner_subject': 'archive-owner',
        'command_id': 'bbbbbbbb-bbbb-4bbb-8bbb-000000009900',
        'request_hash': '',
        'original_request': original,
        'preparation_intent_hash': '',
        'run_request_hash': 'c' * 64,
        'series_id': series_id,
        'series_policy_hash': original['expected_series_policy_hash'],
        'meeting_date': meeting_date,
        'meeting_key': effective['meeting_key'],
        'period_key': effective['period_key'],
        'timezone': effective['timezone'],
        'expected_baseline_ref': None,
        'template_selection': template,
        'source_mode': 'refresh',
        'capture_id': capture_id,
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
        'effective_selection': effective,
        'effective_selection_hash': '',
        'operation_command_id': operation_command_id,
        'derived_operation_id': operation_id,
        'operation_id': operation_id,
        'draft_command_id': draft_command_id,
        'draft_id': str(uuid5(UUID(stage_id), f'draft:{draft_command_id}')),
        'template_use_command_id': str(uuid5(UUID(preparation_id), 'template-use')),
        'stage_hash': 'd' * 64,
        'created_at': '2026-11-02T03:00:00+00:00',
    })


def sync_v2(intent):
    value = {
        **intent,
        'request_hash': sha256_bytes(canonical_bytes(intent['original_request'])),
        'effective_selection_hash': sha256_bytes(canonical_bytes(intent['effective_selection'])),
    }
    value['preparation_intent_hash'] = sha256_bytes(canonical_bytes({
        key: item for key, item in value.items()
        if key not in {'preparation_intent_hash', 'run_request_hash'}
    }))
    return value


@pytest.mark.parametrize('mutator', [
    lambda intent: intent['original_request'].__setitem__('series_id', '75000000-0000-4000-8000-000000000099'),
    lambda intent: intent['original_request'].__setitem__('meeting_date', '2026-11-03'),
    lambda intent: intent['original_request'].__setitem__('expected_series_policy_hash', '9' * 64),
    lambda intent: intent['original_request'].__setitem__('expected_baseline_ref', {'publication_id': intent['draft_id'], 'manifest_hash': 'a' * 64, 'commit': 'b' * 40}),
    lambda intent: intent['original_request'].__setitem__('template_selection', {**intent['template_selection'], 'revision': 2}),
    lambda intent: intent['original_request'].__setitem__('acknowledge_gap_draft_ids', (intent['draft_id'],)),
    lambda intent: intent['original_request'].__setitem__('analysis_mode', 'changed_items'),
])
def test_should_reject_v2_original_request_that_hashes_but_does_not_match_effective_intent(tmp_path, mutator):
    intent = v2_intent()
    mutator(intent)
    intent = sync_v2(intent)

    with pytest.raises(ReportError) as error:
        fake_store(tmp_path).write_intent(intent)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
