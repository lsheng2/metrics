import hashlib
import importlib
import json
from pathlib import Path
import subprocess
import sys
import zipfile

import pytest


PINS = {
    'ai-base-runtime': '0.1.1.dev5',
    'django': '6.0.7',
    'whitenoise': '6.12.0',
    'waitress': '3.0.2',
    'portalocker': '4.4.2',
    'pytest': '9.2.0',
    'pytest-asyncio': '1.5.0',
    'pytest-django': '4.12.0',
    'playwright': '1.57.0',
}


def module():
    return importlib.import_module('scripts.validation.windows_install_smoke')


def write_lock(path, files):
    payload = {
        'schema_version': 1,
        'kind': 'windows-wheelhouse-lock',
        'files': files,
    }
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, sort_keys=True), encoding='utf-8')
    return hashlib.sha256(path.read_bytes()).hexdigest()


@pytest.fixture
def install_input(tmp_path, monkeypatch):
    installer = module()
    source, root = tmp_path / 'source', tmp_path / 'owned'
    (source / 'ai_host').mkdir(parents=True)
    (root / 'wheels').mkdir(parents=True)
    monkeypatch.setattr(installer, 'ROOT', source)
    wheel = root / 'wheels/ai_base_runtime-0.1.1.dev5-py3-none-any.whl'
    payload = b'# synthetic runtime\n'
    with zipfile.ZipFile(wheel, 'w') as archive:
        archive.writestr('ai_base_runtime/__init__.py', payload)
        archive.writestr('ai_base_runtime-0.1.1.dev5.dist-info/METADATA',
                         'Metadata-Version: 2.3\nName: ai-base-runtime\nVersion: 0.1.1.dev5\n')
    digest = hashlib.sha256(wheel.read_bytes()).hexdigest()
    dependency = root / 'wheels/django-6.0.7-py3-none-any.whl'
    dependency.write_bytes(b'synthetic dependency wheel')
    lock = root / 'inputs/wheelhouse-lock.json'
    lock_sha256 = write_lock(lock, {
        wheel.name: digest,
        dependency.name: hashlib.sha256(dependency.read_bytes()).hexdigest(),
    })
    manifest = {
        'distribution': 'ai-base-runtime', 'version': '0.1.1.dev5', 'wheelSha256': digest,
        'packageFiles': {'ai_base_runtime/__init__.py': hashlib.sha256(payload).hexdigest()},
    }
    (source / 'ai_host/runtime_artifact.json').write_text(json.dumps(manifest), encoding='utf-8')
    (source / 'requirements.txt').write_text(
        'sd-metrics-lib[azure,jira]==7.1.0\n'
        + ''.join(f'{name}=={version}\n' for name, version in PINS.items()), encoding='utf-8',
    )
    (root / 'owner.json').write_text(json.dumps({
        'owner': 'mdb2-windows-closure', 'root': str(root), 'repository': str(source),
    }), encoding='utf-8')
    inputs = {
        'schema_version': 1,
        'source': {'repository': str(source)},
        'owned_root': {'path': str(root), 'marker': str(root / 'owner.json')},
        'candidate': {'wheel': str(wheel), 'version': '0.1.1.dev5', 'wheel_sha256': digest},
        'python': {'bootstrap': sys.executable, 'new_environment_root': str(root / 'venv')},
        'wheelhouse': {
            'path': str(root / 'wheels'),
            'manifest': {'path': str(lock), 'sha256': lock_sha256},
        },
    }
    path = source / 'inputs.json'
    path.write_text(json.dumps(inputs), encoding='utf-8')
    return installer, inputs, path, root, source


def test_valid_input_does_not_create_environment_before_validation(install_input):
    installer, inputs, path, root, source = install_input
    request = installer.load_request(path, root / 'evidence/result.json')
    assert request.wheel == Path(inputs['candidate']['wheel'])
    assert request.environment == root / 'venv'
    assert request.requirements == source / 'requirements.txt'
    assert request.wheelhouse_manifest == root / 'inputs/wheelhouse-lock.json'
    assert request.wheelhouse_manifest_sha256 == inputs['wheelhouse']['manifest']['sha256']
    assert not request.environment.exists()
    assert not (root / 'evidence').exists()


