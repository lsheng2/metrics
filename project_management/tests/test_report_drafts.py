from pathlib import Path
from dataclasses import replace
import shutil
import unittest

import portalocker
import pytest

from project_management.app.api import reports as report_api
from project_management.app.domain.contracts import ProjectActor
from project_management.app.domain.capture_values import canonical_bytes, decode_json
from project_management.app.domain.captures import ArchiveError, ArchiveLimits
from project_management.services.report_sources import ReportSourceReader
from project_management.storage.paths import read_bytes, write_bytes
from project_management.tests.report_draft_fixtures import (
    DraftArchive,
    FixedClock,
    StaticSourceReader,
    current_payload,
    draft_command,
    draft_note,
    draft_root,
    draft_selection,
)
from project_management.tests.report_render_fixtures import daily_template, safe_snapshot
from project_management.tests.report_source_fixtures import ReportSourceScenario


def build_service(environment, *, source=None, limits=None, clock=None):
    return report_api.ReportDraftService(
        environment,
        source or StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        limits=limits,
        clock=clock or FixedClock(),
    )


class TestReportDraftIntegration(ReportSourceScenario, unittest.TestCase):
    def test_HT15_save_note_creates_revision2_without_git_commit_using_real_source(self):
        with self.archive_service() as (root, archive):
            captured = self.capture_summary_source(archive)
            self.accept_summary(archive, captured.source_key)
            before_head = self.archive_head(root)
            before_status = self.archive_status(root)
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
                command_id=draft_command(1),
                selection=report_api.ReportSelection(capture_id=captured.capture_id),
                template=daily_template(),
            )
            saved = service.save(
                self.actor,
                self.project.id,
                self.stage.id,
                draft.draft_id,
                command_id=draft_command(2),
                expected_revision=1,
                edits=(draft_note(1),),
                template=daily_template(),
            )

            self.assertEqual((1, 2), (draft.revision, saved.revision))
            self.assertRegex(saved.revision_hash, r'^[a-f0-9]{64}$')
            self.assertEqual((self.actor.subject, '2026-11-02T03:01:00+00:00'), (
                saved.edits[0].author,
                saved.edits[0].edited_at,
            ))
            self.assertEqual(before_head, self.archive_head(root))
            self.assertEqual(before_status, self.archive_status(root))
            self.assertEqual(('snapshot.json',), tuple(
                path.name for path in (Path(root) / 'projects' / self.project.id / 'stages' / self.stage.id / 'runtime'
                                       / 'report-drafts' / draft.draft_id).glob('snapshot.json')
            ))


def test_HT16_create_command_replay_returns_original_revision_without_rereading_source(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    source = StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
    service = build_service(environment, source=source)
    selection = draft_selection()

    created = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(10),
        selection=selection,
        template=daily_template(),
    )
    root = draft_root(environment, created.draft_id)
    (root / 'commands' / f'{draft_command(10)}.json').unlink()
    (root / 'current.json').unlink()
    repaired_create = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(10),
        selection=selection,
        template=daily_template(),
    )
    saved = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        created.draft_id,
        command_id=draft_command(11),
        expected_revision=1,
        edits=(draft_note(2),),
        template=daily_template(),
    )
    source.snapshot = safe_snapshot(days=())
    environment.repository._head = 'd' * 40
    replay = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(10),
        selection=selection,
        template=daily_template(),
    )

    assert (created.revision, repaired_create.revision, saved.revision, replay.revision) == (1, 1, 2, 1)
    assert replay.revision_hash == created.revision_hash
    assert replay.snapshot_hash == created.snapshot_hash
    assert source.calls == 1
    with pytest.raises(report_api.ReportError) as error:
        service.create(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(10),
            selection=report_api.ReportSelection(capture_id=selection.capture_id, timezone='UTC'),
            template=daily_template(),
        )
    assert error.value.code == 'REPORT_REVISION_CONFLICT'


