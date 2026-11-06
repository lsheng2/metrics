from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace

import pytest

from project_management.app.domain.captures import ArchiveError
from project_management.storage.archive_read_history import read_history
from project_management.storage.archive_read_view import GitArchiveReadView
from project_management.storage.git import GitResult, GitRunner
from project_management.storage.paths import read_bytes


def test_cached_reads_do_not_bypass_the_shared_deadline():
    now = [0.0]
    root = Path('unused')
    repository = SimpleNamespace(
        project=None, stage=None, owner_subject='test', root=root, stage_root=root,
        runtime=root, archive=root, objects=root, config=None,
        git=SimpleNamespace(run=lambda *args, **kwargs: GitResult(0, b'\0R\0' + b'a' * 40 + b'\0\0' + b'b' * 40 + b'\0')),
    )
    with GitArchiveReadView(repository, clock=lambda: now[0]) as view:
        assert view.validated(('sample',), lambda: {'a': 1}) == {'a': 1}
        now[0] = 11.0
        with pytest.raises(ArchiveError) as error:
            view.validated(('sample',), lambda: {'a': 2})
        assert error.value.code == 'ARCHIVE_STORAGE_UNAVAILABLE'


@pytest.mark.parametrize('parent', [b'b' * 40, b'b' * 40 + b' ' + b'c' * 40])
def test_incomplete_or_merged_history_is_not_a_missing_record(parent):
    data = b'\0R\0' + b'a' * 40 + b'\0' + parent + b'\0' + b'd' * 40 + b'\0\0\ncaptures/item.json\0'
    with pytest.raises(ArchiveError) as error:
        read_history(lambda *args, **kwargs: GitResult(0, data), 'a' * 40)
    assert error.value.code == 'ARCHIVE_MANIFEST_INVALID'


def test_real_hardlink_is_rejected(tmp_path):
    original = tmp_path / 'original.json'
    linked = tmp_path / 'linked.json'
    original.write_bytes(b'owned')
    linked.hardlink_to(original)
    with pytest.raises(ArchiveError) as error:
        read_bytes(tmp_path, 'linked.json')
    assert error.value.code == 'UNSAFE_PATH'


@pytest.mark.parametrize('failure', ['timeout', 'output_limit'])
def test_runner_reaps_owned_process_and_pipe_threads(tmp_path, monkeypatch, failure):
    import threading
    from project_management.storage import git

    processes, threads = [], []
    popen, thread = subprocess.Popen, threading.Thread
    script = 'import time; time.sleep(10)' if failure == 'timeout' else 'import sys; sys.stdout.buffer.write(b"x"*1000000)'

    def controlled_process(*args, **kwargs):
        process = popen([sys.executable, '-I', '-c', script], **kwargs)
        processes.append(process)
        return process

    def tracked_thread(*args, **kwargs):
        result = thread(*args, **kwargs)
        threads.append(result)
        return result

    monkeypatch.setattr(git.subprocess, 'Popen', controlled_process)
    monkeypatch.setattr(git.threading, 'Thread', tracked_thread)
    runner = GitRunner(tmp_path, tmp_path, timeout=0.2 if failure == 'timeout' else 3, output_limit=100)
    with pytest.raises(ArchiveError) as error:
        runner.run(['version'])
    assert error.value.code == 'ARCHIVE_STORAGE_UNAVAILABLE'
    assert processes and all(item.poll() is not None for item in processes)
    assert threads and all(not item.is_alive() for item in threads)


def test_completed_git_process_wakes_reader_without_polling_sleep(tmp_path, monkeypatch):
    from project_management.storage import git

    def no_sleep(*args):
        raise AssertionError('completed Git is delayed by polling sleep')

    monkeypatch.setattr(git.time, 'sleep', no_sleep)
    result = GitRunner(tmp_path, tmp_path).run(['--version'])
    assert result.stdout.startswith(b'git version ')


@pytest.mark.parametrize(('code', 'expected'), [
    ('ARCHIVE_STORAGE_UNAVAILABLE', 'REPORT_STORAGE_UNAVAILABLE'),
    ('ARCHIVE_READ_UNSUPPORTED', 'REPORT_STORAGE_UNAVAILABLE'),
    ('ARCHIVE_RAW_PAGE_INTEGRITY_FAILED', 'REPORT_ARTIFACT_INVALID'),
])
def test_draft_read_outage_is_not_reported_as_corrupt_artifact(code, expected):
    from contextlib import contextmanager
    from project_management.app.api import reports as report_api

    class UnavailableArchive:
        @contextmanager
        def _report_repository(self, *args, **kwargs):
            raise ArchiveError(code)
            yield

    service = report_api.ReportDraftService(UnavailableArchive(), None, report_api.ReportRenderer())
    with pytest.raises(report_api.ReportError) as error:
        service.get(None, None, None, '00000000-0000-4000-8000-000000000001')
    assert error.value.code == expected


def test_publication_confirmation_does_not_turn_timeout_into_corruption(tmp_path, monkeypatch):
    from project_management.app.api import reports as report_api
    from project_management.tests.report_draft_fixtures import DraftArchive, FixedClock, StaticSourceReader, draft_command
    from project_management.tests.report_render_fixtures import daily_template

    environment = DraftArchive(tmp_path / 'archive-root')
    service = report_api.ReportDraftService(
        environment, StaticSourceReader(source_commit=environment.repository.head(), rule_hash=environment.stage.definition_hash),
        report_api.ReportRenderer(), clock=FixedClock(),
    )
    draft = service.create(
        environment.actor, environment.project.id, environment.stage.id, command_id=draft_command(17800),
        selection=report_api.ReportSelection(capture_id=draft_command(17801)), template=daily_template(),
    )
    service.finalize_and_commit(
        environment.actor, environment.project.id, environment.stage.id, draft.draft_id,
        command_id=draft_command(17802), expected_revision=draft.revision,
    )

    def unavailable(*args):
        raise ArchiveError('ARCHIVE_STORAGE_UNAVAILABLE')

    monkeypatch.setattr(environment.repository, 'read_files', unavailable)
    with pytest.raises(report_api.ReportError) as error:
        service.get(environment.actor, environment.project.id, environment.stage.id, draft.draft_id)
    assert error.value.code == 'REPORT_STORAGE_UNAVAILABLE'
