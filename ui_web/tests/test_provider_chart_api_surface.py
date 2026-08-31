from datetime import date, datetime, timezone
from unittest.mock import patch

from django.test import TestCase
from django.urls import reverse

from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import JiraScopeConfig
from jira_history.models import JiraIssue
from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


class TestProviderChartApiSurface(TestCase):
    def test_shouldExposeProviderProfileReadinessForGrafanaStatusPanel(self):
        # When
        response = self.client.get(reverse('ui_web:provider_profile_readiness_api'), {
            'profile_id': 'nvu-ttl-hsdes',
            'range_mode': 'ww',
            'begin_ww': '26WW01',
            'end_ww': '26WW35',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertEqual('hsdes', payload['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', payload['profile_id'])
        self.assertEqual('seeded_preview', payload['status'])
        self.assertEqual('NVU', payload['scope_labels']['ip']['value'])
        self.assertEqual('provider_owned_saved_query', payload['source_query']['ownership_type'])
        self.assertTrue(payload['blockers'])
        self.assertEqual('profile_default', payload['profile_status_rows'][0]['override_state'])
        self.assertIn('HSD-ES seed facts can render supported preview charts', payload['profile_status_rows'][0]['data_status_reason'])
        self.assertEqual('Open HSD-ES saved query / sign in', payload['profile_status_rows'][0]['auth_action_label'])
        self.assertEqual('https://hsdes.intel.com/appstore/generalapps/#/pages/community/1607367026?queryId=15017652869', payload['profile_status_rows'][0]['auth_action_url'])
        self.assertEqual('Sync Time Range', payload['profile_status_rows'][0]['time_range_action_label'])
        self.assertEqual(
            '/d/ip-quality-dashboard/ip-quality-dashboard?orgId=1&var-profile_id=nvu-ttl-hsdes&var-range_mode=ww&var-begin_ww=26WW01&var-end_ww=26WW35&from=2025-12-29T00%3A00%3A00&to=2026-08-30T23%3A59%3A59&timezone=browser',
            payload['profile_status_rows'][0]['time_range_action_url'],
        )

    def test_shouldReturnHtmlRedirectForAlignedGrafanaTimeRange(self):
        # When
        response = self.client.get(reverse('ui_web:provider_profile_align_dashboard_range_api'), {
            'profile_id': 'nvu-ttl-hsdes',
            'range_mode': 'ww',
            'begin_ww': '26WW01',
            'end_ww': '26WW35',
        }, HTTP_REFERER='http://127.0.0.1:3001/d/ip-quality-dashboard/ip-quality-dashboard')

        # Then
        content = response.content.decode()
        self.assertEqual(200, response.status_code)
        self.assertIn('http://127.0.0.1:3001/d/ip-quality-dashboard/ip-quality-dashboard?', content)
        self.assertIn('var-begin_ww=26WW01', content)
        self.assertIn('var-end_ww=26WW35', content)
        self.assertIn('from=2025-12-29T00%3A00%3A00', content)
        self.assertIn('to=2026-08-30T23%3A59%3A59', content)

    def test_shouldExposeLiveHsdesCacheStatusAfterSuccessfulSync(self):
        # Given
        cache_service = ProviderSyncCacheService()
        snapshot = cache_service.materialize_snapshot(
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

        # When
        response = self.client.get(reverse('ui_web:provider_profile_readiness_api'), {
            'profile_id': 'nvu-ttl-hsdes',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('live_synced', payload['status'])
        self.assertEqual(str(snapshot.id), payload['sync_cache']['latest_snapshot_id'])
        self.assertEqual('live_synced', payload['profile_status_rows'][0]['data_status'])
        self.assertEqual('15017652869', payload['profile_status_rows'][0]['source_query_ref'])

    def test_shouldRenderHsdesChartFromLocalArtifactWhenLiveAdapterFails(self):
        # Given
        cache_service = ProviderSyncCacheService()
        snapshot = cache_service.materialize_snapshot(
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
        cache_service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='component_bug',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{
                'provider_id': 'hsdes',
                'profile_id': 'nvu-ttl-hsdes',
                'bucket_label': '26WW32',
                'dimensions': {'component': 'fwsw'},
                'component_bug_count': 4,
            }],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )

        # When
        with patch('provider_sync.app.api.hsdes.HsdesHttpClient.execute_saved_query', side_effect=AssertionError('live adapter must not be called')):
            response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
                'profile_id': 'nvu-ttl-hsdes',
                'begin_ww': '26WW32',
                'end_ww': '26WW32',
                'chart_id': 'component_bug',
                'chart_version': '1',
            })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('supported', payload['status'])
        self.assertEqual('fwsw', payload['grafana_rows'][0]['component_label'])
        self.assertEqual(4, payload['grafana_rows'][0]['component_bug_count'])

    def test_shouldUseDateRangeLiveFactsInsteadOfWorkWeekArtifactWhenRangeModeIsDate(self):
        # Given
        cache_service = ProviderSyncCacheService()
        snapshot = cache_service.materialize_snapshot(
            provider_id='hsdes',
            profile_id='nvu-ttl-hsdes',
            source_query={
                'ownership_type': 'provider_owned_saved_query',
                'source_query_ref': '15017652869',
                'source_query_hash': 'source-hash',
            },
            field_set_hash='field-hash',
            mapping_version_hash='mapping-hash',
            facts=[{
                'source_item_id': '1607367026-1',
                'source_item_revision': '1',
                'canonical_fields': {
                    'source_item_type': 'bug',
                    'created_at': '2026-08-10T01:00:00Z',
                    'severity_or_priority': 'medium',
                },
            }],
            raw_payload={'total': 1},
            freshness_status=ProviderFreshnessStatus.LIVE_SYNCED,
        )
        cache_service.store_aggregate_artifact(
            snapshot=snapshot,
            chart_id='open_bug_trend',
            chart_version=1,
            begin_ww='26WW32',
            end_ww='26WW32',
            rows=[],
            grafana_rows=[{
                'provider_id': 'hsdes',
                'profile_id': 'nvu-ttl-hsdes',
                'bucket_label': '26WW32',
                'bucket_start': '2026-08-03',
                'bucket_end': '2026-08-09',
                'all_open_bugs': 99,
            }],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )

        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'profile_id': 'nvu-ttl-hsdes',
            'range_mode': 'date',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'begin_date': '2026-08-10',
            'end_date': '2026-08-16',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('date', payload['range_mode'])
        self.assertEqual('live_synced', payload['run_metadata']['freshness_status'])
        self.assertEqual('2026-08-10', payload['grafana_rows'][0]['bucket_start'])
        self.assertIn('2026-08-10-2026-08-16', payload['grafana_rows'][0]['calculation_run_id'])
        self.assertEqual(1, payload['grafana_rows'][0]['all_open_bugs'])

    def test_shouldExposeProviderChartAggregatesForGrafanaSurface(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Open stopper bug',
            issue_type='Bug',
            status='Open',
            severity_value='P1-Stopper',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        run = bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertEqual('supported', payload['status'])
        self.assertEqual(str(run.id), payload['grafana_rows'][0]['calculation_run_id'])
        self.assertEqual('jira', payload['grafana_rows'][0]['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['grafana_rows'][0]['profile_id'])
        self.assertEqual(1, payload['grafana_rows'][0]['all_open_bugs'])
        self.assertFalse(any(key.startswith(('jira_', 'hsdes_')) for key in payload['grafana_rows'][0]))

    def test_shouldUseBrowserDateRangeWhenProviderChartRangeModeIsDate(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Open stopper bug',
            issue_type='Bug',
            status='Open',
            severity_value='P1-Stopper',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'profile_id': 'chiplet-2a-jira',
            'range_mode': 'date',
            'begin_date': '2026-08-03',
            'end_date': '2026-08-09',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('date', payload['range_mode'])
        self.assertEqual('2026-08-03', payload['begin_date'])
        self.assertEqual('2026-08-09', payload['end_date'])
        self.assertEqual('', payload['begin_ww'])
        self.assertEqual('', payload['end_ww'])
        self.assertEqual(1, payload['grafana_rows'][0]['all_open_bugs'])

    def test_shouldExposeHsdesSeededComponentBugAggregatesForGrafanaSurface(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'profile_id': 'nvu-ttl-hsdes',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'component_bug',
            'chart_version': '1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('0.2', payload['contract_version'])
        self.assertEqual('hsdes', payload['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', payload['profile_id'])
        self.assertEqual('supported', payload['status'])
        self.assertEqual('materialized_from_seed_hsdes_facts', payload['run_metadata']['freshness_status'])
        self.assertEqual('fwsw', self._row_value(payload, 'component_label', 'fwsw'))
        self.assertEqual('media', self._row_value(payload, 'component_label', 'media'))
        self.assertEqual(2, self._row_value(payload, 'component_bug_count', 'fwsw'))
        self.assertEqual(1, self._row_value(payload, 'component_bug_count', 'media'))
        self.assertFalse(any(
            key.startswith(('jira_', 'hsdes_'))
            for row in payload['grafana_rows']
            for key in row
        ))

    def test_shouldExposeHsdesOpenBugAgingAsAgeBucketCategoriesForGrafanaSurface(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'profile_id': 'nvu-ttl-hsdes',
            'begin_ww': '26WW32',
            'end_ww': '26WW35',
            'chart_id': 'open_bug_aging',
            'chart_version': '1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('supported', payload['status'])
        self.assertEqual(
            ['0-7 Days', '8-14 Days', '15-30 Days', '31+ Days'],
            [row['age_bucket_label'] for row in payload['grafana_rows']],
        )
        self.assertTrue(all('open_bug_count' in row for row in payload['grafana_rows']))

    def test_shouldDeriveProviderFromProfileWhenProviderIdIsOmitted(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Open stopper bug',
            issue_type='Bug',
            status='Open',
            severity_value='P1-Stopper',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('jira', payload['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['profile_id'])
        self.assertEqual('supported', payload['status'])

    def test_shouldRejectMismatchedExplicitProviderAndProfile(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'provider_id': 'hsdes',
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertIn('does not match selected profile', response.json()['error'])

    def test_shouldExposeProviderChartEvidenceForGrafanaBucketSeriesSelection(self):
        # Given
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open'],
            fixed_status_values=['Fixed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1001',
            summary='Open stopper bug',
            issue_type='Bug',
            status='Open',
            severity_value='P1-Stopper',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        run = bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        chart_response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
        })
        bucket_id = chart_response.json()['grafana_rows'][0]['bucket_id']

        # When
        reference_response = self.client.get(reverse('ui_web:chart_evidence_api'), {
            'scope_id': scope.id,
            'run': str(run.id),
            'begin': '2026-08-03',
            'end': '2026-08-09',
            'chart_id': 'default_bug_trend',
            'bucket': bucket_id,
            'series': 'all_open_bugs',
        })
        response = self.client.get(reverse('ui_web:provider_chart_evidence_api'), {
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
            'run': str(run.id),
            'bucket': bucket_id,
            'series': 'all_open_bugs',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('supported', payload['status'])
        self.assertEqual('jira', payload['provider_id'])
        self.assertEqual('chiplet-2a-jira', payload['profile_id'])
        self.assertEqual('open_bug_trend', payload['chart_id'])
        self.assertEqual(str(run.id), payload['calculation_run_id'])
        self.assertEqual(bucket_id, payload['bucket_id'])
        self.assertEqual('all_open_bugs', payload['provider_series_name'])
        self.assertEqual(reference_response.json()['selection_title'], payload['selection_title'])
        self.assertEqual(reference_response.json()['total_count'], payload['total_count'])
        self.assertEqual(['STDEL-1001'], [row['issue_key'] for row in payload['rows']])

    def test_shouldDeriveProviderFromProfileForProviderChartEvidence(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_evidence_api'), {
            'profile_id': 'nvu-ttl-hsdes',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
            'run': 'run-1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('hsdes', payload['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', payload['profile_id'])
        self.assertEqual('configuration_required', payload['status'])

    def test_shouldReturnSummaryOnlyProviderEvidenceStateWithoutRows(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_evidence_api'), {
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'execution_statistics',
            'chart_version': '1',
            'run': 'run-1',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('summary_only', payload['evidence_capability'])
        self.assertEqual('deferred', payload['status'])
        self.assertEqual([], payload['rows'])
        self.assertIn('ticket-level evidence', payload['reason'])

    def test_shouldReturnUnsupportedProviderEvidenceStateWithoutRows(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_evidence_api'), {
            'provider_id': 'unknown-provider',
            'profile_id': 'unknown-profile',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'chart_version': '1',
            'run': 'run-1',
            'bucket': 'bucket-1',
            'series': 'unknown-provider_all_open_bugs',
        })

        # Then
        payload = response.json()
        self.assertEqual(200, response.status_code)
        self.assertEqual('summary_only', payload['evidence_capability'])
        self.assertEqual('unsupported', payload['status'])
        self.assertEqual([], payload['rows'])

    def test_shouldRejectNativeQueryParamsOnProviderChartApi(self):
        # When
        response = self.client.get(reverse('ui_web:provider_chart_data_api'), {
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'chart_id': 'open_bug_trend',
            'jql': 'project = 131600',
        })

        # Then
        self.assertEqual(400, response.status_code)
        self.assertEqual(['jql'], response.json()['unknown_params'])

    def _row_value(self, payload, value_field, component):
        for row in payload['grafana_rows']:
            if row['dimensions'].get('component') == component:
                return row.get(value_field)
        return None