@pytest.mark.parametrize('mutation', [
    'wheel-hash', 'wheel-version', 'missing-wheel', 'outside-environment',
    'existing-environment', 'wrong-owner', 'foreign-source', 'outside-output',
    'incomplete-manifest', 'package-hash', 'existing-output', 'missing-lock',
    'lock-hash', 'lock-outside-root', 'lock-extra-wheel', 'lock-changed-wheel',
    'lock-unsafe-name', 'lock-invalid-schema',
])
def test_invalid_input_cannot_write_or_start_an_installer(install_input, mutation):
    installer, inputs, path, root, source = install_input
    output = root / 'evidence/result.json'
    if mutation == 'wheel-hash':
        inputs['candidate']['wheel_sha256'] = 'f' * 64
    elif mutation == 'wheel-version':
        inputs['candidate']['version'] = '0.0.0'
    elif mutation == 'missing-wheel':
        Path(inputs['candidate']['wheel']).unlink()
    elif mutation == 'outside-environment':
        inputs['python']['new_environment_root'] = str(root.parent / 'foreign')
    elif mutation == 'existing-environment':
        (root / 'venv').mkdir()
        (root / 'venv/user-file').write_text('retain', encoding='utf-8')
    elif mutation == 'wrong-owner':
        (root / 'owner.json').write_text('{}', encoding='utf-8')
    elif mutation == 'foreign-source':
        inputs['source']['repository'] = str(source.parent)
    elif mutation in {'incomplete-manifest', 'package-hash'}:
        manifest_path = source / 'ai_host/runtime_artifact.json'
        manifest = json.loads(manifest_path.read_text())
        if mutation == 'incomplete-manifest':
            manifest['packageFiles'] = {}
        else:
            manifest['packageFiles']['ai_base_runtime/__init__.py'] = '0' * 64
        manifest_path.write_text(json.dumps(manifest), encoding='utf-8')
    elif mutation == 'existing-output':
        output.parent.mkdir()
        output.write_text('retain', encoding='utf-8')
    elif mutation == 'missing-lock':
        del inputs['wheelhouse']['manifest']
    elif mutation == 'lock-hash':
        inputs['wheelhouse']['manifest']['sha256'] = 'f' * 64
    elif mutation == 'lock-outside-root':
        lock = source / 'wheelhouse-lock.json'
        inputs['wheelhouse']['manifest'] = {'path': str(lock), 'sha256': write_lock(lock, {})}
    elif mutation == 'lock-extra-wheel':
        (root / 'wheels/extra-1.0-py3-none-any.whl').write_bytes(b'extra')
    elif mutation == 'lock-changed-wheel':
        (root / 'wheels/django-6.0.7-py3-none-any.whl').write_bytes(b'changed')
    elif mutation == 'lock-unsafe-name':
        lock = Path(inputs['wheelhouse']['manifest']['path'])
        payload = json.loads(lock.read_text(encoding='utf-8'))
        payload['files']['../escape.whl'] = '0' * 64
        lock.write_text(json.dumps(payload), encoding='utf-8')
        inputs['wheelhouse']['manifest']['sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
    elif mutation == 'lock-invalid-schema':
        lock = Path(inputs['wheelhouse']['manifest']['path'])
        payload = json.loads(lock.read_text(encoding='utf-8'))
        payload['kind'] = 'old-wheelhouse'
        lock.write_text(json.dumps(payload), encoding='utf-8')
        inputs['wheelhouse']['manifest']['sha256'] = hashlib.sha256(lock.read_bytes()).hexdigest()
    else:
        output = source / 'forbidden.json'
    path.write_text(json.dumps(inputs), encoding='utf-8')
    with pytest.raises(ValueError):
        installer.load_request(path, output)
    if mutation == 'existing-output':
        assert output.read_text() == 'retain'
    else:
        assert not output.exists()
    if mutation == 'existing-environment':
        assert (root / 'venv/user-file').read_text(encoding='utf-8') == 'retain'


def test_repository_dependency_pins_support_the_candidate():
    installer = module()
    versions = installer.validate_requirements(installer.ROOT / 'requirements.txt')
    assert all(versions[name] == version for name, version in PINS.items())
    assert 'gunicorn' not in versions


def test_requirements_reject_runtime_extras_but_keep_sd_metrics_extras(install_input):
    installer, _, _, _, source = install_input
    path = source / 'requirements.txt'
    text = path.read_text(encoding='utf-8')
    assert text.startswith('sd-metrics-lib[azure,jira]==7.1.0')
    path.write_text(text.replace('ai-base-runtime==', 'ai-base-runtime[rag]=='), encoding='utf-8')
    with pytest.raises(ValueError):
        installer.validate_requirements(path)


def test_requirements_must_not_resolve_runtime_from_a_range(install_input):
    installer, _, _, _, source = install_input
    path = source / 'requirements.txt'
    path.write_text(path.read_text().replace('ai-base-runtime==', 'ai-base-runtime>='), encoding='utf-8')
    with pytest.raises(ValueError):
        installer.validate_requirements(path)


def test_run_install_rechecks_wheelhouse_lock_before_environment_creation(install_input, monkeypatch):
    installer, _, path, root, _ = install_input
    output = root / 'evidence/result.json'
    request = installer.load_request(path, output)
    (root / 'wheels/django-6.0.7-py3-none-any.whl').write_bytes(b'changed after admission')

    def unexpected_spawn(*args, **kwargs):
        raise AssertionError('installer must validate the lock before spawning subprocesses')

    monkeypatch.setattr(installer.shutil, 'which', lambda name: 'C:/Windows/System32/git.exe')
    monkeypatch.setattr(installer.subprocess, 'run', unexpected_spawn)
    assert installer.run_install(request) == 1
    receipt = json.loads(output.read_text(encoding='utf-8'))
    assert receipt['result'] == 'FAIL'
    assert receipt['wheelhouse']['manifest']['path'] == str(request.wheelhouse_manifest)
    assert receipt['wheelhouse']['manifest']['sha256'] == request.wheelhouse_manifest_sha256
    assert not request.environment.exists()


def test_network_acquisition_keeps_proxy_but_not_user_configuration_or_credentials():
    installer = module()
    clean = {'HOME': 'private', 'PIP_CONFIG_FILE': 'nul'}
    inherited = {
        'HTTPS_PROXY': 'http://proxy.example.test:8080', 'http_proxy': 'http://proxy.example.test:8080',
        'PIP_INDEX_URL': 'https://synthetic-token@example.test/simple',
        'GENAI_API_KEY': 'synthetic-secret', 'PYTHONPATH': 'old-environment', 'HOME': 'user-home',
    }
    acquired = installer.acquisition_environment(clean, inherited)
    assert acquired == {
        **clean, 'HTTPS_PROXY': 'http://proxy.example.test:8080', 'http_proxy': 'http://proxy.example.test:8080',
    }
    assert clean == {'HOME': 'private', 'PIP_CONFIG_FILE': 'nul'}


def test_private_installer_environment_confines_windows_cache_paths(tmp_path):
    installer = module()
    environment = installer.installer_environment(tmp_path)
    assert Path(environment['APPDATA']).is_relative_to(tmp_path)
    assert Path(environment['LOCALAPPDATA']).is_relative_to(tmp_path)
    assert environment['PIP_CONFIG_FILE'] == 'nul'
    assert environment['PYTHONNOUSERSITE'] == '1'


def test_source_guard_detects_unexpected_untracked_download_cache(tmp_path, monkeypatch):
    installer = module()
    subprocess.run(['git', 'init', str(tmp_path)], check=True, capture_output=True, timeout=15)
    monkeypatch.setattr(installer, 'ROOT', tmp_path)
    monkeypatch.setattr(installer, '__file__', str(tmp_path / 'installer.py'))
    before = installer.source_fingerprints()
    (tmp_path / 'cache.body').write_bytes(b'unexpected downloaded payload')
    assert installer.source_fingerprints() != before


@pytest.mark.parametrize('mutation', [
    'clean', 'shared-site', 'outside-module', 'user-site', 'legacy-sdk', 'legacy-sdk-distribution',
    'wrong-version', 'unowned-pth', 'outside-distribution', 'missing-distributions', 'legitimate-stdlib',
])
def test_import_probe_rejects_shared_or_wrong_environment(tmp_path, mutation):
    installer = module()
    prefix, base, source = tmp_path / 'venv', tmp_path / 'python', tmp_path / 'source'
    site = prefix / 'Lib/site-packages'
    result = {
        'prefix': str(prefix), 'base_prefix': str(base), 'user_site': False,
        'paths': [str(site), str(base / 'Lib'), str(base / 'python313.zip'), str(source)],
        'versions': dict(PINS), 'legacy_sdk': False,
        'modules': {name: str(site / name.replace('-', '_') / '__init__.py') for name in PINS},
        'distributions': {name: str(site) for name in PINS},
        'unowned_pth': [],
    }
    if mutation == 'shared-site':
        result['paths'].append(str(tmp_path / 'old/Lib/site-packages'))
    elif mutation == 'outside-module':
        result['modules']['django'] = str(tmp_path / 'old/django/__init__.py')
    elif mutation == 'user-site':
        result['user_site'] = True
    elif mutation == 'legacy-sdk':
        result['legacy_sdk'] = True
    elif mutation == 'legacy-sdk-distribution':
        result['distributions']['ai-base-application-sdk'] = str(site)
    elif mutation == 'wrong-version':
        result['versions']['pytest'] = '9.1.1'
    elif mutation == 'unowned-pth':
        result['unowned_pth'] = [str(site / 'unmanaged.pth')]
    elif mutation == 'outside-distribution':
        result['distributions']['django'] = str(tmp_path / 'old/Lib/site-packages')
    elif mutation == 'missing-distributions':
        del result['distributions']
    elif mutation == 'legitimate-stdlib':
        result['paths'].append(str(base))
    if mutation in {'clean', 'legitimate-stdlib'}:
        installer.validate_import_probe(result, prefix, source)
    else:
        with pytest.raises(ValueError):
            installer.validate_import_probe(result, prefix, source)
