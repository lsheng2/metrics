import json
from datetime import date

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters

from ..data.bug_trend_data import BugTrendChartData, BugTrendChartOption, BugTrendEvidenceData, BugTrendScopeAuditData
from .bug_trend_ai_facade import BugTrendAiFacadeMixin
from .bug_trend_chart_payload import chart_payload, run_metadata_payload
from .bug_trend_provider_setup_facade import BugTrendProviderSetupFacadeMixin
from .bug_trend_scope_config_facade import BugTrendScopeConfigFacadeMixin
from .provider_dashboard_facade import ProviderDashboardFacade


class BugTrendFacade(BugTrendScopeConfigFacadeMixin, BugTrendProviderSetupFacadeMixin, BugTrendAiFacadeMixin):
    def __init__(self, bug_trend_api, scope_metadata_api=None):
        self._bug_trend_api = bug_trend_api
        self._scope_metadata_api = scope_metadata_api
        self._provider_dashboard_facade = ProviderDashboardFacade(bug_trend_api)

    def get_chart_options(self):
        return [
            BugTrendChartOption(
                chart_id=chart.chart_id,
                title=chart.title,
                capability=chart.evidence_contract.capability,
                unsupported_reason=chart.evidence_contract.unsupported_reason,
            )
            for chart in self._bug_trend_api.list_enabled_charts()
        ]

    def get_chart_data(self, scope_id: int, begin: date, end: date, chart_id: str = 'default_bug_trend') -> BugTrendChartData:
        chart = self._bug_trend_api.get_chart(scope_id, begin, end, chart_id)
        return BugTrendChartData(
            chart_id=chart_id,
            scope_id=chart.scope_id,
            contract_version=chart.contract_version,
            calculation_run_id=chart.calculation_run_id or '',
            labels=chart.labels,
            bucket_ids=chart.bucket_ids,
            datasets=[
                {
                    'series_name': dataset.series_name,
                    'type': dataset.chart_type,
                    'values': dataset.values,
                    'color': dataset.color,
                }
                for dataset in chart.datasets
            ],
            bucket_starts=chart.bucket_starts or [],
            bucket_ends=chart.bucket_ends or [],
            bucket_granularity=chart.bucket_granularity or '',
            unavailable_reason=chart.unavailable_reason,
            run_metadata=run_metadata_payload(chart.run_metadata),
            current_evidence_available=chart.current_evidence_available,
        )

    def get_chart_json(self, chart_data: BugTrendChartData) -> str:
        return json.dumps(self.get_chart_payload(chart_data))

    def get_chart_payload(self, chart_data: BugTrendChartData) -> dict:
        return chart_payload(chart_data)

    def get_evidence_data(self, scope_id: int, begin: date, end: date, bucket_id: str = '', series_name: str = '',
                          calculation_run_id: str = '', owner: str = '', status: str = '', severity: str = '',
                          component: str = '', text: str = '', active_chart_id: str = 'default_bug_trend') -> BugTrendEvidenceData:
        result = self._bug_trend_api.get_evidence_tickets(
            BugTrendPageQueryState(
                scope_id=scope_id,
                begin=begin,
                end=end,
                calculation_run_id=calculation_run_id,
                selected_bucket_id=bucket_id,
                selected_series_name=series_name,
                list_filters=BugTrendTicketListFilters(
                    owner=owner,
                    status=status,
                    severity=severity,
                    component=component,
                    text=text,
                ),
                active_chart_id=active_chart_id,
            )
        )
        return BugTrendEvidenceData(
            result.rows,
            result.total_count,
            result.shown_count,
            result.selection_title,
            result.display_fields,
            scope_id,
            calculation_run_id,
            begin.isoformat(),
            end.isoformat(),
            bool(bucket_id or series_name),
            bucket_id,
            series_name,
            owner,
            status,
            severity,
            component,
            text,
            active_chart_id,
        )

    def export_evidence_data(self, scope_id: int, begin: date, end: date, bucket_id: str = '', series_name: str = '',
                             calculation_run_id: str = '', owner: str = '', status: str = '', severity: str = '',
                             component: str = '', text: str = '', active_chart_id: str = 'default_bug_trend'):
        return self._bug_trend_api.export_evidence_tickets(
            BugTrendPageQueryState(
                scope_id=scope_id,
                begin=begin,
                end=end,
                calculation_run_id=calculation_run_id,
                selected_bucket_id=bucket_id,
                selected_series_name=series_name,
                list_filters=BugTrendTicketListFilters(
                    owner=owner,
                    status=status,
                    severity=severity,
                    component=component,
                    text=text,
                ),
                active_chart_id=active_chart_id,
            )
        )

    def get_evidence_payload(self, evidence: BugTrendEvidenceData) -> dict:
        return {
            'scope_id': evidence.scope_id,
            'calculation_run_id': evidence.calculation_run_id,
            'begin': evidence.begin,
            'end': evidence.end,
            'selection_title': evidence.selection_title,
            'total_count': evidence.total_count,
            'shown_count': evidence.shown_count,
            'display_fields': evidence.display_fields,
            'has_selection': evidence.has_selection,
            'rows': [
                {
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
                for row in evidence.rows
            ],
        }

    def get_scope_audit_data(self, scope_id: int) -> BugTrendScopeAuditData:
        audit = self._bug_trend_api.get_scope_audit(scope_id)
        return BugTrendScopeAuditData(
            scope_id=audit.scope_id,
            scope_name=audit.scope_name,
            config_version_hash=audit.config_version_hash,
            observed_values=audit.observed_values,
            coverage=audit.coverage,
        )
