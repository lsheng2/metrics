from copy import deepcopy
from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import json
from pathlib import Path
import uuid

from ai_base_application_sdk import TaskRunClient
import httpx

from project_management.app.api import ProjectActor, ProjectSummary, ScopeDescriptor, ScopeSelection, StageSummary
from project_management.app.api.capture_archive import (
    ArchiveLimits,
    ArchiveStorageConfig,
    CaptureCoverage,
    CaptureSourceIdentity,
    PartCoverage,
    RawPageInput,
    SnapshotInput,
    WorkItemIdentity,
)
from project_management.app.api.reports import ReportDraftService, ReportRenderer
from project_management.app.api.summary_analysis import AiBackendTarget, SummaryAnalysisService
from project_management.app.domain.capture_values import canonical_bytes
from project_management.app.domain.captures import ArchiveError
from project_management.app.domain.source_resolution import SourceResolutionInput
from project_management.app.spi.archive import CommitReceipt
from project_management.out.ai_task_contract import AiTaskContract
from project_management.services.capture import ProjectCaptureService
from project_management.services.capture_archive import CaptureArchiveService
from project_management.services.report_sources import ReportSourceReader
from project_management.storage.paths import safe_relative_path
from project_management.tests.capture_archive_fixtures import ProjectApiStub
from project_management.tests.report_render_fixtures import daily_template
from project_management.tests.summary_fixtures import PACK_ROOT
from provider_sync.app.api.access_contracts import ItemObservation, MembershipObservation, RequestUsage, WorkItemMarker


class FixedRunClock:
    def __init__(self, start=None):
        self.current = start or datetime.now(UTC).replace(microsecond=123456)

    def __call__(self):
        return self.current

    def advance(self, seconds):
        self.current = self.current + timedelta(seconds=seconds)


class ProviderLeaseDouble:
    def __init__(self, stage, items, *, principal_id='principal:archive-owner', incomplete_details=False):
        self.stage = stage
        self.items = tuple(items)
        self.incomplete_details = incomplete_details
        self.sink = None
        self.source_identity = CaptureSourceIdentity(
            stage.descriptor.provider_id,
            'alpha-endpoint',
            stage.descriptor.endpoint,
            principal_id,
            'credential-revision-1',
            stage.definition_hash,
        )
        self.resolved_scope = SourceResolutionInput(
            stage.definition_hash,
            stage.descriptor.provider_id,
            'alpha-endpoint',
            principal_id,
            stage.descriptor.query,
            (),
            'resolver-revision-1',
        )

    def __enter__(self):
        return self

    def __exit__(self, exc_type, exc, traceback):
        return None

    def attach_archive_sink(self, sink):
        self.sink = sink

    def enumerate(self):
        markers = []
        raw_page_ids = []
        for index, item in enumerate(self.items, 1):
            identity = self.identity(item)
            reference = self.sink.append_page(
                RawPageInput(
                    f'membership-{index}',
                    identity,
                    'application/json; charset=utf-8',
                    canonical_bytes({'stable_id': item['stable_id'], 'summary': item['summary']}),
                    f'membership-{index}',
                )
            )
            raw_page_ids.append(reference.page_id)
            markers.append(
                WorkItemMarker(
                    identity,
                    item.get('updated', '2026-11-02T00:00:00Z'),
                    'f' * 64,
                    {'summary': item['summary']},
                )
            )
        return MembershipObservation(
            tuple(markers),
            PartCoverage('complete', 'source-version-1', len(markers), len(markers), None),
            tuple(raw_page_ids),
            self.stage.definition_hash,
            RequestUsage(len(markers), 0),
        )

    def capture_item(self, marker):
        item = next(row for row in self.items if row['stable_id'] == marker.identity.stable_id)
        reference = self.sink.append_page(
            RawPageInput(
                f'detail-{item["stable_id"]}',
                marker.identity,
                'application/json; charset=utf-8',
                canonical_bytes({'stable_id': item['stable_id'], 'comments': item.get('comments', {})}),
                f'detail-{item["stable_id"]}',
            )
        )
        complete = not self.incomplete_details and item.get('complete', True)
        facts = {'summary': item['summary'], 'status': item.get('status', 'Fixed')}
        if item.get('assignee') is not None:
            facts['assignee'] = item['assignee']
        if item.get('reporter') is not None:
            facts['reporter'] = item['reporter']
        coverage = CaptureCoverage(
            PartCoverage('complete', 'facts-v1', 1, 1, None),
            PartCoverage('complete' if complete else 'partial', 'comments-v1',
                         len(item.get('comments', {})), len(item.get('comments', {})), None if complete else 'PROVIDER_HISTORY_PARTIAL'),
            PartCoverage('complete', 'history-v1', 0, 0, None),
            PartCoverage('not_requested', None, None, None, None),
            PartCoverage('not_requested', None, None, None, None),
        )
        snapshot = SnapshotInput(
            marker.identity,
            facts,
            item.get('comments', {}),
            {},
            {},
            {},
            coverage,
            (reference.page_id,),
            complete,
        )
        return ItemObservation(
            snapshot if complete else None,
            marker.identity,
            marker,
            coverage,
            () if complete else ('PROVIDER_HISTORY_PARTIAL',),
            RequestUsage(1, 0),
        )

    def verify_final(self):
        return None

    def identity(self, item):
        return WorkItemIdentity(self.stage.descriptor.provider_id, 'alpha-endpoint',
                                item['stable_id'], item.get('display_key', item['stable_id']))


