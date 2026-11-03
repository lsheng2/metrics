from datetime import UTC, datetime, timedelta
from pathlib import Path
from tempfile import TemporaryDirectory
import uuid

from django.test import TestCase

from project_management.app.api import ApiForProjectManagement, ProjectActor, ProjectError, ScopeSelection
from project_management.app.api.capture_archive import ArchiveLimits, ArchiveStorageConfig, CaptureIntent, CaptureSourceIdentity, RawPageInput
from project_management.container import build_capture_archive_service
from project_management.tests.fakes import FixedCatalog


class TestCaptureArchiveProjectWiring(TestCase):
    def test_archive_factory_uses_real_project_owner_and_keeps_archived_history_readable(self):
        actor = ProjectActor('real-api-owner')
        api = ApiForProjectManagement(FixedCatalog())
        project = api.create_project(actor, key='neutral', name='Neutral Project')
        stage = api.add_stage(actor, project.id, key='one', name='Stage One', selection=ScopeSelection('alpha-jira', 1))
        with TemporaryDirectory() as directory:
            config = ArchiveStorageConfig(
                Path(directory), 'Synthetic Operator', 'operator@example.test',
                ArchiveLimits(64 * 1024**2, 10000, 32 * 1024**2, 5000, 8 * 1024**2, 1000, 1024**2, 2 * 1024**2),
            )
            service = build_capture_archive_service(config, api)
            service.initialize_stage(actor, project.id, stage.id)
            intent = CaptureIntent(
                project.id, stage.id, str(uuid.uuid4()), str(uuid.uuid4()),
                CaptureSourceIdentity('jira', 'verified-test-site', stage.descriptor.endpoint,
                                      'test-principal', 'unknown:settings', stage.definition_hash),
                'a' * 64, ('facts', 'comments'), datetime.now(UTC) + timedelta(minutes=5),
            )
            service.prepare(actor, intent)
            page = service.append_page(actor, intent, RawPageInput('partial-page', None, 'text/plain', b'original', 'request-1'))
            api.archive_project(actor, project.id)
            receipt = service.finalize_partial(actor, project.id, stage.id, intent.capture_id, failure_code='project_archived')
            self.assertFalse(receipt.complete)
            self.assertEqual(b'original', service.read_page(actor, project.id, stage.id, intent.capture_id, page.page_id))
            with self.assertRaises(ProjectError):
                service.read_page(ProjectActor('other-owner'), project.id, stage.id, intent.capture_id, page.page_id)
