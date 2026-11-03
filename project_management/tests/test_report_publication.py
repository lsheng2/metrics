from dataclasses import replace
import unittest

import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.capture_values import decode_json
from project_management.storage.paths import write_bytes
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
from project_management.tests.report_source_fixtures import ReportSourceScenario
from project_management.services.report_sources import ReportSourceReader


FILES = ('edits.json', 'manifest.json', 'report.html', 'report.txt', 'snapshot.json', 'template.json')


class CountingRenderer(report_api.ReportRenderer):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def render(self, *args, **kwargs):
        self.calls += 1
        return super().render(*args, **kwargs)


def build_service(environment, *, source=None, renderer=None):
    return report_api.ReportDraftService(
        environment,
        source or StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        renderer or CountingRenderer(),
        clock=FixedClock(),
    )


class TestReportPublicationIntegration(ReportSourceScenario, unittest.TestCase):
    def test_only_confirmation_commits_exact_selected_revision(self):
        with self.archive_service() as (root, archive):
            captured = self.capture_summary_source(archive)
            self.accept_summary(archive, captured.source_key)
            before_head = self.archive_head(root)
            service = report_api.ReportDraftService(
                archive,
                ReportSourceReader(archive, self.contract),
                report_api.ReportRenderer(),
                clock=FixedClock(),
            )

            draft = service.create(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(100),
                selection=report_api.ReportSelection(capture_id=captured.capture_id),
                template=daily_template(),
            )
            saved = service.save(
                self.actor,
                self.project.id,
                self.stage.id,
                draft.draft_id,
                command_id=draft_command(101),
                expected_revision=1,
                edits=(draft_note(1),),
                template=daily_template(),
            )
            preview = service.render(self.actor, self.project.id, self.stage.id, draft.draft_id, revision=2)

            self.assertEqual(before_head, self.archive_head(root))
            publication = service.finalize_and_commit(
                self.actor,
                self.project.id,
                self.stage.id,
                draft.draft_id,
                command_id=draft_command(102),
                expected_revision=saved.revision,
            )

            publication_root = f'report_publications/{publication.manifest.publication_id}'
            self.assertEqual(tuple(f'{publication_root}/{name}' for name in FILES), tuple(
                path for path in self.archive_files(root) if path.startswith(publication_root)
            ))
            self.assertEqual(saved.revision_hash, publication.manifest.draft_revision_hash)
            self.assertEqual(preview.revision_hash, publication.manifest.draft_revision_hash)
            self.assertEqual(publication.commit_id, self.git_text(
                self.archive_path(root), 'log', '-n', '1', '--format=%H', 'main', '--',
                f'{publication_root}/manifest.json',
            ))
            manifest = decode_json((self.archive_path(root) / publication_root / 'manifest.json').read_bytes())
            self.assertNotIn('commit_id', manifest)
            self.assertNotIn('manifest_sha256', manifest)
            self.assertNotIn('manifest.json', manifest['file_hashes'])
            self.assertIn(draft_note(1).text, service.read_artifact(
                self.actor, self.project.id, self.stage.id, publication.manifest.publication_id, 'plain_text'
            ).decode('utf-8'))
            self.assertEqual(publication.commit_id, archive.read_report_publication(
                self.actor, self.project.id, self.stage.id, publication.manifest.publication_id
            ).commit_id)
            self.assertEqual((publication.manifest.publication_id,), tuple(
                item.manifest.publication_id
                for item in archive.list_report_publications(self.actor, self.project.id, self.stage.id)
            ))
            baseline_draft = service.create(
                self.actor,
                self.project.id,
                self.stage.id,
                command_id=draft_command(103),
                selection=report_api.ReportSelection(
                    capture_id=captured.capture_id,
                    baseline_publication_id=publication.manifest.publication_id,
                ),
                template=daily_template(),
            )
            self.assertEqual('no_change', baseline_draft.snapshot.coverage['comparison_state'])


def test_duplicate_finalize_and_crash_replay_retained_packet_without_rerender(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    renderer = CountingRenderer()
    source = StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
    service = build_service(environment, source=source, renderer=renderer)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(110),
        selection=draft_selection(),
        template=daily_template(),
    )
    saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(111),
        expected_revision=1,
        edits=(draft_note(2),),
        template=daily_template(),
    )

    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        service.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(112), expected_revision=saved.revision,
        )

    assert renderer.calls == 1
    resumed = service.resume_finalization(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(112),
    )
    duplicate = service.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(112), expected_revision=saved.revision,
    )

    assert renderer.calls == 1
    assert duplicate.commit_id == resumed.commit_id
    assert duplicate.manifest.publication_id == resumed.manifest.publication_id
    assert service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id).state == 'finalized'


def test_commit_failure_and_corrupt_packet_do_not_advance_publication(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(120),
        selection=draft_selection(),
        template=daily_template(),
    )
    root = draft_root(environment, draft.draft_id)
    write_bytes(root, 'finalization-files/11111111-1111-4111-8111-111111111111/report.html', b'partial', immutable=True)
    saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(121),
        expected_revision=1,
        edits=(draft_note(3),),
        template=daily_template(),
    )

    environment.repository.fail_append_once = True
    with pytest.raises(report_api.ReportError):
        service.finalize_and_commit(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(122), expected_revision=saved.revision,
        )

    intent = decode_json((root / 'finalization.json').read_bytes())
    packet = root / 'finalization-files' / intent['publication_id']
    (packet / 'report.html').write_bytes(b'corrupted')
    with pytest.raises(report_api.ReportError) as error:
        service.resume_finalization(
            environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
            command_id=draft_command(122),
        )

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'
    assert environment.repository.list_files('report_publications') == ()


def test_amendment_and_historical_export_downloads_preserve_original_bytes(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    original = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(130),
        selection=draft_selection(),
        template=daily_template(),
    )
    first = service.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, original.draft_id,
        command_id=draft_command(131), expected_revision=1,
    )
    original_html = service.read_artifact(
        environment.actor, environment.project.id, environment.stage.id, first.manifest.publication_id, 'html'
    )
    amendment_selection = replace(original.selection, parent_publication_id=first.manifest.publication_id)

    amended = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(132),
        selection=amendment_selection,
        template=daily_template(),
    )
    saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        amended.draft_id,
        command_id=draft_command(133),
        expected_revision=1,
        edits=(draft_note(4, 'Linked amendment note.'),),
        template=daily_template(),
    )
    second = service.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, amended.draft_id,
        command_id=draft_command(134), expected_revision=saved.revision,
    )
    historical = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(135),
        selection=replace(original.selection, purpose='historical_export', baseline_publication_id=None),
        template=daily_template(),
    )
    export = service.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, historical.draft_id,
        command_id=draft_command(136), expected_revision=1,
    )

    assert service.read_artifact(
        environment.actor, environment.project.id, environment.stage.id, first.manifest.publication_id, 'html'
    ) == original_html
    assert second.manifest.parent_publication_id == first.manifest.publication_id
    assert b'Linked amendment note.' in service.read_artifact(
        environment.actor, environment.project.id, environment.stage.id, second.manifest.publication_id, 'html'
    )
    assert export.manifest.purpose == 'historical_export'
    assert export.manifest.baseline_publication_id is None
