from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, sha256_bytes
from project_management.tests.history_persistence_fixtures import (
    continuity_document,
    daily_note_reference_edit,
    history_fixture,
    note_by_id,
    plain_fragment,
    reference_observation,
    prepare_daily,
    slot_fill_edit,
)
from project_management.tests.report_draft_fixtures import draft_command
from project_management.tests.test_daily_reprepare_backend import prepare_refresh_manual, refresh_manual_service
from project_management.app.api.project_runs import ProjectRunWorker
from project_management.services.report_reference_receipts import ReferenceReceiptVerifier
from project_management.services.report_preservation import preserve_parent_content


def draft_revision_bytes(fixture, draft_id, revision):
    return (
        fixture.archive_root / 'projects' / fixture.project.id / 'stages' / fixture.stage.id
        / 'runtime' / 'report-drafts' / draft_id / 'revisions' / f'{revision:08d}.json'
    ).read_bytes()


def fragment_hash(fragment):
    return sha256_bytes(canonical_bytes(fragment))


def context_with_note_text(context, note_id, text, source_hash):
    note_fragment = plain_fragment(text)
    notes = []
    for note in context['notes']:
        if note['note_id'] == note_id:
            status = {**note['source_status'], 'source_hash': source_hash}
            notes.append({**note, 'body_fragment': note_fragment, 'body_hash': fragment_hash(note_fragment),
                          'source_status': status})
        else:
            notes.append(note)
    observations = []
    for observation in context['current_observations']:
        if observation['note_id'] == note_id:
            summary = {**observation['accepted_summary_ref'], 'result_hash': 'e' * 64}
            status = {**observation['source_status'], 'source_hash': source_hash}
            observations.append({**observation, 'source_hash': source_hash, 'source_status': status,
                                 'source_state': 'changed', 'accepted_summary_ref': summary})
        else:
            observations.append(observation)
    return {**context, 'notes': tuple(notes), 'current_observations': tuple(observations)}


@pytest.mark.django_db(transaction=True)
def test_should_seed_saved_capture_reprepare_with_parent_persistent_note_and_slot_fill(tmp_path):
    fixture = history_fixture(tmp_path, document=continuity_document(required_slot=True))
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Validation is active',
        'status': 'Active',
        'comments': {'201': {'id': '201', 'body': 'Validation started.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9500)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    issue_ref = draft.authoring_context['row_order']['rows'][0]['issue_ref']
    persistent_id = '76000000-0000-4000-8000-000000000101'
    parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9501),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill_edit(9501, '40000000-0000-4000-8000-000000000001', 'Parent slot remains.'),),
        continuity_changes=({
            'kind': 'add_persistent_note',
            'note_id': persistent_id,
            'target': 'issue',
            'issue_ref': issue_ref,
            'fragment': plain_fragment('Carry this parent note.'),
            'carry_forward': True,
        },),
    )
    parent_bytes_before = draft_revision_bytes(fixture, parent.draft_id, parent.revision)

    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9502),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=completed.revision,
        expected_draft_revision=parent.revision,
        expected_draft_revision_hash=parent.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=completed.capture_id,
        analysis_mode='manual_only',
    )
    new_draft = fixture.draft_service.get(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        replacement.draft_id,
    )

    assert draft_revision_bytes(fixture, parent.draft_id, parent.revision) == parent_bytes_before
    assert new_draft.revision == 1
    assert new_draft.authored_edits[0].target == {
        'scope': 'template_slot',
        'slot_id': '40000000-0000-4000-8000-000000000001',
    }
    assert new_draft.authored_edits[0].fragment['blocks'][0]['content'][0]['text'] == 'Parent slot remains.'
    assert new_draft.authoring_context['persistent_notes'][0]['note_id'] == persistent_id
    assert new_draft.authoring_context['persistent_notes'][0]['fragment']['blocks'][0]['content'][0]['text'] == 'Carry this parent note.'
    assert new_draft.authoring_context['persistent_notes'][0]['carry_forward'] is True


def prepare_saved_capture(fixture, service, command):
    return service.prepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(command),
        series_id=fixture.series.series_id,
        meeting_date='2026-11-02',
        expected_series_policy_hash=fixture.series.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=f'72000000-0000-4000-8000-{command:012d}',
        analysis_mode='manual_only',
        acknowledge_gap_draft_ids=(),
    )


