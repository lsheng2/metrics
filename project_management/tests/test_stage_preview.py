from dataclasses import replace

from django.test import TestCase

from project_management.app.api import ApiForProjectManagement, ProjectActor, ScopeSelection, StagePreview
from project_management.app.domain.contracts import ProjectError
from project_management.models import ProjectAuditEvent, ProjectStage
from project_management.tests.fakes import FixedCatalog


class CountingCatalog(FixedCatalog):
    def __init__(self):
        super().__init__()
        self.calls = 0

    def resolve(self, selection):
        self.calls += 1
        return super().resolve(selection)


class TestStagePreview(TestCase):
    def setUp(self):
        self.catalog = CountingCatalog()
        self.api = ApiForProjectManagement(self.catalog)
        self.actor = ProjectActor('operator-a')

    def project(self):
        return self.api.create_project(self.actor, key='alpha', name='Alpha')

    def assert_error(self, code, action):
        with self.assertRaises(ProjectError) as raised:
            action()
        self.assertEqual(code, raised.exception.code)

    def test_shouldPreviewOwnedStageDefinitionWithoutMutatingProjectHistory(self):
        # Given
        project = self.project()

        # When
        preview = self.api.preview_stage(
            self.actor,
            project.id,
            key='release-1',
            name=' Release 1 ',
            selection=ScopeSelection('alpha-jira', 1),
        )

        # Then
        self.assertIsInstance(preview, StagePreview)
        self.assertEqual((project.id, 'release-1', 'Release 1'), (preview.project_id, preview.key, preview.name))
        self.assertEqual(ScopeSelection('alpha-jira', 1), preview.selection)
        self.assertEqual(self.catalog.descriptor, preview.descriptor)
        self.assertEqual(self.catalog.descriptor.definition_hash(), preview.definition_hash)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(1, ProjectAuditEvent.objects.count())

    def test_shouldRejectArchivedOrOtherOwnerPreviewBeforeResolvingSource(self):
        # Given
        project = self.project()
        other = ProjectActor('operator-b')

        # When / Then
        self.catalog.calls = 0
        self.assert_error('PROJECT_NOT_FOUND', lambda: self.api.preview_stage(
            other,
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
        ))
        self.assertEqual(0, self.catalog.calls)

        self.api.archive_project(self.actor, project.id)
        self.catalog.calls = 0
        self.assert_error('PROJECT_ARCHIVED', lambda: self.api.preview_stage(
            self.actor,
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
        ))
        self.assertEqual(0, self.catalog.calls)

    def test_shouldRejectConfirmationWhenSourceChangesAfterPreviewWithoutMutation(self):
        # Given
        project = self.project()
        preview = self.api.preview_stage(
            self.actor,
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
        )
        self.catalog.descriptor = replace(self.catalog.descriptor, query='project = BETA')

        # When / Then
        self.assert_error('SOURCE_CHANGED', lambda: self.api.add_stage(
            self.actor,
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
            expected_definition_hash=preview.definition_hash,
        ))
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(1, ProjectAuditEvent.objects.count())

        stage = self.api.add_stage(
            self.actor,
            project.id,
            key='release-2',
            name='Release 2',
            selection=ScopeSelection('alpha-jira', 1),
        )
        self.assertEqual(self.catalog.descriptor.definition_hash(), stage.definition_hash)

    def test_shouldKeepDoubleResolveSourceGuardWhenExpectedHashMatchesFirstResolve(self):
        # Given
        project = self.project()
        preview = self.api.preview_stage(
            self.actor,
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
        )
        descriptor = self.catalog.descriptor
        calls = []

        def changing_source(selection):
            calls.append(selection)
            if len(calls) == 1:
                return descriptor
            return replace(descriptor, query='project = GAMMA')

        self.catalog.resolve = changing_source

        # When / Then
        self.assert_error('SOURCE_CHANGED', lambda: self.api.add_stage(
            self.actor,
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', 1),
            expected_definition_hash=preview.definition_hash,
        ))
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(1, ProjectAuditEvent.objects.count())
