import hashlib
import json
from pathlib import Path
import shutil
import subprocess

import pytest

from scripts.validation import build_report_editor_vendor as builder


ROOT = Path(__file__).resolve().parents[2]


def digest(path):
    return hashlib.sha256(path.read_bytes().replace(b'\r\n', b'\n')).hexdigest()


@pytest.fixture
def vendor_fixture(tmp_path):
    scripts = tmp_path / 'ui_web/frontend/scripts'
    scripts.mkdir(parents=True)
    for name in ('check-report-editor-vendor.mjs', 'shared.mjs'):
        shutil.copy2(ROOT / 'ui_web/frontend/scripts' / name, scripts / name)
    build = tmp_path / 'ui_web/editor_build'
    vendor = tmp_path / 'ui_web/static/js/report_editor/vendor'
    build.mkdir(parents=True)
    vendor.mkdir(parents=True)
    for name in ('report_milkdown.js', 'editor_commands.js', 'package.json', 'package-lock.json'):
        (build / name).write_text(f'synthetic {name}\n', encoding='utf-8')
    (vendor / 'milkdown.bundle.js').write_text('synthetic bundle\n', encoding='utf-8')
    meta = vendor / 'milkdown.bundle.meta.json'
    meta.write_text(json.dumps({'inputs': {
        'report_milkdown.js': {'bytes': 10},
        'editor_commands.js': {'bytes': 10},
        'node_modules/dependency/index.js': {'bytes': 10},
    }}), encoding='utf-8')
    manifest = {
        'schema_version': 2,
        'bundle': 'milkdown.bundle.js',
        'bundle_sha256': digest(vendor / 'milkdown.bundle.js'),
        'source_entry': 'ui_web/editor_build/report_milkdown.js',
        'source_entry_sha256': digest(build / 'report_milkdown.js'),
        'metafile': meta.relative_to(tmp_path).as_posix(),
        'metafile_sha256': digest(meta),
        'package_json': 'ui_web/editor_build/package.json',
        'package_json_sha256': digest(build / 'package.json'),
        'package_lock': 'ui_web/editor_build/package-lock.json',
        'package_lock_sha256': digest(build / 'package-lock.json'),
        'source_inputs_sha256': {
            f'ui_web/editor_build/{name}': digest(build / name)
            for name in ('report_milkdown.js', 'editor_commands.js')
        },
    }
    manifest_path = vendor / 'asset-manifest.json'
    manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    return tmp_path, build, vendor, manifest, manifest_path


def run_checker(root):
    return subprocess.run(
        ['node', str(root / 'ui_web/frontend/scripts/check-report-editor-vendor.mjs')],
        cwd=root, capture_output=True, text=True, timeout=20,
    )


def test_current_transitive_input_manifest_is_accepted(vendor_fixture):
    root, *_ = vendor_fixture
    result = run_checker(root)
    assert result.returncode == 0, result.stderr


def test_changed_command_module_is_refused(vendor_fixture):
    root, build, *_ = vendor_fixture
    (build / 'editor_commands.js').write_text('changed behavior\n', encoding='utf-8')
    result = run_checker(root)
    assert result.returncode != 0
    assert 'editor_commands.js' in result.stderr


@pytest.mark.parametrize('mutation', ['missing', 'extra', 'legacy'])
def test_incomplete_or_legacy_input_inventory_is_refused(vendor_fixture, mutation):
    root, _, _, manifest, path = vendor_fixture
    if mutation == 'missing':
        del manifest['source_inputs_sha256']['ui_web/editor_build/editor_commands.js']
    elif mutation == 'extra':
        manifest['source_inputs_sha256']['ui_web/editor_build/unrelated.js'] = '0' * 64
    else:
        manifest['schema_version'] = 1
        del manifest['source_inputs_sha256']
    path.write_text(json.dumps(manifest), encoding='utf-8')
    assert run_checker(root).returncode != 0


def test_manifest_producer_binds_all_first_party_metafile_inputs(vendor_fixture, monkeypatch):
    root, build, vendor, expected, _ = vendor_fixture
    values = {
        'ROOT': root, 'EDITOR_BUILD': build, 'VENDOR': vendor,
        'SOURCE_ENTRY': build / 'report_milkdown.js',
        'PACKAGE_JSON': build / 'package.json',
        'PACKAGE_LOCK': build / 'package-lock.json',
        'BUNDLE': vendor / 'milkdown.bundle.js',
        'METAFILE': vendor / 'milkdown.bundle.meta.json',
    }
    for name, value in values.items():
        monkeypatch.setattr(builder, name, value)
    payload = builder.manifest_payload()
    assert payload.get('source_inputs_sha256') == expected['source_inputs_sha256']
    assert payload['schema_version'] == 2
