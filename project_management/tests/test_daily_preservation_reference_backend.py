from dataclasses import replace
import shutil

import pytest

from project_management.app.api import reports as report_api
from project_management.app.api.project_runs import ProjectRunWorker
from project_management.app.domain.report_draft_values import canonical_hash
from project_management.services.report_preservation import preserve_parent_content, wrap_publication_reference_edits
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
from project_management.tests.test_daily_reprepare_backend import prepare_refresh_manual, refresh_manual_service


def bad_v2_record(record, edit, *, kind='parent_draft_revision', target_hash=None, record_hash=None):
    legacy_hash = canonical_hash(record)
    return {
        **record,
        'schema_version': 2,
        'historical_association': {
            'schema_version': 1,
            'kind': kind,
            'parent_draft_id': '76000000-0000-4000-8000-000000000001',
            'parent_draft_revision': 1,
            'parent_draft_revision_hash': 'a' * 64,
            'target_hash': target_hash or canonical_hash(edit.target),
            'reference_id': record['reference_id'],
            'record_hash': record_hash or legacy_hash,
        },
    }


@pytest.mark.django_db(transaction=True)
def test_should_emit_review_issues_for_missing_targets_and_removed_row_group(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Validation is active',
        'status': 'Active',
        'comments': {'201': {'id': '201', 'body': 'Validation started.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9560)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    removed_group = '76000000-0000-4000-8000-000000000303'
    grouped_rows = tuple({**row, 'group_id': removed_group} for row in draft.authoring_context['row_order']['rows'])
    parent = replace(
        draft,
        authoring_context={
            **draft.authoring_context,
            'row_order': {**draft.authoring_context['row_order'], 'group_order': (removed_group,), 'rows': grouped_rows},
        },
        authored_edits=(
            report_api.AuthoredEdit(
                '73000000-0000-4000-8000-000000009561',
                'note',
                {'scope': 'daily_note', 'note_id': '76000000-0000-4000-8000-000000009561'},
                plain_fragment('Missing daily note.'),
                None,
                fixture.actor.subject,
                '2026-11-02T03:00:00+00:00',
            ),
            report_api.AuthoredEdit(
                '73000000-0000-4000-8000-000000009562',
                'note',
                {'scope': 'persistent_note', 'note_id': '76000000-0000-4000-8000-000000009562'},
                plain_fragment('Missing persistent note.'),
                None,
                fixture.actor.subject,
                '2026-11-02T03:00:00+00:00',
            ),
        ),
    )

    preserved = preserve_parent_content(parent, draft.authoring_context, draft.template_snapshot)
    issue_codes = tuple(issue['code'] for issue in preserved.preservation['review_issues'])

    assert 'daily_note_missing' in issue_codes
    assert 'persistent_note_missing' in issue_codes
    assert 'row_group_removed' in issue_codes
    assert preserved.context['weekly_seed']['unresolved_action_ids'] == tuple(
        action['action_id'] for action in preserved.context['actions'] if action['tracking_state'] == 'open'
    )


@pytest.mark.django_db(transaction=True)
def test_should_return_preservation_review_issues_from_public_reprepare_result_and_block_finalize(tmp_path):
    fixture = history_fixture(tmp_path)
    service, run_service = refresh_manual_service(fixture, (
        {'stable_id': 'ALPHA-1', 'summary': 'First row remains', 'status': 'Active', 'comments': {}},
        {'stable_id': 'ALPHA-2', 'summary': 'Second row will disappear', 'status': 'Active', 'comments': {}},
    ))
    prepared = prepare_refresh_manual(fixture, service, 9580)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    dropped_issue = draft.authoring_context['row_order']['rows'][1]['issue_ref']
    parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9581),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(),
        continuity_changes=({
            'kind': 'add_persistent_note',
            'note_id': '76000000-0000-4000-8000-000000000580',
            'target': 'issue',
            'issue_ref': dropped_issue,
            'fragment': plain_fragment('This issue disappears in the replacement source.'),
            'carry_forward': True,
        },),
    )
    run_service.capture_service.provider_access.items = ({
        'stable_id': 'ALPHA-1',
        'summary': 'First row remains',
        'status': 'Active',
        'comments': {},
    },)
    queued = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9582),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=completed.revision,
        expected_draft_revision=parent.revision,
        expected_draft_revision_hash=parent.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='refresh',
        capture_id=None,
        analysis_mode='manual_only',
    )
    finished = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        queued.operation_id,
    )
    current = service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9583),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=finished.capture_id,
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )

    assert tuple(issue['code'] for issue in current.preservation_review_issues) == ('persistent_note_missing',)
    current_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, current.draft_id)
    with pytest.raises(report_api.ReportError) as error:
        fixture.draft_service.finalize_and_commit(
            fixture.actor,
            fixture.project.id,
            fixture.stage.id,
            current.draft_id,
            command_id=draft_command(9584),
            expected_revision=current_draft.revision,
        )
    assert error.value.code == 'REPORT_HISTORY_UNAVAILABLE'


