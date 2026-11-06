from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_draft_values import canonical_hash
from project_management.services.report_historical_references import HistoricalReferenceResolver
from project_management.services.report_preservation import preserve_parent_content
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.tests.history_persistence_fixtures import (
    daily_note_edit,
    git_head,
    history_fixture,
    note_by_id,
    plain_fragment,
    prepare_daily,
    ref_for,
    reference_observation,
)
from project_management.tests.report_draft_fixtures import draft_command


def v2_parent_record(record, edit, *, parent_draft_id, parent_revision, parent_hash):
    return {
        **record,
        'schema_version': 2,
        'historical_association': {
            'schema_version': 1,
            'kind': 'parent_draft_revision',
            'parent_draft_id': parent_draft_id,
            'parent_draft_revision': parent_revision,
            'parent_draft_revision_hash': parent_hash,
            'target_hash': canonical_hash(edit.target),
            'reference_id': record['reference_id'],
            'record_hash': canonical_hash(record),
        },
    }


@pytest.mark.django_db(transaction=True)
def test_should_refuse_parent_v2_reference_when_actual_source_draft_is_missing_or_stale(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    day1 = prepare_daily(fixture, 80, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day1.command_id,
        selection=day1.selection,
        template=fixture.template_selection,
        preparation_id=day1.preparation_id,
    )
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    option = verifier.issue_option(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft,
        {'scope': 'daily_note', 'note_id': note_id},
        'id',
        reference_observation(draft),
        membership_proof_hash='b' * 64,
        principal_id='principal:archive-owner',
    )
    saved = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9620),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009620',
            'note',
            {'scope': 'daily_note', 'note_id': note_id},
            option.fragment,
            draft.authoring_context['notes'][0]['body_hash'],
            (option.receipt,),
        ),),
    )
    real_record = saved.authored_edits[0].reference_observations[0]
    resolver = HistoricalReferenceResolver(fixture.draft_service, fixture.actor, fixture.project.id, fixture.stage.id)
    fake_parent = replace(saved, authored_edits=(replace(saved.authored_edits[0], reference_observations=(
        v2_parent_record(
            real_record,
            saved.authored_edits[0],
            parent_draft_id='76000000-0000-4000-8000-000000000999',
            parent_revision=1,
            parent_hash='a' * 64,
        ),
    )),))
    stale_parent = replace(saved, authored_edits=(replace(saved.authored_edits[0], reference_observations=(
        v2_parent_record(
            real_record,
            saved.authored_edits[0],
            parent_draft_id=saved.draft_id,
            parent_revision=saved.revision,
            parent_hash='e' * 64,
        ),
    )),))

    with pytest.raises(report_api.ReportError) as missing:
        preserve_parent_content(fake_parent, saved.authoring_context, saved.template_snapshot, resolver)
    with pytest.raises(report_api.ReportError) as stale:
        preserve_parent_content(stale_parent, saved.authoring_context, saved.template_snapshot, resolver)

    assert missing.value.code == 'REFERENCE_INVALID'
    assert stale.value.code == 'REFERENCE_INVALID'


@pytest.mark.django_db(transaction=True)
def test_should_reject_malformed_parent_v2_reference_shape_with_typed_error(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    day1 = prepare_daily(fixture, 82, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day1.command_id,
        selection=day1.selection,
        template=fixture.template_selection,
        preparation_id=day1.preparation_id,
    )
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    option = verifier.issue_option(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft,
        {'scope': 'daily_note', 'note_id': note_id},
        'id',
        reference_observation(draft),
        membership_proof_hash='b' * 64,
        principal_id='principal:archive-owner',
    )
    saved = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9622),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009622',
            'note',
            {'scope': 'daily_note', 'note_id': note_id},
            option.fragment,
            draft.authoring_context['notes'][0]['body_hash'],
            (option.receipt,),
        ),),
    )
    record = saved.authored_edits[0].reference_observations[0]
    malformed_missing_association = {**record, 'schema_version': 2}
    malformed_missing_kind = {
        **record,
        'schema_version': 2,
        'historical_association': {
            'schema_version': 1,
            'parent_draft_id': saved.draft_id,
            'parent_draft_revision': saved.revision,
            'parent_draft_revision_hash': saved.revision_hash,
            'target_hash': canonical_hash(saved.authored_edits[0].target),
            'reference_id': record['reference_id'],
            'record_hash': canonical_hash(record),
        },
    }

    for bad_record in (malformed_missing_association, malformed_missing_kind):
        bad_parent = replace(saved, authored_edits=(replace(saved.authored_edits[0], reference_observations=(bad_record,)),))
        with pytest.raises(report_api.ReportError) as error:
            preserve_parent_content(
                bad_parent,
                saved.authoring_context,
                saved.template_snapshot,
                HistoricalReferenceResolver(fixture.draft_service, fixture.actor, fixture.project.id, fixture.stage.id),
            )
        assert error.value.code == 'REFERENCE_INVALID'


@pytest.mark.django_db(transaction=True)
def test_should_allow_next_period_when_publication_persistent_edit_has_carry_false(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 90, '2026-11-02', None)
    draft1 = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day1.command_id,
        selection=day1.selection,
        template=fixture.template_selection,
        preparation_id=day1.preparation_id,
    )
    issue_ref = draft1.authoring_context['row_order']['rows'][0]['issue_ref']
    persistent_id = '76000000-0000-4000-8000-000000000900'
    seeded = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft1.draft_id,
        command_id=draft_command(9630),
        expected_revision=draft1.revision,
        expected_revision_hash=draft1.revision_hash,
        edits=(),
        continuity_changes=({
            'kind': 'add_persistent_note',
            'note_id': persistent_id,
            'target': 'issue',
            'issue_ref': issue_ref,
            'fragment': plain_fragment('Do not carry next week.'),
            'carry_forward': True,
        },),
    )
    edited = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft1.draft_id,
        command_id=draft_command(9631),
        expected_revision=seeded.revision,
        expected_revision_hash=seeded.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009631',
            'note',
            {'scope': 'persistent_note', 'note_id': persistent_id},
            plain_fragment('Edited but intentionally not carried.'),
            None,
        ),),
        continuity_changes=({'kind': 'set_persistent_carry', 'note_id': persistent_id, 'carry_forward': False},),
    )
    publication1 = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        edited.draft_id,
        command_id=draft_command(9632),
        expected_revision=edited.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    next_week = prepare_daily(fixture, 91, '2026-11-09', ref_for(publication1))
    draft2 = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=next_week.command_id,
        selection=next_week.selection,
        template=fixture.template_selection,
        preparation_id=next_week.preparation_id,
    )
    note2_id = draft2.authoring_context['current_observations'][0]['note_id']
    saved2 = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft2.draft_id,
        command_id=draft_command(9633),
        expected_revision=draft2.revision,
        expected_revision_hash=draft2.revision_hash,
        edits=(daily_note_edit(9633, note2_id, 'Next week can finalize.', '#0055aa', None),),
    )

    publication2 = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved2.draft_id,
        command_id=draft_command(9634),
        expected_revision=saved2.revision,
    )

    assert draft2.preservation_review_issues == ()
    assert publication2.manifest.report_role == 'daily'