class ProviderAccessDouble:
    def __init__(self, stage, items, *, incomplete_details=False):
        self.stage = stage
        self.items = tuple(items)
        self.incomplete_details = incomplete_details
        self.open_count = 0

    def open_capture(self, context, *, online=False, cancel_requested=None):
        if cancel_requested is not None and cancel_requested():
            from provider_sync.app.api.access_contracts import AccessError

            raise AccessError('CAPTURE_CANCELED')
        self.open_count += 1
        return ProviderLeaseDouble(self.stage, self.items, incomplete_details=self.incomplete_details)


class ProjectRunHttp:
    def __init__(self, contract):
        self.contract = contract
        self.requests = []
        self.force_running = False
        self.force_error = None
        self.on_result = None

    def client_factory(self, backend):
        def transport(request):
            self.requests.append((request.method, request.url.path))
            if self.force_error is not None:
                return httpx.Response(422, json={
                    'contractVersion': 'task-run/1',
                    'error': {'code': self.force_error, 'recovery': 'correct_request'},
                })
            if request.method == 'POST' and request.url.path == '/api/runs':
                payload = json.loads(request.content.decode('utf-8'))
                return httpx.Response(200, json=self.snapshot(payload, state='running' if self.force_running else 'succeeded'))
            if request.method == 'GET' and request.url.path.endswith('/result'):
                if self.on_result is not None:
                    self.on_result()
                    self.on_result = None
                return httpx.Response(200, json=self.result(self.last_submit))
            if request.method == 'POST' and request.url.path.endswith('/cancel'):
                snapshot = self.snapshot(self.last_submit, state='running')
                snapshot['state'] = 'canceled'
                snapshot['terminalAt'] = '2026-11-02T00:00:40.000Z'
                snapshot['result'] = {'availability': 'not_produced', 'sha256': None,
                                      'mediaType': None, 'expiresAt': None}
                snapshot['dispatch']['remoteStop'] = 'confirmed'
                return httpx.Response(200, json={
                    'contractVersion': 'task-run/1',
                    'cancelApplied': True,
                    'run': snapshot,
                })
            raise AssertionError(f'Unexpected Base request: {request.method} {request.url.path}')

        return TaskRunClient(
            base_url=backend.base_url,
            source_app_id=backend.source_app_id,
            run_store_id=backend.run_store_id,
            credential_ref='synthetic-test',
            token='synthetic-only',
            transport=httpx.MockTransport(transport),
        )

    def snapshot(self, submit, *, state):
        self.last_submit = deepcopy(submit)
        output_hash = hashlib.sha256(canonical_bytes(self.output(submit)).decode().encode()).hexdigest()
        return {
            **self.common(submit),
            'sourceAppId': 'metrics-dashboard',
            'clientRunKey': submit['clientRunKey'],
            'state': state,
            'lifecycleVersion': 2,
            'acceptedAt': '2026-11-02T00:00:00.000Z',
            'updatedAt': '2026-11-02T00:00:30.000Z',
            'terminalAt': None if state == 'running' else '2026-11-02T00:00:30.000Z',
            'deadlineAt': submit['deadlineAt'],
            'grantRevision': 'dashboard-join-1',
            'limitPolicyRevision': 'base-b-cancel-synthetic-1',
            'acceptedLimits': submit['limits'],
            'resultRetentionSeconds': 3600,
            'observationRetentionSeconds': 7200,
            'observationExpiresAt': '2026-11-02T02:00:30.000Z',
            'unresolvedExposure': False,
            'dispatch': {'attemptCount': 1, 'knowledge': 'response_received', 'remoteStop': 'not_requested'},
            'result': {
                'availability': 'pending' if state == 'running' else 'available',
                'sha256': None if state == 'running' else output_hash,
                'mediaType': None if state == 'running' else 'application/json',
                'expiresAt': None if state == 'running' else '2026-11-02T01:00:30.000Z',
            },
            'error': None,
        }

    def result(self, submit):
        content = canonical_bytes(self.output(submit)).decode()
        return {
            **self.common(submit),
            'outputSchemaSha256': self.contract.output_schema_hash,
            'content': content,
            'mediaType': 'application/json',
            'sha256': hashlib.sha256(content.encode()).hexdigest(),
        }

    def common(self, submit):
        return {
            'contractVersion': 'task-run/1',
            'runStoreId': 'store-fixture',
            'runId': 'run-fixture',
            'scopeKey': submit['scopeKey'],
            'profile': dict(submit['profile'], definitionSha256=self.contract.definition_hash),
            'inputSha256': submit['input']['sha256'],
            'logicalInputHash': submit['logicalInputHash'],
            'effectiveInputSha256': hashlib.sha256(b'synthetic compiled fixture').hexdigest(),
            'receipt': {
                'revision': 1,
                'executionMode': 'synthetic',
                'backendId': 'fixture',
                'modelName': None,
                'qualificationRef': None,
                'inputTokens': {'value': None, 'certainty': 'unknown'},
                'outputTokens': {'value': None, 'certainty': 'unknown'},
                'providerRequests': {'value': 0, 'certainty': 'known'},
                'cost': {'amountDecimal': None, 'currency': None, 'certainty': 'unknown'},
            },
        }

    def output(self, submit):
        value = json.loads(submit['input']['content'])
        return {
            'kind': 'summary',
            'binding': value['binding'],
            'profile_revision': value['profile_revision'],
            'base_summary_id': None,
            'target_capture_id': value['target_capture_id'],
            'output_language': 'en',
            'what': 'Intermittent failure during validation.',
            'current_position': 'The item is marked Fixed. A validation rerun on build r8 is requested.',
            'verification': 'The supplied evidence does not confirm that the rerun passed.',
            'next_actions': [{
                'action': 'Rerun validation on build r8.',
                'owner_id': 'qa-b',
                'owner_basis': 'explicit',
                'owner_quote': 'Bob (qa-b), please rerun validation on build r8.',
                'owner_confirmed': False,
                'state': 'open',
                'evidence': ['comment:203'],
            }],
            'blockers': [],
            'limitations': [],
            'evidence': ['fields', 'comment:201', 'comment:202', 'comment:203'],
        }


