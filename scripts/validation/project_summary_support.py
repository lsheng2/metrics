import hashlib
from importlib import metadata
import json
import os
from pathlib import Path
import shlex
import subprocess
import sys
from tempfile import TemporaryDirectory
from urllib.parse import urlsplit
import zipfile

from scripts.service_lifecycle_engine import PlatformOperationSet


BASE_COMMIT = '2332d549ab69a7e927865acd0e3db2a19295c609'
BASE_TREE_SHA = 'db92bb903a5d47aeffe3707ef5da27b3dc031b0c7e28bdde527ccb8bf66ac261'
SOURCE_SHA = 'c5534b86913b2bf4867b6352f1e8c0d185b50378c9626dbf424b98aa181e8fe3'
WHEEL_SHA = '32e54c5f443e39daa55190c4de142ac6c12478204d8fba6bf9909149c3b365f9'
SDK020_SELECTION = {
    'schema_version': 1,
    'selection_id': 'sdk020-summary-a2',
    'sdk_version': '0.2.0a1',
    'sdk_wheel_sha256': '1ab6c7aa7255abeb4637734f65613827d39593ff72b7ef9d630885922c2dd134',
    'contract_pack_manifest_sha256': 'e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4',
}


def digest(data):
    return hashlib.sha256(data).hexdigest()


def owned_work_root(value, repository):
    root = Path(value).resolve()
    expected = Path(repository).resolve() / '.tmp' / 'task-run-w5'
    if root != expected or not root.is_dir():
        raise ValueError('Use the prepared owned W5 work directory.')
    return root


def owned_data_root(value, repository):
    requested = Path(value)
    repository = Path(repository).resolve()
    root = requested.resolve()
    if (not requested.is_absolute() or root != requested.absolute()
            or root.is_relative_to(repository) or repository.is_relative_to(root)
            or any((parent / '.git').exists() for parent in (root, *root.parents))):
        raise ValueError('Validation data must be outside code repositories.')
    identity = {'schema_version': 1, 'owner': 'dashboard-w5-join', 'repository': str(repository)}
    marker = root / 'owner.json'
    if root.exists():
        if not root.is_dir():
            raise ValueError('Invalid validation data root.')
        if marker.exists():
            if json.loads(marker.read_text(encoding='utf-8')) != identity:
                raise ValueError('The validation data root has another owner.')
            return root
        if any(root.iterdir()):
            raise ValueError('Refusing an existing unowned validation data root.')
    root.mkdir(parents=True, exist_ok=True)
    write_json(marker, identity)
    return root


def checked_connection(value, directory, pid, scope, *, worker_matches=None):
    try:
        url = urlsplit(value['baseUrl'])
        stop = Path(value['stopFile']).resolve()
        if (value['executionMode'] != 'synthetic' or value['qualification'] != 'synthetic_only'
                or value['contractVersion'] != 'task-run/1' or value['packVersion'] != '0.1.0a2'
                or type(value['pid']) is not int or value['scopeKey'] != scope
                or value['sourceAppId'] != 'metrics-dashboard'
                or value['credentialRef'] != 'synthetic-integration'
                or value['grantRevision'] != 'dashboard-join-1'
                or value['limitPolicyRevision'] != 'base-b-cancel-synthetic-1'
                or not isinstance(value['token'], str) or not value['token']
                or not isinstance(value['runStoreId'], str) or not value['runStoreId']
                or url.scheme != 'http' or url.hostname != '127.0.0.1' or url.port is None
                or url.username or url.password or url.query or url.fragment or url.path not in ('', '/')
                or stop.parent != directory.resolve() or not stop.name.startswith('stop-')):
            raise ValueError
        if value['pid'] != pid and (worker_matches is None or not worker_matches(value['pid'])):
            raise ValueError
    except (ValueError, KeyError, TypeError, AttributeError):
        raise ValueError('Synthetic connection identity is invalid.') from None
    return {**value, 'launcherPid': pid}


def worker_record_matches(record, worker_pid, launcher_pid, command):
    try:
        actual = [part.strip('"').casefold() for part in shlex.split(record['CommandLine'], posix=False)]
        expected = [str(part).strip('"').casefold() for part in command]
        image = record['ExecutablePath'].replace('\\', '/').rsplit('/', 1)[-1].lower()
        return (record['ProcessId'] == worker_pid and record['ParentProcessId'] == launcher_pid
                and image == 'python.exe' and actual[1:] == expected[1:])
    except (ValueError, KeyError, TypeError, AttributeError):
        return False


