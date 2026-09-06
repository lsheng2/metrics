from django.test import TestCase

from bug_metrics.app.api import ApiForBugTrend
from bug_metrics.app.api.provider_profile_registry import ProjectProviderProfileRegistry
from bug_metrics.app.api.scope_provider_binding import ScopeProviderBindingResolver
from bug_metrics.models import BugTrendAuditEvent, BugTrendScopeProviderBinding, JiraScopeConfig


class TestScopeProviderBindingResolver(TestCase):
    def test_shouldResolveExplicitBindingAfterScopeDisplayNameChanges(self):
        scope = self._scope('Renamable Display Scope', 'project = STDEL')
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='stable-jira-profile',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            provenance={'source': 'test'},
        )
        scope.name = 'Renamed Scope'
        scope.save()

        resolution = self._resolver([self._profile('stable-jira-profile', 'jira', 'project = STDEL')]).resolve(scope)

        self.assertEqual('stable-jira-profile', resolution.profile_id)
        self.assertEqual('jira', resolution.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, resolution.status)

    def test_shouldCreateCompatibilityBindingFromSingleMatchingJiraProfile(self):
        scope = self._scope('Display Name', "project = 'STDEL'")

        resolution = self._resolver([self._profile('stable-jira-profile', 'jira', 'project = "STDEL"')]).resolve(scope)

        self.assertEqual('stable-jira-profile', resolution.profile_id)
        self.assertEqual('jira', resolution.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_COMPATIBILITY, resolution.status)
        self.assertEqual('provider_profile_registry', resolution.provenance['matched_by'])

    def test_shouldNotChooseProviderWhenCompatibilityMatchIsAmbiguous(self):
        scope = self._scope('Display Name', 'project = STDEL')

        resolution = self._resolver([
            self._profile('first-jira-profile', 'jira', 'project = STDEL'),
            self._profile('second-jira-profile', 'jira', 'project = STDEL'),
        ]).resolve(scope)

        self.assertEqual('', resolution.profile_id)
        self.assertEqual('', resolution.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_AMBIGUOUS, resolution.status)
        self.assertEqual('ambiguous_scope_provider_binding', resolution.blockers[0]['code'])

    def test_shouldPersistBackfilledBindingWithProvenance(self):
        scope = self._scope('Display Name', 'project = STDEL')
        resolver = self._resolver([self._profile('stable-jira-profile', 'jira', 'project = STDEL')])

        resolution = resolver.backfill(scope, explicit=True)

        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual('stable-jira-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertEqual('stable-jira-profile', resolution.profile_id)
        self.assertEqual('scope_provider_binding_resolver', resolution.provenance['persisted_by'])

    def test_shouldSaveExplicitBindingFromSelectedProviderProfile(self):
        scope = self._scope('Unbound Scope', '')
        resolver = self._resolver([self._profile('stable-jira-profile', 'jira', 'project = STDEL')])

        resolution = resolver.set_explicit(scope, 'stable-jira-profile')

        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual('stable-jira-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, binding.status)
        self.assertEqual('operator_confirmed', binding.provenance['source'])
        self.assertEqual('stable-jira-profile', resolution.profile_id)

    def test_shouldRejectUnknownProviderProfileWithoutChangingExistingBinding(self):
        scope = self._scope('Bound Scope', '')
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='stable-jira-profile',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        resolver = self._resolver([self._profile('stable-jira-profile', 'jira', 'project = STDEL')])

        with self.assertRaises(ValueError):
            resolver.set_explicit(scope, 'missing-profile')

        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual('stable-jira-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)

    def test_shouldAuditExplicitBindingUpdatesWithOldAndNewSnapshots(self):
        scope = self._scope('Audited Scope', '')
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='first-jira-profile',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            provenance={'source': 'test'},
        )
        resolver = self._resolver([
            self._profile('first-jira-profile', 'jira', 'project = FIRST'),
            self._profile('second-jira-profile', 'jira', 'project = SECOND'),
        ])

        resolver.set_explicit(scope, 'second-jira-profile', actor='scope_admin')

        event = BugTrendAuditEvent.objects.get(event_type=BugTrendAuditEvent.EVENT_SCOPE_BINDING_UPDATED)
        self.assertEqual('scope_admin', event.actor)
        self.assertEqual(scope, event.scope)
        self.assertEqual('first-jira-profile', event.request_summary['before']['profile_id'])
        self.assertEqual('second-jira-profile', event.request_summary['after']['profile_id'])

    def test_shouldBulkConfirmOnlyEligibleCompatibilityBindingsAndAuditChangedRows(self):
        eligible = self._scope('Eligible bulk scope', 'project = ELIGIBLE')
        unsafe = self._scope('Unsafe bulk scope', '')
        disabled = self._scope('Disabled bulk scope', 'project = DISABLED')
        disabled.enabled = False
        disabled.save()
        resolver = self._resolver([
            self._profile('eligible-profile', 'jira', 'project = ELIGIBLE'),
            self._profile('disabled-profile', 'jira', 'project = DISABLED'),
        ])

        result = resolver.bulk_confirm_compatibility([eligible, unsafe, disabled], actor='scope_admin')

        eligible_binding = BugTrendScopeProviderBinding.objects.get(scope=eligible)
        self.assertEqual(1, result.changed_count)
        self.assertEqual(2, result.skipped_count)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_EXPLICIT, eligible_binding.status)
        self.assertEqual('eligible-profile', eligible_binding.profile_id)
        self.assertEqual(['Unsafe bulk scope', 'Disabled bulk scope'], [item['scope_name'] for item in result.skipped])
        event = BugTrendAuditEvent.objects.get(event_type=BugTrendAuditEvent.EVENT_SCOPE_BINDING_BULK_CONFIRMED)
        self.assertEqual('scope_admin', event.actor)
        self.assertTrue(event.request_summary['bulk_operation_id'])
        self.assertEqual('eligible-profile', event.request_summary['after']['profile_id'])

    def test_shouldExposeExplicitOnlyReadinessImpactFromBindingHealth(self):
        explicit_scope = self._scope('Explicit readiness scope', '')
        compatibility_scope = self._scope('Compatibility readiness scope', 'project = STDEL')
        disabled_scope = self._scope('Disabled readiness scope', '')
        disabled_scope.enabled = False
        disabled_scope.save()
        BugTrendScopeProviderBinding.objects.create(
            scope=explicit_scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=compatibility_scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'matched_by': 'legacy_jira_scope'},
        )

        health = ApiForBugTrend().get_scope_provider_binding_health()

        self.assertFalse(health['explicit_only_ready'])
        self.assertEqual(1, health['explicit_only_blocked_count'])
        self.assertEqual(['Compatibility readiness scope'], [row['scope_name'] for row in health['explicit_only_impacted_rows']])
        self.assertEqual(1, health['counts']['disabled'])

    def test_shouldReturnConfigurationRequiredWhenNoSafeBindingExists(self):
        scope = self._scope('Unbound Scope', '')

        resolution = self._resolver([]).resolve(scope)

        self.assertEqual('', resolution.profile_id)
        self.assertEqual('', resolution.provider_id)
        self.assertEqual(BugTrendScopeProviderBinding.STATUS_CONFIGURATION_REQUIRED, resolution.status)
        self.assertEqual('scope_provider_binding_missing', resolution.blockers[0]['code'])

    def _resolver(self, records):
        return ScopeProviderBindingResolver(ProjectProviderProfileRegistry.from_records(records))

    def _scope(self, name, jql):
        return JiraScopeConfig.objects.create(
            name=name,
            jql=jql,
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )

    def _profile(self, profile_id, provider_id, native_query_text):
        return {
            'profile_id': profile_id,
            'provider_id': provider_id,
            'enabled': True,
            'source_population': {
                'native_query_text': native_query_text,
            },
        }
