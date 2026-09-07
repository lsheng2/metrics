import json
from dataclasses import replace
from datetime import date

from django.conf import settings

from bug_metrics.app.api import BugTrendPageQueryState, BugTrendTicketListFilters
from bug_metrics.app.api.provider_profile_config import PROFILE_JSON_FIELDS, provider_profile_config_from_post
from bug_metrics.app.api.scope_config import SEMANTIC_LIST_FIELDS, SavedScopeConfig, normalize_scope_list_values, saved_scope_config_from_dict
from bug_metrics.models import JiraScopeConfig
from bug_metrics.provider_profile_security import without_profile_secret_values

from ..data.bug_trend_data import BugTrendChartData, BugTrendChartOption, BugTrendEvidenceData, BugTrendProviderProfileChoice, BugTrendProviderProfileRow, BugTrendProviderSetupEditor, BugTrendScopeAuditData, BugTrendScopeBindingData, BugTrendScopeConfigProviderContext, BugTrendScopeLibraryRow, BugTrendScopeLibraryScopeData, BugTrendScopeOption
from .bug_trend_chart_payload import chart_payload, run_metadata_payload
from .bug_trend_scope_profile import resolve_scope_provider_binding
from .provider_dashboard_facade import ProviderDashboardFacade
from .provider_scope_setup import default_provider_id, provider_detail_rows, provider_id_for_profile, provider_profile_choices_for, provider_setup_options, provider_setup_template, selected_profile_for, selected_profile_id_for


SEMANTIC_MAPPING_TEXT_FIELDS = {
    'severity_field',
    'component_field',
    'owner_field',
    'milestone_field',
    'fix_version_field',
    'package_version_field',
}


