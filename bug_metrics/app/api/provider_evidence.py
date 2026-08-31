from .page_query import BugTrendPageQueryState, BugTrendTicketListFilters
from .provider_aggregate_contracts import (
    DEFERRED_CHART_REASONS,
    PROVIDER_CHART_CONTRACT_VERSION,
    PROVIDER_CHART_EVIDENCE_CAPABILITIES,
    ProviderChartEvidenceQuery,
    evidence_capability_for_result,
    provider_series_to_evidence_series,
)
from .provider_aggregates import provider_query_range_to_dates


class ProviderChartEvidenceService:
    def __init__(self, aggregate_service, get_evidence_tickets):
        self._aggregate_service = aggregate_service
        self._get_evidence_tickets = get_evidence_tickets

    def get_provider_chart_evidence(self, query: ProviderChartEvidenceQuery) -> dict:
        capability = evidence_capability_for_result(query.chart_id, self._provider_evidence_status(query))
        if capability != 'bucket_series':
            return self._provider_evidence_state(query, capability)
        if query.provider_id != 'jira':
            return self._provider_evidence_state(query, 'summary_only')

        scope = self._aggregate_service.jira_scope_for_profile(query.profile_id)
        if scope is None:
            return self._provider_evidence_state(query, 'summary_only', 'unavailable', 'No enabled Jira scope is mapped to the requested provider profile.')

        begin, end = provider_query_range_to_dates(query)
        evidence_series_name = provider_series_to_evidence_series(query.provider_id, query.chart_id, query.selected_series_name)
        result = self._get_evidence_tickets(
            BugTrendPageQueryState(
                scope_id=scope.id,
                begin=begin,
                end=end,
                calculation_run_id=query.calculation_run_id,
                selected_bucket_id=query.selected_bucket_id,
                selected_series_name=evidence_series_name,
                list_filters=BugTrendTicketListFilters(
                    owner=query.owner,
                    status=query.status,
                    severity=query.severity,
                    component=query.component,
                    text=query.text,
                ),
                active_chart_id='default_bug_trend',
            )
        )
        return self._ticket_evidence_payload(query, capability, begin, end, scope, result, evidence_series_name)

    def _ticket_evidence_payload(self, query, capability, begin, end, scope, result, evidence_series_name) -> dict:
        return {
            'contract_version': PROVIDER_CHART_CONTRACT_VERSION,
            'provider_id': query.provider_id,
            'profile_id': query.profile_id,
            'chart_id': query.chart_id,
            'chart_version': query.chart_version,
            'evidence_capability': capability,
            'status': 'supported',
            'reason': '',
            'begin_ww': query.begin_ww,
            'end_ww': query.end_ww,
            'range_mode': query.range_mode,
            'begin_date': begin.isoformat(),
            'end_date': end.isoformat(),
            'source_scope_ref': f'jira_scope:{scope.id}',
            'calculation_run_id': query.calculation_run_id,
            'fact_snapshot_id': query.fact_snapshot_id,
            'bucket_id': query.selected_bucket_id,
            'provider_series_name': query.selected_series_name,
            'series_name': evidence_series_name,
            'selection_title': result.selection_title,
            'total_count': result.total_count,
            'shown_count': result.shown_count,
            'display_fields': result.display_fields,
            'rows': [self._ticket_row(row) for row in result.rows],
        }

    def _ticket_row(self, row) -> dict:
        return {
            'issue_key': row.issue_key,
            'source_url': row.source_url,
            'summary': row.summary,
            'series_name': row.series_name,
            'status': row.status,
            'severity': row.severity,
            'owner': row.owner,
            'component': row.component,
            'created_at': row.created_at,
            'updated_at': row.updated_at,
            'extra_fields': row.extra_fields,
            'extra_field_values': row.extra_field_values,
        }

    def _provider_evidence_status(self, query: ProviderChartEvidenceQuery) -> str:
        if query.provider_id == 'hsdes':
            return 'configuration_required'
        if query.provider_id != 'jira':
            return 'unsupported'
        if query.chart_id in DEFERRED_CHART_REASONS:
            return 'deferred'
        if query.chart_id not in PROVIDER_CHART_EVIDENCE_CAPABILITIES:
            return 'unsupported'
        return 'supported'

    def _provider_evidence_state(self, query: ProviderChartEvidenceQuery, capability: str, status: str = '', reason: str = '') -> dict:
        resolved_status = status or self._provider_evidence_status(query)
        resolved_reason = reason or self._provider_evidence_reason(query, capability, resolved_status)
        return {
            'contract_version': PROVIDER_CHART_CONTRACT_VERSION,
            'provider_id': query.provider_id,
            'profile_id': query.profile_id,
            'chart_id': query.chart_id,
            'chart_version': query.chart_version,
            'evidence_capability': capability,
            'status': resolved_status,
            'reason': resolved_reason,
            'begin_ww': query.begin_ww,
            'end_ww': query.end_ww,
            'range_mode': query.range_mode,
            'begin_date': query.begin_date,
            'end_date': query.end_date,
            'source_scope_ref': '',
            'calculation_run_id': query.calculation_run_id,
            'fact_snapshot_id': query.fact_snapshot_id,
            'bucket_id': query.selected_bucket_id,
            'provider_series_name': query.selected_series_name,
            'series_name': provider_series_to_evidence_series(query.provider_id, query.chart_id, query.selected_series_name),
            'selection_title': '',
            'total_count': 0,
            'shown_count': 0,
            'display_fields': [],
            'rows': [],
        }

    def _provider_evidence_reason(self, query: ProviderChartEvidenceQuery, capability: str, status: str) -> str:
        if query.provider_id == 'hsdes':
            return 'HSD-ES ticket-level evidence requires confirmed field bindings before drilldown can show rows.'
        if query.chart_id in DEFERRED_CHART_REASONS:
            return f'{DEFERRED_CHART_REASONS[query.chart_id]} This summary-only panel does not support ticket-level evidence.'
        if capability == 'range_only':
            return 'This panel supports range-level evidence only; bucket/series ticket-level drilldown is not enabled in this phase.'
        if status == 'unsupported':
            return f'Chart {query.chart_id} does not support ticket-level evidence.'
        return 'This summary-only panel does not support ticket-level evidence.'
