from datetime import datetime, timezone
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_sync.app.api.scope_metadata import ScopeConfigOptions, TrackerFieldOption, TrackerOption
from jira_history.models import JiraIssue


class FakeScopeMetadataFacade:
    def __init__(self):
        self.selected_projects = []

    def get_scope_config(self, scope_id):
        from bug_metrics.app.api import bug_trend_api
        return bug_trend_api.get_scope_config(scope_id)

    def scope_config_from_post(self, post_data):
        from ui_web.facades.bug_trend_facade import BugTrendFacade
        from bug_metrics.app.api import bug_trend_api
        return BugTrendFacade(bug_trend_api).scope_config_from_post(post_data)

    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return {'warnings': ['Metadata refresh failed: offline'], 'options': None}


class FakeSuccessfulScopeMetadataFacade(FakeScopeMetadataFacade):
    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return ScopeConfigOptions(
            projects=[TrackerOption('STDEL', 'STDEL')],
            item_types=[TrackerOption('1', 'Bug')],
            fields=[TrackerFieldOption('customfield_12345', 'Severity', 'Severity (customfield_12345)')],
        )


class FakePartialScopeMetadataFacade(FakeScopeMetadataFacade):
    def get_scope_metadata_options(self, config, selected_projects=None):
        self.selected_projects.append(selected_projects or [])
        return {
            'warnings': ['Unable to load component metadata'],
            'options': ScopeConfigOptions(
                projects=[TrackerOption('STDEL', 'STDEL')],
                fields=[TrackerFieldOption('customfield_12345', 'Severity', 'Severity (customfield_12345)')],
            ),
        }


class TestBugTrendScopeConfigViews(TestCase):
    def test_shouldRenderScopeLibraryWithCreateEditDuplicateAndDisableActions(self):
        # Given
        enabled_scope = JiraScopeConfig.objects.create(
            name='STDEL enabled library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=True,
        )
        JiraScopeConfig.objects.create(
            name='STDEL draft library',
            jql='project = STDEL',
            bug_type_values=['Bug'],
            enabled=False,
        )

        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_library'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('New scope', content)
        self.assertIn('STDEL enabled library', content)
        self.assertIn('STDEL draft library', content)
        self.assertIn(f'?scope_id={enabled_scope.id}', content)
        self.assertIn(f'?duplicate_scope_id={enabled_scope.id}', content)
        self.assertIn('Disable', content)
        self.assertIn('data-confirm="Disable this scope?', content)

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

    def test_shouldRenderNewScopeEditorWithoutExistingScopeId(self):
        # When
        response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {'mode': 'new'})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Save draft', content)
        self.assertIn('Save and enable', content)
        self.assertIn('Discard changes', content)
        self.assertIn('data-dirty-form', content)
        self.assertIn('hx-include="closest form"', content)
        self.assertIn('value=""', content)
        self.assertNotIn('Scope Audit', content)

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
        self.assertIn('Save draft', content)
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
        self.assertIn('Save changes', content)

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

    def test_shouldRefreshMetadataWithoutSavingScopeConfig(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata refresh',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )
        original_hash = scope.config_version_hash

        # When
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
            container.bug_trend_facade = FakeScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'id': str(scope.id),
                'name': scope.name,
                'jql': 'project = STDEL AND issuetype = Bug AND component = Emulation',
                'bug_type_values': 'Bug',
            })
        scope.refresh_from_db()

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertIn('Metadata refresh failed:', content)

    def test_shouldPassCommaSeparatedSelectedProjectsToMetadataRefresh(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata selected projects',
            jql='filter = 131600',
            bug_type_values=['Bug'],
        )
        facade = FakeScopeMetadataFacade()

        # When
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
            container.bug_trend_facade = facade
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {
                'scope_id': str(scope.id),
                'selected_projects': '131600, STDEL',
            })

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual([['131600', 'STDEL']], facade.selected_projects)

    def test_shouldPassRepeatedSelectedProjectValuesToMetadataRefresh(self):
        # Given
        facade = FakeScopeMetadataFacade()

        # When
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
            container.bug_trend_facade = facade
            response = self.client.get(
                reverse('ui_web:bug_trend_scope_metadata'),
                [('jql', 'filter = 131600'), ('bug_type_values', 'Bug'), ('selected_project', '131600'), ('selected_project', 'STDEL')],
            )

        # Then
        self.assertEqual(200, response.status_code)
        self.assertEqual([['131600', 'STDEL']], facade.selected_projects)

    def test_shouldRenderDiscoveredFieldOptionsInMetadataPartial(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL metadata fields',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
            container.bug_trend_facade = FakeSuccessfulScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Project: STDEL', content)
        self.assertIn('Type: Bug', content)
        self.assertIn('Field: Severity (customfield_12345)', content)

    def test_shouldRenderMetadataWarningsAlongsideDiscoveredOptions(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL partial metadata',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
        )

        # When
        with patch('ui_web.views.bug_trend_view.ui_web_container') as container:
            container.bug_trend_facade = FakePartialScopeMetadataFacade()
            response = self.client.get(reverse('ui_web:bug_trend_scope_metadata'), {'scope_id': str(scope.id)})

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Unable to load component metadata', content)
        self.assertIn('Project: STDEL', content)
        self.assertIn('Field: Severity (customfield_12345)', content)


    def _post_payload(self, scope, critical_high_values):
        return {
            'id': str(scope.id),
            'name': scope.name,
            'ip': scope.ip,
            'project_label': scope.project_label,
            'jql': scope.jql,
            'bug_type_values': '\n'.join(scope.bug_type_values),
            'open_status_values': '\n'.join(scope.open_status_values),
            'fixed_status_values': '\n'.join(scope.fixed_status_values),
            'closed_status_values': '\n'.join(scope.closed_status_values),
            'terminal_excluded_status_values': '\n'.join(scope.terminal_excluded_status_values),
            'fixed_resolution_values': '\n'.join(scope.fixed_resolution_values),
            'closed_resolution_values': '\n'.join(scope.closed_resolution_values),
            'reopen_status_values': '\n'.join(scope.reopen_status_values),
            'severity_field': scope.severity_field,
            'critical_high_values': critical_high_values,
            'medium_low_values': '\n'.join(scope.medium_low_values),
            'component_field': scope.component_field,
            'owner_field': scope.owner_field,
            'team_field': scope.team_field,
            'milestone_field': scope.milestone_field,
            'fix_version_field': scope.fix_version_field,
            'package_version_field': scope.package_version_field,
            'display_fields': '\n'.join(scope.display_fields),
            'timezone': scope.timezone,
            'bucket_granularity': scope.bucket_granularity,
            'enabled': 'on',
        }