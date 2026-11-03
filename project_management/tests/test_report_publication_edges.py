from dataclasses import replace
import shutil
from types import SimpleNamespace

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError
from project_management.storage.paths import read_bytes
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    draft_command,
    draft_note,
    draft_root,
    draft_selection,
)
from project_management.tests.report_render_fixtures import daily_template
from project_management.services.report_publication_reads import ReportPublicationResolver


class CountingRenderer(report_api.ReportRenderer):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def render(self, *args, **kwargs):
        self.calls += 1
        return super().render(*args, **kwargs)


class RacingSourceReader(StaticSourceReader):
    def __init__(self, environment):
        super().__init__(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
        self.environment = environment
        self.armed = False

    def read(self, actor, project_id, stage_id, selection):
        snapshot = super().read(actor, project_id, stage_id, selection)
        if self.armed:
            self.environment.repository._head = 'd' * 40
        return snapshot


def service(environment, *, source=None, renderer=None):
    return report_api.ReportDraftService(
        environment,
        source or StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        renderer or CountingRenderer(),
        clock=FixedClock(),
    )


def saved_draft(environment, svc, *, note_text='kept note'):
    draft = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(300), selection=draft_selection(), template=daily_template(),
    )
    saved = svc.save(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(301), expected_revision=1,
        edits=(draft_note(1, note_text),), template=daily_template(),
    )
    return draft, saved


def test_stale_expected_revision_and_conflicting_replay_do_not_finalize_old_head(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    renderer = CountingRenderer()
    svc = service(environment, renderer=renderer)
    draft, saved = saved_draft(environment, svc)

    with pytest.raises(report_api.ReportError) as stale:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(302), expected_revision=1,
        )
    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(303), expected_revision=saved.revision,
        )
    with pytest.raises(report_api.ReportError) as changed_expected:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(303), expected_revision=1,
        )

    assert stale.value.code == 'REPORT_REVISION_CONFLICT'
    assert changed_expected.value.code == 'REPORT_REVISION_CONFLICT'
    assert environment.repository.list_files('report_publications') == ()


def test_missing_retained_packet_file_is_error_without_rerender_or_append(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    renderer = CountingRenderer()
    svc = service(environment, renderer=renderer)
    draft, saved = saved_draft(environment, svc)
    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(310), expected_revision=saved.revision,
        )
    intent = decode_json((draft_root(environment, draft.draft_id) / 'finalization.json').read_bytes())
    (draft_root(environment, draft.draft_id) / 'finalization-files' / intent['publication_id'] / 'report.txt').unlink()

    with pytest.raises(report_api.ReportError) as error:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(310), expected_revision=saved.revision,
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert renderer.calls == 1
    assert environment.repository.list_files('report_publications') == ()


def test_corrupt_committed_manifest_is_not_treated_as_absent_for_replay(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    renderer = CountingRenderer()
    svc = service(environment, renderer=renderer)
    draft = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(315), selection=draft_selection(), template=daily_template(),
    )
    publication = svc.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(316), expected_revision=1,
    )
    manifest_path = environment.repository.archive / f'report_publications/{publication.manifest.publication_id}/manifest.json'
    manifest_path.write_text('{}', encoding='utf-8')

    with pytest.raises(report_api.ReportError) as error:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(316), expected_revision=1,
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert renderer.calls == 1


def test_source_change_between_check_and_final_lock_refuses_before_append(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    source = RacingSourceReader(environment)
    svc = service(environment, source=source)
    draft = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(320), selection=draft_selection(), template=daily_template(),
    )
    source.armed = True

    with pytest.raises(report_api.ReportError) as error:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(321), expected_revision=1,
        )

    assert error.value.code == 'REPORT_SOURCE_CHANGED'
    assert environment.repository.list_files('report_publications') == ()


def test_edit_history_keeps_removed_revision_edits_but_final_view_uses_current(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    svc = service(environment)
    draft, saved = saved_draft(environment, svc, note_text='removed note')
    current = svc.save(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(331), expected_revision=saved.revision, edits=(), template=daily_template(),
    )
    publication = svc.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(332), expected_revision=current.revision,
    )

    edits = decode_json(read_bytes(
        environment.repository.archive,
        f'report_publications/{publication.manifest.publication_id}/edits.json',
    ))
    assert b'removed note' not in svc.read_artifact(
        environment.actor, environment.project.id, environment.stage.id, publication.manifest.publication_id, 'plain_text'
    )
    assert [item['revision'] for item in edits['revisions']] == [1, 2, 3]
    assert edits['revisions'][1]['edits'][0]['text'] == 'removed note'
    assert edits['revisions'][2]['edits'] == []


def test_git_growth_admission_happens_before_append_record(tmp_path, monkeypatch):
    environment = DraftArchive(tmp_path / 'archive-root')
    svc = service(environment)
    draft = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(335), selection=draft_selection(), template=daily_template(),
    )
    from project_management.storage import report_publication_packets

    original_admit = report_publication_packets.admit
    calls = {'append': 0}
    original_append = environment.repository.append_record

    def fail_commit_growth(root, stage_root, capture_root, limits, growth, *, consume_reserved=False):
        if growth.files >= 32:
            raise ArchiveError('ARCHIVE_QUOTA_EXCEEDED')
        return original_admit(root, stage_root, capture_root, limits, growth, consume_reserved=consume_reserved)

    def count_append(*args, **kwargs):
        calls['append'] += 1
        return original_append(*args, **kwargs)

    monkeypatch.setattr(report_publication_packets, 'admit', fail_commit_growth)
    monkeypatch.setattr(environment.repository, 'append_record', count_append)

    with pytest.raises(report_api.ReportError) as error:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(336), expected_revision=1,
        )

    assert error.value.code == 'REPORT_LIMIT'
    assert calls['append'] == 0
    assert not (draft_root(environment, draft.draft_id) / 'finalization.json').exists()


