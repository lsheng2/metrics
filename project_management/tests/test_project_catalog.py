from dataclasses import replace

from django.test import TestCase

from project_management.app.api import ApiForProjectManagement
from project_management.app.domain.contracts import ProjectActor, ProjectError, ScopeSelection
from project_management.models import ProjectAuditEvent
from project_management.tests.fakes import FixedCatalog


class TestProjectCatalog(TestCase):
    def setUp(self):
        self.catalog = FixedCatalog()
        self.api = ApiForProjectManagement(self.catalog)
        self.actor = ProjectActor('operator-a')

    def project(self, key='alpha'):
        return self.api.create_project(self.actor, key=key, name=key.title())

    def stage(self, project_id, key='release-1'):
        return self.api.add_stage(
            self.actor, project_id, key=key, name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
        )

    def assert_error(self, code, action):
        with self.assertRaises(ProjectError) as raised:
            action()
        self.assertEqual(code, raised.exception.code)

    def test_shouldPersistArbitraryProjectsAcrossServiceReload(self):
        alpha = self.project()
        beta = self.project('beta')
        reloaded = ApiForProjectManagement(self.catalog)
        self.assertEqual(
            [(alpha.id, 'alpha', 'Alpha'), (beta.id, 'beta', 'Beta')],
            [(row.id, row.key, row.name) for row in reloaded.list_projects(self.actor)],
        )

    def test_shouldKeepOwnerProjectsSeparate(self):
        project = self.project()
        other = ProjectActor('operator-b')
        self.assertEqual((), self.api.list_projects(other))
        self.assert_error('PROJECT_NOT_FOUND', lambda: self.api.get_project(other, project.id))
        self.assert_error('PROJECT_NOT_FOUND', lambda: self.api.archive_project(other, project.id))
        self.catalog.available = False
        self.assert_error('PROJECT_NOT_FOUND', lambda: self.api.add_stage(
            other, project.id, key='stolen', name='Stolen', selection=ScopeSelection('alpha-jira', 1),
        ))

    def test_shouldCreateProjectIdempotentlyWithoutDuplicateAudit(self):
        first = self.project()
        second = self.project()
        self.assertEqual(first.id, second.id)
        self.assertEqual(1, ProjectAuditEvent.objects.count())
        self.assert_error('PROJECT_KEY_CONFLICT', lambda: self.api.create_project(
            self.actor, key='alpha', name='Changed',
        ))

    def test_shouldPageOnlyOwnersProjects(self):
        self.project()
        beta = self.project('beta')
        self.assertEqual((beta,), self.api.list_projects(self.actor, limit=1, offset=1))
        self.assert_error('INVALID_PROJECT', lambda: self.api.list_projects(self.actor, limit=0))

    def test_shouldRejectInvalidProjectKeysAndNamesBeforePersisting(self):
        for key, name in [('Alpha', 'Alpha'), ('../alpha', 'Alpha'), ('alpha', ''), ('alpha', 'A\nB')]:
            with self.subTest(key=key, name=name):
                self.assert_error('INVALID_PROJECT', lambda: self.api.create_project(self.actor, key=key, name=name))
        self.assertEqual((), self.api.list_projects(self.actor))

    def test_shouldFreezeStageAndReportChangedSourceWithoutRewriting(self):
        project = self.project()
        stage = self.stage(project.id)
        self.catalog.descriptor = replace(self.catalog.descriptor, query='project = BETA')
        detail = self.api.get_project(self.actor, project.id)
        self.assertEqual('source_changed', detail.stages[0].source_status)
        self.assertEqual('project = ALPHA', detail.stages[0].descriptor.query)
        self.assertEqual(stage.definition_hash, detail.stages[0].definition_hash)
        self.assert_error('STAGE_RULE_IMMUTABLE', lambda: self.stage(project.id))

    def test_shouldCreateStageIdempotentlyWithoutDuplicateAudit(self):
        project = self.project()
        first = self.stage(project.id)
        second = self.stage(project.id)
        self.assertEqual(first.id, second.id)
        self.assertEqual(2, ProjectAuditEvent.objects.count())
        self.assert_error('STAGE_RULE_IMMUTABLE', lambda: self.api.add_stage(
            self.actor, project.id, key='release-1', name='Different', selection=ScopeSelection('alpha-jira', 1),
        ))

    def test_shouldPreserveReadAccessWhenProjectArchivedAndSourceMissing(self):
        project = self.project()
        stage = self.stage(project.id)
        self.api.archive_project(self.actor, project.id)
        self.api.archive_project(self.actor, project.id)
        self.catalog.available = False
        detail = self.api.get_project(self.actor, project.id)
        self.assertTrue(detail.project.archived)
        self.assertEqual(stage.id, detail.stages[0].id)
        self.assertEqual('unavailable', detail.stages[0].source_status)
        self.assert_error('PROJECT_ARCHIVED', lambda: self.stage(project.id, 'release-2'))

    def test_shouldRejectSourceDriftBetweenTwoResolves(self):
        project = self.project()
        original = self.catalog.resolve
        calls = []

        def changing(selection):
            calls.append(selection)
            return replace(original(selection), query=f'project = ALPHA{len(calls)}')

        self.catalog.resolve = changing
        self.assert_error('SOURCE_CHANGED', lambda: self.stage(project.id))
        self.assertEqual((), self.api.get_project(self.actor, project.id).stages)

    def test_shouldNotRewriteHistoryWhenDefinitionSourceObjectChanges(self):
        project = self.project()
        self.stage(project.id)
        self.catalog.descriptor = replace(self.catalog.descriptor, endpoint='https://different.example.test')
        detail = self.api.get_project(self.actor, project.id)
        self.assertEqual('https://tracker.example.test', detail.stages[0].descriptor.endpoint)
        self.assertEqual('source_changed', detail.stages[0].source_status)
