import argparse
from datetime import UTC, datetime
import hashlib
import importlib
from importlib import metadata
import json
from pathlib import Path
import subprocess
import sys
import uuid
import xml.etree.ElementTree as ET
import zipfile


ROOT = Path(__file__).resolve().parents[2]
SDK_NAME = 'ai-base-application-sdk'
SDK_VERSION = '0.2.0a1'
WHEEL_NAME = 'ai_base_application_sdk-0.2.0a1-py3-none-any.whl'
WHEEL_SHA = '1ab6c7aa7255abeb4637734f65613827d39593ff72b7ef9d630885922c2dd134'
PACK_SHA = 'e7386f82d2bf3963feccc28cfbfda732b9eddb829831d5ba660b50554e5f81c4'
PACK_ROOT = ROOT / 'project_management/ai_bundle/strict-summary/task-run-contract-0.1.0a2'
TESTS = (
    'project_management/tests/test_sdk_020_compatibility.py',
    'project_management/tests/test_summary_analysis.py',
    'project_management/tests/test_summary_input.py',
)
SOURCE_PATHS = (
    'requirements-ai-task.txt',
    'project_management/out/ai_task_contract.py',
    'project_management/services/summary_analysis.py',
    'project_management/app/domain/summary_input.py',
    'project_management/app/domain/summary_validation.py',
    'project_management/tests/summary_fixtures.py',
    'scripts/validation/run_report_authoring_tests.py',
    'scripts/validation/run_project_sdk_preintegration.py',
    *TESTS,
)


class PreparationError(Exception):
    pass


def digest(path):
    return hashlib.sha256(path.read_bytes()).hexdigest()


def require(condition, code):
    if not condition:
        raise PreparationError(code)


def resolve_work_root(value):
    work = Path(value).resolve(strict=True)
    require(work.is_dir() and work.is_relative_to(ROOT / '.tmp'), 'invalid_work_root')
    require(work != ROOT / '.tmp', 'invalid_work_root')
    return work


def verify_sdk_target(work):
    wheel = work / 'artifacts' / WHEEL_NAME
    require(wheel.is_file() and digest(wheel) == WHEEL_SHA, 'wheel_hash_mismatch')
    target = (work / 'sdk-site').resolve(strict=True)
    require(target.is_relative_to(work) and target.is_dir(), 'invalid_sdk_target')
    checked = 0
    with zipfile.ZipFile(wheel) as archive:
        for entry in archive.infolist():
            if entry.is_dir() or not entry.filename.startswith('ai_base_application_sdk/'):
                continue
            path = (target / entry.filename).resolve(strict=True)
            require(path.is_relative_to(target), 'sdk_path_escape')
            require(path.read_bytes() == archive.read(entry), 'installed_sdk_bytes_mismatch')
            checked += 1
    require(checked >= 6, 'incomplete_sdk_package')
    require('ai_base_application_sdk' not in sys.modules, 'sdk_already_imported')
    sys.path.insert(0, str(target))
    sys.path.insert(1, str(ROOT))
    importlib.invalidate_caches()
    distribution = metadata.distribution(SDK_NAME)
    require(distribution.version == SDK_VERSION, 'sdk_version_mismatch')
    require(Path(distribution.locate_file('')).resolve() == target, 'sdk_metadata_origin_mismatch')
    sdk = importlib.import_module('ai_base_application_sdk')
    module_path = Path(sdk.__file__).resolve()
    require(module_path.is_relative_to(target), 'sdk_module_origin_mismatch')
    return module_path, checked


def verify_pack():
    require(digest(PACK_ROOT / 'manifest.json') == PACK_SHA, 'pack_manifest_mismatch')
    manifest = json.loads((PACK_ROOT / 'manifest.json').read_text(encoding='utf-8'))
    require(manifest['packVersion'] == '0.1.0a2', 'pack_version_mismatch')
    require(manifest['qualification'] == 'synthetic_only', 'pack_qualification_mismatch')
    require(len(manifest['files']) == 21, 'pack_file_count_mismatch')
    for name, expected in manifest['files'].items():
        path = (PACK_ROOT / name).resolve(strict=True)
        require(path.is_relative_to(PACK_ROOT), 'pack_path_escape')
        require(digest(path) == expected, 'pack_content_mismatch')
    return len(manifest['files'])


def original_environment():
    distribution = metadata.distribution(SDK_NAME)
    root = Path(distribution.locate_file('ai_base_application_sdk')).resolve()
    return {
        'version': distribution.version,
        'files': {str(path): digest(path) for path in root.glob('*.py')},
    }


def environment_unchanged(original):
    return all(digest(Path(path)) == expected for path, expected in original['files'].items())


