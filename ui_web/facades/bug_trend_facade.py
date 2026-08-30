import json
from datetime import date

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters, ProviderChartAggregateQuery, ProviderChartEvidenceQuery
from bug_metrics.app.api.provider_aggregate_contracts import FIRST_HSDES_PROFILE_ID, FIRST_JIRA_PROFILE_ID, PROVIDER_CHART_CONTRACT_VERSION
from bug_metrics.app.api.scope_config import SEMANTIC_LIST_FIELDS, SavedScopeConfig, normalize_scope_list_values, saved_scope_config_from_dict
from bug_metrics.models import JiraScopeConfig

from ..data.bug_trend_data import BugTrendChartData, BugTrendChartOption, BugTrendEvidenceData, BugTrendScopeAuditData, BugTrendScopeOption


FIRST_HSDES_ACCESS_CHECK_URL = 'https://hsdes.intel.com/appstore/generalapps/#/pages/community/1607367026?queryId=15017652869'


class BugTrendFacade:
    def __init__(self, bug_trend_api, scope_metadata_api=None):
        self._bug_trend_api = bug_trend_api
        self._scope_metadata_api = scope_metadata_api

    def get_scope_options(self):
        return [
            BugTrendScopeOption(
                id=scope.id,
                name=scope.name,
                label=self._scope_label(scope),
            )
            for scope in self._bug_trend_api.list_enabled_scopes()
        ]

    def get_scope_library(self):
        return self._bug_trend_api.list_scope_configs()

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
                    'bucket_label': chart_data.labels[index],
                    'bucket_start': self._bucket_value(chart_data.bucket_starts, index),
                    'bucket_end': self._bucket_value(chart_data.bucket_ends, index),
                    'bucket_granularity': chart_data.bucket_granularity,
                    'series_name': dataset['series_name'],
                    'series_label': self._series_label(dataset['series_name']),
                    'label': chart_data.labels[index],
                    'value': value,
                    'type': dataset['type'],
                    'color': dataset['color'],
                })
        grafana_rows = self._grafana_rows(chart_data)
        return {
            'scope_id': chart_data.scope_id,
            'chart_id': chart_data.chart_id,
            'contract_version': chart_data.contract_version,
            'calculation_run_id': chart_data.calculation_run_id,
            'labels': chart_data.labels,
            'bucket_ids': chart_data.bucket_ids,
            'bucket_starts': chart_data.bucket_starts,
            'bucket_ends': chart_data.bucket_ends,
            'bucket_granularity': chart_data.bucket_granularity,
            'datasets': chart_data.datasets,
            'points': points,
            'grafana_rows': grafana_rows,
            'unavailable_reason': chart_data.unavailable_reason,
            'run_metadata': chart_data.run_metadata or {},
            'current_evidence_available': chart_data.current_evidence_available,
        }

    def get_provider_chart_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                   chart_id: str, chart_version: int = 1, fact_snapshot_id: str = '',
                                   range_mode: str = 'ww', begin_date: str = '', end_date: str = '') -> dict:
        resolved_provider_id = self._resolve_provider_id(provider_id, profile_id)
        result = self._bug_trend_api.get_provider_chart_aggregates(
            ProviderChartAggregateQuery(
                provider_id=resolved_provider_id,
                profile_id=profile_id,
                begin_ww=begin_ww,
                end_ww=end_ww,
                chart_id=chart_id,
                chart_version=chart_version,
                fact_snapshot_id=fact_snapshot_id,
                range_mode=range_mode,
                begin_date=begin_date,
                end_date=end_date,
            )
        )
        return result.to_dict()

    def get_provider_chart_evidence_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                            chart_id: str, calculation_run_id: str, bucket_id: str = '',
                                            series_name: str = '', chart_version: int = 1, fact_snapshot_id: str = '',
                                            owner: str = '', status: str = '', severity: str = '',
                                            component: str = '', text: str = '', range_mode: str = 'ww',
                                            begin_date: str = '', end_date: str = '') -> dict:
        resolved_provider_id = self._resolve_provider_id(provider_id, profile_id)
        return self._bug_trend_api.get_provider_chart_evidence(
            ProviderChartEvidenceQuery(
                provider_id=resolved_provider_id,
                profile_id=profile_id,
                begin_ww=begin_ww,
                end_ww=end_ww,
                chart_id=chart_id,
                chart_version=chart_version,
                calculation_run_id=calculation_run_id,
                selected_bucket_id=bucket_id,
                selected_series_name=series_name,
                fact_snapshot_id=fact_snapshot_id,
                owner=owner,
                status=status,
                severity=severity,
                component=component,
                text=text,
                range_mode=range_mode,
                begin_date=begin_date,
                end_date=end_date,
            )
        )

    def get_provider_profile_readiness_payload(self, provider_id: str, profile_id: str) -> dict:
        resolved_provider_id = self._resolve_provider_id(provider_id, profile_id)
        readiness = self._bug_trend_api.get_provider_profile_readiness(resolved_provider_id, profile_id)
        readiness['contract_version'] = PROVIDER_CHART_CONTRACT_VERSION
        readiness['provider_id'] = resolved_provider_id
        readiness['profile_status_rows'] = [self._profile_status_row(readiness)]
        return readiness

    def _resolve_provider_id(self, provider_id: str, profile_id: str) -> str:
        explicit_provider_id = provider_id or ''
        profile_provider_id = self._provider_id_for_profile(profile_id)
        if explicit_provider_id and profile_provider_id and explicit_provider_id != profile_provider_id:
            raise ValueError(f'Provider {explicit_provider_id} does not match selected profile {profile_id}.')
        if explicit_provider_id:
            return explicit_provider_id
        if profile_provider_id:
            return profile_provider_id
        raise ValueError(f'Provider could not be resolved for profile {profile_id}.')

    def _provider_id_for_profile(self, profile_id: str) -> str:
        if profile_id == FIRST_HSDES_PROFILE_ID:
            return 'hsdes'
        if profile_id == FIRST_JIRA_PROFILE_ID:
            return 'jira'
        if JiraScopeConfig.objects.filter(enabled=True, name=profile_id).exists():
            return 'jira'
        return ''

    def _profile_status_row(self, readiness: dict) -> dict:
        scope_labels = readiness.get('scope_labels', {})
        source_query = readiness.get('source_query', {})
        blockers = readiness.get('blockers', [])
        sync_cache = readiness.get('sync_cache', {})
        return {
            'provider_id': readiness.get('provider_id', ''),
            'profile_id': readiness.get('profile_id', ''),
            'status': readiness.get('status', ''),
            'data_status': self._profile_data_status(readiness),
            'data_status_reason': self._profile_data_status_reason(readiness),
            'ip': self._scope_label_value(scope_labels, 'ip'),
            'project_or_product': self._scope_label_value(scope_labels, 'project_or_product'),
            'milestone': self._scope_label_value(scope_labels, 'milestone'),
            'scope_label_source': self._scope_label_source(scope_labels),
            'source_query_ownership': source_query.get('ownership_type', ''),
            'source_query_ref': source_query.get('source_query_ref', ''),
            'source_query_name': source_query.get('source_query_name', ''),
            'mapping_version': readiness.get('mapping_version', ''),
            'override_state': 'profile_default',
            'save_profile_action': 'available_in_profile_editor',
            'auth_action_label': self._profile_auth_action_label(readiness),
            'auth_action_url': self._profile_auth_action_url(readiness),
            'blocker_count': len(blockers),
            'freshness_status': sync_cache.get('freshness_status', ''),
            'latest_snapshot_id': sync_cache.get('latest_snapshot_id', ''),
            'latest_successful_sync_at': sync_cache.get('latest_successful_sync_at', ''),
            'cache_age_seconds': sync_cache.get('cache_age_seconds', ''),
            'error_category': sync_cache.get('error_category', ''),
        }

    def _profile_data_status(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'seeded_preview':
            return 'seeded_preview'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'live_synced':
            return 'live_synced'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'failed':
            return 'failed'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'stale':
            return 'stale'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'blocked':
            return 'configuration_required'
        return readiness.get('status', '')

    def _profile_data_status_reason(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'seeded_preview':
            return 'HSD-ES seed facts can render supported preview charts; live HSD-ES sync still requires backend credential, saved-query permission, lookup and field-binding validation.'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'live_synced':
            return 'HSD-ES live sync has materialized provider facts and dashboard aggregate artifacts for this profile.'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'failed':
            return 'HSD-ES live sync failed; the dashboard keeps the latest successful local artifact when one exists.'
        if readiness.get('provider_id') == 'hsdes' and readiness.get('status') == 'stale':
            return 'HSD-ES live sync artifacts are available but older than the configured freshness window.'
        if readiness.get('provider_id') == 'hsdes':
            return 'HSD-ES quality facts require confirmed field bindings and runtime permission validation before aggregate generation.'
        blockers = readiness.get('blockers', [])
        if blockers:
            return blockers[0].get('message', '')
        return ''

    def _profile_auth_action_label(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes':
            return 'Open HSD-ES saved query / sign in'
        return ''

    def _profile_auth_action_url(self, readiness: dict) -> str:
        if readiness.get('provider_id') == 'hsdes':
            return FIRST_HSDES_ACCESS_CHECK_URL
        return ''

    def _scope_label_value(self, scope_labels: dict, name: str) -> str:
        return str(scope_labels.get(name, {}).get('value', ''))

    def _scope_label_source(self, scope_labels: dict) -> str:
        sources = {
            str(label.get('source', ''))
            for label in scope_labels.values()
            if isinstance(label, dict) and label.get('source')
        }
        return ','.join(sorted(sources))

    def _grafana_rows(self, chart_data: BugTrendChartData) -> list[dict]:
        rows = []
        for index, bucket_id in enumerate(chart_data.bucket_ids):
            row = {
                'calculation_run_id': chart_data.calculation_run_id,
                'bucket_id': bucket_id,
                'bucket_label': chart_data.labels[index],
                'bucket_start': self._bucket_value(chart_data.bucket_starts, index),
                'bucket_end': self._bucket_value(chart_data.bucket_ends, index),
                'bucket_granularity': chart_data.bucket_granularity,
            }
            for dataset in chart_data.datasets:
                row[dataset['series_name']] = dataset['values'][index]
            rows.append(row)
        return rows

    def _bucket_value(self, values: list, index: int) -> str:
        return values[index] if values and index < len(values) else ''

    def _series_label(self, series_name: str) -> str:
        return series_name.replace('_', ' ').title()

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

    def new_scope_config(self) -> SavedScopeConfig:
        return saved_scope_config_from_dict({
            'id': None,
            'name': '',
            'ip': '',
            'project_label': '',
            'jql': '',
            'owner_field': 'assignee',
            'timezone': 'UTC',
            'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
            'enabled': False,
        })

    def duplicate_scope_config(self, scope_id: int) -> SavedScopeConfig:
        source = self._bug_trend_api.get_scope_config(scope_id)
        return SavedScopeConfig(
            id=None,
            name=f'{source.name} copy',
            ip=source.ip,
            project_label=source.project_label,
            jql=source.jql,
            bug_type_values=list(source.bug_type_values),
            open_status_values=list(source.open_status_values),
            fixed_status_values=list(source.fixed_status_values),
            closed_status_values=list(source.closed_status_values),
            terminal_excluded_status_values=list(source.terminal_excluded_status_values),
            fixed_resolution_values=list(source.fixed_resolution_values),
            closed_resolution_values=list(source.closed_resolution_values),
            reopen_status_values=list(source.reopen_status_values),
            severity_field=source.severity_field,
            critical_high_values=list(source.critical_high_values),
            medium_low_values=list(source.medium_low_values),
            component_field=source.component_field,
            owner_field=source.owner_field,
            team_field=source.team_field,
            milestone_field=source.milestone_field,
            fix_version_field=source.fix_version_field,
            package_version_field=source.package_version_field,
            display_fields=list(source.display_fields),
            timezone=source.timezone,
            bucket_granularity=source.bucket_granularity,
            enabled=False,
            config_version_hash='',
        )

    def disable_scope_config(self, scope_id: int):
        return self._bug_trend_api.disable_scope_config(scope_id)

    def get_scope_metadata_options(self, config: SavedScopeConfig, selected_projects: list[str] = None):
        if self._scope_metadata_api is None:
            return None
        try:
            return self._scope_metadata_api.discover_scope_options('jira', config.jql, selected_projects or [], config.bug_type_values, refresh=True)
        except Exception as error:
            return {'warnings': [f'Metadata refresh failed: {error}']}

    def save_scope_config(self, post_data) -> tuple[SavedScopeConfig, bool]:
        config = self.scope_config_from_post(post_data)
        if post_data.get('id') and config.id is None:
            raise ValueError({'id': 'Scope id must be numeric.'})
        persisted = self._bug_trend_api.get_scope_config(config.id) if config.id else None
        original_hash = persisted.config_version_hash if persisted else ''
        action = post_data.get('action')
        if action == 'save_enable':
            config.enabled = True
        elif config.id is not None and persisted is not None:
            config.enabled = persisted.enabled
        elif action == 'save_draft' and config.id is None:
            config.enabled = False
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
        return normalize_scope_list_values(value)