class MemoryStageState:
    def __init__(self, head='a' * 40):
        self.files = {}
        self.commits = {}
        self.commit = head
        self.parents = {head: None}


class WritableStageMemoryRepository:
    def __init__(self, root, project, stage, owner_subject, state):
        self.root = root
        self.project = project
        self.stage = stage
        self.owner_subject = owner_subject
        self.state = state
        self.stage_root = root / 'projects' / project.id / 'stages' / stage.id
        self.archive = self.stage_root / 'archive'
        self.runtime = self.stage_root / 'runtime'
        self.objects = self.stage_root / 'objects'
        self.git = None

    def initialize(self):
        self.stage_root.mkdir(parents=True, exist_ok=True)
        self.archive.mkdir(parents=True, exist_ok=True)
        self.runtime.mkdir(parents=True, exist_ok=True)
        self.objects.mkdir(parents=True, exist_ok=True)
        return self.state.commit

    def verify_identity(self):
        self.initialize()
        return None

    def head(self):
        return self.state.commit

    def append_record(self, record_id, namespace, files, *, expected_head, record_fingerprint):
        self.initialize()
        if expected_head != self.state.commit:
            raise ArchiveError('ARCHIVE_CHAIN_CONFLICT')
        self._validate_record(namespace, files)
        parent = self.state.commit
        commit = f'{len(set(self.state.commits.values())) + 1:040x}'
        for path, data in files.items():
            self.state.files[path] = bytes(data)
            self.state.commits[path] = commit
        self.state.parents[commit] = parent
        self.state.commit = commit
        return CommitReceipt(commit, parent, 'f' * 40, record_fingerprint, 'current')

    def read_file(self, git_path, commit='main'):
        safe_relative_path(git_path)
        try:
            return self.state.files[git_path]
        except KeyError:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID') from None

    def list_files(self, prefix, commit='main'):
        safe_relative_path(prefix)
        return tuple(sorted(path for path in self.state.files if path == prefix or path.startswith(prefix.rstrip('/') + '/')))

    def commit_for_path(self, git_path):
        commit = self.find_commit_for_path(git_path)
        if commit is None:
            raise ArchiveError('ARCHIVE_MANIFEST_INVALID')
        return commit

    def find_commit_for_path(self, git_path, commit='main'):
        safe_relative_path(git_path)
        return self.state.commits.get(git_path)

    def parent_for_commit(self, commit_id):
        return self.state.parents.get(commit_id)

    def checkout_state(self, commit_id):
        return 'current' if commit_id == self.state.commit else 'stale'

    def _validate_record(self, namespace, files):
        allowed = {'bootstrap', 'source_resolution', 'captures', 'analysis_attempts', 'accepted_summaries'}
        if namespace not in allowed or not files:
            raise ArchiveError('UNSAFE_PATH')
        for path, data in files.items():
            parts = safe_relative_path(path)
            if parts[0] != namespace and not (namespace == 'bootstrap' and path == '.gitattributes'):
                raise ArchiveError('UNSAFE_PATH')
            if type(data) is not bytes:
                raise ArchiveError('ARCHIVE_MANIFEST_INVALID')