def source_snapshot():
    commit = subprocess.check_output(
        ['git', '-C', str(ROOT), 'rev-parse', 'HEAD'],
        text=True, timeout=15,
    ).strip()
    return commit, [{'path': path, 'sha256': digest(ROOT / path)} for path in SOURCE_PATHS]


def counts_from_junit(path):
    counts = dict(tests=0, failures=0, errors=0, skipped=0)
    if not path.is_file():
        return counts
    for suite in ET.parse(path).getroot().iter('testsuite'):
        for key in counts:
            counts[key] += int(suite.get(key, '0'))
    return counts


def execute(work, module_path, sdk_files, pack_files, original):
    run = work / 'runs' / str(uuid.uuid4())
    run.mkdir(parents=True)
    junit = run / 'junit.xml'
    network_attempts = []
    runtime_ipc_attempts = []
    commit, sources = source_snapshot()
    arguments = [*TESTS, '-q', '--tb=short', '--durations=5', f'--junitxml={junit}']
    exit_code = 2
    failure = None
    try:
        runner = importlib.import_module('scripts.validation.run_report_authoring_tests')
        exit_code = runner.run_tests(
            arguments, allow_loopback=False, network_attempts=network_attempts,
            runtime_ipc_attempts=runtime_ipc_attempts,
        )
    except Exception as error:
        failure = type(error).__name__
    counts = counts_from_junit(junit)
    base_imported = any(
        name == 'app' or name.startswith('app.') or name == 'template_runtime'
        or name.startswith('template_runtime.')
        for name in sys.modules
    )
    unchanged = environment_unchanged(original)
    passed = (
        exit_code == 0 and counts['tests'] > 0
        and not any(counts[key] for key in ('failures', 'errors', 'skipped'))
        and not network_attempts and not base_imported and unchanged
    )
    receipt = {
        'schema_version': 1,
        'status': 'IP-SDK020-READY' if passed else 'PREINTEGRATION_FAILED',
        'created_at': datetime.now(UTC).isoformat(),
        'source_commit': commit,
        'source_kind': 'working_tree_files_bound_below_not_a_clean_commit_claim',
        'source_files': sources,
        'sdk_version': SDK_VERSION,
        'sdk_wheel_sha256': WHEEL_SHA,
        'sdk_module_path': str(module_path),
        'sdk_files_verified': sdk_files,
        'dependency_versions': {
            name: metadata.version(name) for name in ('httpx', 'jsonschema', 'django', 'pytest')
        },
        'pack_version': '0.1.0a2',
        'pack_manifest_sha256': PACK_SHA,
        'pack_files_checked': pack_files,
        'test_selection': list(TESTS),
        'junit_path': str(junit),
        **counts,
        'exit_code': exit_code,
        'failure_type': failure,
        'network_attempts': len(network_attempts),
        'network_operation_labels': network_attempts,
        'network_policy_revision': 2,
        'runtime_ipc_socketpair_attempts': len(runtime_ipc_attempts),
        'runtime_ipc_operation_labels': runtime_ipc_attempts,
        'joined_http_started': False,
        'base_modules_imported': base_imported,
        'main_environment_modified': not unchanged,
        'main_sdk_version_before': original['version'],
        'base_owner_change': 'refine-public-application-sdk',
        'base_receipt_sha256': digest(work / 'artifacts/base-delivery.json'),
        'next_node': 'SDK020.JOIN',
        'next_node_requires_user_release': True,
    }
    receipt_path = run / 'receipt.json'
    with receipt_path.open('x', encoding='utf-8') as stream:
        json.dump(receipt, stream, sort_keys=True, indent=2)
    print(json.dumps({
        'status': receipt['status'], 'receipt': str(receipt_path),
        **counts, 'network_attempts': len(network_attempts),
    }))
    return 0 if passed else 1


def main():
    parser = argparse.ArgumentParser(description='Qualify an installed SDK consumer without starting Base HTTP.')
    parser.add_argument('--work-root', required=True)
    args = parser.parse_args()
    try:
        work = resolve_work_root(args.work_root)
        original = original_environment()
        module_path, sdk_files = verify_sdk_target(work)
        pack_files = verify_pack()
        require((work / 'artifacts/base-delivery.json').is_file(), 'missing_base_receipt')
        return execute(work, module_path, sdk_files, pack_files, original)
    except PreparationError as error:
        print(json.dumps({'status': 'PREINTEGRATION_REFUSED', 'code': str(error)}))
        return 2
    except (OSError, ValueError, KeyError, metadata.PackageNotFoundError, zipfile.BadZipFile) as error:
        print(json.dumps({'status': 'PREINTEGRATION_REFUSED', 'code': type(error).__name__}))
        return 2


if __name__ == '__main__':
    raise SystemExit(main())
