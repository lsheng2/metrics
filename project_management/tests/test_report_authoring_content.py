from dataclasses import replace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.report_authoring import validate_authored_edit_requests
from project_management.app.domain.report_authoring_fragments import validate_rich_text_fragment
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_selection,
)
from project_management.tests.report_render_fixtures import source_key_hash


def build_service(environment):
    return report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=FixedClock(),
    )


def builtin_template():
    return report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '2', {})


def fragment(*blocks):
    return {'schema_version': 2, 'blocks': list(blocks)}


def paragraph(*content):
    return {'type': 'paragraph', 'content': list(content)}


def rich_text(text, *, marks=(), foreground=None, background=None):
    return {
        'type': 'text',
        'text': text,
        'marks': list(marks),
        'foreground': foreground,
        'background': background,
    }


def rich_link(href, *content):
    return {'type': 'link', 'href': href, 'content': list(content)}


def authored_note(value, rich_fragment):
    return report_api.AuthoredEditRequest(
        f'10000000-0000-4000-8000-{value:012d}',
        'note',
        {'scope': 'report'},
        rich_fragment,
        None,
    )


def test_should_keep_colored_link_and_bold_note_when_saved_reopened_rendered_and_published(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(400),
        selection=draft_selection(),
        template=builtin_template(),
    )
    note = authored_note(1, fragment(paragraph(
        rich_text('Decision ', marks=('strong',), foreground='#d22f27', background=None),
        rich_link(
            'https://tracker.example.test/browse/DEMO-101?focused=note#decision',
            rich_text('DEMO-101', marks=('code',), foreground=None, background='#fff1a8'),
        ),
    )))

    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(401),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(note,),
    )
    reopened = service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    rendered = service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=saved.revision)
    publication = service.finalize_and_commit(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(402),
        expected_revision=saved.revision,
    )
    final_rendered = service.render(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        revision=saved.revision,
    )

    assert (draft.authoring_schema, saved.authoring_schema, reopened.authoring_schema) == (
        'report-authoring/2',
        'report-authoring/2',
        'report-authoring/2',
    )
    assert saved.revision_hash != draft.revision_hash
    assert reopened.authored_edits[0].fragment == saved.authored_edits[0].fragment
    assert '<strong style="color:#d22f27;">Decision </strong>' in rendered.html_fragment
    assert '<a href="https://tracker.example.test/browse/DEMO-101?focused=note#decision"' in rendered.html_fragment
    assert '<code style="background-color:#fff1a8;">DEMO-101</code>' in rendered.html_fragment
    assert 'Decision DEMO-101' in rendered.plain_text
    assert '<strong' not in rendered.plain_text
    assert publication.manifest.schema_version == 2
    assert service.read_artifact(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        publication.manifest.publication_id,
        'report.html',
    ) == final_rendered.html_document


def test_should_treat_paint_only_change_as_new_revision(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(410),
        selection=draft_selection(),
        template=builtin_template(),
    )

    first = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(411),
        expected_revision=1,
        expected_revision_hash=draft.revision_hash,
        edits=(authored_note(2, fragment(paragraph(rich_text('Same words', foreground='#aa0000', background=None)))),),
    )
    second = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(412),
        expected_revision=first.revision,
        expected_revision_hash=first.revision_hash,
        edits=(authored_note(2, fragment(paragraph(rich_text('Same words', foreground='#0000aa', background=None)))),),
    )

    assert second.revision == first.revision + 1
    assert second.revision_hash != first.revision_hash
    assert second.authored_edits[0].fragment != first.authored_edits[0].fragment


