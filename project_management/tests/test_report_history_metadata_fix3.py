from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.app.domain.report_authoring_fragments import plain_text_fragment
from project_management.app.domain.report_continuity import PublicationRef
from project_management.app.domain.report_continuity_context import validate_daily_authoring_context
from project_management.tests.test_report_history_composer_fix2 import context, snapshot


BASE_REF = PublicationRef('71000000-0000-4000-8000-000000000001', '1' * 64, '2' * 40)


def persistent(note_id, carry_forward):
    fragment = plain_text_fragment('persistent note')
    return {
        'note_id': note_id,
        'target': 'issue',
        'issue_ref': None,
        'fragment': fragment,
        'revision': 1,
        'carry_forward': carry_forward,
        'provenance': {'origin': 'human'},
    }


def test_should_retain_only_carryforward_persistent_note_refs_and_reject_dangling_refs():
    source = snapshot()
    day1 = context(source, '2026-11-02')
    keep = persistent('10000000-0000-4000-8000-000000000001', True)
    drop = persistent('10000000-0000-4000-8000-000000000002', False)
    old_week = dict(day1, persistent_notes=(keep, drop))

    new_week = context(source, '2026-11-09', old_week, publication=BASE_REF)
    broken = dict(new_week, weekly_seed=dict(
        new_week['weekly_seed'],
        persistent_note_refs=(keep['note_id'], drop['note_id']),
    ))

    assert [note['note_id'] for note in new_week['persistent_notes']] == [keep['note_id']]
    assert new_week['weekly_seed']['persistent_note_refs'] == [keep['note_id']]
    validate_daily_authoring_context(new_week)
    try:
        validate_daily_authoring_context(broken)
    except report_api.ReportError as error:
        assert error.code == 'REPORT_ARTIFACT_INVALID'
    else:
        raise AssertionError('dangling persistent_note_refs accepted')


def test_should_preserve_earlier_refs_after_rollover_and_keep_seed_identity_same_period():
    source = snapshot()
    old_week = context(source, '2026-11-02')
    new_day1 = context(source, '2026-11-09', old_week, publication=BASE_REF)
    new_day2 = context(source, '2026-11-10', new_day1)

    assert old_week['weekly_seed']['note_refs'] == []
    assert new_day1['weekly_seed']['earlier_period_refs'] == [{
        'publication_id': BASE_REF.publication_id,
        'manifest_hash': BASE_REF.manifest_hash,
        'commit': BASE_REF.commit,
    }]
    assert new_day2['weekly_seed']['earlier_period_refs'] == new_day1['weekly_seed']['earlier_period_refs']
    assert new_day2['weekly_seed']['baseline'] == new_day1['weekly_seed']['baseline']
    assert new_day2['weekly_seed']['note_refs'] == new_day1['weekly_seed']['note_refs']
    validate_daily_authoring_context(new_day1)
    validate_daily_authoring_context(new_day2)
