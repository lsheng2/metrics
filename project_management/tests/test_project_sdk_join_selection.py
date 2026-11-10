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


def test_should_admit_only_the_prepared_sdk020_work_root(tmp_path):
    assert project_full_stack.qualify_work_root(WORK) == WORK.resolve()
    copy = tmp_path / WORK.name
    copy.mkdir()

    with pytest.raises(ValueError, match='work root'):
        project_full_stack.qualify_work_root(copy)


def test_should_refuse_work_root_without_sdk_selection(tmp_path):
    with pytest.raises(ValueError, match='SDK selection'):
        verify_installed_sdk(tmp_path, ai_base_application_sdk)


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


def test_should_refuse_manifest_with_unselected_sdk_version(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    manifest = read_json(run_dir / 'runtime-manifest.json')
    manifest['sdk_version'] = '0.1.0a2'
    write_json(run_dir / 'runtime-manifest.json', manifest, replace=True)

    with pytest.raises(ValueError, match='SDK identity'):
        project_full_stack.trusted_manifest(run_dir)


def test_should_refuse_manifest_from_another_work_root(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)
    other = tmp_path / 'other-root' / 'base-source'
    other.mkdir(parents=True)
    manifest = read_json(run_dir / 'runtime-manifest.json')
    manifest['base_source'] = str(other)
    write_json(run_dir / 'runtime-manifest.json', manifest, replace=True)

    with pytest.raises(ValueError, match='work root'):
        project_full_stack.trusted_manifest(run_dir)


def test_should_accept_new_manifest_with_selected_interpreter_and_pack(tmp_path):
    run_dir = prepared_run_without_services(tmp_path)

    manifest = project_full_stack.trusted_manifest(run_dir)

    assert manifest['sdk_version'] == '0.2.0a1'
    assert manifest['sdk_wheel_sha256'] == SDK_SHA