def test_public_download_formats_and_cross_project_copied_publication_are_refused(tmp_path):
    first = DraftArchive(tmp_path / 'first-root')
    first_service = service(first)
    draft = first_service.create(
        first.actor, first.project.id, first.stage.id,
        command_id=draft_command(340), selection=draft_selection(), template=daily_template(),
    )
    publication = first_service.finalize_and_commit(
        first.actor, first.project.id, first.stage.id, draft.draft_id,
        command_id=draft_command(341), expected_revision=1,
    )
    publication_id = publication.manifest.publication_id
    assert first_service.read_artifact(first.actor, first.project.id, first.stage.id, publication_id, 'html').startswith(b'<!doctype html>')
    assert b'Revision hash:' in first_service.read_artifact(first.actor, first.project.id, first.stage.id, publication_id, 'plain_text')
    with pytest.raises(report_api.ReportError):
        first_service.read_artifact(first.actor, first.project.id, first.stage.id, publication_id, 'snapshot.json')

    second = DraftArchive(tmp_path / 'second-root')
    prefix = f'report_publications/{publication_id}'
    copied = {
        path: read_bytes(first.repository.archive, path)
        for path in first.repository.list_files(prefix)
    }
    second.repository.append_record(
        publication_id, 'report_publications', copied,
        expected_head=second.repository.head(), record_fingerprint='0' * 64,
    )
    with pytest.raises(report_api.ReportError) as copied_error:
        service(second).get_publication(second.actor, second.project.id, second.stage.id, publication_id)
    assert copied_error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_corrupt_retained_intent_metadata_refuses_without_rerender_or_append(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    renderer = CountingRenderer()
    svc = service(environment, renderer=renderer)
    draft = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(345), selection=draft_selection(), template=daily_template(),
    )
    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(346), expected_revision=1,
        )
    intent_path = draft_root(environment, draft.draft_id) / 'finalization.json'
    intent = decode_json(intent_path.read_bytes())
    intent['request_hash'] = '0' * 64
    intent_path.write_bytes(canonical_bytes(intent))

    with pytest.raises(report_api.ReportError) as error:
        svc.resume_finalization(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(346),
        )

    assert error.value.code == 'REPORT_REVISION_CONFLICT'
    assert renderer.calls == 1
    assert environment.repository.list_files('report_publications') == ()


def test_git_lookup_failure_is_not_treated_as_absent_publication(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    svc = service(environment)
    draft = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(347), selection=draft_selection(), template=daily_template(),
    )
    calls = {'append': 0}
    original = environment.repository.append_record

    def count_append(*args, **kwargs):
        calls['append'] += 1
        return original(*args, **kwargs)

    environment.repository.fail_find_commit_once = True
    environment.repository.append_record = count_append
    with pytest.raises(report_api.ReportError) as error:
        svc.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(348), expected_revision=1,
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert calls['append'] == 0


def test_repeated_same_source_baseline_ignores_capture_metadata_but_not_partial_coverage(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    svc = service(environment)
    original = svc.create(
        environment.actor, environment.project.id, environment.stage.id,
        command_id=draft_command(350), selection=draft_selection(), template=daily_template(),
    )
    publication = svc.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, original.draft_id,
        command_id=draft_command(351), expected_revision=1,
    )
    new_selection = replace(draft_selection(), baseline_publication_id=publication.manifest.publication_id)
    repeated_source = StaticSourceReader(
        source_commit=environment.repository.head(),
        rule_hash=environment.stage.definition_hash,
    )
    repeated = repeated_source.read(
        environment.actor, environment.project.id, environment.stage.id, new_selection,
    )
    source_hashes = {row.source_key: row.source_hash for row in repeated.rows}

    def chain_with(values):
        return tuple(SimpleNamespace(capture_id=capture_id, source_hash=source_hash, complete=complete)
                     for capture_id, source_hash, complete in values)

    environment.repository.publication_source_chain = lambda source_key: chain_with((
        (original.snapshot.capture_id, source_hashes[source_key], True),
        ('11111111-1111-4111-8111-111111111111', 'f' * 64, True),
        (new_selection.capture_id, source_hashes[source_key], True),
    ))
    with pytest.raises(report_api.ReportError):
        ReportPublicationResolver(environment).same_source_baseline(
            environment.repository, repeated, publication.manifest.publication_id,
        )

    environment.repository.publication_source_chain = lambda source_key: chain_with((
        (original.snapshot.capture_id, source_hashes[source_key], True),
        (new_selection.capture_id, source_hashes[source_key], True),
    ))
    partial_snapshot = replace(StaticSourceReader().snapshot, coverage={'complete': False})
    resolved = ReportPublicationResolver(environment).same_source_baseline(
        environment.repository, repeated, publication.manifest.publication_id,
    )

    assert resolved.coverage['comparison_state'] == 'no_change'
    with pytest.raises(report_api.ReportError):
        partial = StaticSourceReader(
            snapshot=partial_snapshot,
            source_commit=environment.repository.head(),
            rule_hash=environment.stage.definition_hash,
        )
        ReportPublicationResolver(environment).same_source_baseline(
            environment.repository,
            partial.read(environment.actor, environment.project.id, environment.stage.id, replace(
                draft_selection(), baseline_publication_id=publication.manifest.publication_id,
            )),
            publication.manifest.publication_id,
        )