def test_HT16_create_recovers_after_intent_before_revision_without_rereading_source(tmp_path, monkeypatch):
    environment = DraftArchive(tmp_path / 'archive-root')
    source = StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash)
    service = build_service(environment, source=source)
    from project_management.storage import report_drafts as draft_storage

    original_write = draft_storage.write_bytes
    failure = {'armed': True}

    def fail_revision_once(root, relative, data, *, immutable=False, conflict_code='ARCHIVE_CAPTURE_CONFLICT'):
        if failure['armed'] and relative == 'revisions/00000001.json':
            failure['armed'] = False
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        return original_write(root, relative, data, immutable=immutable, conflict_code=conflict_code)

    monkeypatch.setattr(draft_storage, 'write_bytes', fail_revision_once)
    selection = draft_selection()
    with pytest.raises(report_api.ReportError):
        service.create(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(12),
            selection=selection,
            template=daily_template(),
        )

    repaired = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(12),
        selection=selection,
        template=daily_template(),
    )

    assert (repaired.revision, repaired.created_at, source.calls) == (1, '2026-11-02T03:00:00+00:00', 1)


def test_HT17_save_command_cas_repair_provenance_and_removed_notes(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    selection = draft_selection()
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(20),
        selection=selection,
        template=daily_template(),
    )
    note = draft_note(3)

    rev2 = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(21),
        expected_revision=1,
        edits=(note,),
        template=daily_template(),
    )
    root = draft_root(environment, draft.draft_id)
    write_bytes(root, 'current.json', current_payload(1, draft.revision_hash), immutable=False)
    repaired = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(21),
        expected_revision=1,
        edits=(note,),
        template=daily_template(),
    )
    unchanged = report_api.ReportEdit(
        note.edit_id,
        note.kind,
        note.target,
        note.text,
        note.expected_original_hash,
        author='caller spoof',
        edited_at='2000-01-01T00:00:00Z',
    )
    rev3 = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(22),
        expected_revision=2,
        edits=(unchanged,),
        template=daily_template(),
    )
    rev4 = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(23),
        expected_revision=3,
        edits=(),
        template=daily_template(),
    )
    replay_after_head = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(21),
        expected_revision=1,
        edits=(note,),
        template=daily_template(),
    )

    assert (rev2.revision, repaired.revision, rev3.revision, rev4.revision, replay_after_head.revision) == (2, 2, 3, 4, 2)
    assert rev3.edits[0].author == rev2.edits[0].author
    assert rev3.edits[0].edited_at == rev2.edits[0].edited_at
    assert service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id).revision == 4
    assert service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id).edits == ()
    assert service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=2).plain_text.find(note.text) >= 0
    assert service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=4).plain_text.find(note.text) == -1
    with pytest.raises(report_api.ReportError) as error:
        service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(24),
            expected_revision=1,
            edits=(note,),
            template=daily_template(),
        )
    assert error.value.code == 'REPORT_REVISION_CONFLICT'


def test_HT17_save_recovers_after_command_before_revision_with_original_timestamp(tmp_path, monkeypatch):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(25),
        selection=draft_selection(),
        template=daily_template(),
    )
    from project_management.storage import report_drafts as draft_storage

    original_write = draft_storage.write_bytes
    failure = {'armed': True}

    def fail_revision_once(root, relative, data, *, immutable=False, conflict_code='ARCHIVE_CAPTURE_CONFLICT'):
        if failure['armed'] and relative == 'revisions/00000002.json':
            failure['armed'] = False
            raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')
        return original_write(root, relative, data, immutable=immutable, conflict_code=conflict_code)

    monkeypatch.setattr(draft_storage, 'write_bytes', fail_revision_once)
    note = draft_note(7)
    with pytest.raises(report_api.ReportError):
        service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(26),
            expected_revision=1,
            edits=(note,),
            template=daily_template(),
        )

    recovered = service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(26),
        expected_revision=1,
        edits=(note,),
        template=daily_template(),
    )

    assert (recovered.revision, recovered.updated_at, recovered.edits[0].edited_at) == (
        2,
        '2026-11-02T03:02:00+00:00',
        '2026-11-02T03:01:00+00:00',
    )


