"""Offline, owned Windows installation qualification for the selected runtime."""
from __future__ import annotations

import argparse
from dataclasses import dataclass
from email.parser import BytesParser
import importlib
import importlib.metadata as metadata
import importlib.util
import json
import os
from pathlib import Path
import re
import shutil
import site
import subprocess
import sys
import time
import uuid
import zipfile

ROOT = Path(__file__).resolve().parents[2]
sys.path.insert(0, str(ROOT))
from scripts.validation.project_full_stack_support import (
    base_environment, digest_file, read_json, reject_reparse_components, write_json,
)
from scripts.validation.windows_install_wheelhouse import (
    WheelhouseLock, load_wheelhouse_lock, verify_wheelhouse_lock,
)

PINS = {
    'ai-base-runtime': '0.1.1.dev11', 'django': '6.0.7', 'whitenoise': '6.12.0',
    'waitress': '3.0.2', 'portalocker': '4.4.2', 'pytest': '9.2.0',
    'pytest-asyncio': '1.5.0', 'pytest-django': '4.12.0', 'playwright': '1.57.0',
}
MODULES = {
    'ai-base-runtime': 'ai_base_runtime', 'pytest-asyncio': 'pytest_asyncio',
    'pytest-django': 'pytest_django',
}
LEGACY_SDK_DISTRIBUTIONS = {'ai-base-application-sdk'}
LEGACY_SDK_MODULES = {'ai_base_application_sdk'}


@dataclass(frozen=True, slots=True)
class InstallRequest:
    root: Path
    wheel: Path
    wheelhouse: Path
    wheelhouse_manifest: Path
    wheelhouse_manifest_sha256: str
    wheelhouse_lock: WheelhouseLock
    environment: Path
    bootstrap: Path
    requirements: Path
    output: Path
    inputs: Path


def canonical(value):
    path = Path(value)
    if not path.is_absolute():
        raise ValueError('Expected an absolute path')
    reject_reparse_components(path)
    if path.resolve() != path.absolute():
        raise ValueError('Expected a canonical path')
    return path.resolve()


def owned(value, root):
    path = canonical(value)
    if path == root or not path.is_relative_to(root):
        raise ValueError('Path is outside its owned root')
    return path


def validate_requirements(path):
    versions = {}
    for line in path.read_text(encoding='utf-8').splitlines():
        if not line.strip() or line.lstrip().startswith('#'):
            continue
        match = re.fullmatch(r'([A-Za-z0-9_.-]+)(?:\[([A-Za-z0-9_,.-]+)\])?==([^;\s]+)(?:; .+)?', line)
        if not match:
            raise ValueError('Requirements must contain exact named pins')
        name = re.sub(r'[-_.]+', '-', match[1]).lower()
        extras = match[2]
        if name == 'ai-base-runtime' and extras:
            raise ValueError('Runtime extras are not part of the Dashboard candidate')
        if name in versions:
            raise ValueError('Duplicate dependency')
        versions[name] = match[3]
    if any(versions.get(name) != value for name, value in PINS.items()) or 'gunicorn' in versions:
        raise ValueError('Requirements do not match the qualified Windows dependencies')
    return versions


def validate_wheel(wheel, candidate):
    manifest = read_json(ROOT / 'ai_host/runtime_artifact.json')
    if (manifest['distribution'] != 'ai-base-runtime'
            or candidate['version'] != manifest['version']
            or candidate['wheel_sha256'] != manifest['wheelSha256']
            or digest_file(wheel) != manifest['wheelSha256']):
        raise ValueError('Candidate wheel identity mismatch')
    with zipfile.ZipFile(wheel) as archive:
        names = archive.namelist()
        records = [name for name in names if name.endswith('.dist-info/METADATA')]
        if len(records) != 1 or len(names) != len(set(names)):
            raise ValueError('Invalid wheel metadata or duplicate members')
        record = BytesParser().parsebytes(archive.read(records[0]))
        if record['Name'] != 'ai-base-runtime' or record['Version'] != manifest['version']:
            raise ValueError('Wheel distribution or version mismatch')
        files = {name for name in names if name.startswith('ai_base_runtime/') and not name.endswith('/')}
        if not files or files != set(manifest['packageFiles']):
            raise ValueError('Incomplete package manifest')
        import hashlib
        if any(hashlib.sha256(archive.read(name)).hexdigest() != expected
               for name, expected in manifest['packageFiles'].items()):
            raise ValueError('Package file hash mismatch')