def test_should_reject_forged_targets_unsafe_fragments_receipts_and_stale_cas(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(420),
        selection=draft_selection(),
        template=builtin_template(),
    )
    row = draft.snapshot.rows[0]
    valid = authored_note(3, fragment(paragraph(rich_text('Safe note', foreground=None, background=None))))
    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(421),
        expected_revision=1,
        expected_revision_hash=draft.revision_hash,
        edits=(valid,),
    )

    rejected_edits = (
        report_api.AuthoredEditRequest(
            '20000000-0000-4000-8000-000000000001',
            'narrative_override',
            {'scope': 'issue', 'source_key_hash': source_key_hash(row.source_key), 'field': 'status'},
            fragment(paragraph(rich_text('Forged status', foreground=None, background=None))),
            report_api.text_hash(row.status),
        ),
        report_api.AuthoredEditRequest(
            '20000000-0000-4000-8000-000000000002',
            'narrative_override',
            {'scope': 'issue', 'source_key_hash': source_key_hash(row.source_key), 'field': 'what'},
            fragment(paragraph(rich_text('Wrong hash', foreground=None, background=None))),
            '0' * 64,
        ),
        authored_note(4, {'schema_version': 2, 'blocks': [{'type': 'script', 'text': 'alert(1)'}]}),
        authored_note(5, fragment(paragraph(rich_link(
            'https://user:secret@tracker.example.test/browse/DEMO-101',
            rich_text('bad', foreground=None, background=None),
        )))),
        replace(valid, edit_id='20000000-0000-4000-8000-000000000006', reference_receipts=('receipt',)),
        replace(valid, edit_id='20000000-0000-4000-8000-000000000007', assist_receipt_id='20000000-0000-4000-8000-000000000100'),
    )
    for index, edit in enumerate(rejected_edits, 430):
        with pytest.raises(report_api.ReportError):
            service.save_authored(
                environment.actor,
                environment.project.id,
                environment.stage.id,
                draft.draft_id,
                command_id=draft_command(index),
                expected_revision=saved.revision,
                expected_revision_hash=saved.revision_hash,
                edits=(edit,),
            )
    with pytest.raises(report_api.ReportError) as stale:
        service.save_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(450),
            expected_revision=1,
            expected_revision_hash=draft.revision_hash,
            edits=(valid,),
        )
    with pytest.raises(report_api.ReportError):
        service.save_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(451),
            expected_revision=saved.revision,
            expected_revision_hash=saved.revision_hash,
            edits=(valid,),
            continuity_changes=({'type': 'move_row'},),
        )
    assert stale.value.code == 'REPORT_REVISION_CONFLICT'


def test_should_reject_create_authored_when_builtin_version_is_not_the_authored_successor(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)

    with pytest.raises(report_api.ReportError) as error:
        service.create_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(452),
            selection=draft_selection(),
            template=report_api.AuthoringTemplateSelection('builtin', 'daily-standup', '1', {}),
        )

    assert error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'


def test_should_raise_report_error_for_malformed_kind_and_count_link_text_runs(tmp_path, monkeypatch):
    environment = DraftArchive(tmp_path / 'archive-root')
    snapshot = StaticSourceReader().read(environment.actor, environment.project.id, environment.stage.id, draft_selection())
    malformed = report_api.AuthoredEditRequest(
        '20000000-0000-4000-8000-000000000008',
        [],
        {'scope': 'report'},
        fragment(paragraph(rich_text('bad', foreground=None, background=None))),
        None,
    )

    with pytest.raises(report_api.ReportError) as error:
        validate_authored_edit_requests(snapshot, (malformed,))

    monkeypatch.setattr('project_management.app.domain.report_authoring_fragments.MAX_FRAGMENT_NODES', 4)
    too_many_inner_runs = fragment(paragraph(rich_link(
        'https://tracker.example.test/browse/DEMO-101',
        rich_text('a', foreground=None, background=None),
        rich_text('b', foreground=None, background=None),
        rich_text('c', foreground=None, background=None),
    )))
    with pytest.raises(report_api.ReportError):
        validate_rich_text_fragment(too_many_inner_runs)

    assert error.value.code == 'REPORT_EDIT_TARGET_INVALID'


def test_should_replay_same_save_command_and_reject_same_command_with_different_payload(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(460),
        selection=draft_selection(),
        template=builtin_template(),
    )
    first_edit = authored_note(6, fragment(paragraph(rich_text('Replay me', foreground=None, background=None))))
    changed_edit = authored_note(6, fragment(paragraph(rich_text('Different payload', foreground=None, background=None))))

    first = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(461),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(first_edit,),
    )
    replay = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(461),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(first_edit,),
    )

    with pytest.raises(report_api.ReportError) as conflict:
        service.save_authored(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(461),
            expected_revision=draft.revision,
            expected_revision_hash=draft.revision_hash,
            edits=(changed_edit,),
        )

    assert (replay.revision, replay.revision_hash) == (first.revision, first.revision_hash)
    assert conflict.value.code == 'REPORT_REVISION_CONFLICT'


def test_should_persist_explicit_empty_narrative_override_without_resurrecting_original_text(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(470),
        selection=draft_selection(),
        template=builtin_template(),
    )
    row = draft.snapshot.rows[0]
    edit = report_api.AuthoredEditRequest(
        '30000000-0000-4000-8000-000000000001',
        'narrative_override',
        {'scope': 'issue', 'source_key_hash': source_key_hash(row.source_key), 'field': 'what'},
        fragment(),
        report_api.text_hash(row.what),
    )

    saved = service.save_authored(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(471),
        expected_revision=draft.revision,
        expected_revision_hash=draft.revision_hash,
        edits=(edit,),
    )
    rendered = service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=saved.revision)

    assert saved.authored_edits[0].fragment['blocks'] == ()
    assert '<strong>What:</strong> Power rail bring-up' not in rendered.html_fragment
    assert 'Original: Power rail bring-up blocks boot after cold reset.' in rendered.html_fragment
