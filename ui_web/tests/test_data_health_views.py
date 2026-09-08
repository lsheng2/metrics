from datetime import date, datetime, timezone
from pathlib import Path

from django.test import TestCase
from django.urls import reverse
from playwright.sync_api import sync_playwright

from bug_metrics.models import BugTrendAuditEvent, BugTrendCalculationRun, BugTrendScopeProviderBinding, JiraScopeConfig
from jira_sync.models import JiraSyncCursor
from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


class TestDataHealthViews(TestCase):
    def test_shouldRenderReadOnlySyncAndCalculationHealth(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='STDEL data health',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        old_hash = scope.config_version_hash
        JiraSyncCursor.objects.create(
            scope=scope,
            status=JiraSyncCursor.STATUS_FAILED,
            last_successful_sync_at=datetime(2026, 8, 19, 1, 2, tzinfo=timezone.utc),
            last_jira_updated_cutoff=datetime(2026, 8, 19, 3, 4, tzinfo=timezone.utc),
            earliest_reliable_bucket_start=date(2026, 8, 1),
            latest_reliable_bucket_end=date(2026, 8, 9),
            changelog_coverage_status='partial',
            materialized_config_version_hash=old_hash,
            last_error='Jira timeout',
        )
        scope.fixed_status_values = ['Fixed']
        scope.save()
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=old_hash,
            source_coverage_start=date(2026, 8, 1),
            source_coverage_end=date(2026, 8, 31),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        before_counts = self._counts()

        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        self.assertEqual(before_counts, self._counts())
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Data Health', content)
        self.assertIn('class="help-tip"', content)
        self.assertIn('Read-only readiness checks for scope binding', content)
        self.assertIn('STDEL data health', content)
        self.assertIn('Jira timeout', content)
        self.assertIn('partial', content)
        self.assertIn('stale_config', content)
        self.assertIn(str(run.id), content)
        self.assertNotIn('Recalculate now', content)
        self.assertNotIn('Sync now', content)

    def test_shouldRenderProviderSyncCacheHealthWithoutSecrets(self):
        # Given
        cache_service = ProviderSyncCacheService()
        cache_service.materialize_snapshot(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            source_query={
                'ownership_type': 'provider_owned_saved_query',
                'source_query_ref': '15017652869',
                'source_query_hash': 'source-hash',
            },
            field_set_hash='field-hash',
            mapping_version_hash='mapping-hash',
            facts=[],
            raw_payload={'total': 0},
            freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
        )
        cache_service.record_failure(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            error_category='auth_failed',
            message='Bearer secret-token failed',
        )

        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Provider Sync Cache Health', content)
        self.assertIn('Checks whether provider profile facts and snapshots are fresh enough', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('auth_failed', content)
        self.assertIn('Bearer [redacted]', content)
        self.assertNotIn('secret-token', content)

    def test_shouldRenderRegistryProviderProfileHealthWithoutSyncCursors(self):
        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('chiplet-2a-jira', content)
        self.assertIn('nvu-ttl-hsdes', content)
        self.assertIn('metrics_managed_native_query', content)
        self.assertIn('provider_owned_saved_query', content)
        self.assertIn('open_bug_trend', content)
        self.assertIn('Mapping', content)
        self.assertIn('The field normalization version that translates provider-specific facts', content)

    def test_shouldRenderAiSidecarDisabledStatusWithoutCallingAiBase(self):
        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('AI Sidecar Health', content)
        self.assertIn('disabled', content)
        self.assertIn('dashboard_query_agent', content)
        self.assertNotIn('token', content.lower())

    def test_shouldRenderScopeBindingHealthSummaryAndRepairLinks(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Binding health scope',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='chiplet-2a-jira',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'matched_by': 'legacy_jira_scope'},
        )

        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Scope Binding Health', content)
        self.assertIn('responsive-admin-table', content)
        self.assertIn('is-cardable', content)
        self.assertIn('data-label="Scope"', content)
        self.assertIn('data-label="Repair"', content)
        self.assertIn('Explicit-only readiness', content)
        self.assertIn('compatibility_allowed permits inferred legacy bindings', content)
        self.assertIn('The provider profile binding was inferred from legacy behavior', content)
        self.assertIn('Policy: compatibility_allowed', content)
        self.assertIn('Blocked', content)
        self.assertIn('1 impacted scopes', content)
        self.assertIn('Explicit-only impacted scopes', content)
        self.assertIn('Inferred', content)
        self.assertIn('Binding health scope', content)
        self.assertIn('legacy_jira_scope', content)
        self.assertIn(reverse('ui_web:bug_trend_scope_library'), content)

    def test_shouldRenderScopeBindingAuditHistory(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Binding audit scope',
            jql='project = STDEL',
            bug_type_values=['Bug'],
        )
        BugTrendAuditEvent.objects.create(
            event_type=BugTrendAuditEvent.EVENT_SCOPE_BINDING_UPDATED,
            actor='scope_admin',
            scope=scope,
            request_summary={
                'before': {'status': 'compatibility', 'provider_id': 'jira', 'profile_id': 'old-profile'},
                'after': {'status': 'explicit', 'provider_id': 'jira', 'profile_id': 'new-profile'},
            },
        )

        # When
        response = self.client.get(reverse('ui_web:data_health'))

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('Scope Binding Audit History', content)
        self.assertIn('scope_admin', content)
        self.assertIn('scope_binding_updated', content)
        self.assertIn('compatibility: jira / old-profile', content)
        self.assertIn('explicit: jira / new-profile', content)

    def test_shouldAdaptDataHealthAdminTablesOnlyOnPhoneSizedScreens(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='Binding health compact scope',
            jql='project = STDEL AND component = very_long_component_name',
            bug_type_values=['Bug'],
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id='Binding health compact profile with long text',
            provider_id='jira',
            status=BugTrendScopeProviderBinding.STATUS_COMPATIBILITY,
            provenance={'matched_by': 'legacy_jira_scope'},
        )
        response = self.client.get(reverse('ui_web:data_health'))

        # When
        result = self._measure_data_health_responsive_tables(response.content.decode())

        # Then
        self.assertFalse(result['desktop']['page_horizontal_overflow'])
        self.assertNotEqual('none', result['desktop']['thead_display'])
        self.assertNotEqual('grid', result['desktop']['first_cell_display'])
        self.assertFalse(result['phone']['page_horizontal_overflow'])
        self.assertEqual('none', result['phone']['thead_display'])
        self.assertEqual('grid', result['phone']['first_cell_display'])
        self.assertEqual('Scope', result['phone']['first_cell_label'])

    def _counts(self):
        return {
            'scopes': JiraScopeConfig.objects.count(),
            'cursors': JiraSyncCursor.objects.count(),
            'runs': BugTrendCalculationRun.objects.count(),
        }

    def _measure_data_health_responsive_tables(self, html):
        static_dir = Path(__file__).resolve().parents[1] / 'static'
        vendor_css = (static_dir / 'css' / 'vendor_fallbacks.css').read_text(encoding='utf-8')
        main_css = (static_dir / 'css' / 'main.css').read_text(encoding='utf-8')
        html = html.replace('</head>', f'<style>{vendor_css}\n{main_css}</style></head>')
        playwright = sync_playwright().start()
        browser = playwright.chromium.launch(headless=True)
        try:
            return {
                'desktop': self._measure_data_health_viewport(browser, html, 760, 900),
                'phone': self._measure_data_health_viewport(browser, html, 390, 900),
            }
        finally:
            browser.close()
            playwright.stop()

    def _measure_data_health_viewport(self, browser, html, width, height):
        page = browser.new_page(viewport={'width': width, 'height': height})
        try:
            page.set_content(html, wait_until='domcontentloaded')
            return page.evaluate("""
                () => {
                    const table = document.querySelector('.data-health-page .responsive-admin-table.is-cardable');
                    const thead = table.querySelector('thead');
                    const firstCell = table.querySelector('tbody td[data-label]');
                    return {
                        page_horizontal_overflow: document.documentElement.scrollWidth > document.documentElement.clientWidth + 1,
                        table_horizontal_overflow: table.closest('.responsive-admin-table-box').scrollWidth > table.closest('.responsive-admin-table-box').clientWidth + 1,
                        thead_display: getComputedStyle(thead).display,
                        first_cell_display: getComputedStyle(firstCell).display,
                        first_cell_label: firstCell.dataset.label,
                    };
                }
            """)
        finally:
            page.close()
