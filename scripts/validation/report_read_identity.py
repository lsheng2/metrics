from __future__ import annotations

import hashlib
import json
import os
from pathlib import Path
import re
import subprocess
import sys

from scripts.validation.project_full_stack_support import (
    base_environment,
    digest_file,
    environment_digest,
)


ROOT = Path(__file__).resolve().parents[2]
OWNED_SOURCE_FILES = (
    Path('scripts/validation/profile_report_reads.py'),
    Path('scripts/validation/report_read_fixtures.py'),
    Path('scripts/validation/report_read_identity.py'),
    Path('project_management/tests/test_report_read_validation.py'),
)


def preflight_run_manifest(run_dir: Path):
    manifest_path = run_dir / 'runtime-manifest.json'
    if not manifest_path.is_file():
        raise ValueError('Run manifest is missing.')
    manifest = json.loads(manifest_path.read_text(encoding='utf-8'))
    if manifest.get('execution_mode') != 'synthetic':
        raise ValueError('Report read profiling requires a synthetic run manifest.')
    if Path(manifest.get('repository', '')).resolve(strict=False) != ROOT.resolve(strict=True):
        raise ValueError('Run manifest repository does not match this checkout.')
    if Path(manifest.get('run_dir', '')).resolve(strict=False) != run_dir.resolve(strict=True):
        raise ValueError('Run manifest does not describe the selected run directory.')
    catalog = manifest.get('catalog')
    if not isinstance(catalog, dict) or catalog.get('actor') != 'basic:SYNTHETIC_ALICE':
        raise ValueError('Run manifest actor does not match synthetic Alice.')
    for key in ('project_id', 'stage_id'):
        if not isinstance(catalog.get(key), str) or not catalog[key]:
            raise ValueError('Run manifest catalog identity is incomplete.')
    return manifest


def baseline_query(run_dir: Path, project, stage):
    from django.apps import apps

    report_series = apps.get_model('project_management', 'ReportSeries')
    series = report_series.objects.filter(project=project, stage=stage).order_by('created_at', 'id').first()
    if series is None:
        raise ValueError('Baseline scenario requires a report series.')
    if not hasattr(series, 'policy_revisions'):
        raise ValueError('Baseline scenario cannot find series policy revisions.')
    policy = series.policy_revisions.order_by('-revision').first()
    if policy is None or not hasattr(policy, 'payload_json'):
        raise ValueError('Baseline scenario requires a current policy payload.')
    payload = _json_value(policy.payload_json)
    template = payload['default_template_selection']
    for key in ('template_id', 'revision', 'revision_hash'):
        if key not in template:
            raise ValueError('Baseline scenario template payload is incomplete.')
    if template.get('origin') not in {'user', None}:
        raise ValueError('Baseline scenario requires a user template selection.')
    return {
        'series_id': str(series.id),
        'meeting_date': catalog_meeting_date(run_dir, str(project.id), str(stage.id), payload),
        'template_choice': f"user|{template['template_id']}|{template['revision']}|{template['revision_hash']}",
    }


def catalog_meeting_date(run_dir: Path, project_id: str, stage_id: str, policy: dict) -> str:
    date_map = policy.get('calendar', {}).get('date_map', {})
    if isinstance(date_map, dict) and date_map:
        return sorted(date_map)[0]
    archive = run_dir / 'archive' / 'projects' / project_id / 'stages' / stage_id / 'archive'
    dates = []
    for path in archive.glob('captures/*/snapshots/*.json'):
        try:
            dates.extend(extract_dates(json.loads(path.read_text(encoding='utf-8'))))
        except (OSError, json.JSONDecodeError):
            continue
    if not dates:
        raise ValueError('Baseline scenario could not derive a catalog meeting date.')
    return sorted(dates)[-1]


def extract_dates(value):
    dates = []
    if isinstance(value, dict):
        for item in value.values():
            dates.extend(extract_dates(item))
    elif isinstance(value, list):
        for item in value:
            dates.extend(extract_dates(item))
    elif isinstance(value, str):
        match = re.match(r'^(20\d\d-\d\d-\d\d)', value)
        if match:
            dates.append(match.group(1))
    return dates


def first_draft_id(run_dir: Path, project_id: str, stage_id: str) -> str:
    root = run_dir / 'archive' / 'projects' / project_id / 'stages' / stage_id / 'runtime' / 'report-drafts'
    for path in sorted(root.iterdir()):
        if path.is_dir() and (path / 'current.json').is_file():
            return path.name
    raise ValueError('Editor scenario requires an existing current draft.')


