import hashlib
from importlib import metadata
from pathlib import Path
from shutil import copy2, copytree
from types import SimpleNamespace

import ai_base_application_sdk
import pytest

from project_management.tests.test_project_full_stack_lifecycle import prepared_run_without_services
from scripts.validation import project_full_stack
from scripts.validation.project_full_stack_support import read_json, write_json
from scripts.validation.project_summary_support import verify_installed_sdk


WORK = Path(__file__).resolve().parents[2] / '.tmp/sdk-020-join-20261105'
SDK_SHA = '1ab6c7aa7255abeb4637734f65613827d39593ff72b7ef9d630885922c2dd134'


def test_should_admit_new_sdk_fixture_without_reusing_a_legacy_run():
    assert project_full_stack.qualify_work_root(WORK) == WORK.resolve()


def test_should_verify_all_installed_sdk020_bytes_against_selected_wheel():
    assert verify_installed_sdk(WORK, ai_base_application_sdk) == SDK_SHA


def test_should_refuse_unknown_sdk_selection_before_loading_the_wheel(tmp_path):
    value = read_json(WORK / 'sdk-selection.json')
    value['sdk_version'] = '0.2.0a2'
    write_json(tmp_path / 'sdk-selection.json', value)

    with pytest.raises(ValueError, match='SDK selection'):
        verify_installed_sdk(tmp_path, ai_base_application_sdk)


def test_should_refuse_selected_wheel_tampering(tmp_path):
    copy2(WORK / 'sdk-selection.json', tmp_path / 'sdk-selection.json')
    wheel = tmp_path / 'artifacts/ai_base_application_sdk-0.2.0a1-py3-none-any.whl'
    wheel.parent.mkdir()
    wheel.write_bytes(b'not the released wheel')

    with pytest.raises(ValueError, match='wheel digest'):
        verify_installed_sdk(tmp_path, ai_base_application_sdk)


def test_should_refuse_changed_sdk_module_beyond_the_old_two_file_check(tmp_path, monkeypatch):
    package = Path(ai_base_application_sdk.__file__).resolve().parent
    changed = tmp_path / 'ai_base_application_sdk'
    copytree(package, changed)
    metadata_name = 'ai_base_application_sdk-0.2.0a1.dist-info'
    copytree(package.parent / metadata_name, tmp_path / metadata_name)
    distribution = metadata.PathDistribution(tmp_path / metadata_name)
    monkeypatch.setattr(metadata, 'distribution', lambda name: distribution)
    candidate = SimpleNamespace(__file__=changed / '__init__.py')
    assert verify_installed_sdk(WORK, candidate) == SDK_SHA
    (changed / 'validation.py').write_text('INVALID = True\n', encoding='utf-8')

    with pytest.raises(ValueError, match='Installed SDK bytes'):
        verify_installed_sdk(WORK, candidate)


def test_should_refuse_manifest_claiming_legacy_sdk_for_new_fixture(tmp_path):
    run_dir = selected_run(tmp_path)
    manifest = read_json(run_dir / 'runtime-manifest.json')
    manifest['sdk_version'] = '0.1.0a2'
    write_json(run_dir / 'runtime-manifest.json', manifest, replace=True)

    with pytest.raises(ValueError, match='SDK identity'):
        project_full_stack.trusted_manifest(run_dir)


def test_should_refuse_retagging_legacy_run_by_relocation(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    original = (run_dir / 'runtime-manifest.json').read_bytes()

    with pytest.raises(ValueError, match='SDK selection'):
        project_full_stack.relocate_work_root(SimpleNamespace(run_dir=run_dir, work_root=WORK))

    assert (run_dir / 'runtime-manifest.json').read_bytes() == original


def test_should_accept_new_manifest_with_selected_interpreter_and_pack(tmp_path):
    run_dir = selected_run(tmp_path)

    manifest = project_full_stack.trusted_manifest(run_dir)

    assert manifest['sdk_version'] == '0.2.0a1'
    assert manifest['sdk_wheel_sha256'] == SDK_SHA


def selected_run(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    manifest = read_json(run_dir / 'runtime-manifest.json')
    manifest.update(
        base_source=str(WORK / 'base-source'),
        pack_root=str(WORK / 'artifacts/contract-pack'),
        sdk_version='0.2.0a1',
        sdk_wheel_sha256=SDK_SHA,
        sdk_selection_sha256=hashlib.sha256((WORK / 'sdk-selection.json').read_bytes()).hexdigest(),
    )
    write_json(run_dir / 'runtime-manifest.json', manifest, replace=True)
    return run_dir
