from django.core.exceptions import ObjectDoesNotExist
from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.app.api.scope_config import SavedScopeConfig
from bug_metrics.models import BugTrendAuditEvent, JiraScopeConfig
from jira_history.models import JiraIssue


class TestScopeConfigApi(TestCase):
    def test_shouldLoadSavedScopeConfigFromJiraScopeConfigAuthority(self):
        # Given
        scope = self._create_scope(name='STDEL load', critical_high_values=['P1-Critical'])

        # When
        config = bug_trend_api.get_scope_config(scope.id)

        # Then
        self.assertEqual(scope.id, config.id)
        self.assertEqual('STDEL load', config.name)
        self.assertEqual(['P1-Critical'], config.critical_high_values)
        self.assertEqual(scope.config_version_hash, config.config_version_hash)

    def test_shouldValidateRequiredFieldsAndSemanticShapesBeforeSave(self):
        # Given
        config = self._scope_config(name='', jql='', bucket_granularity='monthly')

        # When
        result = bug_trend_api.validate_scope_config(config)

        # Then
        self.assertFalse(result.valid)
        self.assertEqual('Scope name is required.', result.errors['name'])
        self.assertEqual('JQL is required.', result.errors['jql'])
        self.assertEqual('Bucket granularity must be daily or weekly.', result.errors['bucket_granularity'])

    def test_shouldNormalizeSemanticListsWhenSavingScopeConfig(self):
        # Given
        config = self._scope_config(name='STDEL normalized')
        config.critical_high_values = [r'P1-Critical\nP2-High', 'Critical, High', 'P2-High']
        config.medium_low_values = 'P3-Medium\nP4-Low'
        config.fixed_status_values = [r'Fixed\nResolved\nDone']

        # When
        saved = bug_trend_api.save_scope_config(config)
        scope = JiraScopeConfig.objects.get(id=saved.id)

        # Then
        self.assertEqual(['P1-Critical', 'P2-High', 'Critical', 'High'], scope.critical_high_values)
        self.assertEqual(['P3-Medium', 'P4-Low'], scope.medium_low_values)
        self.assertEqual(['Fixed', 'Resolved', 'Done'], scope.fixed_status_values)
        self.assertEqual(scope.critical_high_values, saved.critical_high_values)

    def test_shouldNormalizeSemanticListsWhenSavingModelDirectly(self):
        # Given / When
        scope = JiraScopeConfig.objects.create(
            name='STDEL direct normalized',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=[r'Fixed\nResolved\nDone'],
            critical_high_values=[r'P1-Critical\nP2-High'],
            medium_low_values=['P3-Medium,P4-Low'],
        )

        # Then
        self.assertEqual(['Fixed', 'Resolved', 'Done'], scope.fixed_status_values)
        self.assertEqual(['P1-Critical', 'P2-High'], scope.critical_high_values)
        self.assertEqual(['P3-Medium', 'P4-Low'], scope.medium_low_values)

    def test_shouldNotPersistDraftValidationBeforeExplicitSave(self):
        # Given
        config = self._scope_config(name='STDEL draft', critical_high_values=['P1-Critical'])

        # When
        result = bug_trend_api.validate_scope_config(config)

        # Then
        self.assertTrue(result.valid)
        self.assertFalse(JiraScopeConfig.objects.filter(name='STDEL draft').exists())

    def test_shouldSaveSemanticChangesThroughJiraScopeConfigAndUpdateHash(self):
        # Given
        scope = self._create_scope(name='STDEL semantic', critical_high_values=['P1-Critical'])
        original_hash = scope.config_version_hash
        config = bug_trend_api.get_scope_config(scope.id)
        config.critical_high_values = ['P1-Critical', 'P2-High']

        # When
        saved = bug_trend_api.save_scope_config(config)
        scope.refresh_from_db()

        # Then
        self.assertEqual(['P1-Critical', 'P2-High'], scope.critical_high_values)
        self.assertNotEqual(original_hash, scope.config_version_hash)
        self.assertEqual(scope.config_version_hash, saved.config_version_hash)
        event = BugTrendAuditEvent.objects.get(event_type='scope_saved', scope=scope)
        self.assertEqual(original_hash, event.request_summary['previous_config_version_hash'])
        self.assertEqual(scope.config_version_hash, event.request_summary['current_config_version_hash'])
        self.assertTrue(event.request_summary['semantic_hash_changed'])

    def test_shouldKeepSemanticHashWhenOnlyDisplayIdentityChanges(self):
        # Given
        scope = self._create_scope(name='STDEL identity', ip='old-ip')
        original_hash = scope.config_version_hash
        config = bug_trend_api.get_scope_config(scope.id)
        config.ip = 'new-ip'
        config.project_label = 'Project Label'

        # When
        saved = bug_trend_api.save_scope_config(config)
        scope.refresh_from_db()

        # Then
        self.assertEqual('new-ip', scope.ip)
        self.assertEqual(original_hash, scope.config_version_hash)
        self.assertEqual(original_hash, saved.config_version_hash)

    def test_shouldRequireExplicitActivationBeforeScopeAppearsAsEnabled(self):
        # Given
        saved = bug_trend_api.save_scope_config(self._scope_config(name='STDEL activation', enabled=False))

        # When
        enabled_before = bug_trend_api.list_enabled_scopes()
        activated = bug_trend_api.activate_scope_config(saved.id)
        enabled_after = bug_trend_api.list_enabled_scopes()

        # Then
        self.assertEqual([], enabled_before)
        self.assertTrue(activated.enabled)
        self.assertEqual(['STDEL activation'], [scope.name for scope in enabled_after])
        event = BugTrendAuditEvent.objects.get(event_type='scope_activated', scope_id=saved.id)
        self.assertFalse(event.request_summary['was_enabled'])
        self.assertEqual(activated.config_version_hash, event.request_summary['current_config_version_hash'])

    def test_shouldNotLoadDisabledScopeThroughChartScopeLookupBeforeActivation(self):
        # Given
        saved = bug_trend_api.save_scope_config(self._scope_config(name='STDEL disabled', enabled=False))

        # When / Then
        with self.assertRaises(ObjectDoesNotExist):
            bug_trend_api.get_scope(saved.id)

    def test_shouldMapAuditValueAfterSavingThroughScopeConfigWorkflow(self):
        # Given
        scope = self._create_scope(name='STDEL audit handoff', critical_high_values=['P2-High'])
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-5001',
            issue_type='Bug',
            status='New',
            severity_value='P1-Stopper',
        )
        before = bug_trend_api.get_scope_audit(scope.id)
        config = bug_trend_api.get_scope_config(scope.id)
        config.critical_high_values = ['P2-High', 'P1-Stopper']

        # When
        bug_trend_api.save_scope_config(config)
        after = bug_trend_api.get_scope_audit(scope.id)

        # Then
        before_values = {(value.category, value.value): value for value in before.observed_values}
        after_values = {(value.category, value.value): value for value in after.observed_values}
        self.assertFalse(before_values[('severity', 'P1-Stopper')].mapped)
        self.assertTrue(after_values[('severity', 'P1-Stopper')].mapped)
        self.assertEqual('critical_high', after_values[('severity', 'P1-Stopper')].mapping_group)

    def _create_scope(self, name='STDEL', ip='', critical_high_values=None):
        return JiraScopeConfig.objects.create(
            name=name,
            ip=ip,
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            open_status_values=['New', 'In Progress'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=critical_high_values or ['P1-Critical'],
            medium_low_values=['P3-Medium'],
        )

    def _scope_config(self, name='STDEL config', jql='project = STDEL AND issuetype = Bug',
                      bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY, critical_high_values=None,
                      enabled=False):
        return SavedScopeConfig(
            id=None,
            name=name,
            ip='STDEL',
            project_label='Emulation',
            jql=jql,
            bug_type_values=['Bug'],
            open_status_values=['New', 'In Progress'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            terminal_excluded_status_values=[],
            fixed_resolution_values=['Fixed'],
            closed_resolution_values=['Done'],
            reopen_status_values=['Reopened'],
            severity_field='priority',
            critical_high_values=critical_high_values or ['P1-Critical'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            team_field='',
            milestone_field='fixVersions',
            fix_version_field='fixVersions',
            package_version_field='',
            display_fields=['priority', 'components'],
            timezone='UTC',
            bucket_granularity=bucket_granularity,
            enabled=enabled,
        )