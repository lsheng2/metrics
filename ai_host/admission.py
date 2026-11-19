import hashlib
import json
from importlib.metadata import PackageNotFoundError, distribution, version
from importlib.util import find_spec
from pathlib import Path


class RuntimeCandidateError(Exception):
    pass


def admit_runtime_candidate(artifact_path=None):
    path = Path(artifact_path or Path(__file__).with_name('runtime_artifact.json'))
    try:
        record = json.loads(path.read_text(encoding='utf-8'))
        if record['distribution'] != 'ai-base-runtime':
            raise RuntimeCandidateError('runtime_distribution_mismatch')
        if version(record['distribution']) != record['version']:
            raise RuntimeCandidateError('runtime_version_mismatch')
        dist = distribution(record['distribution'])
        direct_url = json.loads(dist.read_text('direct_url.json') or '{}')
        if direct_url.get('dir_info', {}).get('editable', False):
            raise RuntimeCandidateError('runtime_candidate_editable')
        if direct_url.get('archive_info', {}).get('hashes', {}).get('sha256') != record['wheelSha256']:
            raise RuntimeCandidateError('runtime_wheel_mismatch')
        files = record['packageFiles']
        installed_files = {
            str(item).replace('\\', '/') for item in dist.files or ()
            if str(item).replace('\\', '/').startswith('ai_base_runtime/')
            and '__pycache__' not in item.parts
        }
        if not isinstance(files, dict) or not files or set(files) != installed_files:
            raise RuntimeCandidateError('runtime_file_manifest_invalid')
        package_root = Path(dist.locate_file('ai_base_runtime')).resolve()
        for relative, expected in files.items():
            installed = Path(dist.locate_file(relative)).resolve()
            if (not installed.is_relative_to(package_root)
                    or not installed.is_file() or _sha256(installed) != expected):
                raise RuntimeCandidateError('runtime_file_mismatch')
        spec = find_spec('ai_base_runtime')
        if spec is None or Path(spec.origin or '').resolve() != package_root / '__init__.py':
            raise RuntimeCandidateError('runtime_candidate_shadowed')
    except (OSError, KeyError, TypeError, ValueError, AttributeError, PackageNotFoundError):
        raise RuntimeCandidateError('runtime_candidate_invalid') from None
    return record


def _sha256(path):
    digest = hashlib.sha256()
    with path.open('rb') as handle:
        for chunk in iter(lambda: handle.read(1024 * 1024), b''):
            digest.update(chunk)
    return digest.hexdigest()
