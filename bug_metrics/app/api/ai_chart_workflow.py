from copy import deepcopy
import hashlib
import json
from uuid import uuid4

from django.conf import settings

from .ai_chart_inputs import draft_crosses_boundary, finding, request_findings
from .ai_dashboard_composition_contracts import DashboardCompositionIntent
from .ai_dashboard_composition_rules import AiDashboardCompositionRules
from .ai_dashboard_grafana_publish import grafana_time_range
from .ai_publication_contracts import ChartPublicationPreview, normalized_grafana_base_url
from .provider_aggregate_contracts import ProviderChartAggregateQuery
from .provider_aggregates import ProviderChartAggregateService
from .provider_profiles import ProviderProfileReadinessService


def canonical_bytes(value):
    return json.dumps(value, sort_keys=True, separators=(',', ':'), ensure_ascii=False, allow_nan=False).encode('utf-8')


def data_fingerprint(result):
    rows = sorted((dict(row) for row in result.grafana_rows), key=canonical_bytes)
    return hashlib.sha256(canonical_bytes({
        'profile_id': result.profile_id,
        'provider_id': result.provider_id,
        'chart_id': result.chart_id,
        'chart_version': result.chart_version,
        'fact_snapshot_id': result.fact_snapshot_id,
        'calculation_run_id': result.run_metadata.get('calculation_run_id', ''),
        'source_query_hash': result.source_population.get('source_query_hash', ''),
        'mapping_version_hash': result.source_population.get('mapping_version_hash', ''),
        'rows': rows,
    })).hexdigest()


class AiChartWorkflowService:
    def __init__(self):
        self.profiles = ProviderProfileReadinessService()
        self.rules = AiDashboardCompositionRules(self.profiles)
        self.aggregates = ProviderChartAggregateService()

    def run(self, request):
        envelope = {
            'contract_version': '0.3',
            'workflow_type': 'metrics_ai_dashboard_composition',
            'correlation_id': f'metrics-ai-{uuid4()}',
            'request': self._request_summary(request),
            'status': 'validation_failed',
            'findings': request_findings(request),
            'normalized_render_config': None,
            'publish_readiness': {'ready': False, 'status': 'not_checked'},
        }
        if envelope['findings']:
            return envelope
        uid = self._dashboard_uid(request)
        intent = DashboardCompositionIntent(
            profile_id=request.profile_id, dashboard_uid=uid,
            chart_id=request.chart_id, requested_series=list(request.requested_series),
            range_mode=request.range_mode, range_start=request.range_start, range_end=request.range_end,
            output_type='render_config_draft', panel_title=request.panel_title,
            visualization=request.visualization,
        )
        try:
            validation = self.rules.validate_composition_intent(intent)
        except (KeyError, TypeError, ValueError):
            envelope['findings'] = [finding('invalid_input', 'request', 'Profile, chart or range is not valid.')]
            return envelope
        envelope['status'] = validation['status']
        envelope['findings'] = validation.get('findings', [])
        if not validation.get('valid'):
            return envelope
        render_config = deepcopy(
            validation['draft_render_config'] if request.render_config is None else request.render_config,
        )
        if request.render_config is not None and not render_config:
            envelope['status'] = 'validation_failed'
            envelope['findings'] = [finding('invalid_render_config', 'render_config', 'Render config is empty.')]
            return envelope
        render_config['dashboard_uid'] = uid
        provider_id = self.rules.provider_id_for_profile(request.profile_id)
        if request.render_config is not None and draft_crosses_boundary(
            render_config, profile_id=request.profile_id, provider_id=provider_id,
        ):
            envelope['status'] = 'validation_failed'
            envelope['findings'] = [finding(
                'context_boundary_violation',
                'render_config',
                'Render config crosses the selected provider profile boundary.',
            )]
            return envelope
        try:
            render_validation = self.rules.validate_render_config_draft(render_config)
        except (KeyError, TypeError, ValueError):
            render_validation = {
                'valid': False, 'findings': [finding(
                    'invalid_render_config', 'render_config', 'Render config is not valid.',
                )],
            }
        envelope['render_validation'] = render_validation
        if not render_validation.get('valid'):
            envelope['status'] = 'validation_failed'
            envelope['findings'] = render_validation.get('findings', [])
            return envelope
        envelope['request']['provider_id'] = provider_id
        envelope['request']['dashboard_uid'] = uid
        envelope['normalized_render_config'] = render_config
        envelope['status'] = 'draft_validated'
        result = self.aggregates.get_aggregates(ProviderChartAggregateQuery(
            provider_id=provider_id, profile_id=request.profile_id, chart_id=request.chart_id,
            begin_ww=request.range_start if request.range_mode == 'ww' else '',
            end_ww=request.range_end if request.range_mode == 'ww' else '',
            range_mode=request.range_mode,
            begin_date=request.range_start if request.range_mode == 'date' else '',
            end_date=request.range_end if request.range_mode == 'date' else '',
        ))
        ready = result.status == 'supported' and bool(result.grafana_rows)
        target = normalized_grafana_base_url(settings.METRICS_AI_GRAFANA_BASE_URL)
        envelope['publish_readiness'] = {
            'ready': ready and target is not None,
            'status': result.status if target is not None else 'grafana_not_configured',
            'reason': result.reason if target is not None else 'Grafana publication target is not configured.',
            'next_action': '' if ready and target is not None else (
                'repair_scope_binding' if result.run_metadata.get('binding_status') else 'sync_provider_profile'
            ),
            'provider_id': result.provider_id,
            'profile_id': result.profile_id,
            'fact_snapshot_id': result.fact_snapshot_id,
            'calculation_run_id': result.run_metadata.get('calculation_run_id', ''),
            'freshness_status': result.run_metadata.get('freshness_status', ''),
            'data_fingerprint': data_fingerprint(result) if ready else '',
        }
        return envelope

    def preview(self, request):
        workflow = self.run(request)
        if not workflow['publish_readiness']['ready']:
            return ChartPublicationPreview(workflow=workflow)
        target = normalized_grafana_base_url(settings.METRICS_AI_GRAFANA_BASE_URL)
        dashboard = self.rules.generate_dashboard_from_render_config(workflow['normalized_render_config'])
        dashboard['time'] = grafana_time_range(request)
        dashboard['timezone'] = 'browser'
        publication = {
            **workflow['request'],
            'chart_version': 1,
            'normalized_render_config': workflow['normalized_render_config'],
            'data_fingerprint': workflow['publish_readiness']['data_fingerprint'],
        }
        return ChartPublicationPreview(
            workflow=workflow,
            content={
                'dashboard': dashboard,
                'target': {'grafana_base_url': target, 'uid': dashboard['uid']},
                'publication': publication,
            },
        )

    def _dashboard_uid(self, request):
        identity = self._request_summary(request)
        identity['panel_title'] = request.panel_title
        draft = deepcopy(request.render_config)
        if draft is not None:
            draft.pop('dashboard_uid', None)
        identity['render_config'] = draft
        return 'metrics-ai-' + hashlib.sha256(canonical_bytes(identity)).hexdigest()[:24]

    def _request_summary(self, request):
        return {
            'profile_id': request.profile_id,
            'chart_id': request.chart_id,
            'requested_series': list(request.requested_series),
            'range_mode': request.range_mode,
            'range_start': request.range_start,
            'range_end': request.range_end,
            'visualization': request.visualization,
        }
