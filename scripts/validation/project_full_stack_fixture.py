from __future__ import annotations

from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import io
import json
from pathlib import Path
from types import SimpleNamespace
from urllib.parse import parse_qs, urlsplit
import uuid

import requests
from urllib3.response import HTTPResponse

from bug_metrics.app.api import ApiForBugTrend
from bug_metrics.app.api.provider_connections import ProviderConnectionResolver
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.app.api.scope_config import SavedScopeConfig
from bug_metrics.provider_connections.normalization import endpoint_identifier
from project_management.app.api import ApiForProjectManagement, ProjectActor, ScopeSelection
from project_management.app.api.capture_archive import (
    ArchiveLimits,
    ArchiveStorageConfig,
    CaptureCoverage,
    PartCoverage,
    SourceChainKey,
    StoredSnapshotRef,
    WorkItemIdentity,
)
from project_management.app.domain.capture_values import canonical_bytes, content_hash
from project_management.app.domain.summary_input import build_initial_input
from project_management.out.capture_archive import LocalArchiveRepositoryFactory
from project_management.out.dashboard_scope_catalog import DashboardScopeCatalog
from project_management.services.capture_archive import CaptureArchiveService
from provider_sync.out.capture_reader import BoundCaptureReader
from provider_sync.out.jira_capture import JiraCaptureAdapter
from provider_sync.tests.capture_gateway_fixtures import JiraFixture, comment, issue, page
from provider_sync.app.api.access import ProviderAccessService


PROFILE_ID = 'synthetic-jira'
ENDPOINT = 'https://tracker.example.test/jira'
FROZEN_JQL = 'project = ALPHA AND issuekey = ALPHA-101'
ACTOR_SUBJECT = 'basic:SYNTHETIC_ALICE'
CAPTURE_PLACEHOLDER = '00000000-0000-0000-0000-000000000000'
PROFILE_REVISION = 'project-reporting.summary@review-1'


def synthetic_profile_records() -> list[dict]:
    return [{
        'profile_id': PROFILE_ID,
        'provider_id': 'jira',
        'display_name': 'Qualification Jira',
        'enabled': True,
        'connection_settings': {
            'base_url': ENDPOINT,
            'auth_mode': 'server_pat',
            'credentials': {'token': 'synthetic-only-token'},
            'verify_ssl': True,
        },
        'source_population': {'native_query_text': FROZEN_JQL},
    }]


def install_profile_registry_override() -> None:
    records = synthetic_profile_records()

    def load_synthetic_default(cls):
        return cls.from_records(records)

    ProjectProviderProfileRegistry.load_default = classmethod(load_synthetic_default)


def archive_limits() -> ArchiveLimits:
    return ArchiveLimits(128 * 1024**2, 20000, 64 * 1024**2, 10000, 16 * 1024**2, 2000, 1024**2, 2 * 1024**2)


def prepare_catalog(run_dir: Path) -> dict:
    install_profile_registry_override()
    registry = ProjectProviderProfileRegistry.from_records(synthetic_profile_records())
    project_api = ApiForProjectManagement(DashboardScopeCatalog(ApiForBugTrend(), lambda: registry))
    actor = ProjectActor(ACTOR_SUBJECT)
    scope = ApiForBugTrend().save_scope_config(_scope_config())
    ApiForBugTrend().set_scope_provider_binding(scope.id, PROFILE_ID, actor='qualification')
    project = project_api.create_project(actor, key='qual-alpha', name='Qualification Alpha')
    stage = project_api.add_stage(actor, project.id, key='release-1', name='Release 1', selection=ScopeSelection(PROFILE_ID, scope.id))
    other = project_api.create_project(actor, key='qual-other', name='Qualification Other')
    other_stage = project_api.add_stage(actor, other.id, key='release-2', name='Release 2', selection=ScopeSelection(PROFILE_ID, scope.id))
    vector = build_vector(project.id, stage)
    (run_dir / 'fixture-vector.json').write_text(json.dumps(vector, ensure_ascii=False, sort_keys=True, indent=2) + '\n', encoding='utf-8')
    return {
        'actor': actor.subject,
        'project_id': project.id,
        'stage_id': stage.id,
        'stage_hash': stage.definition_hash,
        'scope_id': scope.id,
        'scope_key': f'projects.{project.id}.stages.{stage.id}',
        'isolation_project_id': other.id,
        'isolation_stage_id': other_stage.id,
        'profile_id': PROFILE_ID,
        'endpoint': ENDPOINT,
        'jql': FROZEN_JQL,
        'fixture_vector_sha256': hashlib.sha256((run_dir / 'fixture-vector.json').read_bytes()).hexdigest(),
    }