@pytest.mark.django_db(transaction=True)
def test_should_allow_day2_finalize_after_day1_human_daily_note_history_is_preserved_readonly(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 70, '2026-11-02', None)
    draft1 = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day1.command_id,
        selection=day1.selection,
        template=fixture.template_selection,
        preparation_id=day1.preparation_id,
    )
    note1_id = draft1.authoring_context['current_observations'][0]['note_id']
    original = note_by_id(draft1.authoring_context, note1_id)
    saved1 = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft1.draft_id,
        command_id=draft_command(9610),
        expected_revision=draft1.revision,
        expected_revision_hash=draft1.revision_hash,
        edits=(daily_note_edit(9610, note1_id, 'Day1 human note remains historical.', '#00aa00', original['body_hash']),),
    )
    publication1 = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved1.draft_id,
        command_id=draft_command(9611),
        expected_revision=saved1.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 71, '2026-11-03', ref_for(publication1))
    draft2 = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day2.command_id,
        selection=day2.selection,
        template=fixture.template_selection,
        preparation_id=day2.preparation_id,
    )
    note2_id = draft2.authoring_context['current_observations'][0]['note_id']
    saved2 = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft2.draft_id,
        command_id=draft_command(9612),
        expected_revision=draft2.revision,
        expected_revision_hash=draft2.revision_hash,
        edits=(daily_note_edit(9612, note2_id, 'Day2 note can still finalize.', '#0055aa', None),),
    )

    publication2 = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved2.draft_id,
        command_id=draft_command(9613),
        expected_revision=saved2.revision,
    )

    assert draft2.preservation_review_issues == ()
    assert publication2.manifest.report_role == 'daily'


@pytest.mark.django_db(transaction=True)
def test_should_edit_inherited_publication_reference_without_new_lookup_or_current_proof_renewal(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    day1 = prepare_daily(fixture, 40, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day1.command_id,
        selection=day1.selection,
        template=fixture.template_selection,
        preparation_id=day1.preparation_id,
    )
    issue_ref = draft.authoring_context['row_order']['rows'][0]['issue_ref']
    persistent_id = '76000000-0000-4000-8000-000000000404'
    seeded = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9570),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(),
        continuity_changes=({
            'kind': 'add_persistent_note',
            'note_id': persistent_id,
            'target': 'issue',
            'issue_ref': issue_ref,
            'fragment': plain_fragment('Seed persistent reference.'),
            'carry_forward': True,
        },),
    )
    option = verifier.issue_option(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        seeded,
        {'scope': 'persistent_note', 'note_id': persistent_id},
        'id',
        reference_observation(seeded),
        membership_proof_hash='b' * 64,
        principal_id='principal:archive-owner',
    )
    saved = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9571),
        expected_revision=seeded.revision,
        expected_revision_hash=seeded.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009571',
            'note',
            {'scope': 'persistent_note', 'note_id': persistent_id},
            option.fragment,
            None,
            (option.receipt,),
        ),),
    )
    publication = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved.draft_id,
        command_id=draft_command(9572),
        expected_revision=saved.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 41, '2026-11-03', ref_for(publication))
    draft2 = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=day2.command_id,
        selection=day2.selection,
        template=fixture.template_selection,
        preparation_id=day2.preparation_id,
    )
    inherited = next(edit for edit in draft2.authored_edits if edit.target == {'scope': 'persistent_note', 'note_id': persistent_id})
    original_membership = fixture.draft_service.source_reader.membership

    def changed_membership(*args):
        return replace(original_membership(*args), proof_hash='c' * 64)

    fixture.draft_service.source_reader.membership = changed_membership
    link = inherited.fragment['blocks'][0]['content'][0]
    edited = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft2.draft_id,
        command_id=draft_command(9573),
        expected_revision=draft2.revision,
        expected_revision_hash=draft2.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            inherited.edit_id,
            'note',
            inherited.target,
            {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'day2 context ', 'marks': [], 'foreground': '#111111', 'background': None},
                link,
            ]}]},
            None,
        ),),
    )

    record = next(edit for edit in edited.authored_edits if edit.edit_id == inherited.edit_id).reference_observations[0]
    assert record['historical_association']['kind'] == 'source_publication'
    assert record['observation']['scope_snapshot_hash'] == 'b' * 64


