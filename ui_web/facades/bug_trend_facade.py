import json
from datetime import date

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters
from bug_metrics.app.api.scope_config import SEMANTIC_LIST_FIELDS, SavedScopeConfig, saved_scope_config_from_dict

from ..data.bug_trend_data import BugTrendChartData, BugTrendChartOption, BugTrendEvidenceData, BugTrendScopeAuditData, BugTrendScopeOption


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
            run_metadata=self._run_metadata_payload(chart.run_metadata),
            current_evidence_available=chart.current_evidence_available,
        )

    def get_chart_json(self, chart_data: BugTrendChartData) -> str:
        return json.dumps(self.get_chart_payload(chart_data))

    def get_chart_payload(self, chart_data: BugTrendChartData) -> dict:
        points = []
        for dataset in chart_data.datasets:
            for index, value in enumerate(dataset['values']):
                points.append({
                    'calculation_run_id': chart_data.calculation_run_id,
                    'bucket_id': chart_data.bucket_ids[index],
                    'series_name': dataset['series_name'],
                    'label': chart_data.labels[index],
                    'value': value,
                    'type': dataset['type'],
                    'color': dataset['color'],
                })
        return {
            'scope_id': chart_data.scope_id,
            'chart_id': chart_data.chart_id,
            'calculation_run_id': chart_data.calculation_run_id,
            'labels': chart_data.labels,
            'bucket_ids': chart_data.bucket_ids,
            'datasets': chart_data.datasets,
            'points': points,
            'unavailable_reason': chart_data.unavailable_reason,
            'run_metadata': chart_data.run_metadata or {},
            'current_evidence_available': chart_data.current_evidence_available,
        }

    def _run_metadata_payload(self, run_metadata) -> dict:
        if not run_metadata:
            return {}
        return {
            'calculation_run_id': run_metadata.calculation_run_id,
            'run_config_version_hash': run_metadata.run_config_version_hash,
            'current_config_version_hash': run_metadata.current_config_version_hash,
            'freshness_status': run_metadata.freshness_status,
            'source_coverage_start': run_metadata.source_coverage_start,
            'source_coverage_end': run_metadata.source_coverage_end,
            'completed_at': run_metadata.completed_at,
        }

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

    def _scope_label(self, scope):
        parts = [part for part in [scope.ip, scope.project_label, scope.name] if part]
        return ' / '.join(parts) if parts else scope.name

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

    def get_scope_config(self, scope_id: int, add_field: str = '', add_value: str = '') -> SavedScopeConfig:
        config = self._bug_trend_api.get_scope_config(scope_id)
        if add_field in SEMANTIC_LIST_FIELDS and add_value:
            values = list(getattr(config, add_field))
            if add_value not in values:
                values.append(add_value)
                setattr(config, add_field, values)
        return config

    def save_scope_config(self, post_data) -> tuple[SavedScopeConfig, bool]:
        config = self.scope_config_from_post(post_data)
        if config.id is None:
            raise ValueError({'id': 'Scope id is required.'})
        original_hash = self._bug_trend_api.get_scope_config(config.id).config_version_hash
        saved = self._bug_trend_api.save_scope_config(config)
        return saved, saved.config_version_hash != original_hash

    def scope_config_from_post(self, post_data) -> SavedScopeConfig:
        payload = {field_name: post_data.get(field_name, '') for field_name in [
            'id', 'name', 'ip', 'project_label', 'jql', 'severity_field', 'component_field',
            'owner_field', 'team_field', 'milestone_field', 'fix_version_field',
            'package_version_field', 'timezone', 'bucket_granularity',
        ]}
        try:
            payload['id'] = int(payload['id']) if payload['id'] else None
        except ValueError:
            payload['id'] = None
        payload['enabled'] = post_data.get('enabled') == 'on'
        for field_name in SEMANTIC_LIST_FIELDS:
            payload[field_name] = self._parse_list_field(post_data.get(field_name, ''))
        return saved_scope_config_from_dict(payload)

    def _parse_list_field(self, value: str) -> list[str]:
        normalized = value.replace('\r\n', '\n').replace(',', '\n')
        return [item.strip() for item in normalized.split('\n') if item.strip()]