from django.test import TestCase

from bug_metrics.app.api import bug_trend_api
from bug_metrics.models import BugTrendChartDefinition, BugTrendEvidenceContract


class TestBugTrendChartCatalogApi(TestCase):
    def test_shouldExposeDefaultBugTrendAsMetricsOwnedBuiltInChart(self):
        # When
        charts = bug_trend_api.list_enabled_charts()

        # Then
        self.assertEqual(['default_bug_trend'], [chart.chart_id for chart in charts])
        chart = charts[0]
        self.assertEqual('Default Bug Trend', chart.title)
        self.assertEqual('chartjs', chart.renderer_type)
        self.assertEqual('reference', chart.integration_route)
        self.assertEqual('bucket_series', chart.evidence_contract.capability)
        self.assertEqual('bug_trend_bucket_issue', chart.evidence_contract.membership_source)
        self.assertIn('owner', chart.evidence_contract.allowed_list_filters)
        self.assertEqual('default_bug_trend_bucket_series', chart.chart_spec['evidence_contract_id'])
        self.assertIn('all_open_bugs', chart.chart_spec['series'])

    def test_shouldAcceptDefaultBugTrendChartForPublishValidation(self):
        # Given
        chart = BugTrendChartDefinition.objects.get(chart_id='default_bug_trend')

        # When
        result = bug_trend_api.validate_chart_for_publish(chart)

        # Then
        self.assertTrue(result.valid)
        self.assertEqual([], result.errors)

    def test_shouldRejectPublishedChartWithUnapprovedEvidenceMembershipSource(self):
        # Given
        contract = BugTrendEvidenceContract.objects.create(
            contract_id='unsafe_contract',
            capability=BugTrendEvidenceContract.CAPABILITY_BUCKET_SERIES,
            membership_source='raw_jira_issue',
            membership_key='issue_key',
            bucket_dimension='bucket_id',
            series_dimension='series_name',
            ticket_identity='jira_issue_key',
            dedupe_policy='unsafe',
            time_boundary_policy='unsafe',
            allowed_list_filters=['owner'],
            export_policy='unsafe',
        )
        chart = BugTrendChartDefinition.objects.create(
            chart_id='unsafe_chart',
            title='Unsafe Chart',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
            status=BugTrendChartDefinition.STATUS_DRAFT,
            chart_spec={'evidence_contract_id': 'unsafe_contract', 'series': ['all_open_bugs']},
        )

        # When
        result = bug_trend_api.validate_chart_for_publish(chart)

        # Then
        self.assertFalse(result.valid)
        self.assertIn('Evidence contract must use an approved Metrics-owned membership source.', result.errors)

    def test_shouldRejectPublishedChartWhenSpecEvidenceContractConflictsWithCatalogContract(self):
        # Given
        contract = BugTrendEvidenceContract.objects.get(contract_id='default_bug_trend_bucket_series')
        chart = BugTrendChartDefinition.objects.create(
            chart_id='conflicting_spec_chart',
            title='Conflicting Spec Chart',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
            chart_spec={'evidence_contract_id': 'different_contract', 'series': ['all_open_bugs']},
        )

        # When
        result = bug_trend_api.validate_chart_for_publish(chart)

        # Then
        self.assertFalse(result.valid)
        self.assertIn('Chart spec evidence contract must match the catalog evidence contract.', result.errors)

    def test_shouldRejectPublishedChartWhenSpecContainsDirectDataSourceLogic(self):
        # Given
        contract = BugTrendEvidenceContract.objects.get(contract_id='default_bug_trend_bucket_series')
        chart = BugTrendChartDefinition.objects.create(
            chart_id='direct_source_spec_chart',
            title='Direct Source Spec Chart',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
            chart_spec={'evidence_contract_id': 'default_bug_trend_bucket_series', 'query': 'select * from jira_issue'},
        )

        # When
        result = bug_trend_api.validate_chart_for_publish(chart)

        # Then
        self.assertFalse(result.valid)
        self.assertIn('Chart specs must not include SQL, secrets, or direct data-source logic.', result.errors)

    def test_shouldRejectBucketSeriesPublishedChartWhenSpecOmitsSeries(self):
        # Given
        contract = BugTrendEvidenceContract.objects.get(contract_id='default_bug_trend_bucket_series')
        chart = BugTrendChartDefinition.objects.create(
            chart_id='empty_series_spec_chart',
            title='Empty Series Spec Chart',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
            chart_spec={'evidence_contract_id': 'default_bug_trend_bucket_series'},
        )

        # When
        result = bug_trend_api.validate_chart_for_publish(chart)

        # Then
        self.assertFalse(result.valid)
        self.assertIn('Chart specs with ticket evidence must declare at least one series.', result.errors)

    def test_shouldRequireUnsupportedReasonForSummaryOnlyChart(self):
        # Given
        contract = BugTrendEvidenceContract.objects.create(
            contract_id='summary_contract',
            capability=BugTrendEvidenceContract.CAPABILITY_SUMMARY_ONLY,
            membership_source='',
            membership_key='',
            ticket_identity='none',
            dedupe_policy='none',
            time_boundary_policy='none',
            export_policy='none',
        )
        chart = BugTrendChartDefinition.objects.create(
            chart_id='summary_chart',
            title='Summary Chart',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
        )

        # When
        result = bug_trend_api.validate_chart_for_publish(chart)

        # Then
        self.assertFalse(result.valid)
        self.assertIn('Summary-only charts must explain why ticket evidence is unsupported.', result.errors)

    def test_shouldRecordCStockRendererDecisionWithoutTriggeringP2CWhenLinkOutIsEnough(self):
        # When
        decision = bug_trend_api.record_renderer_route_decision(
            'default_bug_trend',
            same_page_evidence_required=False,
            c_stock_same_page_capable=False,
            supported_c_stock_capabilities=['chart_values', 'link_out_evidence'],
            decision_summary='C-stock is approved for link-out evidence only.',
        )
        latest = bug_trend_api.latest_renderer_route_decision('default_bug_trend')

        # Then
        self.assertEqual('default_bug_trend', decision.chart_id)
        self.assertEqual('c_stock', decision.renderer_route)
        self.assertFalse(decision.trigger_p2c_spike)
        self.assertEqual(['chart_values', 'link_out_evidence'], latest.supported_c_stock_capabilities)

    def test_shouldTriggerP2CSpikeWhenSamePageEvidenceIsRequiredButCStockCannotProvideIt(self):
        # When
        decision = bug_trend_api.record_renderer_route_decision(
            'default_bug_trend',
            same_page_evidence_required=True,
            c_stock_same_page_capable=False,
            supported_c_stock_capabilities=['chart_values', 'link_out_evidence'],
            decision_summary='Same-page evidence requires plugin spike.',
        )

        # Then
        self.assertTrue(decision.trigger_p2c_spike)

    def test_shouldRecordActualRendererRouteDecision(self):
        # When
        decision = bug_trend_api.record_renderer_route_decision(
            'default_bug_trend',
            same_page_evidence_required=True,
            c_stock_same_page_capable=False,
            supported_c_stock_capabilities=['chart_values'],
            decision_summary='Plugin route required for same-page evidence.',
            renderer_route=BugTrendChartDefinition.ROUTE_C_PLUGIN,
        )

        # Then
        self.assertEqual(BugTrendChartDefinition.ROUTE_C_PLUGIN, decision.renderer_route)
        self.assertTrue(decision.trigger_p2c_spike)

    def test_shouldRejectUnknownRendererRouteDecision(self):
        # When / Then
        with self.assertRaises(ValueError):
            bug_trend_api.record_renderer_route_decision(
                'default_bug_trend',
                same_page_evidence_required=False,
                c_stock_same_page_capable=False,
                supported_c_stock_capabilities=[],
                decision_summary='Invalid route.',
                renderer_route='side_channel',
            )