def source_identity():
    runtime = runtime_source_identity()
    return {
        'source_commit': _git_text('rev-parse', 'HEAD'),
        'git_status_short': _git_text('status', '--short'),
        'owned_file_sha256': {
            path.as_posix(): digest_file(ROOT / path)
            for path in OWNED_SOURCE_FILES
            if (ROOT / path).exists()
        },
        'runtime_source_digest': runtime['digest'],
        'runtime_source_files': runtime['files'],
    }


def runtime_source_identity():
    files = {}
    for path in (ROOT / 'project_management').rglob('*.py'):
        if 'tests' not in path.relative_to(ROOT).parts:
            files[path.relative_to(ROOT).as_posix()] = digest_file(path)
    for pattern in (
        'ui_web/urls.py',
        'ui_web/report_*.py',
        'ui_web/views/project_reports.py',
        'ui_web/views/report_*.py',
        'ui_web/facades/project_reports.py',
        'ui_web/facades/project_runs.py',
        'ui_web/views/project_run_views.py',
        'ui_web/views/project_management_views.py',
        'ui_web/facades/report_*.py',
        'ui_web/templates/projects/reports/**/*.html',
        'ui_web/templates/base.html',
        'ui_web/templates/projects/language_switcher.html',
        'ui_web/static/js/report*.js',
        'ui_web/static/css/main.css',
    ):
        for path in ROOT.glob(pattern):
            if path.is_file():
                files[path.relative_to(ROOT).as_posix()] = digest_file(path)
    return {'digest': _digest(files), 'files': dict(sorted(files.items()))}


def fixture_identity(run_dir: Path, target, manifest: dict):
    archive = run_dir / 'archive' / 'projects' / target.project_id / 'stages' / target.stage_id / 'archive'
    runtime = run_dir / 'archive' / 'projects' / target.project_id / 'stages' / target.stage_id / 'runtime'
    runtime_files = file_digest_map(runtime)
    return {
        'runtime_manifest_sha256': _optional_digest(run_dir / 'runtime-manifest.json'),
        'catalog_sha256': _optional_digest(run_dir / 'catalog.sqlite3'),
        'archive_head': _git_text('-C', str(archive), 'rev-parse', 'main'),
        'manifest_catalog': manifest.get('catalog', {}),
        'runtime_mutable_digest': _digest(runtime_files),
        'runtime_mutable_files': runtime_files,
        'fixture_digest': _digest({
            'run_dir': run_dir.name,
            'project_id': target.project_id,
            'stage_id': target.stage_id,
            'manifest': _optional_digest(run_dir / 'runtime-manifest.json'),
            'catalog': _optional_digest(run_dir / 'catalog.sqlite3'),
        }),
    }


def environment_identity(output_dir: Path, manifest: dict):
    import django
    import ai_base_application_sdk
    from importlib.metadata import version

    safe_environment = base_environment(output_dir / 'environment-digest')
    return {
        'python': sys.executable,
        'python_version': sys.version,
        'sys_path': sys.path,
        'django_version': django.get_version(),
        'django_module_file': getattr(django, '__file__', ''),
        'sdk_version': version('ai-base-application-sdk'),
        'sdk_module_file': ai_base_application_sdk.__file__,
        'manifest_sdk_version': manifest.get('sdk_version'),
        'manifest_sdk_wheel_sha256': manifest.get('sdk_wheel_sha256'),
        'manifest_app_python': manifest.get('app_python'),
        'django_settings_module': os.environ.get('DJANGO_SETTINGS_MODULE', ''),
        'git_version': _git_text('version'),
        'environment_digest': environment_digest(safe_environment),
    }


def file_digest_map(root: Path):
    if not root.exists():
        return {}
    return {
        path.relative_to(root).as_posix(): digest_file(path)
        for path in sorted(root.rglob('*'))
        if path.is_file()
    }


def _json_value(value):
    return json.loads(value) if isinstance(value, str) else value


def _optional_digest(path: Path):
    return digest_file(path) if path.is_file() else None


def _digest(value) -> str:
    data = json.dumps(value, sort_keys=True, separators=(',', ':'), default=str).encode('utf-8')
    return hashlib.sha256(data).hexdigest()


def _git_text(*arguments) -> str:
    return subprocess.run(['git', *arguments], cwd=ROOT, check=True, capture_output=True, text=True, timeout=30).stdout.strip()
