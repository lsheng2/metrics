from dataclasses import asdict
from unittest.mock import patch

from django.db import OperationalError
from django.test import TestCase

from project_management.app.api import ApiForProjectManagement
from project_management.app.domain.contracts import ProjectActor, ProjectError, ScopeSelection
from project_management.models import Project, ProjectAuditEvent, ProjectStage
from project_management.tests.fakes import FixedCatalog


class TestProjectTransactions(TestCase):
    def setUp(self):
        self.catalog = FixedCatalog()
        self.actor = ProjectActor('operator')
        self.api = ApiForProjectManagement(self.catalog)
        self.project = self.api.create_project(self.actor, key='alpha', name='Alpha')

    def add(self):
        return self.api.add_stage(self.actor, self.project.id, key='release', name='Release',
                                  selection=ScopeSelection('alpha-jira', 1))

    def test_shouldRollbackStageWhenAuditWriteFails(self):
        with patch('project_management.out.orm_repository.ProjectAuditEvent.objects.create',
                   side_effect=OperationalError('disk write failed')):
            with self.assertRaises(OperationalError):
                self.add()
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(1, ProjectAuditEvent.objects.count())

    def test_shouldRejectTooManyStagesWithoutTruncatingNewStage(self):
        descriptor = self.catalog.descriptor
        ProjectStage.objects.bulk_create([
            ProjectStage(
                project_id=self.project.id, key=f'stage-{index}', name='Stage',
                selection_json=asdict(ScopeSelection('alpha-jira', 1)),
                descriptor_json=asdict(descriptor), definition_hash=descriptor.definition_hash(),
            )
            for index in range(100)
        ])
        with self.assertRaises(ProjectError) as raised:
            self.add()
        self.assertEqual('PROJECT_LIMIT', raised.exception.code)
        self.assertEqual(100, ProjectStage.objects.count())

    def test_shouldRecheckArchiveAtCommitBoundary(self):
        original = self.catalog.resolve

        def archive_during_prepare(selection):
            Project.objects.filter(pk=self.project.id).update(archived=True)
            return original(selection)

        self.catalog.resolve = archive_during_prepare
        with self.assertRaises(ProjectError) as raised:
            self.add()
        self.assertEqual('PROJECT_ARCHIVED', raised.exception.code)
        self.assertEqual(0, ProjectStage.objects.count())

    def test_shouldReportStorageContentionWithoutMutation(self):
        with patch('project_management.out.orm_repository.Project.objects.filter',
                   side_effect=OperationalError('database is locked')):
            with self.assertRaises(ProjectError) as raised:
                self.api.archive_project(self.actor, self.project.id)
        self.assertEqual('PROJECT_BUSY', raised.exception.code)
        self.assertFalse(Project.objects.get(pk=self.project.id).archived)

    def test_shouldRejectStoredDescriptorIntegrityFailure(self):
        self.add()
        ProjectStage.objects.update(definition_hash='0' * 64)
        with self.assertRaisesRegex(ValueError, 'integrity'):
            self.api.get_project(self.actor, self.project.id)
