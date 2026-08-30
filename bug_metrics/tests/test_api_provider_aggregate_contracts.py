import hashlib
from datetime import date, datetime, timezone

from django.test import TestCase

from bug_metrics.app.api import ProviderChartAggregateQuery, bug_trend_api
from bug_metrics.models import BugTrendCalculationRun, JiraScopeConfig
from jira_history.models import JiraIssue, JiraTransition


class TestProviderAggregateContracts(TestCase):
    def test_shouldProduceFirstWaveQualityAggregatesFromJiraFacts(self):
        # Given
        scope = self._seed_fixed_jira_scope_fixture()
        run = bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        results = {
            chart_id: bug_trend_api.get_provider_chart_aggregates(
                ProviderChartAggregateQuery(
                    provider_id='jira',
                    profile_id='chiplet-2a-jira',
                    begin_ww='26WW32',
                    end_ww='26WW32',
                    chart_id=chart_id,
                )
            )
            for chart_id in ['component_bug', 'rolling_valid_bug', 'open_bug_trend', 'total_bug_trend', 'open_bug_aging']
        }

        # Then
        self.assertEqual({'supported'}, {result.status for result in results.values()})
        self.assertEqual(str(run.id), results['open_bug_trend'].rows[0].calculation_run_id)
        self.assertEqual(2, self._row_value(results['component_bug'], 'component_bug_count', {'component': 'team_int_qemu'}))
        self.assertEqual(2, self._row_value(results['rolling_valid_bug'], 'rolling_valid_bug_count', {}))
        self.assertEqual(1, self._row_value(results['open_bug_trend'], 'all_open_bugs', {}))
        self.assertEqual(2, self._row_value(results['total_bug_trend'], 'total_new_bugs', {}))
        self.assertEqual(1, self._row_value(results['open_bug_aging'], 'aging_0_7_days', {}))

    def test_shouldReturnDeferredStateForUnmappedExecutionAndEfficiencyCharts(self):
        # Given
        self._seed_fixed_jira_scope_fixture()

        # When
        results = [
            bug_trend_api.get_provider_chart_aggregates(
                ProviderChartAggregateQuery(
                    provider_id='jira',
                    profile_id='chiplet-2a-jira',
                    begin_ww='26WW32',
                    end_ww='26WW32',
                    chart_id=chart_id,
                )
            )
            for chart_id in ['execution_statistics', 'automation_statistics', 'shift_left_statistics', 'internal_escaped_bugs']
        ]

        # Then
        self.assertEqual(['deferred', 'deferred', 'deferred', 'deferred'], [result.status for result in results])
        self.assertEqual([[], [], [], []], [result.rows for result in results])
        self.assertTrue(all(result.reason for result in results))

    def test_shouldExposeGrafanaAggregateRowProvenance(self):
        # Given
        scope = self._seed_fixed_jira_scope_fixture()
        run = bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                begin_ww='26WW32',
                end_ww='26WW32',
                chart_id='open_bug_trend',
            )
        )

        # Then
        row = result.rows[0].to_dict()
        self.assertEqual('0.2', result.contract_version)
        self.assertEqual('jira', row['provider_id'])
        self.assertEqual('chiplet-2a-jira', row['profile_id'])
        self.assertEqual(f'jira_scope:{scope.id}', row['source_scope_ref'])
        self.assertEqual('26WW32', row['begin_ww'])
        self.assertEqual('26WW32', row['end_ww'])
        self.assertEqual(str(run.id), row['calculation_run_id'])
        self.assertEqual(result.fact_snapshot_id, row['fact_snapshot_id'])
        self.assertEqual(1, row['mapping_version'])
        self.assertEqual(scope.config_version_hash, row['mapping_version_hash'])
        self.assertEqual('metrics_managed_native_query', row['source_query']['ownership_type'])
        self.assertEqual(1, result.grafana_rows[0]['all_open_bugs'])
        self.assertFalse(any(key.startswith(('jira_', 'hsdes_')) for key in result.grafana_rows[0]))

    def test_shouldMaterializeDailyNewStandardBugAggregateWithProviderNeutralFields(self):
        # Given
        scope = self._seed_fixed_jira_scope_fixture()
        run = bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                begin_ww='26WW32',
                end_ww='26WW32',
                chart_id='daily_new_standard_bug_count',
            )
        )

        # Then
        row = next(item for item in result.rows if item.bucket_date == '2026-08-04')
        self.assertEqual('daily_new_standard_bug_count', row.metric_id)
        self.assertEqual('day', row.bucket_grain)
        self.assertEqual(2, row.value)
        self.assertEqual({'ip': 'chiplet_ip', 'project_or_product': 'chiplet', 'milestone': '2a'}, row.dimensions)
        self.assertEqual(1, row.mapping_version)
        self.assertEqual(result.fact_snapshot_id, row.fact_snapshot_id)
        self.assertEqual(str(run.id), row.calculation_run_id)

    def test_shouldRejectMissingOrStaleAggregateArtifactsWithoutMismatchedRows(self):
        # Given
        scope = self._seed_fixed_jira_scope_fixture()
        old_hash = scope.config_version_hash
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))
        scope.fixed_status_values = ['Fixed', 'Closed', 'Verified Fixed']
        scope.save()

        # When
        stale_result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('jira', 'chiplet-2a-jira', '26WW32', '26WW32', 'open_bug_trend')
        )
        missing_result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('jira', 'chiplet-2a-jira', '26WW33', '26WW33', 'open_bug_trend')
        )

        # Then
        self.assertEqual('stale', stale_result.status)
        self.assertEqual('unavailable', missing_result.status)
        self.assertEqual([], stale_result.rows)
        self.assertEqual([], missing_result.rows)
        self.assertEqual(old_hash, stale_result.run_metadata['run_config_version_hash'])
        self.assertEqual(scope.config_version_hash, stale_result.run_metadata['current_config_version_hash'])

    def test_shouldNormalizeMetricsManagedJqlAndProviderSavedQueryIntoSameSourcePopulationShape(self):
        # Given
        scope = self._seed_fixed_jira_scope_fixture()
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        jira_result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('jira', 'chiplet-2a-jira', '26WW32', '26WW32', 'open_bug_trend')
        )
        hsdes_result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '25WW15', '26WW32', 'open_bug_trend')
        )

        # Then
        self.assertEqual(set(jira_result.source_population.keys()), set(hsdes_result.source_population.keys()))
        self.assertEqual('metrics_managed_native_query', jira_result.source_population['ownership_type'])
        self.assertEqual('provider_owned_saved_query', hsdes_result.source_population['ownership_type'])
        self.assertEqual(hashlib.sha256(scope.jql.encode('utf-8')).hexdigest(), jira_result.source_population['source_query_hash'])
        self.assertEqual('15017652869', hsdes_result.source_population['source_query_ref'])
        self.assertEqual('supported', hsdes_result.status)

    def test_shouldExposeFirstHsdesQualitySeedConfigurationWithProvenance(self):
        # When
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '25WW15', '26WW32', 'open_bug_trend')
        )

        # Then
        source_population = result.source_population
        self.assertEqual('provider_owned_saved_query', source_population['ownership_type'])
        self.assertEqual('15017652869', source_population['source_query_ref'])
        self.assertEqual('NVU All Bugs', source_population['source_query_name'])
        self.assertEqual('ip_fw_sw_sensing.tenant', source_population['tenant_or_site'])
        self.assertEqual('ip_fw_sw_sensing.bug', source_population['subject_or_issue_type'])
        self.assertEqual('All', source_population['criteria_operator'])
        self.assertIn('family in NVU-FW', source_population['criteria_snapshot'])
        self.assertIn('release in NVU-FW.trunk,NVU-FW1.0_RZL,NVU-FW1.0_TTL', source_population['criteria_snapshot'])
        self.assertIn('component not in sw.val,sw.val.tools,ip.sw.val.tool', source_population['exclusion_snapshot'])
        self.assertIn('provider saved query is readable by configured HSD-ES credentials', source_population['permission_assumptions'])
        self.assertEqual('HSD-ES article search returns ip_fw_sw_sensing.bug rows with stable id and revision fields.', source_population['observed_result_contract'])

    def test_shouldReturnHsdesComponentBugRowsFromSeedFactsForGrafana(self):
        # When
        results = {
            chart_id: bug_trend_api.get_provider_chart_aggregates(
                ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '26WW32', '26WW32', chart_id)
            )
            for chart_id in [
                'component_bug',
                'rolling_valid_bug',
                'open_bug_trend',
                'total_bug_trend',
                'open_bug_aging',
                'daily_new_standard_bug_count',
            ]
        }

        # Then
        result = results['component_bug']
        self.assertEqual({'supported'}, {item.status for item in results.values()})
        self.assertEqual('supported', result.status)
        self.assertEqual('materialized_from_seed_hsdes_facts', result.run_metadata['freshness_status'])
        self.assertEqual('hsdes', result.grafana_rows[0]['provider_id'])
        self.assertEqual('nvu-ttl-hsdes', result.grafana_rows[0]['profile_id'])
        self.assertEqual(2, self._row_value(result, 'component_bug_count', {'component': 'fwsw'}))
        self.assertEqual(1, self._row_value(result, 'component_bug_count', {'component': 'media'}))
        self.assertFalse(any(
            key.startswith(('jira_', 'hsdes_'))
            for item in results.values()
            for row in item.grafana_rows
            for key in row
        ))
        self.assertEqual(4, self._row_value(results['open_bug_trend'], 'all_open_bugs', {}))
        self.assertEqual(3, self._row_value(results['total_bug_trend'], 'total_new_bugs', {}))
        self.assertEqual(3, self._row_value(results['open_bug_aging'], 'aging_0_7_days', {}))
        self.assertEqual(2, next(row.value for row in results['daily_new_standard_bug_count'].rows if row.bucket_date == '2026-08-05'))

    def test_shouldReturnDeferredStateForHsdesFirstWaveDeferredCharts(self):
        # When
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '25WW15', '26WW32', 'execution_statistics')
        )

        # Then
        self.assertEqual('deferred', result.status)
        self.assertEqual([], result.rows)
        self.assertIn('deferred in the first wave', result.reason)

    def test_shouldExposeStaticScopeLabelProvenanceForFirstProviderProfiles(self):
        # Given
        self._seed_fixed_jira_scope_fixture()

        # When
        jira_result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('jira', 'chiplet-2a-jira', '26WW32', '26WW32', 'open_bug_trend')
        )
        hsdes_result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('hsdes', 'nvu-ttl-hsdes', '25WW15', '26WW32', 'open_bug_trend')
        )

        # Then
        jira_labels = jira_result.to_dict()['scope_labels']
        hsdes_labels = hsdes_result.to_dict()['scope_labels']
        self.assertEqual({'ip': 'chiplet_ip', 'project_or_product': 'chiplet', 'milestone': '2a'}, {name: label['value'] for name, label in jira_labels.items()})
        self.assertEqual({'ip': 'NVU', 'project_or_product': 'NVU1.0_TTL', 'milestone': 'NVU_TTL_FWSW0.8'}, {name: label['value'] for name, label in hsdes_labels.items()})
        self.assertEqual({'user_configured_static_text'}, {label['source'] for label in jira_labels.values()})
        self.assertEqual({'user_configured_static_text'}, {label['source'] for label in hsdes_labels.values()})
        self.assertEqual({1}, {label['mapping_version'] for label in jira_labels.values()})
        self.assertEqual({1}, {label['mapping_version'] for label in hsdes_labels.values()})

    def test_shouldExposeProviderSeriesStateForGrafanaStatePanels(self):
        # Given
        self._seed_fixed_jira_scope_fixture()

        # When
        result = bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery('jira', 'chiplet-2a-jira', '26WW32', '26WW32', 'execution_statistics')
        )

        # Then
        payload = result.to_dict()
        self.assertEqual([], payload['grafana_rows'])
        self.assertEqual([{
            'provider_id': 'jira',
            'profile_id': 'chiplet-2a-jira',
            'chart_id': 'execution_statistics',
            'chart_version': 1,
            'evidence_capability': 'summary_only',
            'begin_ww': '26WW32',
            'end_ww': '26WW32',
            'range_mode': 'ww',
            'begin_date': '2026-08-03',
            'end_date': '2026-08-09',
            'status': 'deferred',
            'reason': result.reason,
            'fact_snapshot_id': '',
        }], payload['provider_series_state'])

    def _seed_fixed_jira_scope_fixture(self):
        scope = JiraScopeConfig.objects.create(
            name='chiplet-2a-jira',
            ip='chiplet_ip',
            project_label='chiplet',
            jql='project = "131600" AND component = "team_int_qemu"',
            bug_type_values=['Bug'],
            open_status_values=['Open', 'In Progress', 'Reopened'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Stopper', 'P2-High'],
            medium_low_values=['P3-Medium'],
            component_field='components',
            owner_field='assignee',
            milestone_field='2a',
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
            owner_value='Alice',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            summary='Fixed medium bug',
            issue_type='Bug',
            status='Fixed',
            severity_value='P3-Medium',
            component_value='team_int_qemu',
            owner_value='Bob',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            resolved_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
        )
        JiraIssue.objects.create(
            scope=scope,
            issue_key='STDEL-2001',
            summary='Task outside bug facts',
            issue_type='Task',
            status='Open',
            severity_value='P3-Medium',
            component_value='team_int_qemu',
            created_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
            updated_at=datetime(2026, 8, 4, tzinfo=timezone.utc),
        )
        JiraTransition.objects.create(
            scope=scope,
            issue_key='STDEL-1002',
            transitioned_at=datetime(2026, 8, 5, tzinfo=timezone.utc),
            field='status',
            from_value='Open',
            to_value='Fixed',
        )
        return scope

    def _row_value(self, result, metric_id, dimensions):
        for row in result.rows:
            if row.metric_id == metric_id and all(row.dimensions.get(key) == value for key, value in dimensions.items()):
                return row.value
        return None