def test_HT17_historical_revision_refuses_forged_canonical_revision(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(27),
        selection=draft_selection(),
        template=daily_template(),
    )
    service.save(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        draft.draft_id,
        command_id=draft_command(28),
        expected_revision=1,
        edits=(draft_note(8),),
        template=daily_template(),
    )
    revision_path = draft_root(environment, draft.draft_id) / 'revisions' / '00000001.json'
    payload = decode_json(revision_path.read_bytes())
    payload['updated_at'] = '2026-11-02T09:00:00+00:00'
    revision_path.write_bytes(canonical_bytes(payload))

    with pytest.raises(report_api.ReportError) as error:
        service.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=1)

    assert error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_HT18_corruption_wrong_owner_invalid_path_and_quota_reject_safely(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(30),
        selection=draft_selection(),
        template=daily_template(),
    )
    root = draft_root(environment, draft.draft_id)

    (root / 'revisions' / '00000001.json').write_text('{"schema_version":1,"revision":1,"edits":[]}', encoding='utf-8')
    with pytest.raises(report_api.ReportError) as corrupt:
        service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    assert corrupt.value.code == 'REPORT_ARTIFACT_INVALID'

    with pytest.raises(report_api.ReportError) as wrong_owner:
        service.get(ProjectActor('other-owner'), environment.project.id, environment.stage.id, draft.draft_id)
    assert wrong_owner.value.code == 'REPORT_NOT_FOUND'

    with pytest.raises(report_api.ReportError) as bad_path:
        service.get(environment.actor, environment.project.id, environment.stage.id, '../bad')
    assert bad_path.value.code == 'REPORT_INVALID'

    low_quota = DraftArchive(
        tmp_path / 'low-quota-root',
        limits=ArchiveLimits(1024, 1000, 1024, 1000, 1024, 1000, 1024, 1024),
    )
    with pytest.raises(report_api.ReportError) as quota:
        build_service(low_quota).create(
            low_quota.actor,
            low_quota.project.id,
            low_quota.stage.id,
            command_id=draft_command(31),
            selection=draft_selection(),
            template=daily_template(),
        )
    assert quota.value.code == 'REPORT_LIMIT'


def test_HT19_history_limit_current_hash_and_locking_fail_without_new_revision(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    limits = report_api.ReportDraftLimits(max_edit_history_bytes=128)
    service = build_service(environment, limits=limits)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(40),
        selection=draft_selection(),
        template=daily_template(),
    )

    with pytest.raises(report_api.ReportError) as history_limit:
        service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(41),
            expected_revision=1,
            edits=(draft_note(4, 'x' * 80),),
            template=daily_template(),
        )
    assert history_limit.value.code == 'REPORT_LIMIT'
    assert len(tuple((draft_root(environment, draft.draft_id) / 'revisions').glob('*.json'))) == 1

    root = draft_root(environment, draft.draft_id)
    current = decode_json(read_bytes(root, 'current.json'))
    write_bytes(root, 'current.json', current_payload(current['revision'], '0' * 64), immutable=False)
    with pytest.raises(report_api.ReportError) as corrupt_head:
        service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(42),
            expected_revision=1,
            edits=(draft_note(5),),
            template=daily_template(),
        )
    assert corrupt_head.value.code == 'REPORT_ARTIFACT_INVALID'

    write_bytes(root, 'current.json', current_payload(draft.revision, draft.revision_hash), immutable=False)
    with portalocker.Lock(environment.config.root / 'budget.lock', timeout=0, flags=portalocker.LOCK_EX | portalocker.LOCK_NB):
        with pytest.raises(report_api.ReportError) as busy:
            service.save(
                environment.actor,
                environment.project.id,
                environment.stage.id,
                draft.draft_id,
                command_id=draft_command(43),
                expected_revision=1,
                edits=(draft_note(6),),
                template=daily_template(),
            )
    assert busy.value.code == 'REPORT_ARTIFACT_INVALID'