def worker_matches_process(worker_pid, process):
    if sys.platform != 'win32' or process.poll() is not None:
        return False
    script = (
        '[Console]::OutputEncoding = [System.Text.UTF8Encoding]::new()\n'
        f'Get-CimInstance Win32_Process -Filter "ProcessId={int(worker_pid)}" | '
        'Select-Object ProcessId,ParentProcessId,ExecutablePath,CommandLine | ConvertTo-Json -Compress'
    )
    try:
        result = subprocess.run(['powershell.exe', '-NoProfile', '-NonInteractive', '-Command', script],
                                capture_output=True, encoding='utf-8', check=True, timeout=10)
        record = json.loads(result.stdout)
        return worker_record_matches(record, worker_pid, process.pid, process.args)
    except (subprocess.SubprocessError, ValueError):
        return False


def verify_base_source(work, source):
    if source.resolve() != work / 'base-source':
        raise ValueError('Use the fixed owned Base source copy.')
    if digest((work / 'base-tree-full.zip').read_bytes()) != BASE_TREE_SHA:
        raise ValueError('Base commit archive digest mismatch.')
    delta = work / 'artifacts' / 'base-source-delta.zip'
    if digest(delta.read_bytes()) != SOURCE_SHA:
        raise ValueError('Base source delivery digest mismatch.')
    expected = {}
    with zipfile.ZipFile(work / 'base-tree-full.zip') as base:
        if base.testzip() is not None:
            raise ValueError('Base commit archive is corrupt.')
        expected.update({item.filename: digest(base.read(item)) for item in base.infolist() if not item.is_dir()})
    with zipfile.ZipFile(delta) as archive:
        manifest_bytes = archive.read('HANDOFF-SOURCE-MANIFEST.json')
        manifest = json.loads(manifest_bytes)
        if manifest['baseCommit'] != BASE_COMMIT or len(manifest['files']) != 102:
            raise ValueError('Unexpected Base source identity.')
        expected.update(manifest['files'])
        expected['HANDOFF-SOURCE-MANIFEST.json'] = digest(manifest_bytes)
    for name, expected_hash in expected.items():
        target = (source / name).resolve()
        if not target.is_relative_to(source) or digest(target.read_bytes()) != expected_hash:
            raise ValueError(f'Base source copy differs from its fixed input: {name}')
    verify_source_inventory(source, set(expected))
    return {'baseCommit': BASE_COMMIT, 'sourceDeliverySha256': SOURCE_SHA, 'verifiedSourceFiles': len(expected),
            'baseTreeSha256': digest((work / 'base-tree-full.zip').read_bytes())}


def verify_source_inventory(source, expected):
    actual = {path.relative_to(source).as_posix() for path in source.rglob('*')
              if path.is_file() or path.is_symlink()}
    if actual != set(expected):
        raise ValueError('Unexpected or missing resources in the Base source candidate.')


def assert_checkpoint_not_dispatched(archive, *, runner=subprocess.run):
    environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
    result = runner(['git', '-C', str(archive), 'ls-tree', '--name-only', 'main', 'analysis_attempts'],
                    stdin=subprocess.DEVNULL, capture_output=True, env=environment, check=True, timeout=10)
    if result.stdout.strip():
        raise ValueError('Only a source checkpoint with no analysis attempt can use a new Base fixture.')


def probe_base_imports(python, source, data_directory, evidence_directory):
    code = """
import asyncio
import importlib
import socket
import sys
sys.path.insert(0, sys.argv[1])
def deny(*args, **kwargs):
    raise RuntimeError('External connections are forbidden in the import probe.')
async def probe():
    socket.socket.connect = deny
    socket.socket.connect_ex = deny
    socket.create_connection = deny
    importlib.import_module('app.task_run_candidate')
    print('BASE_FACTORY_IMPORT_OK')
asyncio.run(probe())
"""
    with TemporaryDirectory(dir=data_directory) as temporary:
        output = b''
        try:
            result = subprocess.run(
                [str(python), '-I', '-B', '-X', 'importtime', '-c', code, str(source / 'services/app-service')],
                cwd=temporary, env=child_environment(Path(temporary)),
                capture_output=True, timeout=30,
            )
            output = result.stdout + result.stderr
        except subprocess.TimeoutExpired as error:
            output = (error.stdout or b'') + (error.stderr or b'')
            raise
        finally:
            with (evidence_directory / 'base-import-probe.log').open('xb') as stream:
                stream.write(output)
    if result.returncode or b'BASE_FACTORY_IMPORT_OK' not in result.stdout:
        raise RuntimeError('The isolated Base factory import probe failed.')


