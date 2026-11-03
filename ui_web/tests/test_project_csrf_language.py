from django.test import Client, TestCase, override_settings
from django.urls import reverse

from project_management.models import Project, ProjectAuditEvent, ProjectStage
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectCsrfAndAccess(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.start_profile_registry()
        self.scope = self.create_jira_scope()

    def test_shouldKeepCsrfProtectionOnEveryProjectPostRoute(self):
        # Given
        csrf_client = Client(enforce_csrf_checks=True)
        project = self.create_project('alice')
        posts = [
            (reverse('ui_web:projects'), {'key': 'alpha', 'name': 'Alpha'}),
            (reverse('ui_web:project_stage_preview', kwargs={'project_id': project.id}), {
                'key': 'release-1',
                'name': 'Release 1',
                'source': self.source_key(self.scope),
            }),
            (reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}), {'preview_id': 'missing'}),
            (reverse('ui_web:project_archive', kwargs={'project_id': project.id}), {'confirm': 'on'}),
            (reverse('ui_web:project_language'), {'language': 'zh-hans', 'next': reverse('ui_web:projects')}),
        ]

        # When / Then
        for path, payload in posts:
            with self.subTest(path=path):
                response = csrf_client.post(path, payload, **self.auth('alice'))
                self.assertEqual(403, response.status_code)

    def test_shouldReturn405ForWriteOnlyProjectRoutes(self):
        # Given
        project = self.create_project('alice')

        # When / Then
        for name in ['project_stage_preview', 'project_stage_confirm', 'project_archive']:
            with self.subTest(name=name):
                response = self.client.get(reverse(f'ui_web:{name}', kwargs={'project_id': project.id}), **self.auth('alice'))
                self.assertEqual(405, response.status_code)
        self.assertEqual(405, self.client.get(reverse('ui_web:project_language'), **self.auth('alice')).status_code)

    def test_shouldHideOtherOwnerDetailsAndRequireVerifiedIdentityEvenWhenLegacyAuthDisabled(self):
        # Given
        project = self.create_project('alice', name='Secret Alpha')

        # When
        other_owner = self.client.get(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), **self.auth('bob'))
        with self.settings(METRICS_BASIC_AUTH_USERS=None):
            anonymous = self.client.get(reverse('ui_web:projects'))

        # Then
        self.assertEqual(404, other_owner.status_code)
        self.assertNotIn('Secret Alpha', other_owner.content.decode('utf-8'))
        self.assertEqual(401, anonymous.status_code)
        self.assertEqual('Basic realm="Restricted"', anonymous['WWW-Authenticate'])


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectLanguage(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.start_profile_registry()
        self.scope = self.create_jira_scope()

    def test_shouldRenderEnglishAndChineseLabelsWithLocalLanguageRedirect(self):
        # Given
        english = self.client.get(reverse('ui_web:projects'), **self.auth('alice'))

        # When
        switch = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': 'https://example.invalid/projects/'},
            **self.auth('alice'),
        )
        chinese = self.client.get(reverse('ui_web:projects'), **self.auth('alice'))
        invalid = self.client.post(
            reverse('ui_web:projects'),
            {'key': 'Bad Key', 'name': ''},
            **self.auth('alice'),
        )

        # Then
        self.assertContains(english, 'Create project')
        english_content = english.content.decode('utf-8')
        self.assertIn('<html lang="en"', english_content)
        self.assertIn('<option value="en" selected', english_content)
        self.assertNotIn('Create and inspect provider-neutral project containers.', english_content)
        self.assertEqual(reverse('ui_web:projects'), switch['Location'])
        self.assertContains(chinese, '创建项目')
        chinese_content = chinese.content.decode('utf-8')
        self.assertIn('<html lang="zh-hans"', chinese_content)
        self.assertIn('<option value="zh-hans" selected', chinese_content)
        self.assertContains(invalid, '请使用小写字母、数字、下划线或短横线。', status_code=400)

    def test_shouldRejectUnsafeLanguageRedirectTargetsAndAllowLocalNext(self):
        # Given
        unsafe_targets = [
            'https://example.invalid/projects/',
            '//example.invalid/projects/',
            '///example.invalid/projects/',
            '/\\example.invalid/projects/',
            '/projects/\x01',
        ]

        # When / Then
        for target in unsafe_targets:
            with self.subTest(target=target):
                response = self.client.post(
                    reverse('ui_web:project_language'),
                    {'language': 'zh-hans', 'next': target},
                    **self.auth('alice'),
                )
                self.assertEqual(reverse('ui_web:projects'), response['Location'])

        local = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': '/projects/?offset=0'},
            **self.auth('alice'),
        )
        self.assertEqual('/projects/?offset=0', local['Location'])

    def test_shouldNormalizeLanguageNextToKnownProjectGetTargetsOnly(self):
        # Given
        project = self.create_project('alice')
        unknown_targets = ['/missing/', reverse('ui_web:workbench')]
        project_get_targets = [
            reverse('ui_web:projects'),
            reverse('ui_web:project_detail', kwargs={'project_id': project.id}),
        ]
        write_targets = [
            reverse('ui_web:project_stage_preview', kwargs={'project_id': project.id}),
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            reverse('ui_web:project_archive', kwargs={'project_id': project.id}),
        ]

        # When / Then
        for target in unknown_targets:
            with self.subTest(target=target):
                response = self.client.post(
                    reverse('ui_web:project_language'),
                    {'language': 'zh-hans', 'next': target},
                    **self.auth('alice'),
                )
                self.assertEqual(reverse('ui_web:projects'), response['Location'])

        for target in project_get_targets:
            with self.subTest(target=target):
                response = self.client.post(
                    reverse('ui_web:project_language'),
                    {'language': 'zh-hans', 'next': target},
                    **self.auth('alice'),
                )
                self.assertEqual(target, response['Location'])

        for target in write_targets:
            with self.subTest(target=target):
                response = self.client.post(
                    reverse('ui_web:project_language'),
                    {'language': 'zh-hans', 'next': target},
                    **self.auth('alice'),
                )
                self.assertEqual(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), response['Location'])

    def test_shouldKeepProjectStageAuditAndDescriptorBytesUnchangedWhenLocaleChanges(self):
        # Given
        project = self.create_project('alice')
        preview = self.create_preview(project, self.scope)
        self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': self.preview_id()},
            **self.auth('alice'),
        )
        before_descriptor = ProjectStage.objects.get().descriptor_json
        before_counts = (Project.objects.count(), ProjectStage.objects.count(), ProjectAuditEvent.objects.count())

        # When
        switch = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': reverse('ui_web:project_detail', kwargs={'project_id': project.id})},
            **self.auth('alice'),
        )
        after_descriptor = ProjectStage.objects.get().descriptor_json
        after_counts = (Project.objects.count(), ProjectStage.objects.count(), ProjectAuditEvent.objects.count())

        # Then
        self.assertEqual(200, preview.status_code)
        self.assertEqual(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), switch['Location'])
        self.assertEqual(before_descriptor, after_descriptor)
        self.assertEqual(before_counts, after_counts)