def build_runtime_environment(connection: dict):
    from ai_base_application_sdk import TaskRunClient
    import httpx
    from project_management.app.api.report_factories import build_report_service
    from project_management.app.domain.summary_contracts import AiBackendTarget
    from project_management.app.api.run_factories import _policy_from_settings
    from project_management.app.api.project_runs import ProjectRunRuntime, ProjectRunService, ProjectRunWorker
    from project_management.out.ai_task_contract import AiTaskContract
    from provider_sync.app.api.access_factory import capture_limits_from_settings
    from django.conf import settings

    registry = ProjectProviderProfileRegistry.from_records(synthetic_profile_records())
    project_api = ApiForProjectManagement(DashboardScopeCatalog(ApiForBugTrend(), lambda: registry))
    archive = CaptureArchiveService(project_api, LocalArchiveRepositoryFactory(), archive_config(Path(settings.METRICS_PROJECT_ARCHIVE_ROOT)))
    provider = create_provider_fixture(project_api, archive)
    capture = __import__('project_management.services.capture', fromlist=['ProjectCaptureService']).ProjectCaptureService(
        project_api, provider.service, archive, required_parts=('facts', 'comments', 'history')
    )
    contract = AiTaskContract.load(connection['packRoot'])

    def backend(actor, project_id, stage_id):
        return AiBackendTarget(connection['baseUrl'], connection['sourceAppId'], connection['runStoreId'],
                               f'projects.{project_id}.stages.{stage_id}', connection['grantRevision'],
                               connection['limitPolicyRevision'])

    def client(target):
        return TaskRunClient(
            base_url=target.base_url,
            source_app_id=target.source_app_id,
            credential_ref=connection['credentialRef'],
            token=connection['token'],
            run_store_id=target.run_store_id,
            transport=httpx.AsyncHTTPTransport(retries=0, trust_env=False),
        )

    analysis = __import__('project_management.app.api.summary_analysis', fromlist=['SummaryAnalysisService']).SummaryAnalysisService(archive, contract, client)
    draft = build_report_service(project_api=project_api, archive=archive, contract=contract)
    service = ProjectRunService(project_api, archive, capture, analysis, draft, backend,
                                policy=_policy_from_settings(settings),
                                capture_limits=capture_limits_from_settings(settings))
    return ProjectRunRuntime(service, ProjectRunWorker(service))


def archive_config(root: Path) -> ArchiveStorageConfig:
    return ArchiveStorageConfig(root, 'Synthetic Validation', 'validation@example.test', archive_limits())


def create_provider_fixture(project_api, archive):
    detail = project_api.get_project(ProjectActor(ACTOR_SUBJECT), _current_ids(project_api)[0])
    stage = next(row for row in detail.stages if row.source_status == 'current')
    scenario = SimpleNamespace(actor=ProjectActor(ACTOR_SUBJECT), project=detail.project, stage=stage)
    fixture = JiraFixture(scenario, archive=archive, query=FROZEN_JQL)
    fixture.project_api = project_api
    fixture.service.project_api = project_api
    fixture.service = ProviderAccessService(project_api, fixture.resolver, {'jira': JiraCaptureAdapter()},
                                            archive, reader_factory=fixture.reader_factory,
                                            profile_registry=fixture.registry)
    fixture.rows = [qualification_issue()]
    fixture.comments = qualification_comments()
    fixture.transport = StrictJiraHttpAdapter(fixture)
    return fixture


def build_vector(project_id: str, stage) -> dict:
    snapshot = qualification_snapshot(stage)
    source_hash = content_hash({
        'identity': snapshot.identity,
        'facts': snapshot.facts,
        'comments_by_id': snapshot.comments_by_id,
        'history_by_id': snapshot.history_by_id,
        'attachments_by_id': snapshot.attachments_by_id,
        'dependencies_by_id': snapshot.dependencies_by_id,
    })
    reference = StoredSnapshotRef(snapshot.identity, CAPTURE_PLACEHOLDER, 1, None, source_hash,
                                  f'captures/{CAPTURE_PLACEHOLDER}/snapshots/{source_hash}.json')
    source_key = SourceChainKey('jira', endpoint_identifier('jira', ENDPOINT, 'server_pat'), '101',
                                'principal-1', stage.definition_hash)
    prepared = build_initial_input(project_id, stage, source_key, reference, snapshot, PROFILE_REVISION)
    value = json.loads(prepared.input_content)
    return {'schema_version': 1, 'scope_key': f'projects.{project_id}.stages.{stage.id}',
            'capture_placeholder': CAPTURE_PLACEHOLDER, 'input_template': value,
            'input_template_sha256': prepared.input_hash, 'output_template': expected_output(value)}


def qualification_snapshot(stage):
    identity = WorkItemIdentity('jira', endpoint_identifier('jira', ENDPOINT, 'server_pat'), '101', 'ALPHA-101')
    fields = qualification_issue()['fields']
    return __import__('project_management.app.api.capture_archive', fromlist=['SnapshotInput']).SnapshotInput(
        identity, fields, {row['id']: row for row in qualification_comments()}, {}, {}, {},
        CaptureCoverage(
            PartCoverage('complete', content_hash(fields), 1, 1, None),
            PartCoverage('complete', content_hash(qualification_comments()), 3, 3, None),
            PartCoverage('complete', content_hash([]), 0, 0, None),
            PartCoverage('not_requested', None, 0, 0, 'BODY_NOT_REQUESTED'),
            PartCoverage('not_requested', None, 0, 0, 'BODY_NOT_REQUESTED'),
        ),
        (), True,
    )


