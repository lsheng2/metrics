import json
from datetime import date, datetime, timezone
from pathlib import Path
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import (
    BugTrendBucket,
    BugTrendBucketIssue,
    BugTrendCalculationRun,
    BugTrendScopeProviderBinding,
    JiraScopeConfig,
    ProviderProfileConfig,
)


class TestUiDesignBaselineGate(TestCase):
    def test_shouldDocumentAndEnforceSharedUiContracts(self):
        project_root = Path(__file__).resolve().parents[2]
        template_root = project_root / 'ui_web' / 'templates'
        overlay_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'templates' / 'project-overlay.md'
        audit_path = project_root / '.github' / 'skills' / 'lsheng2-ui-design' / 'reports' / '2026-09-08-ui-baseline-audit.md'

        overlay = overlay_path.read_text(encoding='utf-8')
        audit = audit_path.read_text(encoding='utf-8')
        self.assertIn('ui_web.tests.test_ui_design_baseline_gate', overlay)
        self.assertIn('Provider Setup inventory and Provider Profile Config editor', audit)
        self.assertIn('Monkey-user flow', audit)

        dirty_templates = [
            path
            for path in template_root.rglob('*.html')
            if 'data-dirty-form' in path.read_text(encoding='utf-8')
        ]
        self.assertEqual(
            {
                template_root / 'bug_trend_scope_config.html',
                template_root / 'partials' / 'provider_profile_editor.html',
            },
            set(dirty_templates),
        )
        for path in dirty_templates:
            content = path.read_text(encoding='utf-8')
            self.assertIn('dashboard-edit-form', content, str(path))
            self.assertIn('data-required-form', content, str(path))
            self.assertIn('dashboard-unsaved-banner', content, str(path))
            self.assertIn('dashboard-validation-banner', content, str(path))
            self.assertIn('dashboard-action-bar', content, str(path))
            self.assertIn('dashboard-action-group', content, str(path))

        css = (project_root / 'ui_web' / 'static' / 'css' / 'main.css').read_text(encoding='utf-8')
        for color in ['green', 'blue', 'purple']:
            self.assertIn(f'is-provider-{color}', css)

        for path in [
            template_root / 'bug_trend_scope_config.html',
            template_root / 'partials' / 'provider_profile_editor.html',
        ]:
            content = path.read_text(encoding='utf-8')
            self.assertIn('provider-tab-shell', content, str(path))
            self.assertIn('scope-provider-choice', content, str(path))
            self.assertIn('provider-tab-check', content, str(path))
            self.assertIn('role="tablist"', content, str(path))
            self.assertIn('role="tabpanel"', content, str(path))
            self.assertIn('is-provider-{{', content, str(path))

        for path in [
            template_root / 'partials' / 'current_tasks_filters.html',
            template_root / 'partials' / 'pull_request_filters.html',
            template_root / 'partials' / 'bug_trend_content.html',
            template_root / 'partials' / 'bug_trend_evidence.html',
        ]:
            content = path.read_text(encoding='utf-8')
            self.assertNotIn('data-dirty-form', content, str(path))
            self.assertNotIn('dashboard-action-bar', content, str(path))

    def test_shouldKeepCoreUiSurfacesWithinBaselineAtDesktopAndPhone(self):
        scope, _, _ = self._seed_bound_scope_with_run()
        responses = [
            ('provider_setup_inventory', self.client.get(reverse('ui_web:provider_setup')), {'table': True}),
            (
                'provider_profile_jira_editor',
                self.client.get(reverse('ui_web:provider_setup'), {'mode': 'new', 'provider_id': 'jira'}),
                {'editor': True, 'provider_tabs': True},
            ),
            (
                'provider_profile_hsdes_editor',
                self.client.get(reverse('ui_web:provider_setup'), {'mode': 'new', 'provider_id': 'hsdes'}),
                {'editor': True, 'provider_tabs': True},
            ),
            (
                'scope_config_hsdes_editor',
                self.client.get(reverse('ui_web:bug_trend_scope_config'), {
                    'mode': 'new',
                    'provider_id': 'hsdes',
                    'profile_id': 'nvu-ttl-hsdes',
                }),
                {'editor': True, 'provider_tabs': True},
            ),
            ('scope_library', self.client.get(reverse('ui_web:bug_trend_scope_library')), {'table': True}),
            ('data_health', self.client.get(reverse('ui_web:data_health')), {'table': True}),
            (
                'workbench',
                self.client.get(reverse('ui_web:workbench'), {
                    'scope_id': scope.id,
                    'begin': '2026-09-01',
                    'end': '2026-09-07',
                    'chart_id': 'default_bug_trend',
                }),
                {},
            ),
        ]

        for label, response, _ in responses:
            self.assertEqual(200, response.status_code, label)

        results = self._measure_baseline_pages([
            (label, response.content.decode(), expectations)
            for label, response, expectations in responses
        ])

        for label, viewport_results in results.items():
            for viewport, metrics in viewport_results.items():
                self.assertFalse(metrics['page_horizontal_overflow'], f'{label} {viewport}')
                self.assertEqual([], metrics['clipped_action_buttons'], f'{label} {viewport}')
                self.assertGreater(metrics['visible_button_count'], 0, f'{label} {viewport}')
                if metrics['expects_table']:
                    self.assertGreater(metrics['responsive_table_count'], 0, f'{label} {viewport}')
                if metrics['expects_editor']:
                    self.assertEqual(1, metrics['required_summary_count'], f'{label} {viewport}')
                    self.assertEqual(1, metrics['dirty_banner_count'], f'{label} {viewport}')
                    self.assertGreater(metrics['action_bar_count'], 0, f'{label} {viewport}')
                    self.assertLessEqual(metrics['action_bar_button_height_delta'], 1, f'{label} {viewport}')
                    self.assertLessEqual(metrics['editor_control_height_delta'], 1, f'{label} {viewport}')
                if metrics['expects_provider_tabs']:
                    self.assertGreater(metrics['provider_tab_shell_count'], 0, f'{label} {viewport}')
                    self.assertTrue(metrics['selected_provider_check_visible'], f'{label} {viewport}')

    def test_shouldSupportMonkeyUserProviderProfileScopeWorkbenchJourney(self):
        new_jira_page = self.client.get(reverse('ui_web:provider_setup'), {
            'mode': 'new',
            'provider_id': 'jira',
        })
        self.assertIn('id="provider-profile-id" name="profile_id" value=""', new_jira_page.content.decode())
        self.assertIn('provider-setup-choice is-provider-green is-selected', new_jira_page.content.decode())

        jira_payload = self._jira_profile_payload('monkey-jira-profile')
        with patch('bug_metrics.app.api.provider_profile_connection_test.create_jira_client') as create_jira_client:
            create_jira_client.return_value.get_server_info.return_value = {
                'serverTitle': 'Monkey Jira',
                'version': '10.0',
            }
            test_response = self.client.post(reverse('ui_web:provider_setup'), {
                **jira_payload,
                'action': 'test_connection',
                'connection_api_token': 'secret-jira-token',
            })
        self.assertEqual(200, test_response.status_code)
        test_content = test_response.content.decode()
        self.assertIn('Connection test: success', test_content)
        self.assertIn('Jira connection succeeded.', test_content)
        self.assertNotIn('secret-jira-token', test_content)

        save_profile_response = self.client.post(reverse('ui_web:provider_setup'), jira_payload, follow=True)
        jira_profile = ProviderProfileConfig.objects.get(profile_id='monkey-jira-profile')
        self.assertEqual(200, save_profile_response.status_code)
        self.assertEqual(ProviderProfileConfig.LIFECYCLE_ENABLED, jira_profile.lifecycle_state)

        hsdes_payload = self._hsdes_profile_payload('monkey-hsdes-profile')
        with patch('bug_metrics.app.api.provider_profile_connection_test.HsdesHttpClient') as hsdes_client:
            hsdes_client.return_value.execute_saved_query.return_value = {'total': 1, 'data': [{'id': '1'}]}
            hsdes_response = self.client.post(reverse('ui_web:provider_setup'), {
                **hsdes_payload,
                'action': 'test_connection',
            })
        hsdes_content = hsdes_response.content.decode()
        self.assertEqual(200, hsdes_response.status_code)
        self.assertIn('HSD-ES Connection Probe', hsdes_content)
        self.assertIn('value="15017652869"', hsdes_content)
        self.assertIn('value="ip_fw_sw_sensing.tenant"', hsdes_content)
        self.assertIn('value="ip_fw_sw_sensing.bug"', hsdes_content)
        self.assertIn('HSD-ES saved-query probe succeeded.', hsdes_content)
        self.assertNotIn('Advanced source settings', hsdes_content)

        self.client.post(reverse('ui_web:provider_setup'), hsdes_payload, follow=True)
        self.assertEqual(
            ProviderProfileConfig.LIFECYCLE_ENABLED,
            ProviderProfileConfig.objects.get(profile_id='monkey-hsdes-profile').lifecycle_state,
        )

        hsdes_scope_page = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'hsdes',
            'profile_id': 'monkey-hsdes-profile',
        })
        hsdes_scope_content = hsdes_scope_page.content.decode()
        self.assertEqual(200, hsdes_scope_page.status_code)
        self.assertIn('option value="monkey-hsdes-profile" selected', hsdes_scope_content)
        self.assertIn('scope-provider-choice is-provider-blue is-selected', hsdes_scope_content)

        scope_response = self.client.get(reverse('ui_web:bug_trend_scope_config'), {
            'mode': 'new',
            'provider_id': 'jira',
            'profile_id': 'monkey-jira-profile',
        })
        scope_content = scope_response.content.decode()
        self.assertEqual(200, scope_response.status_code)
        self.assertIn('option value="monkey-jira-profile" selected', scope_content)
        self.assertIn('scope-provider-choice is-provider-green is-selected', scope_content)

        save_scope_response = self.client.post(
            reverse('ui_web:bug_trend_scope_config'),
            self._scope_payload('Monkey Jira Scope', 'monkey-jira-profile'),
            follow=True,
        )
        scope = JiraScopeConfig.objects.get(name='Monkey Jira Scope')
        binding = BugTrendScopeProviderBinding.objects.get(scope=scope)
        self.assertEqual(200, save_scope_response.status_code)
        self.assertTrue(scope.enabled)
        self.assertEqual('monkey-jira-profile', binding.profile_id)
        self.assertEqual('jira', binding.provider_id)

        run, bucket = self._seed_run_and_issue(scope)
        workbench_response = self.client.get(reverse('ui_web:workbench'), {
            'scope_id': scope.id,
            'begin': '2026-09-01',
            'end': '2026-09-07',
            'chart_id': 'default_bug_trend',
            'run': str(run.id),
            'bucket': str(bucket.id),
            'series': 'new_critical_high',
        })
        workbench_content = workbench_response.content.decode()
        self.assertEqual(200, workbench_response.status_code)
        self.assertIn('id="workbench-profile" value="monkey-jira-profile"', workbench_content)
        self.assertIn('id="workbench-provider" value="jira"', workbench_content)
        self.assertIn('MONKEY-1', workbench_content)
        self.assertIn('data-workbench-evidence-workspace', workbench_content)

    def _measure_baseline_pages(self, pages):
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            results = {}
            for label, html, expectations in pages:
                browser_html = self._browser_html(html)
                results[label] = {
                    'desktop': self._measure_viewport(browser, browser_html, expectations, 1440, 900),
                    'phone': self._measure_viewport(browser, browser_html, expectations, 390, 900),
                }
            return results
        finally:
            browser.close()
            playwright.stop()

    def _measure_viewport(self, browser, html, expectations, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                expectations => {
                    const visible = element => Boolean(
                        element
                        && (element.offsetWidth || element.offsetHeight || element.getClientRects().length)
                    );
                    const max = values => values.length ? Math.max(...values) : 0;
                    const min = values => values.length ? Math.min(...values) : 0;
                    const heightDelta = selector => {
                        const heights = Array.from(document.querySelectorAll(selector))
                            .filter(visible)
                            .map(element => Math.round(element.getBoundingClientRect().height))
                            .filter(value => value > 0);
                        return max(heights) - min(heights);
                    };
                    const actionButtons = Array.from(document.querySelectorAll('.dashboard-action-bar .button')).filter(visible);
                    const clippedActionButtons = actionButtons
                        .filter(button => button.scrollWidth > Math.ceil(button.clientWidth) + 1)
                        .map(button => button.innerText.trim());
                    const selectedChecks = Array.from(document.querySelectorAll('.provider-setup-choice.is-selected .provider-tab-check'))
                        .filter(visible);
                    return {
                        expects_editor: Boolean(expectations.editor),
                        expects_provider_tabs: Boolean(expectations.provider_tabs),
                        expects_table: Boolean(expectations.table),
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        visible_button_count: Array.from(document.querySelectorAll('.button')).filter(visible).length,
                        clipped_action_buttons: clippedActionButtons,
                        responsive_table_count: document.querySelectorAll('.responsive-admin-table').length,
                        provider_tab_shell_count: document.querySelectorAll('.provider-tab-shell').length,
                        selected_provider_check_visible: selectedChecks.some(check => check.getBoundingClientRect().width >= 14),
                        required_summary_count: document.querySelectorAll('[data-required-summary]').length,
                        dirty_banner_count: document.querySelectorAll('[data-dirty-banner]').length,
                        action_bar_count: document.querySelectorAll('.dashboard-action-bar').length,
                        action_bar_button_height_delta: heightDelta('.dashboard-action-bar .button'),
                        editor_control_height_delta: heightDelta('.dashboard-form-field .input, .dashboard-form-field select'),
                    };
                }
            """, expectations)
        finally:
            page.close()

    def _browser_html(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        main_js = (static_dir / 'js' / 'main.js').read_text(encoding='utf-8')
        return html.replace(
            '</head>',
            f'<style>{vendor_css}\n{main_css}</style></head>',
        ).replace(
            '</body>',
            f'<script>{main_js}</script></body>',
        )

    def _jira_profile_payload(self, profile_id):
        return {
            'action': 'enable_profile',
            'id': '',
            'profile_id': profile_id,
            'provider_id': 'jira',
            'display_name': 'Monkey Jira Profile',
            'lifecycle_state': 'draft',
            'mapping_version': '1',
            'connection_base_url': 'https://jira.example.test',
            'connection_auth_mode': 'server_pat',
            'credential_ref': 'profile:local',
            'source_population': json.dumps({'native_query_text': 'project = MONKEY'}),
            'scope_labels': json.dumps({'ip': 'monkey-ip', 'project_or_product': 'monkey-project'}),
            'field_bindings': json.dumps({'severity': {'native_field': 'priority'}}),
            'value_mappings': json.dumps({'bug_type_values': ['Bug']}),
            'chart_bindings': json.dumps({'open_bug_trend': {'support_status': 'supported'}}),
            'sync_policy': json.dumps({'live_sync': 'supported'}),
            'readiness_policy': json.dumps({'ready_status': 'ready'}),
        }

    def _hsdes_profile_payload(self, profile_id):
        return {
            'action': 'enable_profile',
            'id': '',
            'profile_id': profile_id,
            'provider_id': 'hsdes',
            'display_name': 'Monkey HSD-ES Profile',
            'lifecycle_state': 'draft',
            'mapping_version': '1',
            'connection_base_url': 'https://hsdes-api.example.test/rest',
            'connection_auth_mode': 'kerberos',
            'credential_ref': 'profile:local',
            'hsdes_saved_query_id': '15017652869',
            'hsdes_tenant': 'ip_fw_sw_sensing.tenant',
            'hsdes_subject': 'ip_fw_sw_sensing.bug',
            'source_population': json.dumps({
                'provider_id': 'hsdes',
                'ownership_type': 'provider_owned_saved_query',
            }),
            'scope_labels': json.dumps({'ip': 'NVU', 'project_or_product': 'NVU1.0_TTL'}),
            'field_bindings': json.dumps({'item_id': {'native_field': 'id'}}),
            'value_mappings': json.dumps({'bug_type_values': ['bug']}),
            'chart_bindings': json.dumps({'component_bug': {'support_status': 'supported_from_seed_facts'}}),
            'sync_policy': json.dumps({'live_sync': 'configuration_required'}),
            'readiness_policy': json.dumps({'ready_status': 'seeded_preview'}),
        }

    def _scope_payload(self, name, profile_id):
        return {
            'action': 'save_enable',
            'id': '',
            'name': name,
            'ip': 'MONKEY',
            'project_label': 'Monkey',
            'jql': 'project = MONKEY',
            'bug_type_values': 'Bug',
            'open_status_values': 'Open',
            'fixed_status_values': 'Fixed',
            'closed_status_values': 'Closed',
            'terminal_excluded_status_values': '',
            'fixed_resolution_values': '',
            'closed_resolution_values': '',
            'reopen_status_values': '',
            'severity_field': 'priority',
            'critical_high_values': 'P1-Critical',
            'medium_low_values': 'P3-Medium',
            'component_field': 'components',
            'owner_field': 'assignee',
            'team_field': '',
            'milestone_field': '',
            'fix_version_field': '',
            'package_version_field': '',
            'display_fields': '',
            'timezone': 'UTC',
            'bucket_granularity': 'weekly',
            'provider_id': 'jira',
            'profile_id': profile_id,
        }

    def _seed_bound_scope_with_run(self):
        scope = JiraScopeConfig.objects.create(
            name='Baseline Workbench Scope',
            jql='project = BASELINE',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            enabled=True,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        run, bucket = self._seed_run_and_issue(scope)
        return scope, run, bucket

    def _seed_run_and_issue(self, scope):
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 9, 8, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 9, 1),
            source_coverage_end=date(2026, 9, 7),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 9, 1),
            bucket_end=date(2026, 9, 7),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            new_critical_high_count=1,
            open_count=1,
        )
        BugTrendBucketIssue.objects.create(
            scope=scope,
            bucket=bucket,
            calculation_run=run,
            series_name='new_critical_high',
            issue_key='MONKEY-1',
            summary='Monkey user visible ticket',
            status='Open',
            severity_value='P1-Critical',
            component_value='ui',
            owner_value='Monkey User',
            created_at=datetime(2026, 9, 2, tzinfo=timezone.utc),
            updated_at=datetime(2026, 9, 3, tzinfo=timezone.utc),
        )
        return run, bucket