@pytest.mark.django_db(transaction=True)
def test_should_preserve_empty_reference_action_and_row_order_in_saved_capture_reprepare(tmp_path):
    verifier = ReferenceReceiptVerifier('unit-secret')
    fixture = history_fixture(tmp_path, reference_verifier=verifier)
    service = report_api.ReportPreparationService(
        fixture.continuity,
        fixture.draft_service,
        fixture.template_service,
    )
    prepared = prepare_saved_capture(fixture, service, 9510)
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, prepared.draft_id)
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    action_id = draft.authoring_context['actions'][0]['action_id']
    first_row = draft.authoring_context['row_order']['rows'][0]
    second_row = draft.authoring_context['row_order']['rows'][1]
    original = note_by_id(draft.authoring_context, note_id)
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
    parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9511),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(
            daily_note_reference_edit(9511, note_id, option, original['body_hash']),
            report_api.AuthoredEditRequest(
                '73000000-0000-4000-8000-000000009512',
                'note',
                {'scope': 'report_action', 'action_id': action_id},
                plain_fragment(''),
                None,
            ),
        ),
        continuity_changes=(
            {'kind': 'set_action_tracking', 'action_id': action_id, 'expected_state': 'open',
             'state': 'done', 'resolution': plain_fragment('Resolved by parent validation.'),
             'evidence_refs': ('EV-101-A',)},
            {'kind': 'move_row', 'issue_ref': second_row['issue_ref'], 'group_id': second_row['group_id'],
             'after_issue_ref': None},
        ),
    )

    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9513),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=None,
        expected_draft_revision=parent.revision,
        expected_draft_revision_hash=parent.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=prepared.effective_selection['capture_id'],
        analysis_mode='manual_only',
    )
    new_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, replacement.draft_id)
    new_note = note_by_id(new_draft.authoring_context, note_id)

    assert new_draft.revision == 1
    assert new_note['body_fragment']['blocks'][0]['content'][0]['content'][0]['foreground'] == '#0055aa'
    assert new_draft.authored_edits[0].reference_observations[0]['reference_id'] == option.reference_id
    assert new_draft.authored_edits[1].fragment['blocks'][0]['content'][0]['text'] == ''
    assert new_draft.authoring_context['actions'][0]['tracking_state'] == 'done'
    assert new_draft.authoring_context['actions'][0]['resolution']['fragment']['blocks'][0]['content'][0]['text'] == 'Resolved by parent validation.'
    assert new_draft.authoring_context['row_order']['rows'][0]['issue_ref'] == second_row['issue_ref']
    assert new_draft.authoring_context['row_order']['rows'][1]['issue_ref'] == first_row['issue_ref']

    original_membership = fixture.draft_service.source_reader.membership

    def changed_membership(*args):
        return replace(original_membership(*args), proof_hash='c' * 64)

    fixture.draft_service.source_reader.membership = changed_membership
    link = new_draft.authored_edits[0].fragment['blocks'][0]['content'][0]
    edited = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        new_draft.draft_id,
        command_id=draft_command(9514),
        expected_revision=new_draft.revision,
        expected_revision_hash=new_draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            new_draft.authored_edits[0].edit_id,
            'note',
            new_draft.authored_edits[0].target,
            {'schema_version': 2, 'blocks': [{'type': 'paragraph', 'content': [
                {'type': 'text', 'text': 'follow-up ', 'marks': [], 'foreground': None, 'background': None},
                link,
            ]}]},
                new_note['body_hash'],
        ),),
    )

    assert edited.authored_edits[0].reference_observations[0]['schema_version'] == 2
    assert edited.authored_edits[0].reference_observations[0]['observation']['scope_snapshot_hash'] == 'b' * 64


@pytest.mark.django_db(transaction=True)
def test_should_preserve_parent_context_after_refresh_worker_creates_replacement(tmp_path):
    fixture = history_fixture(tmp_path, document=continuity_document(required_slot=True))
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Validation is active',
        'status': 'Active',
        'comments': {'201': {'id': '201', 'body': 'Validation started.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9520)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    issue_ref = draft.authoring_context['row_order']['rows'][0]['issue_ref']
    parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9521),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill_edit(9521, '40000000-0000-4000-8000-000000000001', 'Refresh slot remains.'),),
        continuity_changes=({
            'kind': 'add_persistent_note',
            'note_id': '76000000-0000-4000-8000-000000000202',
            'target': 'issue',
            'issue_ref': issue_ref,
            'fragment': plain_fragment('Refresh worker carries this.'),
            'carry_forward': True,
        },),
    )
    queued = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9522),
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
    new_draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, finished.draft_id)

    assert queued.state == 'queued'
    assert finished.draft_revision == 1
    assert new_draft.authored_edits[0].fragment['blocks'][0]['content'][0]['text'] == 'Refresh slot remains.'
    assert new_draft.authoring_context['persistent_notes'][0]['fragment']['blocks'][0]['content'][0]['text'] == 'Refresh worker carries this.'


