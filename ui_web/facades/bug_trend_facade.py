import json
from datetime import date

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters

from ..data.bug_trend_data import BugTrendChartData, BugTrendEvidenceData, BugTrendScopeOption


class BugTrendFacade:
    def __init__(self, bug_trend_api):
        self._bug_trend_api = bug_trend_api

    def get_scope_options(self):
        return [
            BugTrendScopeOption(
                id=scope.id,
                name=scope.name,
                label=self._scope_label(scope),
            )
            for scope in self._bug_trend_api.list_enabled_scopes()
        ]

    def get_chart_data(self, scope_id: int, begin: date, end: date) -> BugTrendChartData:
        chart = self._bug_trend_api.get_chart(scope_id, begin, end)
        return BugTrendChartData(
            scope_id=chart.scope_id,
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
            unavailable_reason=chart.unavailable_reason,
        )

    def get_chart_json(self, chart_data: BugTrendChartData) -> str:
        return json.dumps({
            'scope_id': chart_data.scope_id,
            'calculation_run_id': chart_data.calculation_run_id,
            'labels': chart_data.labels,
            'bucket_ids': chart_data.bucket_ids,
            'datasets': chart_data.datasets,
            'unavailable_reason': chart_data.unavailable_reason,
        })

    def get_evidence_data(self, scope_id: int, begin: date, end: date, bucket_id: str = '', series_name: str = '',
                          calculation_run_id: str = '', owner: str = '', status: str = '', severity: str = '',
                          component: str = '', text: str = '') -> BugTrendEvidenceData:
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
        )

    def _scope_label(self, scope):
        parts = [part for part in [scope.ip, scope.project_label, scope.name] if part]
        return ' / '.join(parts) if parts else scope.name