@pytest.mark.django_db(transaction=True)
def test_should_reject_existing_v2_reference_with_bad_target_hash_record_hash_or_kind(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    day1 = prepare_daily(fixture, 50, '2026-11-02', None)
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
        command_id=draft_command(9590),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009590',
            'note',
            {'scope': 'daily_note', 'note_id': note_id},
            option.fragment,
            draft.authoring_context['notes'][0]['body_hash'],
            (option.receipt,),
        ),),
    )
    edit = saved.authored_edits[0]
    record = edit.reference_observations[0]
    bad_parent = replace(saved, authored_edits=(replace(edit, reference_observations=(
        bad_v2_record(record, edit, target_hash='d' * 64),
    )),))

    with pytest.raises(report_api.ReportError) as parent_error:
        preserve_parent_content(bad_parent, saved.authoring_context, saved.template_snapshot)

    publication = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved.draft_id,
        command_id=draft_command(9591),
        expected_revision=saved.revision,
    )
    bad_hash = replace(edit, reference_observations=(bad_v2_record(record, edit, record_hash='e' * 64),))
    bad_kind = replace(edit, reference_observations=(bad_v2_record(record, edit, kind='wrong_kind'),))

    with pytest.raises(report_api.ReportError) as hash_error:
        wrap_publication_reference_edits(publication, (bad_hash,))
    with pytest.raises(report_api.ReportError) as kind_error:
        wrap_publication_reference_edits(publication, (bad_kind,))

    assert parent_error.value.code == 'REFERENCE_INVALID'
    assert hash_error.value.code == 'REFERENCE_INVALID'
    assert kind_error.value.code == 'REFERENCE_INVALID'


@pytest.mark.django_db(transaction=True)
def test_should_wrap_linked_correction_references_to_source_publication(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    day1 = prepare_daily(fixture, 60, '2026-11-02', None)
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
        command_id=draft_command(9600),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009600',
            'note',
            {'scope': 'daily_note', 'note_id': note_id},
            option.fragment,
            draft.authoring_context['notes'][0]['body_hash'],
            (option.receipt,),
        ),),
    )
    publication = fixture.draft_service.finalize_and_commit(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        saved.draft_id,
        command_id=draft_command(9601),
        expected_revision=saved.revision,
    )
    linked = fixture.draft_service.create_linked_revision(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9602),
        publication_ref=ref_for(publication),
    )
    shutil.rmtree(
        fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
        / 'runtime' / 'report-drafts' / draft.draft_id,
    )
    original_membership = fixture.draft_service.source_reader.membership

    def changed_membership(*args):
        return replace(original_membership(*args), proof_hash='c' * 64)

    fixture.draft_service.source_reader.membership = changed_membership
    inherited = linked.authored_edits[0]
    link = inherited.fragment['blocks'][0]['content'][0]
    edited = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        linked.draft_id,
        command_id=draft_command(9603),
        expected_revision=linked.revision,
        expected_revision_hash=linked.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            inherited.edit_id,
            'note',
            inherited.target,
            {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'correction ', 'marks': [], 'foreground': '#222222', 'background': None},
                link,
            ]}]},
            note_by_id(linked.authoring_context, note_id)['body_hash'],
        ),),
    )

    record = edited.authored_edits[0].reference_observations[0]
    assert record['historical_association']['kind'] == 'source_publication'
    assert record['observation']['scope_snapshot_hash'] == 'b' * 64
