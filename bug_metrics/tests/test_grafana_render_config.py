import sys
from importlib.util import module_from_spec, spec_from_file_location
from pathlib import Path
from unittest import TestCase


REPO_ROOT = Path(__file__).resolve().parents[2]
RENDER_CONFIG_PATH = REPO_ROOT / 'scripts' / 'grafana_render_config.py'
ALLOWLIST_PATH = REPO_ROOT / 'openspec' / 'docs' / 'current-baseline' / 'grafana-approved-data-surfaces.json'
IP_QUALITY_RENDER_CONFIG_PATH = REPO_ROOT / 'ops' / 'grafana' / 'render_configs' / 'ip_quality_dashboard.json'
CURRENT_DASHBOARD_PATH = REPO_ROOT / 'ops' / 'grafana' / 'provider_parity_dashboard.json'

spec = spec_from_file_location('grafana_render_config', RENDER_CONFIG_PATH)
grafana_render_config = module_from_spec(spec)
sys.modules[spec.name] = grafana_render_config
spec.loader.exec_module(grafana_render_config)


class TestGrafanaRenderConfig(TestCase):
    def test_shouldAcceptRenderConfigWithApprovedProviderChartRecipe(self):
        # Given
        render_config = self._valid_render_config()
        allowlist = grafana_render_config.load_allowlist(ALLOWLIST_PATH)

        # When
        findings = grafana_render_config.validate_render_config(render_config, allowlist, Path('render.json'))

        # Then
        self.assertEqual([], findings)

    def test_shouldRejectPanelWithoutChartRecipeRef(self):
        # Given
        render_config = self._valid_render_config()
        render_config['sections'][0]['panels'][0].pop('chart_recipe_ref')
        allowlist = grafana_render_config.load_allowlist(ALLOWLIST_PATH)

        # When
        findings = grafana_render_config.validate_render_config(render_config, allowlist, Path('render.json'))

        # Then
        self.assertTrue(any('chart_recipe_ref is required' in finding.message for finding in findings))

    def test_shouldRejectRenderConfigWithUnapprovedValueAndCategoryFields(self):
        # Given
        render_config = self._valid_render_config()
        panel = render_config['sections'][0]['panels'][0]
        panel['category_field'] = 'provider_native_component'
        panel['value_fields'] = ['new_critical']
        allowlist = grafana_render_config.load_allowlist(ALLOWLIST_PATH)

        # When
        findings = grafana_render_config.validate_render_config(render_config, allowlist, Path('render.json'))

        # Then
        messages = [finding.message for finding in findings]
        self.assertTrue(any('value_fields outside approved chart recipe' in message for message in messages))
        self.assertTrue(any('category_field' in message and 'not approved' in message for message in messages))

    def test_shouldGenerateDeterministicDashboardWithCurrentProviderTargets(self):
        # Given
        render_config = grafana_render_config.load_render_config(IP_QUALITY_RENDER_CONFIG_PATH)
        allowlist = grafana_render_config.load_allowlist(ALLOWLIST_PATH)
        current_dashboard = grafana_render_config.load_json(CURRENT_DASHBOARD_PATH)

        # When
        first_dashboard = grafana_render_config.generate_dashboard(render_config, allowlist)
        second_dashboard = grafana_render_config.generate_dashboard(render_config, allowlist)

        # Then
        self.assertEqual(first_dashboard, second_dashboard)
        self.assertEqual('ip-quality-dashboard', first_dashboard['uid'])
        self.assertEqual('IP Quality Dashboard', first_dashboard['title'])
        self.assertEqual(
            {'profile_id', 'range_mode', 'begin_ww', 'end_ww'},
            {item['name'] for item in first_dashboard['templating']['list']},
        )
        self.assertEqual(
            self._provider_target_keys(current_dashboard),
            self._provider_target_keys(first_dashboard),
        )

    def test_shouldWriteGeneratedDashboardArtifactThatPassesGrafanaValidator(self):
        # Given
        import tempfile
        with tempfile.TemporaryDirectory() as temp_dir:
            output_path = Path(temp_dir) / 'ip_quality_dashboard.generated.json'

            # When
            dashboard = grafana_render_config.write_generated_dashboard(
                IP_QUALITY_RENDER_CONFIG_PATH,
                ALLOWLIST_PATH,
                output_path,
            )
            findings = grafana_render_config.validate_generated_dashboard(output_path, ALLOWLIST_PATH)

            # Then
            self.assertTrue(output_path.exists())
            self.assertEqual('ip-quality-dashboard', dashboard['uid'])
            self.assertEqual([], findings)

    def _valid_render_config(self):
        return {
            'dashboard_uid': 'ip-quality-dashboard',
            'title': 'IP Quality Dashboard',
            'profile_variable': 'profile_id',
            'variables': [
                {'name': 'profile_id', 'kind': 'profile'},
                {'name': 'range_mode', 'kind': 'constant', 'values': ['ww', 'date']},
            ],
            'range_controls': {
                'mode_variable': 'range_mode',
                'fetch_label': 'Fetch/cache from provider',
                'display_label': 'Display time window',
                'modes': ['ww', 'date'],
            },
            'sections': [
                {
                    'id': 'quality',
                    'title': 'Quality',
                    'panels': [
                        {
                            'panel_id': 'open_bug_trend',
                            'title': 'Open Bug Trend',
                            'type': 'timeseries',
                            'layout': {'x': 0, 'y': 0, 'w': 12, 'h': 8},
                            'chart_recipe_ref': {'chart_id': 'open_bug_trend', 'chart_version': 1},
                            'provider_binding': 'selected_provider_quality',
                            'render_root': 'grafana_rows',
                            'render_shape': 'wide_bucket_series',
                            'category_field': 'bucket_label',
                            'value_fields': ['all_open_bugs', 'new_critical_high'],
                            'evidence_capability': 'bucket_series',
                            'evidence_link': {
                                'enabled': True,
                                'fields': ['calculation_run_id', 'bucket_id'],
                            },
                        },
                    ],
                },
            ],
        }

    def _provider_target_keys(self, dashboard):
        return sorted(
            (
                target['metricsContract']['shape'],
                target['metricsContract'].get('chartRecipeId', ''),
                target['root_selector'],
            )
            for panel in dashboard['panels']
            for target in panel.get('targets', [])
            if target.get('url', '').startswith('/api/provider-')
        )
