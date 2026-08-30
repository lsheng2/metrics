import json
import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase
from urllib.parse import parse_qsl, urlparse


REPO_ROOT = Path(__file__).resolve().parents[2]
ARTIFACT_PATH = REPO_ROOT / 'ops' / 'grafana' / 'provider_parity_dashboard.json'
VALIDATOR_PATH = REPO_ROOT / 'scripts' / 'validate_grafana_artifacts.py'
ALLOWLIST_PATH = REPO_ROOT / 'openspec' / 'docs' / 'current-baseline' / 'grafana-approved-data-surfaces.json'

spec = spec_from_file_location('validate_grafana_provider_parity_artifacts', VALIDATOR_PATH)
validate_grafana_artifacts = module_from_spec(spec)
sys.modules[spec.name] = validate_grafana_artifacts
spec.loader.exec_module(validate_grafana_artifacts)


class TestGrafanaProviderParityDashboard(TestCase):
    def test_shouldRenderTopLevelProfileReadinessPanel(self):
        # Given / When
        artifact = self._artifact()

        # Then
        panels = {panel['title']: panel for panel in artifact['panels']}
        panel = panels['PROFILE / Selected Profile Status']
        self.assertEqual('table', panel['type'])
        self.assertLess(panel['gridPos']['y'], self._row_panel_y(artifact, 'QUALITY'))
        self.assertIn('profile-derived', panel['description'])
        target = panel['targets'][0]
        params = self._query_params(target)
        self.assertEqual('/api/provider-profiles/readiness/', urlparse(target['url']).path)
        self.assertEqual('$profile_id', params['profile_id'])
        self.assertEqual('$.profile_status_rows', target['root_selector'])
        self.assertEqual('0.2', target['metricsContract']['contractVersion'])
        self.assertEqual('profile_readiness_summary', target['metricsContract']['shape'])
        self.assertIn('provider_id', self._target_columns(target))
        self.assertIn('ip', self._target_columns(target))
        self.assertIn('project_or_product', self._target_columns(target))
        self.assertIn('milestone', self._target_columns(target))
        self.assertIn('data_status_reason', self._target_columns(target))
        self.assertIn('auth_action_label', self._target_columns(target))
        self.assertIn('auth_action_url', self._target_columns(target))
        self.assertTrue(self._field_override_links(panel, 'auth_action_label'))
        self.assertTrue(any('${__data.fields.auth_action_url}' in link['url'] for link in self._field_override_links(panel, 'auth_action_label')))

    def test_shouldDeclareProviderNeutralVariablesAndReferenceSections(self):
        # Given / When
        artifact = self._artifact()

        # Then
        variables = {item['name']: item for item in artifact['templating']['list']}
        self.assertEqual({'profile_id', 'begin_ww', 'end_ww'}, set(variables))
        self.assertEqual('custom', variables['profile_id']['type'])
        self.assertEqual('chiplet-2a-jira,nvu-ttl-hsdes', variables['profile_id']['query'])
        self.assertEqual(['chiplet-2a-jira', 'nvu-ttl-hsdes'], [option['value'] for option in variables['profile_id']['options']])
        self.assertEqual('chiplet-2a-jira', variables['profile_id']['current']['value'])
        self.assertEqual('26WW32', variables['begin_ww']['current']['value'])
        self.assertEqual('26WW32', variables['end_ww']['current']['value'])
        self.assertEqual(['QUALITY', 'EXECUTION', 'EFFICIENCY'], [panel['title'] for panel in artifact['panels'] if panel['type'] == 'row'])

    def test_shouldWireSupportedQualityPanelsToProviderNeutralAggregateSurface(self):
        # Given
        artifact = self._artifact()
        supported_chart_ids = {
            'component_bug',
            'rolling_valid_bug',
            'open_bug_trend',
            'total_bug_trend',
            'open_bug_aging',
            'daily_new_standard_bug_count',
        }
        expected_value_fields = {
            'component_bug': {'component_bug_count'},
            'rolling_valid_bug': {'rolling_valid_bug_count'},
            'open_bug_trend': {'all_open_bugs', 'all_open_critical_high', 'new_critical_high', 'new_medium_low', 'fixed_or_closed_bugs'},
            'total_bug_trend': {'total_new_bugs', 'total_open_bugs', 'total_fixed_or_closed_bugs'},
            'open_bug_aging': {'aging_0_7_days', 'aging_8_14_days', 'aging_15_30_days', 'aging_31_plus_days'},
            'daily_new_standard_bug_count': {'new_standard_bugs'},
        }

        # When
        primary_targets = [target for target in self._targets(artifact) if self._target_shape(target) == 'wide_bucket_series']
        chart_ids = {self._query_params(target)['chart_id'] for target in primary_targets}

        # Then
        self.assertEqual(supported_chart_ids, chart_ids)
        for target in primary_targets:
            params = self._query_params(target)
            self.assertEqual('/api/provider-charts/data/', urlparse(target['url']).path)
            self.assertNotIn('provider_id', params)
            self.assertEqual('$profile_id', params['profile_id'])
            self.assertEqual('$begin_ww', params['begin_ww'])
            self.assertEqual('$end_ww', params['end_ww'])
            self.assertNotIn('space_id', params)
            self.assertNotIn('release_target', params)
            self.assertNotIn('milestone', params)
            self.assertEqual('0.2', target['metricsContract']['contractVersion'])
            self.assertEqual('grafana_rows', target['metricsContract']['root'])
            value_fields = set(target['metricsContract']['valueFields'])
            self.assertEqual(expected_value_fields[params['chart_id']], value_fields)
            self.assertFalse(any(field.startswith(('jira_', 'hsdes_')) for field in value_fields))
            self.assertEqual('string', self._target_column_types(target)['mapping_version'])

    def test_shouldExposeSelectedProviderAndDeferredStatePanelsThroughProviderSeriesState(self):
        # Given
        artifact = self._artifact()
        supported_chart_ids = {
            'component_bug',
            'rolling_valid_bug',
            'open_bug_trend',
            'total_bug_trend',
            'open_bug_aging',
            'daily_new_standard_bug_count',
        }

        # When
        state_targets = [target for target in self._targets(artifact) if self._target_shape(target) == 'provider_series_state']
        state_chart_ids = {self._query_params(target)['chart_id'] for target in state_targets}
        selected_provider_state_chart_ids = {
            self._query_params(target)['chart_id']
            for target in state_targets
            if 'provider_id' not in self._query_params(target)
        }

        # Then
        self.assertTrue(supported_chart_ids.issubset(selected_provider_state_chart_ids))
        self.assertTrue({'execution_statistics', 'automation_statistics', 'shift_left_statistics', 'internal_escaped_bugs'}.issubset(state_chart_ids))
        for target in state_targets:
            self.assertEqual('$.provider_series_state', target['root_selector'])
            self.assertEqual('0.2', target['metricsContract']['contractVersion'])
            self.assertEqual('/api/provider-charts/data/', urlparse(target['url']).path)
            self.assertIn('status', target['metricsContract']['requiredFields'])
            self.assertIn('reason', target['metricsContract']['requiredFields'])

    def test_shouldPassApprovedDataSurfaceValidator(self):
        # When
        findings = validate_grafana_artifacts.validate_artifact_root(
            ARTIFACT_PATH.parent,
            validate_grafana_artifacts.load_allowlist(ALLOWLIST_PATH),
        )

        # Then
        self.assertEqual([], findings)

    def test_shouldBindEveryProviderPanelToApprovedChartRecipe(self):
        # Given
        artifact = self._artifact()

        # When
        provider_targets = [
            target for target in self._targets(artifact)
            if urlparse(target['url']).path == '/api/provider-charts/data/'
        ]

        # Then
        self.assertTrue(provider_targets)
        for target in provider_targets:
            contract = target['metricsContract']
            params = self._query_params(target)
            self.assertEqual('metrics', contract['semanticOwner'])
            self.assertEqual(params['chart_id'], contract['chartRecipeId'])
            self.assertEqual(int(params['chart_version']), contract['chartRecipeVersion'])
            self.assertIn(contract['providerBinding'], {'selected_provider_quality', 'selected_provider_state', 'first_wave_deferred'})

    def test_shouldNotKeepComparisonProviderVariablesOrPanelQueries(self):
        # Given
        artifact = self._artifact()

        # When
        variable_names = {item['name'] for item in artifact['templating']['list']}
        target_urls = [target['url'] for target in self._targets(artifact)]

        # Then
        self.assertNotIn('comparison_provider_id', variable_names)
        self.assertNotIn('comparison_profile_id', variable_names)
        self.assertNotIn('provider_id', variable_names)
        self.assertNotIn('space_id', variable_names)
        self.assertNotIn('release_target', variable_names)
        self.assertNotIn('milestone', variable_names)
        self.assertTrue(all('$comparison_provider_id' not in url for url in target_urls))
        self.assertTrue(all('$comparison_profile_id' not in url for url in target_urls))
        self.assertTrue(all('provider_id=$provider_id' not in url for url in target_urls))
        self.assertTrue(all('space_id=$space_id' not in url for url in target_urls))
        self.assertTrue(all('release_target=$release_target' not in url for url in target_urls))
        self.assertTrue(all('milestone=$milestone' not in url for url in target_urls))

    def test_shouldDeclareEvidenceCapabilityForEveryProviderPanel(self):
        # Given
        artifact = self._artifact()

        # When
        contracts = [
            target['metricsContract']
            for target in self._targets(artifact)
            if urlparse(target['url']).path == '/api/provider-charts/data/'
        ]

        # Then
        self.assertTrue(contracts)
        for contract in contracts:
            self.assertIn(contract['evidenceCapability'], {'bucket_series', 'range_only', 'summary_only'})

    def test_shouldExposeBucketSeriesEvidenceLinkOnlyForBucketSeriesPanels(self):
        # Given
        artifact = self._artifact()

        # When
        linked_targets = []
        unlinked_targets = []
        for panel in artifact['panels']:
            provider_evidence_links = [
                link['url']
                for link in panel.get('fieldConfig', {}).get('defaults', {}).get('links', [])
                if '/api/provider-charts/evidence/' in link.get('url', '')
            ]
            for target in panel.get('targets', []):
                contract = target.get('metricsContract', {})
                if not contract:
                    continue
                if provider_evidence_links:
                    linked_targets.append((target, contract, provider_evidence_links))
                else:
                    unlinked_targets.append((target, contract))

        # Then
        self.assertTrue(linked_targets)
        for target, contract, links in linked_targets:
            self.assertEqual('bucket_series', contract['evidenceCapability'])
            self.assertEqual(['calculation_run_id', 'bucket_id'], contract['evidenceLinkFields'])
            self.assertIn('bucket_id', self._target_columns(target))
            self.assertTrue(any('/api/provider-charts/evidence/' in link for link in links))
        for _, contract in unlinked_targets:
            self.assertNotEqual('bucket_series', contract['evidenceCapability'])
            self.assertEqual([], contract.get('evidenceLinkFields', []))

    def test_shouldKeepDailyMetricPanelOnMetricsOwnedAggregateSurface(self):
        # Given
        artifact = self._artifact()

        # When
        daily_targets = [
            target for target in self._targets(artifact)
            if self._query_params(target).get('chart_id') == 'daily_new_standard_bug_count'
        ]

        # Then
        self.assertTrue(daily_targets)
        for target in daily_targets:
            contract = target['metricsContract']
            self.assertEqual('/api/provider-charts/data/', urlparse(target['url']).path)
            self.assertEqual('metrics', contract['calculationOwner'])
            self.assertEqual('materialized_aggregate', contract['aggregationOwner'])
            self.assertEqual('day', contract['bucketGrain'])

    def _artifact(self):
        return json.loads(ARTIFACT_PATH.read_text(encoding='utf-8'))

    def _targets(self, artifact):
        return [
            target
            for panel in artifact['panels']
            for target in panel.get('targets', [])
        ]

    def _query_params(self, target):
        return dict(parse_qsl(urlparse(target['url']).query, keep_blank_values=True))

    def _target_shape(self, target):
        return target.get('metricsContract', {}).get('shape', '')

    def _target_columns(self, target):
        return {column['selector'] for column in target.get('columns', [])}

    def _target_column_types(self, target):
        return {
            column['selector']: column.get('type')
            for column in target.get('columns', [])
        }

    def _row_panel_y(self, artifact, title):
        return next(panel['gridPos']['y'] for panel in artifact['panels'] if panel['title'] == title)

    def _field_override_links(self, panel, field_name):
        for override in panel.get('fieldConfig', {}).get('overrides', []):
            matcher = override.get('matcher', {})
            if matcher.get('id') != 'byName' or matcher.get('options') != field_name:
                continue
            links = []
            for property_item in override.get('properties', []):
                if property_item.get('id') == 'links':
                    links.extend(property_item.get('value', []))
            return links
        return []