def load_request(input_path, output_path):
    try:
        inputs = canonical(input_path)
        data = read_json(inputs)
        if data['schema_version'] != 1 or canonical(data['source']['repository']) != ROOT.resolve():
            raise ValueError('Input source mismatch')
        root = canonical(data['owned_root']['path'])
        if root.is_relative_to(ROOT.resolve()) or ROOT.resolve().is_relative_to(root):
            raise ValueError('Installation root overlaps source')
        if not (inputs.is_relative_to(ROOT.resolve()) or inputs.is_relative_to(root)):
            raise ValueError('Input is outside source and owned roots')
        marker = canonical(data['owned_root']['marker'])
        if marker != root / 'owner.json':
            raise ValueError('Unexpected owner marker')
        owner = read_json(marker)
        if (owner['owner'] != 'mdb2-windows-closure' or canonical(owner['root']) != root
                or canonical(owner['repository']) != ROOT.resolve()):
            raise ValueError('Wrong installation owner')
        wheelhouse = owned(data['wheelhouse']['path'], root)
        manifest_input = data['wheelhouse']['manifest']
        wheelhouse_manifest = owned(manifest_input['path'], root)
        wheelhouse_manifest_sha256 = manifest_input['sha256']
        wheelhouse_lock = load_wheelhouse_lock(wheelhouse, wheelhouse_manifest, wheelhouse_manifest_sha256, root)
        wheel = owned(data['candidate']['wheel'], wheelhouse)
        environment = owned(data['python']['new_environment_root'], root)
        output = owned(output_path, root)
        if (environment.exists() or output.exists() or output.is_relative_to(environment)
                or output.is_relative_to(wheelhouse) or environment.is_relative_to(wheelhouse)
                or wheelhouse.is_relative_to(environment)):
            raise ValueError('Fresh, separate environment and output required')
        bootstrap = canonical(data['python']['bootstrap'])
        if not bootstrap.is_file():
            raise ValueError('Bootstrap interpreter missing')
        requirements = ROOT / 'requirements.txt'
        validate_requirements(requirements)
        validate_wheel(wheel, data['candidate'])
        return InstallRequest(root, wheel, wheelhouse, wheelhouse_manifest, wheelhouse_manifest_sha256,
                              wheelhouse_lock, environment, bootstrap, requirements, output, inputs)
    except (KeyError, TypeError, OSError, zipfile.BadZipFile) as error:
        raise ValueError('Invalid installation inputs') from error


def validate_import_probe(result, prefix, source):
    prefix, source = prefix.resolve(), source.resolve()
    base = Path(result['base_prefix']).resolve()
    if Path(result['prefix']).resolve() != prefix or base == prefix or result['user_site']:
        raise ValueError('Interpreter or user-site mismatch')
    if (result['legacy_sdk'] or legacy_sdk_distribution_present(result.get('distributions', {}))
            or any(result['versions'].get(name) != value for name, value in PINS.items())):
        raise ValueError('Wrong dependencies or legacy SDK')
    for text in result['paths']:
        path = Path(text).resolve()
        if path.is_relative_to(prefix) or path == source:
            continue
        if (path == base or path.is_relative_to(base / 'Lib') and 'site-packages' not in path.parts
                or path.is_relative_to(base / 'DLLs') or path == base / f'python{sys.version_info.major}{sys.version_info.minor}.zip'):
            continue
        raise ValueError('Shared or external import path')
    for text in (*result['modules'].values(), *result.get('distributions', {}).values()):
        if not Path(text).resolve().is_relative_to(prefix):
            raise ValueError('Import or distribution outside the new environment')
    if set(result['modules']) != set(PINS):
        raise ValueError('Incomplete import probe')
    if not set(PINS).issubset({re.sub(r'[-_.]+', '-', name).lower() for name in result.get('distributions', {})}):
        raise ValueError('Incomplete distribution probe')
    if result.get('unowned_pth'):
        raise ValueError('Unmanaged path bootstrap')


def normalized_distribution_name(name):
    return re.sub(r'[-_.]+', '-', str(name)).lower()


def legacy_sdk_distribution_present(distributions):
    return any(normalized_distribution_name(name) in LEGACY_SDK_DISTRIBUTIONS for name in distributions)


def legacy_sdk_module_present():
    return any(importlib.util.find_spec(module_name) is not None for module_name in LEGACY_SDK_MODULES)