def test_store_refuses_copied_foreign_draft_and_corrupted_source_fields(tmp_path):
    first = DraftArchive(tmp_path / 'first-root')
    second = DraftArchive(tmp_path / 'second-root')
    service = build_service(first)
    draft = service.create(
        first.actor,
        first.project.id,
        first.stage.id,
        command_id=draft_command(50),
        selection=draft_selection(),
        template=daily_template(),
    )
    shutil.copytree(draft_root(first, draft.draft_id), draft_root(second, draft.draft_id))

    with pytest.raises(report_api.ReportError) as copied_error:
        build_service(second).get(second.actor, second.project.id, second.stage.id, draft.draft_id)
    assert copied_error.value.code == 'REPORT_ARTIFACT_INVALID'

    snapshot_path = draft_root(first, draft.draft_id) / 'snapshot.json'
    snapshot = decode_json(snapshot_path.read_bytes())
    snapshot['source_commit'] = 'not-a-commit'
    snapshot_path.write_bytes(canonical_bytes(snapshot))

    with pytest.raises(report_api.ReportError) as source_error:
        service.get(first.actor, first.project.id, first.stage.id, draft.draft_id)
    assert source_error.value.code == 'REPORT_ARTIFACT_INVALID'


def test_create_refuses_malformed_source_commit_and_template_drift_rejects_render(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    bad_source = StaticSourceReader(source_commit='not-a-commit', rule_hash=environment.stage.definition_hash)
    with pytest.raises(report_api.ReportError) as bad_create:
        build_service(environment, source=bad_source).create(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(60),
            selection=draft_selection(),
            template=daily_template(),
        )
    assert bad_create.value.code == 'REPORT_ARTIFACT_INVALID'

    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(61),
        selection=draft_selection(),
        template=daily_template(),
    )

    class DriftRenderer(report_api.ReportRenderer):
        def template_definition(self, template):
            definition = super().template_definition(template)
            return replace(definition, template_hash='0' * 64)

    drifted = report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        DriftRenderer(),
        clock=FixedClock(),
    )
    with pytest.raises(report_api.ReportError) as render_error:
        drifted.render(environment.actor, environment.project.id, environment.stage.id, draft.draft_id, revision=1)
    assert render_error.value.code == 'REPORT_TEMPLATE_UNSUPPORTED'


def test_state_markers_invalid_requests_and_naive_clock_fail_safely(tmp_path):
    environment = DraftArchive(tmp_path / 'archive-root')
    service = build_service(environment)
    draft = service.create(
        environment.actor,
        environment.project.id,
        environment.stage.id,
        command_id=draft_command(70),
        selection=draft_selection(),
        template=daily_template(),
    )
    (draft_root(environment, draft.draft_id) / 'finalized.json').write_text('{}', encoding='utf-8')
    with pytest.raises(report_api.ReportError) as marker_error:
        service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    assert marker_error.value.code == 'REPORT_ARTIFACT_INVALID'

    (draft_root(environment, draft.draft_id) / 'finalized.json').unlink()
    with pytest.raises(report_api.ReportError) as edit_error:
        service.save(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            draft.draft_id,
            command_id=draft_command(71),
            expected_revision=1,
            edits=object(),
            template=daily_template(),
        )
    assert edit_error.value.code == 'REPORT_INVALID'

    from datetime import datetime

    naive = report_api.ReportDraftService(
        environment,
        StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(),
        clock=lambda: datetime(2026, 11, 2, 3, 0, 0),
    )
    with pytest.raises(report_api.ReportError) as clock_error:
        naive.create(
            environment.actor,
            environment.project.id,
            environment.stage.id,
            command_id=draft_command(72),
            selection=draft_selection(),
            template=daily_template(),
        )
    assert clock_error.value.code == 'REPORT_INVALID'
