from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.tests.history_persistence_fixtures import (
    continuity_document,
    daily_note_edit,
    daily_note_reference_edit,
    history_fixture,
    note_by_id,
    plain_fragment,
    prepare_daily,
    reference_observation,
    slot_fill_edit,
)
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_should_allow_repeated_full_active_daily_note_save_without_revising_note_again(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(fixture.actor, fixture.project.id, fixture.stage.id, command_id=day1.command_id, selection=day1.selection, template=fixture.template_selection, preparation_id=day1.preparation_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    original = note_by_id(draft.authoring_context, note_id)
    edit = daily_note_edit(9, note_id, 'Repeated full active edit.', '#ff0000', original['body_hash'])
    first = fixture.draft_service.save_authored(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id, command_id=draft_command(8410), expected_revision=draft.revision, expected_revision_hash=draft.revision_hash, edits=(edit,))
    second = fixture.draft_service.save_authored(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id, command_id=draft_command(8411), expected_revision=first.revision, expected_revision_hash=first.revision_hash, edits=(edit,))

    assert note_by_id(second.authoring_context, note_id)['revision'] == note_by_id(first.authoring_context, note_id)['revision']
    assert note_by_id(second.authoring_context, note_id)['body_hash'] == note_by_id(first.authoring_context, note_id)['body_hash']


@pytest.mark.django_db(transaction=True)
def test_should_save_daily_note_and_required_slot_together_then_finalize(tmp_path):
    fixture = history_fixture(tmp_path, document=continuity_document(required_slot=True))
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(fixture.actor, fixture.project.id, fixture.stage.id, command_id=day1.command_id, selection=day1.selection, template=fixture.template_selection, preparation_id=day1.preparation_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    original = note_by_id(draft.authoring_context, note_id)
    saved = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(8420), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(daily_note_edit(10, note_id, 'Daily text with required slot.', '#ff0000', original['body_hash']), slot_fill_edit(11, '40000000-0000-4000-8000-000000000001', 'Required slot filled.')),
    )

    publication = fixture.draft_service.finalize_and_commit(fixture.actor, fixture.project.id, fixture.stage.id, saved.draft_id, command_id=draft_command(8421), expected_revision=saved.revision)
    assert publication.manifest.report_role == 'daily'


@pytest.mark.django_db(transaction=True)
def test_should_save_daily_note_reference_receipt_and_reuse_observation(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(fixture.actor, fixture.project.id, fixture.stage.id, command_id=day1.command_id, selection=day1.selection, template=fixture.template_selection, preparation_id=day1.preparation_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    original = note_by_id(draft.authoring_context, note_id)
    option = verifier.issue_option(fixture.actor, fixture.project.id, fixture.stage.id, draft, {'scope': 'daily_note', 'note_id': note_id}, 'id', reference_observation(draft), membership_proof_hash='b' * 64, principal_id='principal:archive-owner')
    edit = daily_note_reference_edit(12, note_id, option, original['body_hash'])
    saved = fixture.draft_service.save_authored(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id, command_id=draft_command(8430), expected_revision=draft.revision, expected_revision_hash=draft.revision_hash, edits=(edit,))
    reused = fixture.draft_service.save_authored(fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id, command_id=draft_command(8431), expected_revision=saved.revision, expected_revision_hash=saved.revision_hash, edits=(replace(edit, reference_receipts=()),))

    assert saved.authored_edits[0].reference_observations[0]['reference_id'] == option.reference_id
    assert reused.authored_edits[0].reference_observations == saved.authored_edits[0].reference_observations


@pytest.mark.django_db(transaction=True)
def test_should_apply_persistent_note_action_tracking_and_row_move_in_one_save(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(fixture.actor, fixture.project.id, fixture.stage.id, command_id=day1.command_id, selection=day1.selection, template=fixture.template_selection, preparation_id=day1.preparation_id)
    first_row = draft.authoring_context['row_order']['rows'][0]
    second_row = draft.authoring_context['row_order']['rows'][1]
    action_id = draft.authoring_context['actions'][0]['action_id']
    persistent_id = '76000000-0000-4000-8000-000000000001'
    saved = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(8440), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash, edits=(),
        continuity_changes=(
            {'kind': 'add_persistent_note', 'note_id': persistent_id, 'target': 'issue', 'issue_ref': first_row['issue_ref'], 'fragment': plain_fragment('Carry this context.'), 'carry_forward': True},
            {'kind': 'set_action_tracking', 'action_id': action_id, 'expected_state': 'open', 'state': 'done', 'resolution': plain_fragment('Resolved in validation.'), 'evidence_refs': ('EV-101-A',)},
            {'kind': 'move_row', 'issue_ref': second_row['issue_ref'], 'group_id': second_row['group_id'], 'after_issue_ref': None},
        ),
    )

    assert saved.authoring_context['persistent_notes'][0]['note_id'] == persistent_id
    assert saved.authoring_context['actions'][0]['tracking_state'] == 'done'
    assert saved.authoring_context['actions'][0]['resolution']['resolved_by'] == fixture.actor.subject
    assert saved.authoring_context['row_order']['rows'][0]['issue_ref'] == second_row['issue_ref']


@pytest.mark.django_db(transaction=True)
def test_should_bind_continuity_changes_into_save_command_hash(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day1.command_id, selection=day1.selection,
        template=fixture.template_selection, preparation_id=day1.preparation_id,
    )
    note_id = '76000000-0000-4000-8000-000000000010'
    first = ({'kind': 'add_persistent_note', 'note_id': note_id, 'target': 'report', 'issue_ref': None,
              'fragment': plain_fragment('First command payload.'), 'carry_forward': True},)
    fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(8450), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash, edits=(), continuity_changes=first,
    )

    with pytest.raises(report_api.ReportError) as conflict:
        fixture.draft_service.save_authored(
            fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
            command_id=draft_command(8450), expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash, edits=(),
            continuity_changes=({**first[0], 'carry_forward': False},),
        )

    assert conflict.value.code == 'REPORT_REVISION_CONFLICT'


@pytest.mark.django_db(transaction=True)
def test_should_edit_and_clear_persistent_note_and_report_action_narrative(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day1.command_id, selection=day1.selection,
        template=fixture.template_selection, preparation_id=day1.preparation_id,
    )
    action_id = draft.authoring_context['actions'][0]['action_id']
    persistent_id = '76000000-0000-4000-8000-000000000011'
    seeded = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(8460), expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash, edits=(),
        continuity_changes=({'kind': 'add_persistent_note', 'note_id': persistent_id, 'target': 'report',
                             'issue_ref': None, 'fragment': plain_fragment('Seed persistent.'), 'carry_forward': True},),
    )
    edited = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft.draft_id,
        command_id=draft_command(8461), expected_revision=seeded.revision,
        expected_revision_hash=seeded.revision_hash,
        edits=(
            report_api.AuthoredEditRequest('73000000-0000-4000-8000-000000000061', 'note',
                                           {'scope': 'persistent_note', 'note_id': persistent_id}, plain_fragment(''), None),
            report_api.AuthoredEditRequest('73000000-0000-4000-8000-000000000062', 'note',
                                           {'scope': 'report_action', 'action_id': action_id}, plain_fragment('Edited AR narrative.'), None),
        ),
    )

    assert edited.authoring_context['persistent_notes'][0]['fragment']['blocks'][0]['content'][0]['text'] == ''
    assert edited.authoring_context['persistent_notes'][0]['revision'] == 2
    assert edited.authoring_context['actions'][0]['body_fragment']['blocks'][0]['content'][0]['text'] == 'Edited AR narrative.'
