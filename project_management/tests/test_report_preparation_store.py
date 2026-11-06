from types import SimpleNamespace
from uuid import UUID, uuid5

import pytest

from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_contracts import ReportError
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


def preparation_intent(*, meeting_date='2026-11-02',
                       command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009900',
                       created_at='2026-11-02T03:00:00+00:00'):
    project_id = '70000000-0000-4000-8000-000000000001'
    stage_id = '70000000-0000-4000-8000-000000000002'
    series_id = '75000000-0000-4000-8000-000000000001'
    slot_id = str(uuid5(UUID(series_id), f'daily:{meeting_date}'))
    preparation_id = str(uuid5(UUID(stage_id), f'preparation:{slot_id}'))
    operation_command_id = str(uuid5(UUID(preparation_id), 'operation-command'))
    derived_operation_id = run_operation_id(stage_id, operation_command_id)
    draft_command_id = run_draft_command_id(derived_operation_id)
    draft_id = str(uuid5(UUID(stage_id), f'draft:{draft_command_id}'))
    template = {
        'template_id': '76000000-0000-4000-8000-000000000001',
        'revision': 1,
        'revision_hash': 'a' * 64,
        'origin': 'user',
    }
    request = {
        'series_id': series_id,
        'meeting_date': meeting_date,
        'expected_series_policy_hash': 'b' * 64,
        'expected_baseline_ref': None,
        'template_selection': template,
        'source_mode': 'saved_capture',
        'capture_id': '72000000-0000-4000-8000-000000000001',
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
    }
    effective = {
        'series_id': series_id,
        'series_policy_hash': 'b' * 64,
        'meeting_date': meeting_date,
        'meeting_key': f'intel-workweek:7:{meeting_date}',
        'period_key': 'intel-workweek:7:2026:ww45',
        'calendar_id': 'intel-workweek',
        'calendar_revision': 7,
        'timezone': 'Asia/Shanghai',
        'expected_baseline_ref': None,
        'template_selection': template,
        'source_mode': 'saved_capture',
        'capture_id': request['capture_id'],
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
    }
    return {
        'schema_version': 1,
        'preparation_id': preparation_id,
        'slot_id': slot_id,
        'slot_key': {'series_id': series_id, 'local_date': meeting_date},
        'project_id': project_id,
        'stage_id': stage_id,
        'owner_subject': 'archive-owner',
        'command_id': command_id,
        'request_hash': sha256_bytes(canonical_bytes(request)),
        'series_id': series_id,
        'series_policy_hash': request['expected_series_policy_hash'],
        'meeting_date': meeting_date,
        'meeting_key': effective['meeting_key'],
        'period_key': effective['period_key'],
        'timezone': effective['timezone'],
        'expected_baseline_ref': None,
        'template_selection': template,
        'source_mode': 'saved_capture',
        'capture_id': request['capture_id'],
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
        'effective_selection': effective,
        'effective_selection_hash': sha256_bytes(canonical_bytes(effective)),
        'operation_command_id': operation_command_id,
        'derived_operation_id': derived_operation_id,
        'operation_id': None,
        'draft_command_id': draft_command_id,
        'draft_id': draft_id,
        'template_use_command_id': str(uuid5(UUID(preparation_id), 'template-use')),
        'created_at': created_at,
    }


def sync_hashes(intent):
    request = {
        'series_id': intent['series_id'],
        'meeting_date': intent['meeting_date'],
        'expected_series_policy_hash': intent['series_policy_hash'],
        'expected_baseline_ref': intent['expected_baseline_ref'],
        'template_selection': intent['template_selection'],
        'source_mode': intent['source_mode'],
        'capture_id': intent['capture_id'],
        'analysis_mode': intent['analysis_mode'],
        'acknowledge_gap_draft_ids': tuple(intent['acknowledge_gap_draft_ids']),
    }
    return {
        **intent,
        'request_hash': sha256_bytes(canonical_bytes(request)),
        'effective_selection_hash': sha256_bytes(canonical_bytes(intent['effective_selection'])),
    }