@pytest.mark.django_db(transaction=True)
def test_should_not_overwrite_replacement_user_edit_on_reprepare_response_loss_retry(tmp_path):
    fixture = history_fixture(tmp_path, document=continuity_document(required_slot=True))
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Validation is active',
        'status': 'Active',
        'comments': {'201': {'id': '201', 'body': 'Validation started.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9530)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9531),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill_edit(9531, '40000000-0000-4000-8000-000000000001', 'Parent slot before retry.'),),
    )
    replacement = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9532),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=completed.revision,
        expected_draft_revision=parent.revision,
        expected_draft_revision_hash=parent.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=completed.capture_id,
        analysis_mode='manual_only',
    )
    current = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, replacement.draft_id)
    edited = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        current.draft_id,
        command_id=draft_command(9533),
        expected_revision=current.revision,
        expected_revision_hash=current.revision_hash,
        edits=(slot_fill_edit(9533, '40000000-0000-4000-8000-000000000001', 'Replacement user edit survives.'),),
    )

    retry = service.reprepare(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=draft_command(9532),
        preparation_id=prepared.preparation_id,
        expected_operation_revision=completed.revision,
        expected_draft_revision=parent.revision,
        expected_draft_revision_hash=parent.revision_hash,
        expected_baseline_ref=None,
        template_selection=fixture.template_selection,
        source_mode='saved_capture',
        capture_id=completed.capture_id,
        analysis_mode='manual_only',
    )
    retried = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, retry.draft_id)

    assert retry.draft_revision == edited.revision
    assert retried.authored_edits[0].fragment['blocks'][0]['content'][0]['text'] == 'Replacement user edit survives.'


@pytest.mark.django_db(transaction=True)
def test_should_report_template_slot_mismatch_instead_of_silently_dropping_parent_fill(tmp_path):
    fixture = history_fixture(tmp_path, document=continuity_document(required_slot=True))
    service, run_service = refresh_manual_service(fixture, ({
        'stable_id': 'ALPHA-1',
        'summary': 'Validation is active',
        'status': 'Active',
        'comments': {'201': {'id': '201', 'body': 'Validation started.'}},
    },))
    prepared = prepare_refresh_manual(fixture, service, 9540)
    completed = ProjectRunWorker(run_service, daily_preparation_service=service).execute(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        prepared.operation_id,
    )
    draft = fixture.draft_service.get(fixture.actor, fixture.project.id, fixture.stage.id, completed.draft_id)
    parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9541),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(slot_fill_edit(9541, '40000000-0000-4000-8000-000000000001', 'Parent slot cannot disappear silently.'),),
    )
    replacement_template = {
        **parent.template_snapshot,
        'resolved_document': {
            **parent.template_snapshot['resolved_document'],
            'blocks': tuple(block for block in parent.template_snapshot['resolved_document']['blocks'] if block['kind'] != 'slot'),
        },
    }

    preserved = preserve_parent_content(parent, parent.authoring_context, replacement_template)

    assert preserved.preservation['initial_authored_edits'] == []
    assert preserved.preservation['review_issues'] == [{
        'code': 'template_slot_removed',
        'target': {'scope': 'template_slot', 'slot_id': '40000000-0000-4000-8000-000000000001'},
        'reason': 'Parent slot is not present in the replacement template.',
    }]


@pytest.mark.django_db(transaction=True)
def test_should_not_copy_unmodified_ai_note_over_changed_source_but_keep_human_note(tmp_path):
    fixture = history_fixture(tmp_path)
    prepared = prepare_daily(fixture, 30, '2026-11-02', None)
    draft = fixture.draft_service.create_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        command_id=prepared.command_id,
        selection=prepared.selection,
        template=fixture.template_selection,
        preparation_id=prepared.preparation_id,
    )
    note_id = draft.authoring_context['current_observations'][0]['note_id']
    changed_context = context_with_note_text(draft.authoring_context, note_id, 'Replacement source narrative.', 'f' * 64)

    unchanged_parent = preserve_parent_content(draft, changed_context, draft.template_snapshot)

    assert note_by_id(unchanged_parent.context, note_id)['body_fragment']['blocks'][0]['content'][0]['text'] == 'Replacement source narrative.'

    original = note_by_id(draft.authoring_context, note_id)
    human_parent = fixture.draft_service.save_authored(
        fixture.actor,
        fixture.project.id,
        fixture.stage.id,
        draft.draft_id,
        command_id=draft_command(9551),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(report_api.AuthoredEditRequest(
            '73000000-0000-4000-8000-000000009551',
            'note',
            {'scope': 'daily_note', 'note_id': note_id},
            plain_fragment('Human edited narrative.'),
            original['body_hash'],
        ),),
    )

    human_preserved = preserve_parent_content(human_parent, changed_context, draft.template_snapshot)

    assert note_by_id(human_preserved.context, note_id)['body_fragment']['blocks'][0]['content'][0]['text'] == 'Human edited narrative.'
    assert note_by_id(human_preserved.context, note_id)['source_status']['source_hash'] == 'f' * 64
