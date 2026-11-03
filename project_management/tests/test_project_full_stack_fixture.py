from __future__ import annotations

import asyncio
import json
from pathlib import Path
import subprocess
import sys
from types import SimpleNamespace
import uuid

import pytest
import requests

from bug_metrics.app.api import ApiForBugTrend
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from project_management.app.api import ApiForProjectManagement, ProjectActor
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.out.dashboard_scope_catalog import DashboardScopeCatalog
from project_management.services.capture import ProjectCaptureService
from project_management.services.capture_archive import CaptureArchiveService
from scripts.validation.project_full_stack_base import ExactDynamicVectorExecutor, load_profile
from scripts.validation.project_full_stack_fixture import (
    ACTOR_SUBJECT,
    CAPTURE_PLACEHOLDER,
    ENDPOINT,
    FROZEN_JQL,
    archive_config,
    create_provider_fixture,
    prepare_catalog,
    synthetic_profile_records,
)
from scripts.validation.project_full_stack_support import ensure_data_root, initialize_run_dir
from project_management.tests.summary_fixtures import PACK_ROOT


@pytest.mark.django_db(transaction=True)
def test_should_accept_only_dynamic_capture_id_fields_in_exact_base_vector(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    prepare_catalog(run_dir)
    vector = json.loads((run_dir / 'fixture-vector.json').read_text(encoding='utf-8'))
    profile = load_profile(PACK_ROOT)
    vector = {**vector, 'schema_documents': profile['schemaDocuments']}
    executor = ExactDynamicVectorExecutor(vector, tmp_path / 'observations.jsonl', profile['inputSchema'])
    capture_id = str(uuid.uuid4())
    submitted = bind_capture_id(vector['input_template'], capture_id)
    compiled = SimpleNamespace(
        messages=[('user', json.dumps(submitted, ensure_ascii=False, sort_keys=True, separators=(',', ':')))],
        effective_input_sha256='e' * 64,
    )

    result = json.loads(asyncio.run(executor.execute(compiled)))

    assert result['target_capture_id'] == capture_id
    changed = bind_capture_id(vector['input_template'], capture_id)
    changed['evidence'][2]['value']['body'] = 'Changed retained text.'
    changed_compiled = SimpleNamespace(
        messages=[('user', json.dumps(changed, ensure_ascii=False, sort_keys=True, separators=(',', ':')))],
        effective_input_sha256='e' * 64,
    )
    with pytest.raises(ValueError):
        asyncio.run(executor.execute(changed_compiled))


@pytest.mark.django_db(transaction=True)
def test_should_capture_through_actual_jira_fixture_and_record_strict_transcript(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    prepare_catalog(run_dir)
    project_api = prepared_project_api()
    archive_root = tmp_path / 'archive'
    archive_root.mkdir()
    archive = CaptureArchiveService(project_api, LocalArchiveRepositoryFactory(), archive_config(archive_root))
    provider = create_provider_fixture(project_api, archive)
    receipt = ProjectCaptureService(project_api, provider.service, archive).capture(provider.context())

    assert receipt.complete is True
    assert [row['path'] for row in provider.transport.transcript] == [
        '/jira/rest/api/2/myself',
        '/jira/rest/api/2/search',
        '/jira/rest/api/2/search',
        '/jira/rest/api/2/issue/101',
        '/jira/rest/api/2/issue/101/comment',
        '/jira/rest/api/2/issue/101/comment',
        '/jira/rest/api/2/issue/101',
            '/jira/rest/api/2/search',
            '/jira/rest/api/2/search',
            '/jira/rest/api/2/myself',
    ]


@pytest.mark.django_db(transaction=True)
def test_should_reject_nonregistered_jira_request_boundaries(tmp_path):
    run_dir = tmp_path / 'run'
    run_dir.mkdir()
    prepare_catalog(run_dir)
    project_api = prepared_project_api()
    archive_root = tmp_path / 'archive'
    archive_root.mkdir()
    archive = CaptureArchiveService(project_api, LocalArchiveRepositoryFactory(), archive_config(archive_root))
    provider = create_provider_fixture(project_api, archive)
    session = requests.Session()
    session.mount('https://', provider.transport)

    with pytest.raises(AssertionError):
        session.get(f'{ENDPOINT}/rest/api/2/filter/123')
    with pytest.raises(AssertionError):
        session.get(f'{ENDPOINT}/rest/api/2/search', params={
            'jql': FROZEN_JQL + ' ORDER BY updated',
            'validateQuery': 'true',
            'startAt': '0',
            'maxResults': '0',
            'fields': 'id',
        })
    with pytest.raises(AssertionError):
        session.get(f'{ENDPOINT}/rest/api/2/search', params=[
            ('jql', FROZEN_JQL),
            ('jql', FROZEN_JQL),
            ('validateQuery', 'true'),
            ('startAt', '0'),
            ('maxResults', '0'),
            ('fields', 'id'),
        ])


def test_shouldAssembleRuntimeWithPageSizeTwoCaptureLimitWhenUsingQualificationSettings(tmp_path):
    data_root = ensure_data_root(tmp_path / 'data')
    run_dir = data_root / str(uuid.uuid4())
    run_dir.mkdir()
    initialize_run_dir(run_dir, data_root)
    script = runtime_capture_limits_probe(run_dir)

    result = subprocess.run(
        [sys.executable, '-I', '-c', script],
        cwd=Path.cwd(),
        capture_output=True,
        text=True,
        timeout=60,
    )

    assert result.returncode == 0, result.stdout + result.stderr
    observed = json.loads(result.stdout)
    assert observed == {'factory_page_size': 2, 'request_page_size': 2}


def prepared_project_api():
    registry = ProjectProviderProfileRegistry.from_records(synthetic_profile_records())
    return ApiForProjectManagement(DashboardScopeCatalog(ApiForBugTrend(), lambda: registry))


def bind_capture_id(template: dict, capture_id: str) -> dict:
    value = json.loads(json.dumps(template, ensure_ascii=False))
    assert value['target_capture_id'] == CAPTURE_PLACEHOLDER
    value['target_capture_id'] = capture_id
    value['delta']['to_capture_id'] = capture_id
    for row in value['evidence']:
        row['capture_id'] = capture_id
    return value


def runtime_capture_limits_probe(run_dir):
    return f"""
import json
import os
from pathlib import Path
import sys
sys.path.insert(0, {str(Path.cwd())!r})
os.environ['DJANGO_SETTINGS_MODULE'] = 'scripts.validation.project_full_stack_settings'
os.environ['METRICS_PROJECT_FULL_STACK_RUN_DIR'] = {str(run_dir)!r}
os.environ['METRICS_PROJECT_FULL_STACK_BOOTSTRAP'] = '1'
import django
django.setup()
from django.core.management import call_command
call_command('migrate', interactive=False, verbosity=0)
from scripts.validation.project_full_stack_fixture import prepare_catalog, build_runtime_environment
from project_management.app.domain.run_admission_values import capture_limits_payload
prepare_catalog(Path({str(run_dir)!r}))
connection = {{
    'baseUrl': 'http://127.0.0.1:48640',
    'sourceAppId': 'metrics-dashboard',
    'runStoreId': 'store-fixture',
    'credentialRef': 'synthetic-integration',
    'token': 'synthetic-token',
    'grantRevision': 'dashboard-join-1',
    'limitPolicyRevision': 'base-b-cancel-synthetic-1',
    'packRoot': {str(PACK_ROOT)!r},
}}
runtime = build_runtime_environment(connection)
payload = capture_limits_payload(runtime.run_service.capture_limits)
print(json.dumps({{
    'factory_page_size': runtime.run_service.capture_limits.page_size,
    'request_page_size': payload['page_size'],
}}, sort_keys=True))
"""
