from django.test import SimpleTestCase
from django.http import QueryDict

from ui_web.workbench_state import WorkbenchPageQueryState
from ui_web.workbench_grafana import grafana_full_dashboard_url, grafana_panel_embed_url


class TestWorkbenchPageQueryState(SimpleTestCase):
    def test_shouldRoundTripWorkbenchPageQueryStateFromQueryParams(self):
        # Given
        query = QueryDict(
            'profile_id=nvu-ttl-hsdes&provider_id=hsdes&range_mode=date&begin=2026-08-01&end=2026-08-31'
            '&chart_id=open_bug_trend&chart_version=2&run=run-1&snapshot=snapshot-1'
            '&bucket=bucket-1&series=new_critical_high&text=display&status=open&severity=critical'
            '&owner=alice&component=media'
        )

        # When
        state = WorkbenchPageQueryState.from_query(query)

        # Then
        self.assertEqual(query['profile_id'], state.profile_id)
        self.assertEqual('', state.scope_id)
        self.assertEqual(query['provider_id'], state.provider_id)
        self.assertEqual(query['range_mode'], state.range_mode)
        self.assertEqual(query['begin'], state.begin)
        self.assertEqual(query['end'], state.end)
        self.assertEqual(query['chart_id'], state.chart_id)
        self.assertEqual(query['chart_version'], state.chart_version)
        self.assertEqual(query['run'], state.calculation_run_id)
        self.assertEqual(query['snapshot'], state.fact_snapshot_id)
        self.assertEqual(query['bucket'], state.selected_bucket_id)
        self.assertEqual(query['series'], state.selected_series_name)
        self.assertEqual(query['text'], state.list_filters.text)

    def test_shouldKeepChartQuerySeparateFromEvidenceSelectionAndFilters(self):
        # Given
        state = WorkbenchPageQueryState.from_query(QueryDict(
            'profile_id=nvu-ttl-hsdes&range_mode=ww&begin=26WW32&end=26WW35'
            '&chart_id=open_bug_trend&run=run-1&bucket=bucket-1&series=new_critical_high&text=display'
        ))

        # When
        chart_query = state.chart_query_params()
        evidence_query = state.evidence_query_params()

        # Then
        self.assertEqual('open_bug_trend', chart_query['chart_id'])
        self.assertNotIn('bucket', chart_query)
        self.assertNotIn('series', chart_query)
        self.assertNotIn('text', chart_query)
        self.assertEqual('bucket-1', evidence_query['bucket'])
        self.assertEqual('new_critical_high', evidence_query['series'])
        self.assertEqual('display', evidence_query['text'])

    def test_shouldClearSelectionWithoutChangingProfileRangeChartOrListFilters(self):
        # Given
        state = WorkbenchPageQueryState.from_query(QueryDict(
            'profile_id=nvu-ttl-hsdes&range_mode=ww&begin=26WW32&end=26WW35'
            '&chart_id=open_bug_trend&run=run-1&bucket=bucket-1&series=new_critical_high&status=open'
        ))

        # When
        cleared = state.cleared_selection()

        # Then
        self.assertEqual(state.profile_id, cleared.profile_id)
        self.assertEqual(state.scope_id, cleared.scope_id)
        self.assertEqual(state.range_mode, cleared.range_mode)
        self.assertEqual(state.chart_id, cleared.chart_id)
        self.assertEqual(state.calculation_run_id, cleared.calculation_run_id)
        self.assertEqual(state.list_filters.status, cleared.list_filters.status)
        self.assertEqual('', cleared.selected_bucket_id)
        self.assertEqual('', cleared.selected_series_name)

    def test_shouldRejectIncompleteEvidenceSelection(self):
        # Given
        state = WorkbenchPageQueryState.from_query(QueryDict(
            'profile_id=nvu-ttl-hsdes&chart_id=open_bug_trend&run=run-1&bucket=bucket-1'
        ))

        # When # Then
        self.assertEqual(
            'Chart evidence selection requires both bucket and series.',
            state.selection_validation_error(),
        )

    def test_shouldRejectEvidenceSelectionWithoutRunOrSnapshot(self):
        # Given
        state = WorkbenchPageQueryState.from_query(QueryDict(
            'profile_id=nvu-ttl-hsdes&chart_id=open_bug_trend&bucket=bucket-1&series=new_critical_high'
        ))

        # When # Then
        self.assertEqual(
            'Chart evidence selection requires a calculation run or fact snapshot.',
            state.selection_validation_error(),
        )

    def test_shouldRejectNonNumericChartVersion(self):
        # Given
        state = WorkbenchPageQueryState.from_query(QueryDict(
            'profile_id=nvu-ttl-hsdes&chart_id=open_bug_trend&chart_version=latest'
        ))

        # When # Then
        self.assertEqual('chart_version must be an integer.', state.selection_validation_error())

    def test_shouldBuildCompactGrafanaPanelUrlSeparateFromFullDashboardUrl(self):
        # Given
        state = WorkbenchPageQueryState.from_query(QueryDict(
            'scope_id=7&begin=2026-08-03&end=2026-08-09&chart_id=default_bug_trend'
        ))

        # When
        panel_url = grafana_panel_embed_url(state)
        dashboard_url = grafana_full_dashboard_url(state)

        # Then
        self.assertIn('/d-solo/metrics-bug-trend-c-stock/', panel_url)
        self.assertIn('panelId=1', panel_url)
        self.assertIn('var-scope_id=7', panel_url)
        self.assertIn('var-begin=2026-08-03', panel_url)
        self.assertIn('/d/metrics-bug-trend-c-stock/', dashboard_url)
        self.assertNotIn('/d-solo/', dashboard_url)