def reprepare_intent(parent, *, command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009902',
                     capture_id='72000000-0000-4000-8000-000000009902'):
    preparation_id = str(uuid5(UUID(parent['preparation_id']), f'reprepare:{command_id}'))
    operation_command_id = str(uuid5(UUID(preparation_id), 'operation-command'))
    derived_operation_id = run_operation_id(parent['stage_id'], operation_command_id)
    draft_command_id = run_draft_command_id(derived_operation_id)
    draft_id = str(uuid5(UUID(parent['stage_id']), f'draft:{draft_command_id}'))
    effective = {
        **parent['effective_selection'],
        'capture_id': capture_id,
    }
    value = {
        'schema_version': 3,
        'kind': 'daily_reprepare',
        'preparation_id': preparation_id,
        'slot_id': parent['slot_id'],
        'slot_key': parent['slot_key'],
        'project_id': parent['project_id'],
        'stage_id': parent['stage_id'],
        'owner_subject': parent['owner_subject'],
        'command_id': command_id,
        'request_hash': '',
        'series_id': parent['series_id'],
        'series_policy_hash': parent['series_policy_hash'],
        'meeting_date': parent['meeting_date'],
        'meeting_key': parent['meeting_key'],
        'period_key': parent['period_key'],
        'timezone': parent['timezone'],
        'expected_baseline_ref': parent['expected_baseline_ref'],
        'template_selection': parent['template_selection'],
        'source_mode': 'saved_capture',
        'capture_id': capture_id,
        'analysis_mode': 'manual_only',
        'acknowledge_gap_draft_ids': (),
        'effective_selection': effective,
        'effective_selection_hash': '',
        'operation_command_id': operation_command_id,
        'derived_operation_id': derived_operation_id,
        'operation_id': None,
        'draft_command_id': draft_command_id,
        'draft_id': draft_id,
        'template_use_command_id': str(uuid5(UUID(preparation_id), 'template-use')),
        'created_at': '2026-11-02T03:05:00+00:00',
        'parent_preparation_id': parent['preparation_id'],
        'parent_intent_hash': sha256_bytes(canonical_bytes(parent)),
        'parent_operation_id': parent['derived_operation_id'],
        'expected_parent_operation_revision': 5,
        'expected_parent_operation_state': 'partial',
        'parent_draft_id': parent['draft_id'],
        'expected_parent_draft_revision': 1,
        'expected_parent_draft_revision_hash': 'c' * 64,
        'stage_hash': 'd' * 64,
        'preparation_intent_hash': None,
        'run_request_hash': None,
        'reprepare_intent_hash': '',
    }
    return sync_reprepare_hashes(value)


def sync_reprepare_hashes(value):
    value = {
        **value,
        'request_hash': sha256_bytes(canonical_bytes({
            'kind': 'daily_reprepare',
            'command_id': value['command_id'],
            'parent_preparation_id': value['parent_preparation_id'],
            'parent_intent_hash': value['parent_intent_hash'],
            'parent_operation_id': value['parent_operation_id'],
            'expected_parent_operation_revision': value['expected_parent_operation_revision'],
            'expected_parent_operation_state': value['expected_parent_operation_state'],
            'parent_draft_id': value['parent_draft_id'],
            'expected_parent_draft_revision': value['expected_parent_draft_revision'],
            'expected_parent_draft_revision_hash': value['expected_parent_draft_revision_hash'],
            'series_id': value['series_id'],
            'meeting_date': value['meeting_date'],
            'expected_series_policy_hash': value['series_policy_hash'],
            'expected_baseline_ref': value['expected_baseline_ref'],
            'template_selection': value['template_selection'],
            'source_mode': value['source_mode'],
            'capture_id': None if value['source_mode'] == 'refresh' else value['capture_id'],
            'analysis_mode': value['analysis_mode'],
            'acknowledge_gap_draft_ids': tuple(value['acknowledge_gap_draft_ids']),
        })),
        'effective_selection_hash': sha256_bytes(canonical_bytes(value['effective_selection'])),
    }
    value['reprepare_intent_hash'] = sha256_bytes(canonical_bytes({
        key: item for key, item in value.items()
        if key not in {'preparation_intent_hash', 'run_request_hash', 'reprepare_intent_hash'}
    }))
    return value


def legacy_prepare_subset_hash_for_reprepare(value):
    return sha256_bytes(canonical_bytes({
        'series_id': value['series_id'],
        'meeting_date': value['meeting_date'],
        'expected_series_policy_hash': value['series_policy_hash'],
        'expected_baseline_ref': value['expected_baseline_ref'],
        'template_selection': value['template_selection'],
        'source_mode': value['source_mode'],
        'capture_id': value['capture_id'],
        'analysis_mode': value['analysis_mode'],
        'acknowledge_gap_draft_ids': (),
    }))