def import_probe():
    distributions = list(metadata.distributions())
    managed = {Path(dist.locate_file(item)).resolve() for dist in distributions for item in dist.files or ()}
    paths = [Path(path) for path in site.getsitepackages()]
    result = {
        'prefix': sys.prefix, 'base_prefix': sys.base_prefix, 'user_site': site.ENABLE_USER_SITE,
        'paths': sys.path, 'versions': {name: metadata.version(name) for name in PINS},
        'modules': {name: importlib.import_module(MODULES.get(name, name)).__file__ for name in PINS},
        'distributions': {dist.metadata['Name']: str(Path(dist.locate_file('')).resolve()) for dist in distributions},
        'legacy_sdk': legacy_sdk_distribution_present({dist.metadata['Name']: '' for dist in distributions}) or legacy_sdk_module_present(),
        'unowned_pth': [str(path) for parent in paths for path in parent.glob('*.pth') if path.resolve() not in managed],
    }
    from ai_host.admission import admit_runtime_candidate
    result['admission'] = admit_runtime_candidate()
    return result


def source_fingerprints():
    result = subprocess.run(['git', 'ls-files', '--cached', '--others', '--exclude-standard', '-z'],
                            cwd=ROOT, check=True, capture_output=True, timeout=30)
    paths = sorted(set(result.stdout.decode('utf-8').split('\0')) - {''})
    hashes = {name: digest_file(ROOT / name) for name in paths
              if not name.startswith(('.env', '.tmp/')) and (ROOT / name).is_file()
              and (ROOT / name).suffix in {'.py', '.txt', '.json', '.html', '.js', '.css', '.ps1', '.md'}}
    return {'inventory': paths, 'hashes': hashes}


def acquisition_environment(environment, inherited=None):
    source = os.environ if inherited is None else inherited
    return {**environment, **{key: value for key, value in source.items()
                              if key.upper() in {'HTTP_PROXY', 'HTTPS_PROXY'}}}


def installer_environment(directory):
    environment = base_environment(directory)
    environment.update(
        APPDATA=str(directory / 'home/AppData/Roaming'),
        LOCALAPPDATA=str(directory / 'home/AppData/Local'),
        PIP_CONFIG_FILE=os.devnull, PYTHONNOUSERSITE='1', PYTHONUTF8='1',
    )
    return environment