class BugTrendFacade:
    def __init__(self, bug_trend_api, scope_metadata_api=None):
        self._bug_trend_api = bug_trend_api
        self._scope_metadata_api = scope_metadata_api
        self._provider_dashboard_facade = ProviderDashboardFacade(bug_trend_api)

    def get_scope_options(self):
        options = []
        for scope in self._bug_trend_api.list_enabled_scopes():
            binding = resolve_scope_provider_binding(self._bug_trend_api, scope)
            options.append(BugTrendScopeOption(
                scope.id,
                scope.name,
                self._scope_label(scope),
                binding.profile_id,
                binding.provider_id,
                binding.status,
                binding.blockers,
            ))
        return options

    def get_scope_library(self):
        return self._bug_trend_api.list_scope_configs()

    def get_scope_library_rows(self):
        if not hasattr(self._bug_trend_api, 'list_scope_provider_bindings'):
            return [
                BugTrendScopeLibraryRow(self._saved_scope_data(scope), BugTrendScopeBindingData('', '', 'configuration_required', '-', [], False, True))
                for scope in self.get_scope_library()
            ]
        configs_by_id = {config.id: config for config in self.get_scope_library()}
        rows = []
        represented_profile_ids = set()
        for scope, binding in self._bug_trend_api.list_scope_provider_bindings():
            config = configs_by_id.get(scope.id)
            if not config:
                continue
            rows.append(self._scope_library_row(config, binding))
            if binding.profile_id and binding.status in {'explicit', 'compatibility'}:
                represented_profile_ids.add(binding.profile_id)
        for profile in self.get_scope_provider_profile_choices():
            if profile.profile_id in represented_profile_ids:
                continue
            rows.append(self._provider_profile_row(profile))
        return rows

    def get_scope_library_summary(self, rows=None) -> dict:
        rows = rows if rows is not None else self.get_scope_library_rows()
        return {
            'total': len(rows),
            'saved_scope_count': sum(1 for row in rows if row.source_kind == 'saved_scope'),
            'provider_profile_count': sum(1 for row in rows if row.source_kind == 'provider_profile'),
            'compatibility_ready_count': sum(1 for row in rows if row.binding.can_confirm),
            'needs_attention_count': sum(1 for row in rows if row.binding.can_edit),
        }

    def get_scope_binding_policy(self) -> str:
        if not hasattr(self._bug_trend_api, 'get_scope_binding_policy'):
            return 'compatibility_allowed'
        return self._bug_trend_api.get_scope_binding_policy()

    def get_scope_binding_audit_events(self, limit: int = 12) -> list[dict]:
        if not hasattr(self._bug_trend_api, 'list_scope_binding_audit_events'):
            return []
        return self._bug_trend_api.list_scope_binding_audit_events(limit)

    def confirm_scope_provider_binding(self, scope_id: int):
        return self._bug_trend_api.confirm_scope_provider_binding(scope_id)

    def bulk_confirm_scope_provider_bindings(self):
        if not hasattr(self._bug_trend_api, 'bulk_confirm_scope_provider_bindings'):
            return {'changed_count': 0, 'skipped_count': 0, 'changed': [], 'skipped': []}
        result = self._bug_trend_api.bulk_confirm_scope_provider_bindings()
        return result.to_dict() if hasattr(result, 'to_dict') else result

    def set_scope_provider_binding(self, scope_id: int, profile_id: str):
        return self._bug_trend_api.set_scope_provider_binding(scope_id, profile_id)

    def get_scope_delete_impact(self, scope_id: int) -> dict:
        if not hasattr(self._bug_trend_api, 'get_scope_delete_impact'):
            return {}
        return self._bug_trend_api.get_scope_delete_impact(scope_id)

    def export_scope_config_package(self, scope_id: int) -> dict:
        return self._bug_trend_api.export_scope_config_package(scope_id)

    def import_scope_config_package(self, package: dict):
        return self._bug_trend_api.import_scope_config_package(package)

    def delete_archived_scope_config(self, scope_id: int, confirmation: str) -> dict:
        return self._bug_trend_api.delete_archived_scope_config(scope_id, confirmation)

    def list_provider_profile_rows(self) -> list[BugTrendProviderProfileRow]:
        return [
            self._provider_profile_config_row(profile)
            for profile in self._bug_trend_api.list_provider_profile_configs()
        ]

    def get_provider_setup_summary(self, rows=None) -> dict:
        rows = rows if rows is not None else self.list_provider_profile_rows()
        return {
            'total': len(rows),
            'enabled': sum(1 for row in rows if row.lifecycle_state == 'enabled'),
            'draft': sum(1 for row in rows if row.lifecycle_state == 'draft'),
            'archived': sum(1 for row in rows if row.lifecycle_state == 'archived'),
            'jira': sum(1 for row in rows if row.provider_id == 'jira'),
            'hsdes': sum(1 for row in rows if row.provider_id == 'hsdes'),
        }

    def get_provider_setup_editor(self, profile_id: str = '', provider_id: str = '', post_data=None) -> BugTrendProviderSetupEditor:
        if post_data is not None:
            profile = provider_profile_config_from_post(post_data)
        elif profile_id:
            profile = self._bug_trend_api.get_provider_profile_config(profile_id)
        else:
            profile = self._bug_trend_api.new_provider_profile_config(provider_id or 'jira')
        display_profile = self._display_profile_config(profile)
        selected_provider_id = profile.provider_id if profile_id and post_data is None else provider_id or profile.provider_id
        profile_choices = self.get_scope_provider_profile_choices()
        template = provider_setup_template(selected_provider_id)
        return BugTrendProviderSetupEditor(
            display_profile,
            provider_setup_options(profile_choices, selected_provider_id, allow_template_creation=True),
            selected_provider_id,
            template.label,
            template.color,
            template.summary,
            template.source_query_label,
            template.source_query_help,
            template.metadata_supported,
            template.metadata_summary,
            provider_detail_rows(template, self._profile_choice_from_config(display_profile)),
            self._provider_profile_json_fields(display_profile),
            json.dumps(without_profile_secret_values(display_profile.connection_settings or {}), sort_keys=True),
            display_profile.connection_settings.get('connection_status_label', 'Configuration required'),
        )

    def save_provider_profile_config(self, post_data):
        return self._bug_trend_api.save_provider_profile_config(provider_profile_config_from_post(post_data))

    def test_provider_profile_connection(self, post_data):
        return self._bug_trend_api.test_provider_profile_connection(provider_profile_config_from_post(post_data))

    def duplicate_provider_profile_config(self, profile_id: str):
        return self._bug_trend_api.duplicate_provider_profile_config(profile_id)

    def archive_provider_profile_config(self, profile_id: str):
        return self._bug_trend_api.archive_provider_profile_config(profile_id)

    def restore_provider_profile_config(self, profile_id: str):
        return self._bug_trend_api.restore_provider_profile_config(profile_id)

    def delete_archived_provider_profile_config(self, profile_id: str, confirmation: str) -> dict:
        return self._bug_trend_api.delete_archived_provider_profile_config(profile_id, confirmation)

    def export_provider_profile_package(self, profile_id: str) -> dict:
        return self._bug_trend_api.export_provider_profile_package(profile_id)

    def import_provider_profile_package(self, package: dict):
        return self._bug_trend_api.import_provider_profile_package(package)

    def get_scope_provider_profile_choices(self):
        if not hasattr(self._bug_trend_api, 'list_scope_provider_profile_choices'):
            return []
        return [
            BugTrendProviderProfileChoice(
                choice.get('profile_id', ''),
                choice.get('provider_id', ''),
                choice.get('display_name', ''),
                dict(choice.get('connection_settings', {}) or {}),
                dict(choice.get('scope_labels', {}) or {}),
                dict(choice.get('source_population', {}) or {}),
                choice.get('mapping_version_hash', ''),
            )
            for choice in self._bug_trend_api.list_scope_provider_profile_choices()
        ]

    def get_scope_provider_binding_health(self) -> dict:
        if not hasattr(self._bug_trend_api, 'get_scope_provider_binding_health'):
            return {'total': 0, 'counts': {}, 'rows': []}
        return self._bug_trend_api.get_scope_provider_binding_health()

    def get_scope_config_provider_context(
        self,
        config: SavedScopeConfig,
        selected_provider_id: str = '',
        selected_profile_id: str = '',
    ) -> BugTrendScopeConfigProviderContext:
        profile_choices = self.get_scope_provider_profile_choices()
        requested_provider_id = selected_provider_id
        requested_profile_id = selected_profile_id
        selected_provider_id = self._selected_provider_id(profile_choices, requested_provider_id, requested_profile_id, '')
        selected_profile_id = selected_profile_id_for(profile_choices, selected_provider_id, requested_profile_id, '')
        selected_profile = selected_profile_for(profile_choices, selected_profile_id)
        selected_template = provider_setup_template(selected_provider_id)
        if config.id is None:
            return BugTrendScopeConfigProviderContext(
                selected_profile_id,
                selected_provider_id,
                'draft',
                'Save draft with a provider profile to create an explicit binding, or repair it later from Scope Library.',
                [],
                profile_choices,
                False,
                selected_provider_id,
                selected_template.metadata_supported,
                selected_template.metadata_summary,
                selected_provider_id,
                selected_profile_id,
                provider_profile_choices_for(profile_choices, selected_provider_id),
                provider_setup_options(profile_choices, selected_provider_id),
                selected_template.label,
                selected_template.color,
                selected_template.summary,
                selected_template.source_query_label,
                selected_template.source_query_help,
                provider_detail_rows(selected_template, selected_profile),
            )
        binding = self._scope_config_binding_data(config)
        selected_provider_id = self._selected_provider_id(profile_choices, requested_provider_id, requested_profile_id, binding.provider_id)
        selected_profile_id = selected_profile_id_for(profile_choices, selected_provider_id, requested_profile_id, binding.profile_id)
        selected_profile = selected_profile_for(profile_choices, selected_profile_id)
        selected_template = provider_setup_template(selected_provider_id)
        return BugTrendScopeConfigProviderContext(
            binding.profile_id,
            binding.provider_id,
            binding.status,
            binding.provenance_summary,
            binding.blockers,
            profile_choices,
            True,
            selected_provider_id,
            selected_template.metadata_supported,
            selected_template.metadata_summary,
            selected_provider_id,
            selected_profile_id,
            provider_profile_choices_for(profile_choices, selected_provider_id),
            provider_setup_options(profile_choices, selected_provider_id),
            selected_template.label,
            selected_template.color,
            selected_template.summary,
            selected_template.source_query_label,
            selected_template.source_query_help,
            provider_detail_rows(selected_template, selected_profile),
        )

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

    def _binding_data(self, binding) -> BugTrendScopeBindingData:
        provenance = dict(getattr(binding, 'provenance', {}) or {})
        provenance_summary = provenance.get('matched_by') or provenance.get('source') or '-'
        return BugTrendScopeBindingData(
            binding.profile_id,
            binding.provider_id,
            binding.status,
            provenance_summary,
            list(binding.blockers or []),
            binding.status == 'compatibility' and bool(binding.profile_id and binding.provider_id),
            binding.status not in {'explicit', 'disabled'},
        )

    def _scope_config_binding_data(self, config: SavedScopeConfig) -> BugTrendScopeBindingData:
        if hasattr(self._bug_trend_api, 'list_scope_provider_bindings'):
            for scope, binding in self._bug_trend_api.list_scope_provider_bindings():
                if str(scope.id) == str(config.id):
                    return self._binding_data(binding)
        return self._binding_data(resolve_scope_provider_binding(self._bug_trend_api, config))

    def selected_scope_provider_profile_id(self, post_data) -> str:
        provider_id = str(post_data.get('provider_id', '') or '').strip()
        profile_id = str(post_data.get('profile_id', '') or '').strip()
        if not provider_id or not profile_id:
            return ''
        profile_choices = self.get_scope_provider_profile_choices()
        return profile_id if provider_id_for_profile(profile_choices, profile_id) == provider_id else ''

    def _selected_provider_id(
        self,
        profile_choices: list[BugTrendProviderProfileChoice],
        requested_provider_id: str,
        requested_profile_id: str,
        current_provider_id: str,
    ) -> str:
        requested_provider_id = str(requested_provider_id or '').strip().lower()
        if requested_provider_id:
            return requested_provider_id
        profile_provider_id = provider_id_for_profile(profile_choices, requested_profile_id)
        if profile_provider_id:
            return profile_provider_id
        if current_provider_id:
            return current_provider_id
        return default_provider_id(profile_choices)

    def _scope_library_row(self, scope, binding) -> BugTrendScopeLibraryRow:
        return BugTrendScopeLibraryRow(
            self._saved_scope_data(scope),
            self._binding_data(binding),
            delete_impact=self.get_scope_delete_impact(scope.id),
            delete_confirmation=f'DELETE {scope.name}',
        )

    def _saved_scope_data(self, scope) -> BugTrendScopeLibraryScopeData:
        return BugTrendScopeLibraryScopeData(
            str(scope.id),
            scope.name,
            scope.ip,
            scope.project_label,
            scope.enabled,
            scope.config_version_hash,
        )

    def _provider_profile_row(self, profile: BugTrendProviderProfileChoice) -> BugTrendScopeLibraryRow:
        scope_labels = profile.scope_labels or {}
        source_population = profile.source_population or {}
        source_detail = source_population.get('source_query_name') or source_population.get('source_query_ref') or 'provider profile registry'
        return BugTrendScopeLibraryRow(
            BugTrendScopeLibraryScopeData(
                profile.profile_id,
                profile.display_name or profile.profile_id,
                scope_labels.get('ip', ''),
                scope_labels.get('project_or_product', ''),
                True,
                profile.mapping_version_hash,
            ),
            BugTrendScopeBindingData(
                profile.profile_id,
                profile.provider_id,
                'provider_profile',
                source_population.get('ownership_type', 'provider_profile_registry'),
                [],
                False,
                False,
            ),
            'provider_profile',
            'Provider profile',
            source_detail,
            False,
            False,
            False,
        )

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

    def get_provider_chart_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                   chart_id: str, chart_version: int = 1, fact_snapshot_id: str = '',
                                   range_mode: str = 'ww', begin_date: str = '', end_date: str = '') -> dict:
        return self._provider_dashboard_facade.get_provider_chart_payload(provider_id, profile_id, begin_ww, end_ww, chart_id, chart_version, fact_snapshot_id, range_mode, begin_date, end_date)

    def get_provider_chart_evidence_payload(self, provider_id: str, profile_id: str, begin_ww: str, end_ww: str,
                                            chart_id: str, calculation_run_id: str, bucket_id: str = '',
                                            series_name: str = '', chart_version: int = 1, fact_snapshot_id: str = '',
                                            owner: str = '', status: str = '', severity: str = '',
                                            component: str = '', text: str = '', range_mode: str = 'ww',
                                            begin_date: str = '', end_date: str = '') -> dict:
        return self._provider_dashboard_facade.get_provider_chart_evidence_payload(provider_id, profile_id, begin_ww, end_ww, chart_id, calculation_run_id, bucket_id, series_name, chart_version, fact_snapshot_id, owner, status, severity, component, text, range_mode, begin_date, end_date)

    def get_provider_profile_readiness_payload(self, provider_id: str, profile_id: str, range_mode: str = 'ww',
                                               begin_ww: str = '', end_ww: str = '', begin_date: str = '',
                                               end_date: str = '') -> dict:
        return self._provider_dashboard_facade.get_provider_profile_readiness_payload(provider_id, profile_id, range_mode, begin_ww, end_ww, begin_date, end_date)

    def get_provider_profile_time_range_action_url(self, provider_id: str, profile_id: str, range_mode: str = 'ww',
                                                   begin_ww: str = '', end_ww: str = '', begin_date: str = '',
                                                   end_date: str = '') -> str:
        return self._provider_dashboard_facade.get_provider_profile_time_range_action_url(provider_id, profile_id, range_mode, begin_ww, end_ww, begin_date, end_date)

    def get_ai_dashboard_catalog_payload(self, profile_id: str = '') -> dict:
        return self._bug_trend_api.list_ai_dashboard_composition_catalog(profile_id)

    def get_ai_sidecar_status_payload(self) -> dict:
        return self._bug_trend_api.get_ai_sidecar_status()

    def validate_ai_dashboard_composition_intent(self, request) -> dict:
        return self._bug_trend_api.validate_ai_dashboard_composition_intent(request)

    def run_ai_dashboard_workflow(self, request) -> dict:
        return self._bug_trend_api.run_ai_dashboard_workflow(request)

    def validate_ai_dashboard_render_config_draft(self, draft_render_config: dict) -> dict:
        return self._bug_trend_api.validate_ai_dashboard_render_config_draft(draft_render_config)

    def validate_ai_dashboard_workspace_artifact(self, request) -> dict:
        return self._bug_trend_api.validate_ai_dashboard_workspace_artifact(request)

    def validate_ai_gcx_publication_precondition(self, request) -> dict:
        return self._bug_trend_api.validate_ai_gcx_publication_precondition(request)

    def record_ai_gcx_publication_callback(self, request) -> dict:
        return self._bug_trend_api.record_ai_gcx_publication_callback(request)

    def publish_ai_grafana_dashboard_demo(self, request, correlation_id: str) -> dict:
        return self._bug_trend_api.publish_ai_grafana_dashboard_demo(request, correlation_id)

    def request_ai_grafana_publish_approval(self, request) -> dict:
        return self._bug_trend_api.request_ai_grafana_publish_approval(request)

    def decide_ai_grafana_publish_approval(self, approval_id: str, decision: str, actor: str) -> dict:
        return self._bug_trend_api.decide_ai_grafana_publish_approval(approval_id, decision, actor)

    def get_ai_grafana_publish_approval(self, approval_id: str) -> dict:
        return self._bug_trend_api.get_ai_grafana_publish_approval(approval_id)

    def list_ai_grafana_publish_history(self, limit: int = 25) -> dict:
        return self._bug_trend_api.list_ai_grafana_publish_history(limit)

    def get_ai_dashboard_context_payload(self, query) -> dict:
        return self._bug_trend_api.get_ai_dashboard_context(query)

    def get_ai_workspace_context_bundle_payload(self, profile_id: str) -> dict:
        return self._bug_trend_api.get_ai_workspace_context_bundle(profile_id)

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
        if add_field in SEMANTIC_MAPPING_TEXT_FIELDS and add_value:
            setattr(config, add_field, add_value)
        return config

    def new_scope_config(self, provider_id: str = '', profile_id: str = '') -> SavedScopeConfig:
        payload = {
            'id': None,
            'name': '',
            'ip': '',
            'project_label': '',
            'jql': '',
            'owner_field': 'assignee',
            'timezone': 'UTC',
            'bucket_granularity': JiraScopeConfig.GRANULARITY_WEEKLY,
            'enabled': False,
        }
        if profile_id:
            payload.update(self._scope_defaults_from_profile(profile_id))
        return saved_scope_config_from_dict(payload)

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

    def _provider_profile_config_row(self, profile) -> BugTrendProviderProfileRow:
        template = provider_setup_template(profile.provider_id)
        return BugTrendProviderProfileRow(
            profile.profile_id,
            profile.provider_id,
            template.label,
            template.color,
            profile.display_name,
            profile.lifecycle_state,
            profile.source_kind,
            self._provider_source_summary(profile),
            profile.mapping_version_hash,
            profile.source_version_hash,
            self._bug_trend_api.get_provider_profile_delete_impact(profile.profile_id),
            f'DELETE {profile.profile_id}',
        )

    def _display_profile_config(self, profile):
        return replace(profile, connection_settings=self._display_connection_settings(profile.provider_id, profile.connection_settings))

    def _display_connection_settings(self, provider_id: str, connection_settings: dict) -> dict:
        display_settings = dict(connection_settings or {})
        display_settings['base_url'] = self._settings_reference_value(display_settings.get('base_url'))
        display_settings['auth_mode'] = self._settings_reference_value(display_settings.get('auth_mode'))
        display_settings['auth_mode_label'] = self._auth_mode_label(provider_id, display_settings.get('auth_mode'))
        credentials = dict(display_settings.get('credentials') or {})
        settings_credentials = self._settings_credentials_for_provider(provider_id)
        for key in ['email', 'username', 'password']:
            if not credentials.get(key) and settings_credentials.get(key):
                credentials[key] = settings_credentials[key]
        for key in ['api_token', 'token']:
            if credentials.get(key) or settings_credentials.get(key):
                credentials[key] = '********'
        if credentials:
            display_settings['credentials'] = credentials
        display_settings['connection_status_label'] = self._connection_status_label(provider_id, display_settings, credentials)
        return display_settings

    def _auth_mode_label(self, provider_id: str, auth_mode: str) -> str:
        auth_mode = str(auth_mode or '').strip()
        labels = {
            'jira': {
                'server_pat': 'API token / PAT',
                'cloud_basic': 'Email + API token',
            },
            'hsdes': {
                'kerberos': 'Windows Integrated Auth',
                'windows_integrated': 'Windows Integrated Auth',
                'basic': 'Username + password',
                'token': 'Bearer token',
            },
            'github': {
                'token': 'Personal access token',
            },
        }
        return labels.get(str(provider_id or '').strip().lower(), {}).get(auth_mode, auth_mode or 'Not selected')

    def _connection_status_label(self, provider_id: str, connection_settings: dict, credentials: dict) -> str:
        provider_id = str(provider_id or '').strip().lower()
        auth_mode = str(connection_settings.get('auth_mode', '') or '').strip()
        if not str(connection_settings.get('base_url', '') or '').strip():
            return 'Base URL required'
        if provider_id == 'jira':
            if auth_mode == 'cloud_basic':
                return 'Ready to test' if credentials.get('email') and credentials.get('api_token') else 'Email and API token required'
            return 'Ready to test' if credentials.get('api_token') else 'API token required'
        if provider_id == 'hsdes':
            if auth_mode in {'kerberos', 'windows_integrated'}:
                return 'Ready to test with Windows Integrated Auth'
            if auth_mode == 'basic':
                return 'Ready to test' if credentials.get('username') and credentials.get('password') else 'Username and password required'
            if auth_mode == 'token':
                return 'Ready to test' if credentials.get('token') else 'Bearer token required'
            return 'Authentication method required'
        if provider_id == 'github':
            return 'Ready to test' if credentials.get('token') else 'Token required'
        return 'Configuration required'

    def _settings_reference_value(self, value):
        raw_value = str(value or '')
        if not raw_value.startswith('settings:'):
            return value
        setting_name = raw_value.removeprefix('settings:').strip()
        if not setting_name.replace('_', '').isalnum():
            return value
        setting_value = getattr(settings, setting_name, None)
        return setting_value if setting_value not in {None, ''} else value

    def _settings_credentials_for_provider(self, provider_id: str) -> dict:
        provider_id = str(provider_id or '').strip().lower()
        if provider_id == 'jira':
            return {
                'email': getattr(settings, 'METRICS_JIRA_EMAIL', '') or '',
                'api_token': getattr(settings, 'METRICS_JIRA_API_TOKEN', '') or '',
            }
        if provider_id == 'hsdes':
            return {
                'username': getattr(settings, 'METRICS_HSDES_USERNAME', '') or '',
                'password': getattr(settings, 'METRICS_HSDES_PASSWORD', '') or '',
                'token': getattr(settings, 'METRICS_HSDES_TOKEN', '') or '',
            }
        if provider_id == 'github':
            return {
                'token': getattr(settings, 'METRICS_GITHUB_TOKEN', '') or '',
            }
        return {}

    def _provider_profile_json_fields(self, profile) -> list[dict]:
        return [
            {
                'name': field_name,
                'label': field_name.replace('_', ' ').title(),
                'value': json.dumps(getattr(profile, field_name), indent=2, sort_keys=True),
            }
            for field_name in PROFILE_JSON_FIELDS
            if field_name != 'connection_settings'
        ]

    def _profile_choice_from_config(self, profile):
        return BugTrendProviderProfileChoice(
            profile.profile_id,
            profile.provider_id,
            profile.display_name,
            dict(getattr(profile, 'connection_settings', {}) or {}),
            dict(profile.scope_labels or {}),
            dict(profile.source_population or {}),
            profile.mapping_version_hash,
        )

    def _scope_defaults_from_profile(self, profile_id: str) -> dict:
        profile = self._bug_trend_api.get_provider_profile_config(profile_id)
        value_mappings = dict(profile.value_mappings or {})
        field_bindings = dict(profile.field_bindings or {})
        source_population = dict(profile.source_population or {})
        return {
            'name': profile.profile_id,
            'ip': dict(profile.scope_labels or {}).get('ip', ''),
            'project_label': dict(profile.scope_labels or {}).get('project_or_product', ''),
            'jql': source_population.get('native_query_text') or source_population.get('source_query_ref') or '',
            'bug_type_values': value_mappings.get('bug_type_values', []),
            'open_status_values': value_mappings.get('open_status_values', []),
            'fixed_status_values': value_mappings.get('fixed_status_values', []),
            'closed_status_values': value_mappings.get('closed_status_values', []),
            'critical_high_values': value_mappings.get('critical_high_values', []),
            'medium_low_values': value_mappings.get('medium_low_values', []),
            'severity_field': self._native_field(field_bindings, 'severity'),
            'component_field': self._native_field(field_bindings, 'component'),
            'owner_field': self._native_field(field_bindings, 'owner') or 'assignee',
            'milestone_field': self._native_field(field_bindings, 'milestone'),
            'fix_version_field': self._native_field(field_bindings, 'release'),
        }

    def _native_field(self, field_bindings: dict, canonical_field: str) -> str:
        binding = field_bindings.get(canonical_field, {})
        return binding.get('native_field', '') if isinstance(binding, dict) else ''

    def _provider_source_summary(self, profile) -> str:
        connection_settings = dict(getattr(profile, 'connection_settings', {}) or {})
        connection_summary = (
            connection_settings.get('base_url')
            or connection_settings.get('credential_ref')
            or connection_settings.get('auth_mode')
        )
        if connection_summary:
            return connection_summary
        source_population = dict(profile.source_population or {})
        return (
            source_population.get('source_query_name')
            or source_population.get('source_query_ref')
            or source_population.get('native_query_text')
            or source_population.get('tenant_or_site')
            or '-'
        )
