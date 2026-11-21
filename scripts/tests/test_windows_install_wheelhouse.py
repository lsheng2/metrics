import hashlib
import importlib
import json
from pathlib import Path

import pytest


def module():
    return importlib.import_module('scripts.validation.windows_install_wheelhouse')


def write_lock(path, files, *, kind='windows-wheelhouse-lock'):
    payload = {
        'schema_version': 1,
        'kind': kind,
        'files': files,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def locked_wheelhouse(tmp_path):
    root = tmp_path / 'owned'
    wheelhouse = root / 'wheels'
    wheelhouse.mkdir(parents=True)
    wheels = {
        'ai_base_runtime-0.1.1.dev5-py3-none-any.whl': b'runtime',
        'django-6.0.7-py3-none-any.whl': b'django',
    }
    for name, payload in wheels.items():
        (wheelhouse / name).write_bytes(payload)
    files = {name: hashlib.sha256(payload).hexdigest() for name, payload in wheels.items()}
    manifest = root / 'inputs/wheelhouse-lock.json'
    sha256 = write_lock(manifest, files)
    return root, wheelhouse, manifest, sha256, files


def test_wheelhouse_lock_accepts_exact_owned_top_level_wheels(locked_wheelhouse):
    root, wheelhouse, manifest, sha256, files = locked_wheelhouse
    lock = module().load_wheelhouse_lock(wheelhouse, manifest, sha256, root)
    assert lock.wheelhouse == wheelhouse
    assert lock.manifest == manifest
    assert lock.sha256 == sha256
    assert lock.files == files


@pytest.mark.parametrize('mutation', [
    'missing-wheel', 'extra-wheel', 'changed-wheel', 'changed-lock', 'unsafe-name',
    'invalid-sha', 'wrong-kind', 'outside-manifest', 'directory-wheel',
])
def test_wheelhouse_lock_rejects_unowned_or_drifted_wheelhouse(locked_wheelhouse, mutation):
    root, wheelhouse, manifest, sha256, files = locked_wheelhouse
    if mutation == 'missing-wheel':
        (wheelhouse / 'django-6.0.7-py3-none-any.whl').unlink()
    elif mutation == 'extra-wheel':
        (wheelhouse / 'extra-1.0-py3-none-any.whl').write_bytes(b'extra')
    elif mutation == 'changed-wheel':
        (wheelhouse / 'django-6.0.7-py3-none-any.whl').write_bytes(b'changed')
    elif mutation == 'changed-lock':
        manifest.write_text(manifest.read_text(encoding='utf-8') + '\n', encoding='utf-8')
    elif mutation == 'unsafe-name':
        files['../escape.whl'] = '0' * 64
        sha256 = write_lock(manifest, files)
    elif mutation == 'invalid-sha':
        files['django-6.0.7-py3-none-any.whl'] = 'not-a-sha'
        sha256 = write_lock(manifest, files)
    elif mutation == 'wrong-kind':
        sha256 = write_lock(manifest, files, kind='old-wheelhouse')
    elif mutation == 'outside-manifest':
        manifest = root.parent / 'wheelhouse-lock.json'
        sha256 = write_lock(manifest, files)
    else:
        (wheelhouse / 'django-6.0.7-py3-none-any.whl').unlink()
        (wheelhouse / 'django-6.0.7-py3-none-any.whl').mkdir()
    with pytest.raises(ValueError):
        module().load_wheelhouse_lock(wheelhouse, manifest, sha256, root)
