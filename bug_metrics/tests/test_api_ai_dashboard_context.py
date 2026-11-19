from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.tests.ai_publication_fixtures import seed_publication_data


class TestProviderAiDashboardContext(TestCase):
    def test_shouldExposeAiCompositionCatalogWithoutProviderCredentialsOrNativeQueries(self):
        catalog = bug_trend_api.list_ai_dashboard_composition_catalog('nvu-ttl-hsdes')

        self.assertEqual('0.2', catalog['contract_version'])
        self.assertEqual('profile_catalog', catalog['catalog_type'])
        self.assertEqual({'ww', 'date'}, set(catalog['range_modes']))
        self.assertEqual({'max_rows', 'max_days'}, set(catalog['limits']))
        self.assertTrue(catalog['security_policy']['publication_requires_runtime_approval'])
        self.assertNotIn('publication_requires_metrics_precondition', catalog['security_policy'])
        profile = catalog['profiles'][0]
        self.assertEqual('nvu-ttl-hsdes', profile['profile_id'])
        self.assertEqual('hsdes', profile['provider_id'])
        self.assertIn('source_query_hash', profile['source_population'])
        serialized_catalog = str(catalog).lower()
        self.assertNotIn('native_query_text', serialized_catalog)
        self.assertNotIn('password', serialized_catalog)
        self.assertNotIn('token', serialized_catalog)
        self.assertNotIn('api_key', serialized_catalog)
        open_bug_recipe = catalog['chart_recipes']['open_bug_trend']
        self.assertEqual(
            ['all_open_bugs', 'all_open_critical_high', 'new_critical_high', 'new_medium_low', 'fixed_or_closed_bugs'],
            open_bug_recipe['allowed_series'],
        )
        self.assertEqual('supported', open_bug_recipe['support_status'])

    def test_shouldExposeWorkbenchContextForResolvedScopeBinding(self):
        scope, _ = seed_publication_data()

        context = bug_trend_api.get_ai_workbench_context({
            'binding_key': f'metrics.scope.{scope.id}',
            'profile_id': 'chiplet-2a-jira',
            'provider_id': 'jira',
            'begin': '2026-08-03',
            'end': '2026-08-30',
        })

        self.assertEqual('ready', context['status'])
        self.assertEqual('metrics.workbench', context['context_ref']['kind'])
        self.assertEqual(['jira'], context['boundary']['allowed_provider_ids'])
        self.assertEqual(['chiplet-2a-jira'], context['boundary']['allowed_profile_ids'])
        self.assertEqual({'date', 'ww'}, set(context['boundary']['range_modes']))
        files_by_role = {item['role']: item for item in context['files']}
        self.assertIn('context_boundary', files_by_role)
        self.assertIn('provider_profile', files_by_role)
        self.assertIn('canonical_field_map', files_by_role)
        self.assertIn('data_block_catalog', files_by_role)
        self.assertIn('grafana_render_contract', files_by_role)
        serialized = str(context).lower()
        self.assertNotIn('native_query_text', serialized)
        self.assertNotIn('password', serialized)
        self.assertNotIn('token', serialized)
        self.assertNotIn('api_key', serialized)

    def test_shouldRejectWorkbenchContextWhenProfileDoesNotMatchBinding(self):
        scope, _ = seed_publication_data()

        context = bug_trend_api.get_ai_workbench_context({
            'binding_key': f'metrics.scope.{scope.id}',
            'profile_id': 'nvu-ttl-hsdes',
            'provider_id': 'hsdes',
            'begin': '2026-08-03',
            'end': '2026-08-30',
        })

        self.assertEqual({'status': 'binding_unresolved'}, context)