def qualification_issue():
    return issue(status='Fixed', summary='Intermittent validation failure',
                 assignee={'key': 'dev-a', 'displayName': 'Alice'},
                 reporter={'key': 'qa-b', 'displayName': 'Bob'},
                 description='Investigate retained evidence.')


def qualification_comments():
    return [
        comment(201, 'Failure observed.'),
        comment(202, 'Retained log text including Unicode: 原文 preserved. ' + 'x' * 13000),
        comment(203, 'Bob (qa-b), please rerun validation on build r8.'),
    ]


def expected_output(value: dict) -> dict:
    return {
        'kind': 'summary', 'binding': value['binding'], 'profile_revision': value['profile_revision'],
        'base_summary_id': None, 'target_capture_id': CAPTURE_PLACEHOLDER, 'output_language': 'en',
        'what': 'Intermittent failure during validation.',
        'current_position': 'The item is marked Fixed. A validation rerun on build r8 is requested.',
        'verification': 'The supplied evidence does not confirm that the rerun passed.',
        'next_actions': [{'action': 'Rerun validation on build r8.', 'owner_id': 'qa-b',
                          'owner_basis': 'explicit',
                          'owner_quote': 'Bob (qa-b), please rerun validation on build r8.',
                          'owner_confirmed': False, 'state': 'open', 'evidence': ['comment:203']}],
        'blockers': [], 'limitations': [], 'evidence': ['fields', 'comment:201', 'comment:202', 'comment:203'],
    }


def _scope_config() -> SavedScopeConfig:
    return SavedScopeConfig(None, 'QUALIFY Synthetic Jira Scope', 'QUAL', 'ALPHA', FROZEN_JQL, ['Bug'], ['Open'],
                            ['Fixed'], ['Closed'], [], ['Fixed'], ['Done'], ['Reopened'], 'priority', ['P1'],
                            ['P3'], 'component', 'assignee', 'team', 'fixVersion', 'fixVersion', '',
                            ['summary', 'status'], 'UTC', 'weekly', True)


def _current_ids(project_api) -> tuple[str, str]:
    projects = project_api.list_projects(ProjectActor(ACTOR_SUBJECT), limit=20)
    project = next(row for row in projects if row.key == 'qual-alpha')
    detail = project_api.get_project(ProjectActor(ACTOR_SUBJECT), project.id)
    return project.id, detail.stages[0].id


class StrictJiraHttpAdapter(requests.adapters.HTTPAdapter):
    def __init__(self, fixture):
        super().__init__(max_retries=0)
        self.fixture = fixture
        self.transcript = []

    def send(self, request, **kwargs):
        parsed = urlsplit(request.url)
        params = parse_qs(parsed.query, keep_blank_values=True)
        self._validate(request, parsed, params)
        simple = {key: values[0] for key, values in params.items()}
        status, value = self.fixture.respond(parsed.path, simple)
        data = value if isinstance(value, bytes) else json.dumps(value, ensure_ascii=False).encode('utf-8')
        self.transcript.append({'method': request.method, 'path': parsed.path, 'query': simple,
                                'response_sha256': hashlib.sha256(data).hexdigest()})
        response = requests.Response()
        response.status_code = status
        response.headers['Content-Type'] = 'application/json'
        response.headers['Content-Length'] = str(len(data))
        response.raw = HTTPResponse(body=io.BytesIO(data), preload_content=False)
        response.url = request.url
        response.request = request
        return response

    def _validate(self, request, parsed, params):
        if request.method != 'GET' or parsed.scheme != 'https' or parsed.netloc != 'tracker.example.test':
            raise AssertionError('Unexpected synthetic Jira authority.')
        if parsed.username or parsed.password or parsed.fragment:
            raise AssertionError('Unexpected synthetic Jira credentials or fragment.')
        if any(len(values) != 1 for values in params.values()):
            raise AssertionError('Unexpected duplicate synthetic Jira query key.')
        simple = {key: values[0] for key, values in params.items()}
        if not self._allowed(parsed.path, simple):
            raise AssertionError(f'Unexpected synthetic Jira request: {parsed.path} {simple}')

    def _allowed(self, path, params):
        if path == '/jira/rest/api/2/myself':
            return params == {}
        if path == '/jira/rest/api/2/search':
            base = {'jql': FROZEN_JQL, 'validateQuery': 'true', 'startAt': '0'}
            return (params == {**base, 'maxResults': '0', 'fields': 'id'}
                    or params == {**base, 'maxResults': '2',
                                  'fields': 'id,key,summary,updated,status,assignee,resolution,issuelinks'})
        if path == '/jira/rest/api/2/issue/101':
            return params == {'fields': '*all', 'expand': 'changelog,names,schema'}
        if path == '/jira/rest/api/2/issue/101/comment':
            return params in ({'startAt': '0', 'maxResults': '2'}, {'startAt': '2', 'maxResults': '2'})
        return False
