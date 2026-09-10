from datetime import date, datetime, timezone

from bug_metrics.models import (
    BugTrendBucket,
    BugTrendCalculationRun,
    BugTrendChartDefinition,
    BugTrendEvidenceContract,
    BugTrendScopeProviderBinding,
    JiraScopeConfig,
)


class WorkbenchViewTestSupport:
    def _seed_trend_data(self, bind_profile=True):
        scope = JiraScopeConfig.objects.create(
            name='Workbench trend',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        run = BugTrendCalculationRun.objects.create(
            scope=scope,
            status=BugTrendCalculationRun.STATUS_COMPLETED,
            completed_at=datetime(2026, 8, 19, tzinfo=timezone.utc),
            config_version_hash=scope.config_version_hash,
            source_coverage_start=date(2026, 8, 3),
            source_coverage_end=date(2026, 8, 9),
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        bucket = BugTrendBucket.objects.create(
            calculation_run=run,
            scope=scope,
            bucket_start=date(2026, 8, 3),
            bucket_end=date(2026, 8, 9),
            granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
            new_critical_high_count=1,
            open_count=1,
        )
        if bind_profile:
            BugTrendScopeProviderBinding.objects.create(
                scope=scope,
                profile_id='chiplet-2a-jira',
                provider_id='jira',
                status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
            )
        return scope, run, bucket

    def _bound_scope(self, profile_id, provider_id):
        scope = JiraScopeConfig.objects.create(
            name=f'{profile_id} workbench scope',
            jql='project = STDEL AND issuetype = Bug',
            bug_type_values=['Bug'],
            fixed_status_values=['Fixed'],
            closed_status_values=['Closed'],
            severity_field='priority',
            critical_high_values=['P1-Critical'],
            medium_low_values=['P3-Medium'],
            bucket_granularity=JiraScopeConfig.GRANULARITY_WEEKLY,
        )
        BugTrendScopeProviderBinding.objects.create(
            scope=scope,
            profile_id=profile_id,
            provider_id=provider_id,
            status=BugTrendScopeProviderBinding.STATUS_EXPLICIT,
        )
        return scope

    def _publish_summary_only_chart(self):
        contract = BugTrendEvidenceContract.objects.create(
            contract_id='workbench_summary_only_contract',
            capability=BugTrendEvidenceContract.CAPABILITY_SUMMARY_ONLY,
            membership_source='',
            membership_key='',
            ticket_identity='none',
            dedupe_policy='none',
            time_boundary_policy='none',
            export_policy='none',
            unsupported_reason='Summary-only chart has no ticket evidence.',
        )
        BugTrendChartDefinition.objects.create(
            chart_id='summary_only_chart',
            title='Summary Only',
            renderer_type=BugTrendChartDefinition.RENDERER_CHARTJS,
            integration_route=BugTrendChartDefinition.ROUTE_REFERENCE,
            evidence_contract=contract,
            status=BugTrendChartDefinition.STATUS_PUBLISHED,
            enabled=True,
        )
