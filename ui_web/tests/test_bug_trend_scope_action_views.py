import json
from datetime import datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.core.files.uploadedfile import SimpleUploadedFile
from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendAuditEvent, BugTrendCalculationRun, BugTrendScopeProviderBinding, JiraScopeConfig
from jira_sync.app.api.scope_metadata import ScopeConfigOptions, TrackerFieldOption, TrackerOption
from jira_history.models import JiraIssue


from ui_web.tests.bug_trend_scope_config_test_support import BugTrendScopeConfigViewTestSupport


class TestBugTrendScopeActionViews(BugTrendScopeConfigViewTestSupport, TestCase):
    def test_shouldDisableScopeFromLibraryWithoutDeletingConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL disable from library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {'action': 'disable', 'scope_id': str(scope.id)})
        scope.refresh_from_db()

        # Then
        self.assertEqual(302, response.status_code)
        self.assertFalse(scope.enabled)
        self.assertTrue(JiraScopeConfig.objects.filter(id=scope.id).exists())

    def test_shouldExportScopeConfigPackageFromLibrary(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL export from library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'), {'export_scope_id': str(scope.id)})

        # Then
        package = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('attachment; filename="scope-%s.json"' % scope.id, response['Content-Disposition'])
        self.assertEqual('metrics.scope-config', package['format'])
        self.assertEqual('STDEL export from library', package['scope']['name'])
        self.assertIn('calculation_runs', package['excludes'])

    def test_shouldImportScopePackageAsArchivedScopeFromLibrary(self):
        # Given
        package = {
            'format': 'metrics.scope-config',
            'version': 1,
            'scope': {
                'id': 999,
                'name': 'STDEL imported library',
                'ip': 'NVU',
                'project_label': 'STDEL',
                'jql': 'project = STDEL',
                'bug_type_values': ['Bug'],
                'open_status_values': ['New'],
                'fixed_status_values': ['Fixed'],
                'closed_status_values': [],
                'terminal_excluded_status_values': [],
                'fixed_resolution_values': [],
                'closed_resolution_values': [],
                'reopen_status_values': [],
                'severity_field': 'priority',
                'critical_high_values': ['P1-Critical'],
                'medium_low_values': ['P3-Medium'],
                'component_field': '',
                'owner_field': 'assignee',
                'team_field': '',
                'milestone_field': '',
                'fix_version_field': '',
                'package_version_field': '',
                'display_fields': [],
                'timezone': 'UTC',
                'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
                'enabled': True,
                'config_version_hash': 'source-hash',
            },
            'provider_binding': {
                'profile_id': 'chiplet-2a-jira',
                'provider_id': 'jira',
                'status': 'explicit',
            },
        }
        upload = SimpleUploadedFile('scope.json', json.dumps(package).encode('utf-8'), content_type='application/json')

        # When
        response = self.client.post(
            reverse('ui_web:bug_trend_scope_library'),
            {'action': 'import_scope', 'scope_package': upload},
            follow=True,
        )

        # Then
        imported = JiraScopeConfig.objects.get(name='STDEL imported library imported')
        binding = BugTrendScopeProviderBinding.objects.get(scope=imported)
        self.assertEqual(200, response.status_code)
        self.assertFalse(imported.enabled)
        self.assertEqual('chiplet-2a-jira', binding.profile_id)
        self.assertIn('Imported STDEL imported library imported as an archived draft.', response.content.decode())

    def test_shouldDeleteOnlyArchivedScopeFromLibraryWithConfirmation(self):
        # Given
        enabled_scope = JiraScopeConfig.objects.create(
            name='STDEL enabled protected delete',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )
        archived_scope = JiraScopeConfig.objects.create(
            name='STDEL archived delete from library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            enabled=False,
        )

        # When
        protected_response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {
            'action': 'delete_archived',
            'scope_id': str(enabled_scope.id),
            'delete_confirmation': 'DELETE STDEL enabled protected delete',
        }, follow=True)
        deleted_response = self.client.post(reverse('ui_web:bug_trend_scope_library'), {
            'action': 'delete_archived',
            'scope_id': str(archived_scope.id),
            'delete_confirmation': 'DELETE STDEL archived delete from library',
        }, follow=True)

        # Then
        self.assertTrue(JiraScopeConfig.objects.filter(id=enabled_scope.id).exists())
        self.assertFalse(JiraScopeConfig.objects.filter(id=archived_scope.id).exists())
        self.assertIn('Only archived scopes can be deleted.', protected_response.content.decode())
        self.assertIn('Archived scope deleted', deleted_response.content.decode())

    def test_shouldRenderNewScopeEditorWithoutExistingScopeId(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Save Draft', content)
        self.assertIn('Enable Scope', content)
        self.assertIn('Cancel Editing', content)
        self.assertIn('scope-editor-actions', content)
        self.assertIn('provider-action-cancel', content)
        self.assertIn('data-dirty-form', content)
        self.assertIn('hx-include="closest form"', content)
        self.assertIn('value=""', content)
        self.assertNotIn('Scope Audit', content)

    def test_shouldMarkUnsavedScopeFieldAndShowConsistentEditorActionsInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})
        result = self._measure_scope_config_dirty_state(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(0, result['initial_dirty_fields'])
        self.assertTrue(result['dirty_field_highlighted'])
        self.assertTrue(result['dirty_control_highlighted'])
        self.assertTrue(result['dirty_banner_visible'])
        self.assertIn('Unsaved *', result['dirty_label_text'])
        self.assertTrue(result['cancel_button_visible'])
        self.assertLessEqual(result['action_button_height_delta'], 1)
        self.assertGreaterEqual(result['action_gap_px'], 8)
        self.assertFalse(result['page_horizontal_overflow'])

    def test_shouldHighlightActionRequiredScopeFieldsInBrowser(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})
        result = self._measure_scope_required_validation(response.content.decode())

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual(['name', 'jql', 'bug_type_values'], result['save_draft_missing_names'])
        self.assertTrue(result['save_draft_summary_visible'])
        self.assertEqual('scope-name', result['save_draft_focused_id'])
        self.assertIn('At least one bug type value is required before saving this scope.', result['save_draft_messages'])
        self.assertEqual(
            [
                'critical_high_values',
                'medium_low_values',
                'open_status_values',
                'fixed_status_values',
                'closed_status_values',
                'severity_field',
            ],
            result['enable_missing_names'],
        )
        self.assertTrue(result['enable_summary_visible'])
        self.assertEqual('scope-critical-high', result['enable_focused_id'])
        self.assertIn('Add at least one fixed or closed status value before enabling this scope.', result['enable_messages'])

    def test_shouldRenderDuplicateEditorAsDisabledDraftWithoutMutatingSource(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL source duplicate',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'duplicate_scope_id': str(scope.id)})
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('STDEL source duplicate copy', content)
        self.assertIn('Save Draft', content)
        self.assertNotIn('Scope Audit', content)
        self.assertTrue(scope.enabled)

    def test_shouldLinkUnmappedAuditSeverityIntoConfigEditorWithoutSaving(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL config handoff',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            severity_field='priority',
            critical_high_values=['P2-High'],
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-9001',
            issue_type='Bug',
            status='New',
            severity_value='P1-Stopper',
            created_at=datetime(2026, 8, 1, tzinfo=timezone.utc),
        )

        # When
        audit_response = self.client.get(reverse('ui_web:bug_trend_scope_audit'), {'scope_id': scope.id})
        config_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'scope_id': scope.id,
            'add_field': 'critical_high_values',
            'add_value': 'P1-Stopper',
        })
        scope.refresh_from_db()

        # Then
        self.assertEqual(200, audit_response.status_code)
        self.assertIn('Add as critical/high', audit_response.content.decode())
        self.assertEqual(200, config_response.status_code)
        self.assertIn('P1-Stopper', config_response.content.decode())
        self.assertEqual(['P2-High'], scope.critical_high_values)

    def test_shouldSaveScopeConfigAndShowRecalculationPromptWhenSemanticHashChanges(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL config save',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['New'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P2-High'],
            medium_low_values=['P3-Medium'],
            enabled=True,
        )
        original_hash = scope.config_version_hash
        BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=original_hash,
            source_coverage_start=datetime(2026, 8, 1, tzinfo=timezone.utc).date(),
            source_coverage_end=datetime(2026, 8, 31, tzinfo=timezone.utc).date(),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), self._post_payload(scope, 'P2-High\nP1-Stopper'), follow=True)
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertNotEqual(original_hash, scope.config_version_hash)
        self.assertEqual(['P2-High', 'P1-Stopper'], scope.critical_high_values)
        self.assertIn('Scope config saved.', content)
        self.assertIn('Semantic config changed. Recalculate this scope before using existing Bug Trend runs as current evidence.', content)

    def test_shouldRenderExistingEnabledScopeSaveAsChangesNotDraft(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL enabled edit label',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Save Changes', content)

    def test_shouldRenderValidationErrorsWhenScopeConfigPostIsInvalid(self):
        # Given
        first_scope = JiraScopeConfig.objects.create(
            name='STDEL duplicate owner',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        second_scope = JiraScopeConfig.objects.create(
            name='STDEL editable',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        payload = self._post_payload(second_scope, 'P2-High')
        payload['name'] = first_scope.name

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload)
        second_scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Scope config was not saved.', content)
        self.assertIn('name: Scope name must be unique.', content)
        self.assertEqual('STDEL editable', second_scope.name)

    def test_shouldCreateDraftScopeWhenScopeConfigPostHasNoId(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL editable no id',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        payload = self._post_payload(scope, 'P2-High')
        payload['id'] = ''
        payload['name'] = 'STDEL created from form'
        payload['action'] = 'save_draft'

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload, follow=True)

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        created = JiraScopeConfig.objects.get(name='STDEL created from form')
        self.assertFalse(created.enabled)
        self.assertIn('Scope config saved.', content)

    def test_shouldRenderValidationErrorsWhenScopeConfigPostHasMalformedId(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL editable bad id',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        payload = self._post_payload(scope, 'P2-High')
        payload['id'] = 'abc'

        # When
        response = self.client.post(reverse('ui_web:bug_trend_scope_config'), payload)

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Scope config was not saved.', content)
        self.assertIn('id: Scope id must be numeric.', content)

    def test_shouldRenderValidationErrorsWhenScopeConfigGetHasMalformedScopeId(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'scope_id': 'abc'})

        # Then
        content = response.content.decode()
        self.assertEqual(400, response.status_code)
        self.assertIn('Scope config was not saved.', content)
        self.assertIn('scope_id: A valid scope id is required.', content)
        self.assertNotIn('Save scope config', content)
