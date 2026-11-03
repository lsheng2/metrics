from dataclasses import replace
from datetime import UTC, datetime, timedelta
import os
from pathlib import Path
import subprocess
from tempfile import TemporaryDirectory
import uuid

from project_management.app.api.capture_archive import CaptureArchiveService
from project_management.app.domain.captures import (
    ArchiveLimits,
    ArchiveStorageConfig,
    CaptureCoverage,
    CaptureIntent,
    CaptureSourceIdentity,
    MembershipInput,
    PartCoverage,
    RawPageInput,
    SnapshotInput,
    SourceChainKey,
    WorkItemIdentity,
)
from project_management.app.domain.contracts import (
    ProjectActor,
    ProjectDetail,
    ProjectError,
    ProjectSummary,
    ScopeDescriptor,
    ScopeSelection,
    StageSummary,
)
from project_management.out.capture_archive import LocalArchiveRepositoryFactory


class ProjectApiStub:
    def __init__(self, project, stage, owner_subject='archive-owner'):
        self.project = project
        self.stage = stage
        self.owner_subject = owner_subject
        self.calls = 0

    def get_project(self, actor, project_id):
        self.calls += 1
        if actor.subject != self.owner_subject or project_id != self.project.id:
            raise ProjectError('PROJECT_NOT_FOUND')
        return ProjectDetail(self.project, (self.stage,))


class ArchiveFixture:
    def __init__(self, case, *, limits=None, create_root=True):
        self.case = case
        self.limits = limits
        self.create_root = create_root

    def __enter__(self):
        self.temporary = TemporaryDirectory()
        self.root = Path(self.temporary.name) / 'project-reporting-archive'
        if self.create_root:
            self.root.mkdir()
        checkout = Path.cwd().resolve()
        assert not self.root.resolve().is_relative_to(checkout)
        self.service = CaptureArchiveService(
            ProjectApiStub(self.case.project, self.case.stage),
            LocalArchiveRepositoryFactory(),
            ArchiveStorageConfig(self.root, 'Archive Test', 'archive@example.test', self.limits or self.case.limits()),
        )
        return self.root, self.service

    def __exit__(self, exc_type, exc, traceback):
        self.temporary.cleanup()


class CaptureArchiveScenario:
    def setUp(self):
        self.actor = ProjectActor('archive-owner')
        self.project = ProjectSummary(str(uuid.uuid4()), 'alpha', 'Alpha', False, datetime.now(UTC))
        descriptor = ScopeDescriptor(
            provider_id='jira',
            profile_id='alpha-jira',
            endpoint='https://tracker.example.test/jira',
            source_ref='scope:1',
            query_kind='jql',
            query='project = ALPHA',
            source_version='query-version-1',
        )
        self.stage = StageSummary(
            id=str(uuid.uuid4()),
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
            descriptor=descriptor,
            definition_hash=descriptor.definition_hash(),
            created_at=datetime.now(UTC),
            source_status='current',
        )

    def archive_service(self, *, limits=None, create_root=True):
        return ArchiveFixture(self, limits=limits, create_root=create_root)

    def limits(self, **overrides):
        values = {
            'max_root_bytes': 64 * 1024 * 1024,
            'max_root_files': 10000,
            'max_stage_bytes': 32 * 1024 * 1024,
            'max_stage_files': 5000,
            'max_capture_bytes': 8 * 1024 * 1024,
            'max_capture_files': 1000,
            'max_raw_page_bytes': 1024 * 1024,
            'max_object_bytes': 2 * 1024 * 1024,
        }
        values.update(overrides)
        return ArchiveLimits(**values)

    def intent(self, *, capture_id=None, principal_id='principal:archive-owner', deadline_at=None):
        return CaptureIntent(
            project_id=self.project.id,
            stage_id=self.stage.id,
            capture_id=capture_id or str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            source=CaptureSourceIdentity(
                provider_id='jira',
                endpoint_id='alpha-endpoint',
                endpoint_url=self.stage.descriptor.endpoint,
                principal_id=principal_id,
                credential_revision='credential-revision-1',
                rule_hash=self.stage.definition_hash,
            ),
            original_input_hash='a' * 64,
            required_parts=('facts', 'comments'),
            deadline_at=deadline_at or datetime.now(UTC) + timedelta(minutes=10),
        )

    def item(self, *, stable_id='ALPHA-1', display_key='ALPHA-1'):
        return WorkItemIdentity('jira', 'alpha-endpoint', stable_id, display_key)

    def source_key(self, intent, item=None):
        identity = item or self.item()
        return SourceChainKey(
            identity.provider_id,
            identity.endpoint_id,
            identity.stable_id,
            intent.source.principal_id,
            intent.source.rule_hash,
        )

    def page(self, payload=b'{"summary":"raw bytes"}', *, page_key='facts-page-1', item=None):
        return RawPageInput(page_key, item or self.item(), 'application/json; charset=utf-8', payload, 'request-page-1')

    def snapshot(self, raw_page_ids, *, item=None, summary='retained facts'):
        return SnapshotInput(
            identity=item or self.item(),
            facts={'summary': summary, 'priority': 'P1'},
            comments_by_id={'c1': {'id': 'c1', 'body': 'needs review'}},
            history_by_id={},
            attachments_by_id={},
            dependencies_by_id={},
            coverage=CaptureCoverage(
                facts=self.complete_part(),
                comments=self.complete_part(),
                history=PartCoverage('not_requested', None, None, None, None),
                attachments=PartCoverage('not_requested', None, None, None, None),
                dependencies=PartCoverage('not_requested', None, None, None, None),
            ),
            raw_page_ids=raw_page_ids,
            consistent=True,
        )

    def membership(self, page_id, *, item=None, state='complete'):
        return MembershipInput((item or self.item(),), PartCoverage(state, 'source-version-1', 1, 1, None), (page_id,))

    def complete_part(self):
        return PartCoverage('complete', 'source-version-1', 1, 1, None)

    def archive_path(self, root):
        return root / 'projects' / self.project.id / 'stages' / self.stage.id / 'archive'

    def git_text(self, root, *arguments):
        return self.git(root, *arguments).decode('utf-8').strip()

    def git(self, root, *arguments):
        environment = {key: value for key, value in os.environ.items() if not key.upper().startswith('GIT_')}
        result = subprocess.run(
            ['git', '-C', str(root), *arguments],
            check=True,
            stdin=subprocess.DEVNULL,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            env=environment,
            timeout=30,
        )
        return result.stdout
