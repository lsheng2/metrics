import pytest

from project_management.app.api import reports as report_api
from project_management.services import report_period_views
from project_management.tests.history_persistence_fixtures import (
    git_head,
    history_fixture,
    plain_fragment,
    prepare_daily,
    ref_for,
    weekly_document,
)
from project_management.tests.report_draft_fixtures import draft_command


@pytest.mark.django_db(transaction=True)
def test_should_merge_later_selected_action_resolution_into_weekly_view(tmp_path):
    fixture = history_fixture(tmp_path)
    day1 = prepare_daily(fixture, 1, '2026-11-02', None)
    draft1 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day1.command_id, selection=day1.selection,
        template=fixture.template_selection, preparation_id=day1.preparation_id,
    )
    action_id = draft1.authoring_context['actions'][0]['action_id']
    publication1 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, draft1.draft_id,
        command_id=draft_command(8811), expected_revision=draft1.revision,
    )
    fixture.source_reader.source_commit = git_head(fixture.archive_root, fixture.project.id, fixture.stage.id)
    day2 = prepare_daily(fixture, 2, '2026-11-03', ref_for(publication1))
    draft2 = fixture.draft_service.create_authored(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=day2.command_id, selection=day2.selection,
        template=fixture.template_selection, preparation_id=day2.preparation_id,
    )
    saved2 = fixture.draft_service.save_authored(
        fixture.actor, fixture.project.id, fixture.stage.id, draft2.draft_id,
        command_id=draft_command(8820), expected_revision=draft2.revision,
        expected_revision_hash=draft2.revision_hash, edits=(),
        continuity_changes=({
            'kind': 'set_action_tracking',
            'action_id': action_id,
            'expected_state': 'open',
            'state': 'done',
            'resolution': plain_fragment('Closed after Tuesday validation.'),
            'evidence_refs': ('EV-101-A',),
        },),
    )
    publication2 = fixture.draft_service.finalize_and_commit(
        fixture.actor, fixture.project.id, fixture.stage.id, saved2.draft_id,
        command_id=draft_command(8821), expected_revision=saved2.revision,
    )
    weekly = fixture.template_service.create(
        fixture.actor, fixture.project.id, command_id=draft_command(8822),
        name='Weekly matrix', document=weekly_document(),
        fill_policy={'schema_version': 2, 'instructions': {}, 'daily_note_instructions': None},
    )
    template = report_api.UserTemplateSelection(str(weekly.template_id), weekly.revision, weekly.revision_hash)

    forward = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8823), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45',
        selected_publication_refs=(ref_for(publication1), ref_for(publication2)),
        template=template,
    )
    reverse = fixture.draft_service.create_period_view(
        fixture.actor, fixture.project.id, fixture.stage.id,
        command_id=draft_command(8824), series_id=fixture.series.series_id,
        period_key='intel-workweek:7:2026:ww45',
        selected_publication_refs=(ref_for(publication2), ref_for(publication1)),
        template=template,
    )

    assert _action_view(forward, action_id) == {
        'tracking_state': 'done',
        'resolution_text': 'Closed after Tuesday validation.',
        'unresolved': False,
        'visible_cell_actions': (),
    }
    assert _action_view(reverse, action_id) == _action_view(forward, action_id)


def test_should_skip_unchanged_later_inherited_action_copy():
    merge = getattr(report_period_views, '_merge_revised_records')
    selected = merge((
        _catalog_contexts('actions', 'action_id', _action('A-1', '2026-11-02', 'Corrected Monday narrative.', 'open')),
        _catalog_contexts('actions', 'action_id', _action('A-1', '2026-11-02', 'Stale Monday narrative.', 'open')),
    ), 'actions', 'action_id')

    assert selected == (_action('A-1', '2026-11-02', 'Corrected Monday narrative.', 'open'),)


def test_should_apply_later_action_resolution_without_replacing_corrected_narrative():
    merge = getattr(report_period_views, '_merge_revised_records')
    monday = _action('A-1', '2026-11-02', 'Corrected Monday narrative.', 'open')
    tuesday_initial = _action('A-1', '2026-11-02', 'Stale Monday narrative.', 'open')
    tuesday_final = {
        **tuesday_initial,
        'tracking_state': 'done',
        'resolution': _resolution('Closed after Tuesday validation.'),
    }

    selected = merge((
        _catalog_contexts('actions', 'action_id', monday),
        _catalog_contexts('actions', 'action_id', tuesday_initial, tuesday_final),
    ), 'actions', 'action_id')

    assert selected == ({
        **monday,
        'tracking_state': 'done',
        'resolution': _resolution('Closed after Tuesday validation.'),
    },)


def test_should_apply_later_persistent_note_fragment_and_carry_flag():
    merge = getattr(report_period_views, '_merge_revised_records')
    day1 = _persistent_note('P-1', 'Carry Monday context.', True, 1)
    day2_initial = _persistent_note('P-1', 'Carry Monday context.', True, 1)
    day2_final = _persistent_note('P-1', 'Tuesday confirmed context.', False, 2)

    selected = merge((
        _catalog_contexts('persistent_notes', 'note_id', day1),
        _catalog_contexts('persistent_notes', 'note_id', day2_initial, day2_final),
    ), 'persistent_notes', 'note_id')

    assert selected == (_persistent_note('P-1', 'Tuesday confirmed context.', False, 2),)


def _action_view(draft, action_id):
    action = next(item for item in draft.authoring_context['actions'] if item['action_id'] == action_id)
    matrix = report_api.build_meeting_matrix(draft.snapshot, draft.authoring_context)
    visible = tuple(
        item
        for row in matrix.rows
        for cell in row.cells
        for item in cell.action_ids
        if item == action_id
    )
    return {
        'tracking_state': action['tracking_state'],
        'resolution_text': action['resolution']['fragment']['blocks'][0]['content'][0]['text'],
        'unresolved': action_id in draft.authoring_context['weekly_seed']['unresolved_action_ids'],
        'visible_cell_actions': visible,
    }


def _catalog_contexts(field, identity, initial, final=None):
    return {
        'initial': {field: (initial,)},
        'selected': {field: (initial if final is None else final,)},
    }


def _action(action_id, local_date, text, state):
    return {
        'action_id': action_id,
        'issue_ref': {'provider_id': 'jira', 'endpoint_fingerprint': 'ep', 'stable_id': '10001'},
        'issued_meeting': {'local_date': local_date},
        'owner_ref': None,
        'body_fragment': plain_fragment(text),
        'basis': 'recorded',
        'tracking_state': state,
        'evidence_refs': (),
        'resolution': None,
    }


def _resolution(text):
    return {
        'fragment': plain_fragment(text),
        'evidence_refs': ('EV-101-A',),
        'resolved_by': 'archive-owner',
        'resolved_at': '2026-11-03T00:00:00+00:00',
    }


def _persistent_note(note_id, text, carry_forward, revision):
    return {
        'note_id': note_id,
        'target': 'report',
        'issue_ref': None,
        'fragment': plain_fragment(text),
        'carry_forward': carry_forward,
        'revision': revision,
        'body_hash': f'hash-{revision}',
        'provenance': (),
        'prior_revision_hash': None if revision == 1 else f'hash-{revision - 1}',
    }
