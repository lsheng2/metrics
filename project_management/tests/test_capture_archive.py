from dataclasses import replace
from datetime import UTC, datetime, timedelta
import hashlib
import os
from pathlib import Path
import re
import subprocess
from tempfile import TemporaryDirectory
import unittest
import uuid

from project_management.app.domain.captures import (
    ArchiveError,
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
from project_management.app.api.capture_archive import CaptureArchiveService
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


class CaptureArchiveCase(unittest.TestCase):
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

    def test_shouldArchiveCaptureRawBytesAndSnapshotThroughPublicServiceUsingRealGit(self):
        with self.archive_service() as (root, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            prepared = service.prepare(self.actor, intent)
            page = RawPageInput(
                page_key='facts-page-1',
                item=self.item(),
                content_type='application/json; charset=utf-8',
                payload='{"summary":"保留原始字节","emoji":"🚀"}'.encode('utf-8'),
                request_fingerprint='request-page-1',
            )

            page_ref = service.append_page(self.actor, intent, page)
            snapshot_ref = service.append_snapshot(self.actor, intent, self.snapshot((page_ref.page_id,)))
            receipt = service.finalize(
                self.actor,
                intent,
                MembershipInput((self.item(),), self.complete_part(), (page_ref.page_id,)),
                complete=True,
            )

            archive = self.archive_path(root)
            manifest_bytes = self.git(archive, 'show', f'{receipt.commit_id}:captures/{intent.capture_id}/manifest.json')
            self.assertEqual(receipt.commit_id, self.git_text(archive, 'rev-parse', 'main'))
            self.assertEqual(hashlib.sha256(manifest_bytes).hexdigest(), receipt.manifest_sha256)
            self.assertEqual(page.payload, service.read_page(self.actor, self.project.id, self.stage.id, intent.capture_id, page_ref.page_id))
            self.assertEqual(snapshot_ref.source_hash, service.source_chain(
                self.actor,
                self.project.id,
                self.stage.id,
                SourceChainKey(
                    snapshot_ref.identity.provider_id,
                    snapshot_ref.identity.endpoint_id,
                    snapshot_ref.identity.stable_id,
                    intent.source.principal_id,
                    intent.source.rule_hash,
                ),
                limit=1,
            ).items[0].source_hash)

    def test_shouldCheckOwnerBeforeCreatingArchiveRoot(self):
        with self.archive_service(create_root=False) as (root, service):
            with self.assertRaises(ProjectError) as raised:
                service.initialize_stage(ProjectActor('intruder'), self.project.id, self.stage.id)

            self.assertEqual('PROJECT_NOT_FOUND', raised.exception.code)
            self.assertFalse(root.exists())

    def test_shouldReplaySameRawPageAndRejectChangedBytesForSameCaptureIntent(self):
        with self.archive_service() as (_, service):
            service.initialize_stage(self.actor, self.project.id, self.stage.id)
            intent = self.intent()
            service.prepare(self.actor, intent)
            page = RawPageInput(
                page_key='raw-page',
                item=self.item(),
                content_type='text/plain; charset=utf-8',
                payload=b'original bytes',
                request_fingerprint='request-page-1',
            )

            first = service.append_page(self.actor, intent, page)
            replay = service.append_page(self.actor, intent, page)
            changed = replace(page, payload=b'changed bytes')

            self.assertEqual(first, replay)
            with self.assertRaises(ArchiveError) as raised:
                service.append_page(self.actor, intent, changed)
            self.assertEqual('ARCHIVE_CAPTURE_CONFLICT', raised.exception.code)

    def archive_service(self, create_root=True):
        case = self

        class ArchiveContext:
            def __enter__(self):
                self.temporary = TemporaryDirectory()
                root = Path(self.temporary.name) / 'project-reporting-archive'
                if create_root:
                    root.mkdir()
                checkout = Path.cwd().resolve()
                assert not root.resolve().is_relative_to(checkout)
                api = ProjectApiStub(case.project, case.stage)
                service = CaptureArchiveService(
                    api,
                    LocalArchiveRepositoryFactory(),
                    ArchiveStorageConfig(root, 'Archive Test', 'archive@example.test', case.limits()),
                )
                return root, service

            def __exit__(self, exc_type, exc, traceback):
                self.temporary.cleanup()

        return ArchiveContext()

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

    def intent(self):
        return CaptureIntent(
            project_id=self.project.id,
            stage_id=self.stage.id,
            capture_id=str(uuid.uuid4()),
            request_id=str(uuid.uuid4()),
            source=CaptureSourceIdentity(
                provider_id='jira',
                endpoint_id='alpha-endpoint',
                endpoint_url=self.stage.descriptor.endpoint,
                principal_id='principal:archive-owner',
                credential_revision='credential-revision-1',
                rule_hash=self.stage.definition_hash,
            ),
            original_input_hash='a' * 64,
            required_parts=('facts', 'comments'),
            deadline_at=datetime.now(UTC) + timedelta(minutes=10),
        )

    def item(self):
        return WorkItemIdentity('jira', 'alpha-endpoint', 'ALPHA-1', 'ALPHA-1')

    def snapshot(self, raw_page_ids):
        return SnapshotInput(
            identity=self.item(),
            facts={'summary': '保留原始字节', 'priority': 'P1'},
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


if __name__ == '__main__':
    unittest.main()