def test_should_adopt_intent_only_reservation_and_preserve_original_created_at(tmp_path):
    store = fake_store(tmp_path)
    original = preparation_intent()
    retry = {**original, 'created_at': '2026-11-02T04:00:00+00:00'}
    store.write_intent(original)

    intent, disposition = store.reserve(
        retry['command_id'], retry['request_hash'], retry['slot_id'], retry,
    )

    assert disposition == 'created'
    assert intent['created_at'] == original['created_at']
    assert store.command(original['command_id'])['preparation_id'] == original['preparation_id']
    assert store.slot(original['slot_id'])['intent_hash'] == sha256_bytes(canonical_bytes(original))


def test_should_reject_changed_reprepare_payload_when_adopting_intent_only_replacement(tmp_path):
    store = fake_store(tmp_path)
    parent = preparation_intent()
    replacement = reprepare_intent(parent)
    changed = sync_reprepare_hashes({
        **replacement,
        'expected_parent_operation_revision': replacement['expected_parent_operation_revision'] + 1,
    })
    store.reserve(parent['command_id'], parent['request_hash'], parent['slot_id'], parent)
    store.write_intent(replacement)

    with pytest.raises(ReportError) as error:
        store.reserve_replacement(replacement['command_id'], changed['request_hash'], parent, changed)

    assert error.value.code == 'REPORT_PREPARATION_COMMAND_CONFLICT'
    assert store.command(replacement['command_id']) is None
    assert store.slot(parent['slot_id'])['preparation_id'] == parent['preparation_id']


def test_should_hash_reprepare_request_from_parent_cas_not_standard_prepare_subset(tmp_path):
    parent = preparation_intent()
    original = reprepare_intent(parent)
    changed = sync_reprepare_hashes({
        **original,
        'expected_parent_draft_revision': original['expected_parent_draft_revision'] + 1,
    })

    assert original['request_hash'] != changed['request_hash']
    assert original['request_hash'] != legacy_prepare_subset_hash_for_reprepare(original)