class WritableStageMemoryRepositoryFactory:
    _states = {}

    def open(self, config, project, stage, owner_subject):
        key = (str(config.root), project.id, stage.id, owner_subject)
        state = self._states.setdefault(key, MemoryStageState())
        return WritableStageMemoryRepository(config.root, project, stage, owner_subject, state)


class ManualRunEnvironment:
    def __init__(self, root: Path, *, items=None, policy=None, incomplete_details=False,
                 notifier=True, limits=None, capture_limits=None, project=None, stage=None):
        root.mkdir(parents=True, exist_ok=True)
        self.actor = ProjectActor('archive-owner')
        self.project = project or ProjectSummary(str(uuid.uuid4()), 'alpha', 'Alpha', False, datetime(2026, 11, 2, tzinfo=UTC))
        descriptor = ScopeDescriptor(
            provider_id='jira',
            profile_id='alpha-jira',
            endpoint='https://tracker.example.test/jira',
            source_ref='scope:1',
            query_kind='jql',
            query='project = ALPHA',
            source_version='query-version-1',
        )
        self.stage = stage or StageSummary(
            str(uuid.uuid4()),
            'release-1',
            'Release 1',
            ScopeSelection('alpha-jira', 1),
            descriptor,
            descriptor.definition_hash(),
            datetime(2026, 11, 2, tzinfo=UTC),
            'current',
        )
        self.clock = FixedRunClock()
        self.project_api = ProjectApiStub(self.project, self.stage)
        self.archive = CaptureArchiveService(
            self.project_api,
            WritableStageMemoryRepositoryFactory(),
            ArchiveStorageConfig(root, 'Archive Test', 'archive@example.test', limits or self.limits()),
        )
        self.contract = AiTaskContract.load(PACK_ROOT)
        self.http = ProjectRunHttp(self.contract)
        self.provider = ProviderAccessDouble(
            self.stage,
            items or (self.default_item(),),
            incomplete_details=incomplete_details,
        )
        self.capture_service = ProjectCaptureService(
            self.project_api,
            self.provider,
            self.archive,
            clock=self.clock,
            required_parts=('facts', 'comments', 'history'),
        )
        self.analysis_service = SummaryAnalysisService(
            self.archive,
            self.contract,
            self.http.client_factory,
            clock=self.clock,
        )
        self.draft_service = ReportDraftService(
            self.archive,
            ReportSourceReader(self.archive, self.contract),
            ReportRenderer(),
            clock=self.clock,
        )
        from project_management.app.api.project_runs import ProjectRunService, ProjectRunWorker

        self.backend_calls = 0
        self.run_service = ProjectRunService(
            self.project_api,
            self.archive,
            self.capture_service,
            self.analysis_service,
            self.draft_service,
            self.backend,
            policy=policy,
            capture_limits=capture_limits,
            clock=self.clock,
            notifier=(lambda *args: None) if notifier is True else notifier,
        )
        self.worker = ProjectRunWorker(self.run_service)

    def default_item(self):
        return {
            'stable_id': 'ALPHA-1',
            'summary': 'Intermittent validation failure',
            'status': 'Fixed',
            'assignee': {'key': 'dev-a', 'displayName': 'Alice'},
            'reporter': {'key': 'qa-b', 'displayName': 'Bob'},
            'comments': {
                '201': {'id': '201', 'body': 'Failure observed.', 'author': {'key': 'dev-a'}},
                '202': {'id': '202', 'body': 'Logs attached. Failure reproduced on build r7.'},
                '203': {'id': '203', 'body': 'Bob (qa-b), please rerun validation on build r8.'},
            },
        }

    def backend(self, actor, project_id, stage_id):
        self.backend_calls += 1
        return AiBackendTarget(
            'http://127.0.0.1:18888',
            'metrics-dashboard',
            'store-fixture',
            f'projects.{project_id}.stages.{stage_id}',
            'dashboard-join-1',
            'base-b-cancel-synthetic-1',
        )

    def request(self, command_id=None, *, timezone='Asia/Shanghai', template=None):
        from project_management.app.api.project_runs import RunRequest

        return RunRequest(
            command_id or str(uuid.uuid4()),
            self.stage.definition_hash,
            template or daily_template(),
            timezone,
        )

    def limits(self):
        return ArchiveLimits(
            max_root_bytes=64 * 1024 * 1024,
            max_root_files=10000,
            max_stage_bytes=32 * 1024 * 1024,
            max_stage_files=5000,
            max_capture_bytes=8 * 1024 * 1024,
            max_capture_files=1000,
            max_raw_page_bytes=1024 * 1024,
            max_object_bytes=2 * 1024 * 1024,
        )
