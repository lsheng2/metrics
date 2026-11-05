from __future__ import annotations

from pathlib import Path
from types import SimpleNamespace

from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_support import read_json
from project_management.tests.test_project_full_stack_lifecycle import prepared_run_without_services


def test_should_accept_approved_clean_work_root_alias():
    clean = Path.cwd() / '.tmp' / 'task-run-w5-clean-merged-20261103'

    resolved = project_full_stack.qualify_work_root(clean)

    assert resolved == clean.resolve()


def test_should_relocate_manifest_to_clean_work_root_without_changing_business_identity(tmp_path):
    clean = Path.cwd() / '.tmp' / 'task-run-w5-clean-merged-20261103'
    run_dir = prepared_run_without_services(tmp_path, work=Path.cwd() / '.tmp/task-run-w5')
    before = read_json(run_dir / 'runtime-manifest.json')

    result = project_full_stack.relocate_work_root(SimpleNamespace(run_dir=run_dir, work_root=clean))

    after = read_json(run_dir / 'runtime-manifest.json')
    assert result['status'] == 'relocated'
    assert after['catalog'] == before['catalog']
    assert after['routes'] == before['routes']
    assert after['run_dir'] == before['run_dir']
    assert after['execution_mode'] == before['execution_mode']
    assert Path(after['base_source']) == clean / 'base-source'
    assert Path(after['pack_root']) == clean / 'artifacts' / 'contract-pack'
