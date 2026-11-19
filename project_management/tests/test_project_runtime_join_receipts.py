import sys
from uuid import uuid4

import django
import pytest

from scripts.validation import project_runtime_join as join
from scripts.validation.project_full_stack_support import (
    ensure_data_root, initialize_run_dir, read_json, write_json,
)


@pytest.fixture
def controlled_run(tmp_path, monkeypatch):
    root = ensure_data_root(tmp_path / 'data')
    run_dir = root / str(uuid4())
    run_dir.mkdir()
    initialize_run_dir(run_dir, root)
    monkeypatch.setattr(join.project_full_stack, 'trusted_manifest', lambda path: {'scenario': 'single'})
    monkeypatch.setattr(join, 'source_identity', lambda: {'commit': 'synthetic-source'})
    monkeypatch.setattr(django, 'setup', lambda: None)
    monkeypatch.setattr('ai_host.admission.admit_runtime_candidate', lambda: {
        'version': 'synthetic-version', 'wheelSha256': 'synthetic-wheel', 'sourceCommit': 'synthetic-source',
    })
    monkeypatch.setenv('DJANGO_SETTINGS_MODULE', 'synthetic')
    monkeypatch.setenv('METRICS_PROJECT_FULL_STACK_RUN_DIR', str(run_dir))
    monkeypatch.delenv('METRICS_PROJECT_FULL_STACK_BOOTSTRAP', raising=False)
    return run_dir


def invoke(monkeypatch, run_dir, action):
    monkeypatch.setattr(sys, 'argv', ['project_runtime_join.py', action, '--run-dir', str(run_dir)])
    return join.main()


def test_reopen_keeps_each_receipt_without_overwriting_prior_evidence(controlled_run, monkeypatch):
    run_dir = controlled_run
    original = {'status': 'passed', 'result': {'operation_id': 'original-run'}}
    write_json(run_dir / 'evidence/runtime-join.json', original)
    write_json(run_dir / 'evidence/runtime-reopen.json', original)
    monkeypatch.setattr(join, 'reopen_case', lambda *args: {'state': 'passed', 'operation_id': 'original-run'})

    assert invoke(monkeypatch, run_dir, 'reopen') == 0
    assert invoke(monkeypatch, run_dir, 'reopen') == 0

    receipts = list((run_dir / 'evidence').glob('runtime-reopen-*/receipt.json'))
    assert len(receipts) == 2
    assert all(read_json(path)['status'] == 'passed' for path in receipts)
    assert read_json(run_dir / 'evidence/runtime-join.json') == original
    assert read_json(run_dir / 'evidence/runtime-reopen.json') == original


def test_failed_reopen_preserves_original_exception_and_failure_receipt(controlled_run, monkeypatch):
    def failed(*args):
        raise RuntimeError('synthetic operation failure')

    monkeypatch.setattr(join, 'reopen_case', failed)
    with pytest.raises(RuntimeError, match='synthetic operation failure'):
        invoke(monkeypatch, controlled_run, 'reopen')

    receipt, = (controlled_run / 'evidence').glob('runtime-reopen-*/receipt.json')
    assert read_json(receipt)['status'] == 'failed'
    assert read_json(receipt)['error'] == 'RuntimeError'


def test_join_marker_collision_does_not_leave_success_receipt(controlled_run, monkeypatch):
    marker = controlled_run / 'evidence/runtime-join.json'
    original = {'status': 'passed', 'result': {'operation_id': 'other-run'}}

    def colliding_run(*args):
        write_json(marker, original)
        return {'state': 'passed', 'operation_id': 'new-run'}

    monkeypatch.setattr(join, 'run_case', colliding_run)
    with pytest.raises(FileExistsError) as failure:
        invoke(monkeypatch, controlled_run, 'run')

    assert failure.value.filename == str(marker)
    receipt, = (controlled_run / 'evidence').glob('runtime-run-*/receipt.json')
    assert read_json(receipt)['status'] == 'failed'
    assert read_json(marker) == original


def test_completed_join_cannot_be_dispatched_again(controlled_run, monkeypatch):
    write_json(controlled_run / 'evidence/runtime-join.json', {'status': 'passed'})

    def forbidden(*args):
        raise AssertionError('completed join must not dispatch')

    monkeypatch.setattr(join, 'run_case', forbidden)
    with pytest.raises(ValueError, match='cannot be relabeled or repeated'):
        invoke(monkeypatch, controlled_run, 'run')

    assert not list((controlled_run / 'evidence').glob('runtime-run-*'))