def run_install(request):
    run = request.root / 'install-runs' / str(uuid.uuid4())
    owned(run, request.root).mkdir(parents=True)
    environment = installer_environment(run)
    git = shutil.which('git')
    if git is None:
        raise ValueError('Git is required by the real project host')
    environment['PATH'] = os.pathsep.join([
        str(request.environment / 'Scripts'), str(request.bootstrap.parent),
        str(Path(git).parent), os.environ.get('SYSTEMROOT', '') + '/System32',
    ])
    receipt = {
        'schema_version': 1, 'gate': 'V1', 'result': 'FAIL', 'run': str(run),
        'inputs_sha256': digest_file(request.inputs), 'requirements_sha256': digest_file(request.requirements),
        'wheel_sha256': digest_file(request.wheel), 'wheelhouse': request.wheelhouse_lock.receipt(),
        'source_before': None, 'commands': [],
    }

    def command(argv, label, timeout=600, *, expect_failure=False, acquisition=False):
        log = run / f'{label}.log'
        entry = {'argv': list(map(str, argv)), 'cwd': str(ROOT), 'log': str(log)}
        receipt['commands'].append(entry)
        start = time.monotonic()
        try:
            with log.open('wb') as stream:
                child_env = acquisition_environment(environment) if acquisition else environment
                result = subprocess.run(entry['argv'], cwd=ROOT, env=child_env, check=True, timeout=timeout,
                                        stdout=stream, stderr=subprocess.STDOUT, creationflags=subprocess.CREATE_NO_WINDOW)
            entry['returncode'] = result.returncode
        except subprocess.CalledProcessError as error:
            entry['returncode'] = error.returncode
            if not expect_failure:
                raise
        finally:
            entry['seconds'] = time.monotonic() - start
            entry['log_sha256'] = digest_file(log)
        if expect_failure and entry['returncode'] == 0:
            raise ValueError('Expected offline failure unexpectedly succeeded')
        return log

    try:
        verify_wheelhouse_lock(request.wheelhouse_lock)
        receipt['source_before'] = source_fingerprints()
        command([request.bootstrap, '-I', '-m', 'venv', request.environment], 'create-venv')
        python = request.environment / 'Scripts/python.exe'
        pip = [python, '-I', '-m', 'pip', '--isolated', '--disable-pip-version-check', '--no-cache-dir']
        command([*pip, 'download', '--no-index', '--retries', '0', '--timeout', '15', '--only-binary=:all:',
                 '--find-links', request.wheelhouse, '--dest', request.wheelhouse, '-r', request.requirements],
                'acquire-wheels', acquisition=True)
        verify_wheelhouse_lock(request.wheelhouse_lock)
        wheels = sorted(request.wheelhouse.glob('*.whl'))
        receipt['wheels'] = {path.name: digest_file(path) for path in wheels}
        constraints = run / 'windows-constraints.txt'
        resolved = {}
        for wheel in wheels:
            with zipfile.ZipFile(wheel) as archive:
                names = [name for name in archive.namelist() if name.endswith('.dist-info/METADATA')]
                if len(names) != 1:
                    raise ValueError('Dependency wheel metadata invalid')
                info = BytesParser().parsebytes(archive.read(names[0]))
                key = re.sub(r'[-_.]+', '-', info['Name']).lower()
                if key in resolved:
                    raise ValueError('Duplicate wheel distribution')
                resolved[key] = info['Version']
        constraints.write_text(''.join(f'{key}=={value}\n' for key, value in sorted(resolved.items())), encoding='utf-8')
        receipt['constraints'] = {'path': str(constraints), 'sha256': digest_file(constraints)}
        empty = run / 'empty-wheelhouse'
        empty.mkdir()
        command([*pip, 'install', '--no-index', '--find-links', empty, '--no-cache-dir',
                 '--only-binary=:all:', 'ai-base-runtime==0.1.1.dev11'], 'offline-missing-wheel', expect_failure=True)
        install = [*pip, 'install', '--no-index', '--find-links', request.wheelhouse,
                   '--no-cache-dir', '--only-binary=:all:', '-c', constraints]
        verify_wheelhouse_lock(request.wheelhouse_lock)
        command([*install, request.wheel], 'install-direct-runtime')
        command([*install, '-r', request.requirements], 'install-requirements')
        command([*pip, 'check'], 'pip-check')
        probe = command([python, '-I', __file__, '--probe'], 'import-admission')
        result = json.loads(probe.read_text(encoding='utf-8'))
        validate_import_probe(result, request.environment, ROOT)
        receipt['environment'] = result
        command([python, '-I', ROOT / 'scripts/validation/run_report_authoring_tests.py',
                 ROOT / 'ai_host/tests/test_admission.py', ROOT / 'ai_host/tests/test_workbench_package.py',
                 ROOT / 'ai_host/tests/test_metrics_tools.py',
                 ROOT / 'ai_host/tests/test_serve_process.py', '-q', '--tb=short', '-p', 'no:cacheprovider',
                 '-o', 'asyncio_default_fixture_loop_scope=function', '--basetemp', run / 'pytest',
                 '--junitxml', run / 'tests.xml'], 'installed-host', timeout=300)
        receipt['serve'] = [read_json(path) for path in (run / 'pytest').rglob('serve-evidence.json')]
        if not receipt['serve'] or any(item['returncode'] != 0 or item['forced_cleanup'] for item in receipt['serve']):
            raise ValueError('Missing or failed normal serve cleanup')
        receipt['source_after'] = source_fingerprints()
        if receipt['source_before'] != receipt['source_after']:
            raise ValueError('Source changed during installation qualification')
        verify_wheelhouse_lock(request.wheelhouse_lock)
        receipt['result'] = 'PASS'
    except (OSError, ValueError, subprocess.SubprocessError) as error:
        receipt['failure_type'] = type(error).__name__
        receipt['failed_step'] = receipt['commands'][-1] if receipt['commands'] else None
    write_json(request.output, receipt)
    print(json.dumps({'result': receipt['result'], 'receipt': str(request.output), 'run': str(run)}))
    return 0 if receipt['result'] == 'PASS' else 1


def main():
    if sys.argv[1:] == ['--probe']:
        print(json.dumps(import_probe(), sort_keys=True))
        return 0
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument('--inputs', type=Path, required=True)
    parser.add_argument('--output', type=Path, required=True)
    args = parser.parse_args()
    if sys.platform != 'win32':
        parser.error('This qualification lane requires native Windows')
    try:
        request = load_request(args.inputs, args.output)
    except ValueError:
        print(json.dumps({'result': 'FAIL', 'failure': 'invalid_installation_inputs'}))
        return 2
    return run_install(request)


if __name__ == '__main__':
    raise SystemExit(main())