def test_should_replay_original_command_after_two_replacements_without_reclaiming_active_slot(tmp_path):
    store = fake_store(tmp_path)
    original = preparation_intent()
    first = reprepare_intent(original, command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009911')
    second = reprepare_intent(first, command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009912',
                              capture_id='72000000-0000-4000-8000-000000009912')
    store.reserve(original['command_id'], original['request_hash'], original['slot_id'], original)
    store.reserve_replacement(first['command_id'], first['request_hash'], original, first)
    store.reserve_replacement(second['command_id'], second['request_hash'], first, second)

    replay, disposition = store.existing(original['command_id'], original['request_hash'], original['slot_id'])

    assert replay['preparation_id'] == original['preparation_id']
    assert disposition == 'created'
    assert store.slot(original['slot_id'])['preparation_id'] == second['preparation_id']


def test_should_repair_slot_only_replacement_for_exact_replay_and_reject_changed_payload(tmp_path):
    store = fake_store(tmp_path)
    parent = preparation_intent()
    replacement = reprepare_intent(parent)
    changed = sync_reprepare_hashes({
        **replacement,
        'expected_parent_draft_revision': replacement['expected_parent_draft_revision'] + 1,
    })
    store.reserve(parent['command_id'], parent['request_hash'], parent['slot_id'], parent)
    store.write_intent(replacement)
    store.replace_slot(parent, replacement)

    exact, disposition = store.reserve_replacement(replacement['command_id'], replacement['request_hash'], parent, replacement)
    with pytest.raises(ReportError) as error:
        store.reserve_replacement(replacement['command_id'], changed['request_hash'], parent, changed)

    assert disposition == 'created'
    assert exact['preparation_id'] == replacement['preparation_id']
    assert error.value.code == 'REPORT_PREPARATION_COMMAND_CONFLICT'


def test_should_not_repair_missing_slot_to_old_original_after_replacement_chain(tmp_path):
    store = fake_store(tmp_path)
    original = preparation_intent()
    first = reprepare_intent(original, command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009921')
    second = reprepare_intent(first, command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009922',
                              capture_id='72000000-0000-4000-8000-000000009922')
    store.reserve(original['command_id'], original['request_hash'], original['slot_id'], original)
    store.reserve_replacement(first['command_id'], first['request_hash'], original, first)
    store.reserve_replacement(second['command_id'], second['request_hash'], first, second)
    (store.runtime / 'report-preparation-slots' / f"{original['slot_id']}.json").unlink()

    with pytest.raises(ReportError) as error:
        store.existing(original['command_id'], original['request_hash'], original['slot_id'])

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert not (store.runtime / 'report-preparation-slots' / f"{original['slot_id']}.json").exists()


def test_should_reject_slot_without_intent(tmp_path):
    store = fake_store(tmp_path)
    intent = preparation_intent()
    store.write_slot(intent['slot_id'], intent)
    intent_path = store.runtime / 'report-preparations' / intent['preparation_id'] / 'intent.json'
    intent_path.unlink(missing_ok=True)

    with pytest.raises(ReportError) as error:
        store.reserve(intent['command_id'], intent['request_hash'], intent['slot_id'], intent)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_should_reject_tampered_slot_hash_and_unknown_intent_key(tmp_path):
    store = fake_store(tmp_path)
    intent = preparation_intent()
    store.reserve(intent['command_id'], intent['request_hash'], intent['slot_id'], intent)
    slot_path = store.runtime / 'report-preparation-slots' / f"{intent['slot_id']}.json"
    slot = store.slot(intent['slot_id'])
    slot_path.write_bytes(canonical_bytes({**slot, 'intent_hash': '0' * 64}))

    with pytest.raises(ReportError) as bad_slot:
        store.reserve('bbbbbbbb-bbbb-4bbb-8bbb-000000009901', intent['request_hash'], intent['slot_id'], intent)

    slot_path.write_bytes(canonical_bytes(slot))
    intent_path = store.runtime / 'report-preparations' / intent['preparation_id'] / 'intent.json'
    intent_path.write_bytes(canonical_bytes({**intent, 'unexpected': True}))
    with pytest.raises(ReportError) as bad_intent:
        store.reserve('bbbbbbbb-bbbb-4bbb-8bbb-000000009902', intent['request_hash'], intent['slot_id'], intent)

    assert bad_slot.value.code == 'REPORT_ARTIFACT_INVALID'
    assert bad_intent.value.code == 'REPORT_ARTIFACT_INVALID'


def test_should_reject_tampered_command_binding(tmp_path):
    store = fake_store(tmp_path)
    intent = preparation_intent()
    store.reserve(intent['command_id'], intent['request_hash'], intent['slot_id'], intent)
    command_path = store.runtime / 'report-preparation-commands' / f"{intent['command_id']}.json"
    command = store.command(intent['command_id'])
    command_path.write_bytes(canonical_bytes({**command, 'preparation_id': '71000000-0000-4000-8000-000000000999'}))

    with pytest.raises(ReportError) as error:
        store.reserve(intent['command_id'], intent['request_hash'], intent['slot_id'], intent)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_should_reject_existing_command_redirect_to_another_valid_slot(tmp_path):
    store = fake_store(tmp_path)
    first = preparation_intent()
    second = preparation_intent(
        meeting_date='2026-11-03',
        command_id='bbbbbbbb-bbbb-4bbb-8bbb-000000009901',
        created_at='2026-11-03T03:00:00+00:00',
    )
    store.reserve(first['command_id'], first['request_hash'], first['slot_id'], first)
    store.reserve(second['command_id'], second['request_hash'], second['slot_id'], second)
    command_path = store.runtime / 'report-preparation-commands' / f"{second['command_id']}.json"
    command = store.command(second['command_id'])
    command_path.write_bytes(canonical_bytes({**command, 'disposition': 'existing', 'preparation_id': first['preparation_id']}))

    with pytest.raises(ReportError) as error:
        store.reserve(second['command_id'], second['request_hash'], second['slot_id'], second)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_should_reject_nested_intent_shapes_even_when_hashes_are_recomputed(tmp_path):
    store = fake_store(tmp_path)
    valid = preparation_intent()
    cases = []
    cases.append(sync_hashes({**valid, 'template_selection': {**valid['template_selection'], 'extra': True}}))
    cases.append(sync_hashes({**valid, 'template_selection': {**valid['template_selection'], 'origin': 'system'}}))
    cases.append(sync_hashes({**valid, 'expected_baseline_ref': {'publication_id': valid['draft_id'], 'manifest_hash': 'a' * 64}}))
    duplicate_gap = {
        **valid,
        'acknowledge_gap_draft_ids': (valid['draft_id'], valid['draft_id']),
        'effective_selection': {
            **valid['effective_selection'],
            'acknowledge_gap_draft_ids': (valid['draft_id'], valid['draft_id']),
        },
    }
    cases.append(sync_hashes(duplicate_gap))
    mismatched = {
        **valid,
        'effective_selection': {**valid['effective_selection'], 'capture_id': '72000000-0000-4000-8000-000000009999'},
    }
    cases.append(sync_hashes(mismatched))

    for item in cases:
        with pytest.raises(ReportError) as error:
            store.write_intent(item)
        assert error.value.code == 'REPORT_ARTIFACT_INVALID'
