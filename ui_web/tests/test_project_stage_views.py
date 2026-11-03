from django.test import TestCase, override_settings
from django.urls import reverse

from project_management.models import ProjectAuditEvent, ProjectStage
from ui_web.tests.project_fixtures import ProjectRouteTestSupport


@override_settings(METRICS_BASIC_AUTH_USERS=ProjectRouteTestSupport.basic_auth_users,
                   METRICS_PROJECT_LOCAL_OPERATOR_USERNAME='')
class TestProjectStageViews(ProjectRouteTestSupport, TestCase):
    def setUp(self):
        self.start_profile_registry()
        self.scope = self.create_jira_scope()

    def test_shouldPreviewConfirmOnceAndRejectReplayedOrTamperedPreview(self):
        # Given
        project = self.create_project('alice')

        # When
        preview = self.create_preview(project, self.scope)
        preview_id = self.preview_id()
        confirm = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )
        replay = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )
        tampered = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id + 'x'},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(200, preview.status_code)
        self.assertEqual(302, confirm.status_code)
        self.assertEqual(409, replay.status_code)
        self.assertEqual(409, tampered.status_code)
        self.assertEqual(1, ProjectStage.objects.count())
        self.assertEqual(1, ProjectAuditEvent.objects.filter(kind='stage_created').count())

    def test_shouldRejectFreshPreviewWhenOnlyPostedTokenChanges(self):
        # Given
        project = self.create_project('alice')
        self.create_preview(project, self.scope)
        preview_id = self.preview_id()

        # When
        response = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id[:-1] + ('A' if preview_id[-1] != 'A' else 'B')},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(409, response.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(0, ProjectAuditEvent.objects.filter(kind='stage_created').count())

    def test_shouldRejectFreshPreviewWhenOnlyPreviewActorChanges(self):
        # Given
        project = self.create_project('alice')
        self.create_preview(project, self.scope)
        preview_id = self.preview_id()
        session = self.client.session
        session['project_stage_preview'] = {
            **session['project_stage_preview'],
            'actor_subject': 'basic:bob',
        }
        session.save()

        # When
        response = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(409, response.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(0, ProjectAuditEvent.objects.filter(kind='stage_created').count())

    def test_shouldRejectFreshPreviewWhenOnlyRouteProjectChanges(self):
        # Given
        project = self.create_project('alice')
        other_project = self.create_project('alice', key='beta', name='Beta')
        self.create_preview(project, self.scope)
        preview_id = self.preview_id()

        # When
        response = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': other_project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(409, response.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(0, ProjectAuditEvent.objects.filter(kind='stage_created').count())

    def test_shouldRejectFreshPreviewWhenOnlyPreviewAgeChanges(self):
        # Given
        project = self.create_project('alice')
        self.create_preview(project, self.scope)
        preview_id = self.preview_id()
        self.expire_preview()

        # When
        response = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(409, response.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(0, ProjectAuditEvent.objects.filter(kind='stage_created').count())

    def test_shouldRejectUnicodePreviewTokenWithoutCompareDigestCrashOrMutation(self):
        # Given
        project = self.create_project('alice')
        self.create_preview(project, self.scope)

        # When
        response = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': '预览-token'},
            **self.auth('alice'),
        )

        # Then
        self.assertEqual(409, response.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(0, ProjectAuditEvent.objects.filter(kind='stage_created').count())

    def test_shouldRejectExpiredOtherProjectAndOtherOwnerPreviewsWithoutMutation(self):
        # Given
        project = self.create_project('alice')
        other_project = self.create_project('alice', key='beta', name='Beta')
        self.create_preview(project, self.scope)
        preview_id = self.preview_id()

        # When
        wrong_project = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': other_project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )
        self.expire_preview()
        expired = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )
        bob_session = self.client.session
        bob_session['project_stage_preview'] = {
            **bob_session['project_stage_preview'],
            'preview_id': 'other-owner-preview',
        }
        bob_session.save()
        other_owner = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': 'other-owner-preview'},
            **self.auth('bob'),
        )

        # Then
        self.assertEqual(409, wrong_project.status_code)
        self.assertEqual(409, expired.status_code)
        self.assertEqual(409, other_owner.status_code)
        self.assertEqual(0, ProjectStage.objects.count())

    @override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_shouldReturn503ForPreviewWhenSessionBackendIsClientSignedCookie(self):
        # Given
        project = self.create_project('alice')

        # When
        response = self.create_preview(project, self.scope)

        # Then
        self.assertEqual(503, response.status_code)
        self.assertIn('Project preview requires server-side sessions.', response.content.decode('utf-8'))
        self.assertEqual(0, ProjectStage.objects.count())

    @override_settings(SESSION_ENGINE='django.contrib.sessions.backends.signed_cookies')
    def test_shouldRenderTranslatedServerSessionError(self):
        # Given
        project = self.create_project('alice')
        self.client.cookies['django_language'] = 'zh-hans'

        # When
        response = self.create_preview(project, self.scope)

        # Then
        self.assertEqual(503, response.status_code)
        self.assertIn('项目预览需要服务器端会话', response.content.decode('utf-8'))

    def test_shouldBlockConfirmationAfterArchiveAndKeepArchivedDetailReadable(self):
        # Given
        project = self.create_project('alice')
        preview = self.create_preview(project, self.scope)
        preview_id = self.preview_id()

        # When
        archive = self.client.post(
            reverse('ui_web:project_archive', kwargs={'project_id': project.id}),
            {'confirm': 'on'},
            **self.auth('alice'),
        )
        confirm = self.client.post(
            reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id}),
            {'preview_id': preview_id},
            **self.auth('alice'),
        )
        detail = self.client.get(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), **self.auth('alice'))

        # Then
        content = detail.content.decode('utf-8')
        self.assertEqual(200, preview.status_code)
        self.assertEqual(302, archive.status_code)
        self.assertEqual(409, confirm.status_code)
        self.assertEqual(200, detail.status_code)
        self.assertIn('Archived', content)
        self.assertNotIn('name="source"', content)
        self.assertEqual(0, ProjectStage.objects.count())

    def test_shouldDisplayArchiveConfirmationErrors(self):
        # Given
        project = self.create_project('alice')

        # When
        response = self.client.post(
            reverse('ui_web:project_archive', kwargs={'project_id': project.id}),
            {},
            **self.auth('alice'),
        )

        # Then
        content = response.content.decode('utf-8')
        self.assertEqual(400, response.status_code)
        self.assertIn('This field is required.', content)
        self.assertIn('aria-invalid="true"', content)

    def test_shouldSwitchLanguageFromPreviewBackToDetailWithoutApprovingAndRetainDraft(self):
        # Given
        project = self.create_project('alice')
        preview = self.create_preview(project, self.scope, stage_key='release-zh')

        # When
        switch = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': reverse('ui_web:project_stage_confirm', kwargs={'project_id': project.id})},
            **self.auth('alice'),
        )
        detail = self.client.get(switch['Location'], **self.auth('alice'))

        # Then
        content = detail.content.decode('utf-8')
        self.assertEqual(200, preview.status_code)
        self.assertEqual(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), switch['Location'])
        self.assertEqual(200, detail.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertEqual(0, ProjectAuditEvent.objects.filter(kind='stage_created').count())
        self.assertIn('value="release-zh"', content)
        self.assertIn('value="Release 1"', content)
        self.assertIn(f'value="jira/alpha-jira/{self.scope.id}" selected', content)

    def test_shouldSwitchLanguageFromInvalidArchiveBackToDetailWithoutMutating(self):
        # Given
        project = self.create_project('alice')
        response = self.client.post(
            reverse('ui_web:project_archive', kwargs={'project_id': project.id}),
            {},
            **self.auth('alice'),
        )

        # When
        switch = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': reverse('ui_web:project_archive', kwargs={'project_id': project.id})},
            **self.auth('alice'),
        )
        detail = self.client.get(switch['Location'], **self.auth('alice'))

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), switch['Location'])
        self.assertEqual(200, detail.status_code)
        self.assertFalse(self.api().get_project(self.actor('alice'), project.id).project.archived)

    def test_shouldSwitchLanguageFromInvalidPreviewFormBackToDetailWithEnteredDraft(self):
        # Given
        project = self.create_project('alice')
        response = self.client.post(
            reverse('ui_web:project_stage_preview', kwargs={'project_id': project.id}),
            {'key': 'draft-stage', 'name': 'Draft Stage', 'source': 'not-a-source'},
            **self.auth('alice'),
        )

        # When
        switch = self.client.post(
            reverse('ui_web:project_language'),
            {'language': 'zh-hans', 'next': reverse('ui_web:project_stage_preview', kwargs={'project_id': project.id})},
            **self.auth('alice'),
        )
        detail = self.client.get(switch['Location'], **self.auth('alice'))

        # Then
        content = detail.content.decode('utf-8')
        self.assertEqual(400, response.status_code)
        self.assertEqual(reverse('ui_web:project_detail', kwargs={'project_id': project.id}), switch['Location'])
        self.assertEqual(200, detail.status_code)
        self.assertEqual(0, ProjectStage.objects.count())
        self.assertIn('value="draft-stage"', content)
        self.assertIn('value="Draft Stage"', content)
