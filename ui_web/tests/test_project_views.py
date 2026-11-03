from django.conf import settings
from django.test import TestCase, override_settings
from django.urls import reverse

from project_management.app.api import ProjectActor, ScopeSelection
from project_management.models import Project
from ui_web.project_sources import ProjectSourceChoices
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectViews(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.start_profile_registry()

    def test_shouldCreateProjectsThroughPostAndListOnlyVerifiedOwnersProjects(self):
        # Given / When
        for key, name in [('alpha', 'Alpha'), ('beta', 'Beta')]:
            response = self.client.post(reverse('ui_web:projects'), {'key': key, 'name': name}, **self.auth('alice'))
            self.assertEqual(302, response.status_code)
        self.client.post(reverse('ui_web:projects'), {'key': 'gamma', 'name': 'Gamma'}, **self.auth('bob'))

        # Then
        response = self.client.get(reverse('ui_web:projects'), **self.auth('alice'))
        content = response.content.decode('utf-8')
        self.assertEqual(200, response.status_code)
        self.assertIn('Alpha', content)
        self.assertIn('Beta', content)
        self.assertNotIn('Gamma', content)

    def test_shouldPreserveFailedCreateInputAndKeepStablePagination(self):
        # Given
        invalid = self.client.post(
            reverse('ui_web:projects'),
            {'key': 'Invalid Key', 'name': 'Draft Name'},
            **self.auth('alice'),
        )
        for index in range(51):
            self.create_project('alice', key=f'project-{index:02d}', name=f'Project {index:02d}')

        # When
        page = self.client.get(reverse('ui_web:projects'), {'offset': '50'}, **self.auth('alice'))

        # Then
        invalid_content = invalid.content.decode('utf-8')
        page_content = page.content.decode('utf-8')
        self.assertEqual(400, invalid.status_code)
        self.assertIn('value="Invalid Key"', invalid_content)
        self.assertIn('value="Draft Name"', invalid_content)
        self.assertEqual(200, page.status_code)
        self.assertIn('Project 50', page_content)
        self.assertIn('offset=0', page_content)

    def test_shouldPreserveCreateInputWhenProjectKeyConflictsWithDifferentName(self):
        # Given
        self.create_project('alice', key='alpha', name='Alpha')

        # When
        response = self.client.post(
            reverse('ui_web:projects'),
            {'key': 'alpha', 'name': 'Changed Alpha'},
            **self.auth('alice'),
        )

        # Then
        content = response.content.decode('utf-8')
        self.assertEqual(409, response.status_code)
        self.assertIn('Project key is already used with different details.', content)
        self.assertIn('value="alpha"', content)
        self.assertIn('value="Changed Alpha"', content)

    def test_shouldRejectMalformedAndOversizedOffsetsWithoutFallingBackToFirstPage(self):
        # Given
        self.create_project('alice', key='alpha', name='Alpha')

        # When / Then
        for raw_offset in ['abc', '-1', '2147483648', '9' * 40]:
            with self.subTest(raw_offset=raw_offset):
                response = self.client.get(reverse('ui_web:projects'), {'offset': raw_offset}, **self.auth('alice'))
                self.assertEqual(400, response.status_code)
                self.assertIn('Project request is invalid.', response.content.decode('utf-8'))

    def test_shouldRenderTranslatedSourceStatusWithoutMutatingDomainValue(self):
        # Given
        scope = self.create_jira_scope(name='Changing Jira')
        project = self.create_project('alice')
        self.api().add_stage(
            self.actor('alice'),
            project.id,
            key='release-1',
            name='Release 1',
            selection=ScopeSelection('alpha-jira', scope.id),
        )
        scope.jql = 'project = BETA'
        scope.save()
        self.client.cookies[settings.LANGUAGE_COOKIE_NAME] = 'zh-hans'

        # When
        response = self.client.get(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), **self.auth('alice'))
        detail = self.api().get_project(ProjectActor('basic:alice'), project.id)

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual('source_changed', detail.stages[0].source_status)
        self.assertIn('来源已变更', response.content.decode('utf-8'))

    def test_shouldExposeOnlySafeCurrentJiraAndHsdesSourceChoices(self):
        # Given
        explicit = self.create_jira_scope(name='Explicit Jira')
        self.create_jira_scope(name='Compatibility Jira', status='compatibility')
        self.create_jira_scope(name='Mismatched Jira', provider_id='hsdes')
        self.create_jira_scope(name='Disabled Jira', enabled=False)

        # When
        choices = ProjectSourceChoices().list_choices()

        # Then
        keys = [choice.key for choice in choices]
        self.assertIn(f'jira/alpha-jira/{explicit.id}', keys)
        self.assertIn('hsdes/beta-hsd', keys)
        self.assertNotIn('hsdes/disabled-hsd', keys)
        self.assertEqual(2, len(keys))
        self.assertEqual('jira', choices[0].provider_id)
        self.assertEqual(explicit.id, choices[0].selection.scope_id)

    def test_shouldRejectDisabledOrMismatchedDisplayedSourceAtDomainConfirmation(self):
        # Given
        scope = self.create_jira_scope()
        project = self.create_project('alice')
        Project.objects.filter(id=project.id).update(name='Alpha Project')

        # When
        response = self.client.post(
            reverse('ui_web:project_stage_preview', kwargs={'project_id': project.id}),
            {'key': 'release-1', 'name': 'Release 1', 'source': f'jira/alpha-jira/{scope.id + 1000}'},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(400, response.status_code)
        self.assertIn('Select a valid choice', response.content.decode('utf-8'))