def sdk_selection(work):
    path = work / 'sdk-selection.json'
    if not path.exists():
        return {'sdk_version': '0.1.0a2', 'sdk_wheel_sha256': WHEEL_SHA}
    try:
        value = json.loads(path.read_text(encoding='utf-8'))
        if value != SDK020_SELECTION or type(value.get('schema_version')) is not int:
            raise ValueError
    except (OSError, ValueError, TypeError):
        raise ValueError('SDK selection is not an approved release combination.') from None
    return value


def sdk_selection_digest(work):
    path = work / 'sdk-selection.json'
    return digest(path.read_bytes()) if path.is_file() else None


def verify_installed_sdk(work, sdk_module):
    selection = sdk_selection(work)
    wheel = work / 'artifacts' / f'ai_base_application_sdk-{selection["sdk_version"]}-py3-none-any.whl'
    if digest(wheel.read_bytes()) != selection['sdk_wheel_sha256']:
        raise ValueError('SDK wheel digest mismatch.')
    installed = Path(sdk_module.__file__).resolve().parent
    with zipfile.ZipFile(wheel) as archive:
        expected = {name.removeprefix('ai_base_application_sdk/'): archive.read(name)
                    for name in archive.namelist()
                    if name.startswith('ai_base_application_sdk/') and not name.endswith('/')}
        for name, content in expected.items():
            path = (installed / name).resolve(strict=True)
            if not path.is_relative_to(installed) or path.read_bytes() != content:
                raise ValueError('Installed SDK bytes differ from the delivered wheel.')
        actual = {path.relative_to(installed).as_posix() for path in installed.rglob('*')
                  if path.is_file() and '__pycache__' not in path.parts}
        if actual != set(expected):
            raise ValueError('Installed SDK package inventory differs from the delivered wheel.')
        distribution = metadata.distribution('ai-base-application-sdk')
        if (distribution.version != selection['sdk_version']
                or Path(distribution.locate_file('')).resolve() != installed.parent):
            raise ValueError('Installed SDK metadata identity differs from the selected package.')
        for name in ('METADATA', 'WHEEL'):
            relative = f'ai_base_application_sdk-{selection["sdk_version"]}.dist-info/{name}'
            if Path(distribution.locate_file(relative)).read_bytes() != archive.read(relative):
                raise ValueError('Installed SDK metadata bytes differ from the delivered wheel.')
    return selection['sdk_wheel_sha256']


def write_json(path, value):
    with path.open('x', encoding='utf-8') as stream:
        json.dump(value, stream, ensure_ascii=False, sort_keys=True, indent=2, allow_nan=False)
        stream.write('\n')


def child_environment(directory):
    environment = {key: value for key, value in os.environ.items()
                   if key.upper() in {'PATH', 'SYSTEMROOT', 'WINDIR', 'COMSPEC', 'PATHEXT'}}
    home, temp = directory / 'home', directory / 'tmp'
    home.mkdir()
    temp.mkdir()
    environment.update(HOME=str(home), USERPROFILE=str(home), TEMP=str(temp), TMP=str(temp),
                       NO_PROXY='127.0.0.1,localhost')
    return environment


def stop_owned_fixture(process, connection, directory):
    if process is None:
        return {'normal': True, 'forced': False, 'exitCode': None}
    forced = False
    if connection is not None and process.poll() is None:
        checked_connection(connection, directory, process.pid, connection['scopeKey'],
                           worker_matches=lambda child: worker_matches_process(child, process))
        Path(connection['stopFile']).touch()
    try:
        code = process.wait(timeout=15 if connection else 1)
    except subprocess.TimeoutExpired:
        forced = True
        if sys.platform == 'win32' and process.poll() is None:
            subprocess.run(['taskkill', '/PID', str(process.pid), '/T', '/F'],
                           capture_output=True, check=False, timeout=10)
        else:
            process.terminate()
        try:
            code = process.wait(timeout=5)
        except subprocess.TimeoutExpired:
            process.kill()
            code = process.wait(timeout=5)
    worker_stopped = connection is None or not PlatformOperationSet().process_exists(connection['pid'])
    return {'normal': code == 0 and not forced and worker_stopped, 'forced': forced, 'exitCode': code,
            'launcherPid': process.pid, 'workerPid': connection['pid'] if connection else None,
            'workerStopped': worker_stopped}
