from datetime import date, datetime, timezone

from django.test import TestCase

from bug_metrics.app.api import (
    DashboardCompositionIntent,
    GcxPublicationPreconditionRequest,
    ProviderActionPlanRequest,
    ProviderAiChartDraftRequest,
    ProviderAiChartExplanationRequest,
    ProviderAiDashboardContextQuery,
    bug_trend_api,
)
from bug_metrics.models import BugTrendAuditEvent, JiraScopeConfig
from jira_history.models import JiraIssue
from provider_sync.app.api import ProviderFreshnessStatus, ProviderSyncCacheService


class TestProviderAiDashboardContext(TestCase):
    def test_shouldExposeAiReadableApprovedChartDefinitionsWithProviderProvenance(self):
        # Given
        self._create_jira_scope()

        # When
        context = bug_trend_api.get_ai_dashboard_context(
            ProviderAiDashboardContextQuery(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                begin_ww='26WW32',
                end_ww='26WW32',
                chart_ids=['open_bug_trend', 'daily_new_standard_bug_count'],
            )
        )

        # Then
        self.assertEqual('0.1', context['contract_version'])
        self.assertEqual('jira', context['query_state']['provider_id'])
        charts_by_id = {chart['chart_id']: chart for chart in context['charts']}
        open_bug_trend = charts_by_id['open_bug_trend']
        self.assertEqual('bucket_series', open_bug_trend['evidence_capability'])
        self.assertEqual(
            ['all_open_bugs', 'all_open_critical_high', 'new_critical_high', 'new_medium_low', 'fixed_or_closed_bugs'],
            open_bug_trend['series'],
        )
        self.assertEqual('metrics', open_bug_trend['semantic_owner'])
        self.assertEqual('summary_only', open_bug_trend['effective_evidence_capability'])
        self.assertEqual('metrics_managed_native_query', open_bug_trend['provider_provenance']['ownership_type'])
        self.assertEqual('project = "131600" AND component = "team_int_qemu"', open_bug_trend['provider_provenance']['native_query_text'])
        self.assertEqual('range_only', charts_by_id['daily_new_standard_bug_count']['evidence_capability'])
        self.assertEqual('summary_only', charts_by_id['daily_new_standard_bug_count']['effective_evidence_capability'])

    def test_shouldExposeHsdesSeedPreviewContextWithoutDroppingSavedQueryProvenance(self):
        # When
        context = bug_trend_api.get_ai_dashboard_context(
            ProviderAiDashboardContextQuery(
                provider_id='hsdes',
                profile_id='nvu-ttl-hsdes',
                begin_ww='25WW15',
                end_ww='26WW32',
                chart_ids=['open_bug_trend', 'execution_statistics'],
            )
        )

        # Then
        charts_by_id = {chart['chart_id']: chart for chart in context['charts']}
        self.assertEqual('supported', charts_by_id['open_bug_trend']['provider_support_status'])
        self.assertEqual('bucket_series', charts_by_id['open_bug_trend']['evidence_capability'])
        self.assertEqual('bucket_series', charts_by_id['open_bug_trend']['effective_evidence_capability'])
        self.assertEqual('provider_owned_saved_query', charts_by_id['open_bug_trend']['provider_provenance']['ownership_type'])
        self.assertEqual('15017652869', charts_by_id['open_bug_trend']['provider_provenance']['source_query_ref'])
        self.assertEqual('ip_fw_sw_sensing.tenant', charts_by_id['open_bug_trend']['provider_provenance']['tenant_or_site'])
        self.assertEqual('ip_fw_sw_sensing.bug', charts_by_id['open_bug_trend']['provider_provenance']['subject_or_issue_type'])
        self.assertEqual('deferred', charts_by_id['execution_statistics']['provider_support_status'])
        self.assertTrue(charts_by_id['execution_statistics']['deferred_reason'])

    def test_shouldExposeLiveHsdesSnapshotProvenanceInAiContext(self):
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
            grafana_rows=[],
            source_population=snapshot.source_query_json,
            run_metadata={'freshness_status': ProviderFreshnessStatus.LIVE_SYNCED},
        )

        # When
        context = bug_trend_api.get_ai_dashboard_context(
            ProviderAiDashboardContextQuery(
                provider_id='hsdes',
                profile_id='nvu-ttl-hsdes',
                begin_ww='26WW32',
                end_ww='26WW32',
                chart_ids=['component_bug'],
            )
        )

        # Then
        self.assertEqual('live_synced', context['provider_facts_context']['freshness_status'])
        self.assertEqual(str(snapshot.id), context['provider_facts_context']['latest_snapshot_id'])
        self.assertEqual('live_synced', context['charts'][0]['run_metadata']['freshness_status'])

    def test_shouldExplainSupportedQualityChartFromFactsAndAggregateCitations(self):
        # Given
        scope = self._create_jira_scope()
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
        bug_trend_api.recalculate_scope(scope.id, date(2026, 8, 3), date(2026, 8, 9))

        # When
        explanation = bug_trend_api.explain_ai_dashboard_chart(
            ProviderAiChartExplanationRequest(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                begin_ww='26WW32',
                end_ww='26WW32',
                chart_id='open_bug_trend',
            )
        )

        # Then
        citation_types = {citation['source_type'] for citation in explanation['citations']}
        self.assertEqual('supported', explanation['status'])
        self.assertTrue({'chart_definition', 'chart_data', 'provider_facts', 'aggregate_artifact'}.issubset(citation_types))
        self.assertNotIn('prompt_memory', citation_types)

    def test_shouldExplainDeferredChartFromDeferredReasonCitation(self):
        # When
        explanation = bug_trend_api.explain_ai_dashboard_chart(
            ProviderAiChartExplanationRequest(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                begin_ww='26WW32',
                end_ww='26WW32',
                chart_id='automation_statistics',
            )
        )

        # Then
        self.assertEqual('deferred', explanation['status'])
        self.assertIn('Automation semantics require coverage field mappings', explanation['answer'])
        self.assertEqual(['chart_definition', 'deferred_reason', 'provider_facts'], [citation['source_type'] for citation in explanation['citations']])

    def test_shouldCreateProviderNeutralAiChartDraftAndRejectNativeQueryDraft(self):
        # When
        draft = bug_trend_api.create_ai_provider_chart_draft(
            ProviderAiChartDraftRequest(
                chart_id='open_bug_trend',
                title='Open Bug Trend Focus',
                provider_neutral_intent='Compare open bug risk over WW buckets.',
                series=['all_open_bugs', 'new_critical_high'],
                data_surface='/api/provider-charts/data/',
                evidence_capability='bucket_series',
                visualization='timeseries',
            )
        )

        # Then
        self.assertEqual('draft_validated', draft['status'])
        self.assertEqual('metrics', draft['semantic_owner'])
        self.assertEqual('/api/provider-charts/data/', draft['data_surface'])

        with self.assertRaises(ValueError):
            bug_trend_api.create_ai_provider_chart_draft(
                ProviderAiChartDraftRequest(
                    chart_id='open_bug_trend',
                    title='Unsafe Native Draft',
                    provider_neutral_intent='Use JQL project = "131600" to query Jira directly.',
                    series=['all_open_bugs'],
                    data_surface='/api/provider-charts/data/',
                    evidence_capability='bucket_series',
                    visualization='timeseries',
                )
            )

    def test_shouldExposeFlexibleAiEntryPlacementsOnSameBackendContracts(self):
        # When
        placements = bug_trend_api.list_ai_entry_placements()

        # Then
        placements_by_id = {placement['placement_id']: placement for placement in placements}
        self.assertEqual({'grafana_app_scenes', 'metrics_ui_sidebar', 'separate_ai_dashboard'}, set(placements_by_id.keys()))
        backend_contract_sets = {tuple(placement['backend_contracts']) for placement in placements}
        self.assertEqual(1, len(backend_contract_sets))
        self.assertIn('ai_dashboard_context', next(iter(backend_contract_sets)))

    def test_shouldCreateJiraProviderActionPlanWithoutDirectWrite(self):
        # When
        plan = bug_trend_api.create_provider_action_plan(
            ProviderActionPlanRequest(
                provider_id='jira',
                profile_id='chiplet-2a-jira',
                source_item_id='STDEL-1001',
                action_type='update_fields',
                proposed_changes={'priority': 'P2-High'},
                reason='Open bug trend shows rising critical risk.',
                actor='local_operator',
            )
        )

        # Then
        self.assertEqual('approval_required', plan['approval_state'])
        self.assertFalse(plan['direct_write_performed'])
        self.assertEqual('jira', plan['provider_id'])
        self.assertEqual([{'field': 'priority', 'before': '', 'after': 'P2-High'}], plan['before_after_preview'])
        event = BugTrendAuditEvent.objects.get(event_type='provider_action_plan_proposed')
        self.assertEqual('local_operator', event.actor)
        self.assertEqual('STDEL-1001', event.request_summary['source_item_id'])

    def test_shouldCreateNonExecutableHsdesActionSuggestionWithoutDirectWrite(self):
        # When
        plan = bug_trend_api.create_provider_action_plan(
            ProviderActionPlanRequest(
                provider_id='hsdes',
                profile_id='nvu-ttl-hsdes',
                source_item_id='16000000001',
                action_type='update_fields',
                proposed_changes={'priority': 'high'},
                reason='Open bug trend needs owner triage.',
                actor='local_operator',
            )
        )

        # Then
        self.assertEqual('unsupported', plan['approval_state'])
        self.assertEqual('disabled', plan['execution_mode'])
        self.assertFalse(plan['direct_write_performed'])
        self.assertEqual('hsdes', plan['provider_id'])
        self.assertIn('HSD-ES writes remain disabled', plan['unsupported_reason'])
        event = BugTrendAuditEvent.objects.get(event_type='provider_action_plan_unsupported')
        self.assertEqual('16000000001', event.request_summary['source_item_id'])

    def test_shouldExposeAiCompositionCatalogWithoutProviderCredentialsOrNativeQueries(self):
        # When
        catalog = bug_trend_api.list_ai_dashboard_composition_catalog('nvu-ttl-hsdes')

        # Then
        self.assertEqual('0.2', catalog['contract_version'])
        self.assertEqual('profile_catalog', catalog['catalog_type'])
        self.assertEqual({'ww', 'date'}, set(catalog['range_modes']))
        self.assertEqual({'max_rows', 'max_days'}, set(catalog['limits']))
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
        self.assertEqual(['all_open_bugs', 'all_open_critical_high', 'new_critical_high', 'new_medium_low', 'fixed_or_closed_bugs'], open_bug_recipe['allowed_series'])
        self.assertEqual('supported', open_bug_recipe['support_status'])

    def test_shouldReturnNeedsMetricRecipeWhenCompositionIntentRequestsUnapprovedSeries(self):
        # When
        validation = bug_trend_api.validate_ai_dashboard_composition_intent(
            DashboardCompositionIntent(
                profile_id='nvu-ttl-hsdes',
                dashboard_uid='ip-quality-dashboard',
                chart_id='open_bug_trend',
                requested_series=['new_critical'],
                range_mode='ww',
                range_start='26WW10',
                range_end='26WW35',
                output_type='render_config_draft',
                actor='ai_sidecar',
            )
        )

        # Then
        self.assertEqual('needs_metric_recipe', validation['status'])
        self.assertFalse(validation['valid'])
        self.assertEqual(['new_critical'], validation['needs_metric_recipe']['requested_series'])
        self.assertIn('new_critical_high', validation['needs_metric_recipe']['available_series'])
        self.assertEqual('unapproved_series', validation['findings'][0]['code'])
        self.assertNotIn('draft_render_config', validation)

    def test_shouldValidateVisibilityOnlyCompositionIntentForApprovedSeries(self):
        # When
        validation = bug_trend_api.validate_ai_dashboard_composition_intent(
            DashboardCompositionIntent(
                profile_id='nvu-ttl-hsdes',
                dashboard_uid='ip-quality-dashboard',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW10',
                range_end='26WW35',
                output_type='render_config_draft',
                actor='ai_sidecar',
            )
        )

        # Then
        self.assertTrue(validation['valid'])
        self.assertEqual('draft_validated', validation['status'])
        draft_panel = validation['draft_render_config']['sections'][0]['panels'][0]
        self.assertEqual({'chart_id': 'open_bug_trend', 'chart_version': 1}, draft_panel['chart_recipe_ref'])
        self.assertEqual(['new_critical_high'], draft_panel['value_fields'])
        self.assertEqual('approval_required', validation['publication_audit']['approval_state'])

    def test_shouldBlockGcxPublicationPreconditionWhenDraftRenderConfigIsInvalid(self):
        # When
        precondition = bug_trend_api.validate_ai_gcx_publication_precondition(
            GcxPublicationPreconditionRequest(
                operation='grafana_import',
                actor='ai_sidecar',
                draft_render_config={
                    'dashboard_uid': 'ip-quality-dashboard',
                    'title': 'IP Quality Dashboard',
                    'profile_variable': 'profile_id',
                    'variables': [],
                    'range_controls': {'modes': ['ww']},
                    'sections': [{
                        'id': 'quality',
                        'title': 'Quality',
                        'panels': [{
                            'panel_id': 'invalid_new_critical',
                            'title': 'Invalid New Critical',
                            'type': 'timeseries',
                            'layout': {'x': 0, 'y': 0, 'w': 12, 'h': 8},
                            'chart_recipe_ref': {'chart_id': 'open_bug_trend', 'chart_version': 1},
                            'provider_binding': 'selected_provider_quality',
                            'render_root': 'grafana_rows',
                            'render_shape': 'wide_bucket_series',
                            'category_field': 'bucket_label',
                            'value_fields': ['new_critical'],
                            'evidence_capability': 'bucket_series',
                        }],
                    }],
                },
            )
        )

        # Then
        self.assertFalse(precondition['mutation_allowed'])
        self.assertEqual('blocked', precondition['status'])
        self.assertEqual('metrics_precondition_failed', precondition['publication_audit']['validation_status'])
        self.assertTrue(any(finding['code'] == 'render_config_validation_failed' for finding in precondition['findings']))
        self.assertFalse(BugTrendAuditEvent.objects.filter(event_type='ai_gcx_publication_precondition_passed').exists())

    def test_shouldAllowGcxPublicationPreconditionForValidatedDraftAndRecordAudit(self):
        # Given
        validation = bug_trend_api.validate_ai_dashboard_composition_intent(
            DashboardCompositionIntent(
                profile_id='nvu-ttl-hsdes',
                dashboard_uid='ip-quality-dashboard',
                chart_id='open_bug_trend',
                requested_series=['new_critical_high'],
                range_mode='ww',
                range_start='26WW10',
                range_end='26WW35',
                output_type='render_config_draft',
                actor='ai_sidecar',
            )
        )

        # When
        precondition = bug_trend_api.validate_ai_gcx_publication_precondition(
            GcxPublicationPreconditionRequest(
                operation='grafana_import',
                actor='ai_sidecar',
                draft_render_config=validation['draft_render_config'],
            )
        )

        # Then
        self.assertTrue(precondition['mutation_allowed'])
        self.assertEqual('precondition_passed', precondition['status'])
        self.assertEqual('validated', precondition['publication_audit']['validation_status'])
        self.assertEqual('approval_required', precondition['publication_audit']['approval_state'])
        event = BugTrendAuditEvent.objects.get(event_type='ai_gcx_publication_precondition_passed')
        self.assertEqual('ai_sidecar', event.actor)
        self.assertEqual('grafana_import', event.request_summary['operation'])

    def _create_jira_scope(self):
        return JiraScopeConfig.objects.create(
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
