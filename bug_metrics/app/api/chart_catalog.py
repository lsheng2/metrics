from dataclasses import dataclass
from typing import List

from bug_metrics.models import BugTrendAuditEvent, BugTrendChartDefinition, BugTrendChartPublishRequest, BugTrendEvidenceContract, BugTrendRendererRouteDecision
from .series import BUG_TREND_SERIES


@dataclass(slots=True)
class EvidenceContractDefinition:
    contract_id: str
    capability: str
    membership_source: str
    allowed_list_filters: List[str]
    unsupported_reason: str


@dataclass(slots=True)
class ChartDefinition:
    chart_id: str
    chart_version: int
    title: str
    renderer_type: str
    integration_route: str
    status: str
    enabled: bool
    built_in: bool
    chart_spec: dict
    evidence_contract: EvidenceContractDefinition


@dataclass(slots=True)
class ChartValidationResult:
    valid: bool
    errors: List[str]


@dataclass(slots=True)
class RendererRouteDecisionResult:
    chart_id: str
    renderer_route: str
    same_page_evidence_required: bool
    c_stock_same_page_capable: bool
    supported_c_stock_capabilities: List[str]
    trigger_p2c_spike: bool
    decision_summary: str


@dataclass(slots=True)
class AiChartDraftRequest:
    chart_id: str
    title: str
    renderer_type: str
    integration_route: str
    evidence_contract_id: str
    spec: dict
    actor: str = 'local_operator'


@dataclass(slots=True)
class ChartPublishResult:
    chart_id: str
    status: str
    governance_mode: str
    published: bool


class ChartCatalogService:
    APPROVED_GOVERNANCE_MODES = {'personal', 'cloud'}

    def list_enabled_charts(self) -> List[ChartDefinition]:
        charts = BugTrendChartDefinition.objects.select_related('evidence_contract').filter(
            enabled=True,
            status=BugTrendChartDefinition.STATUS_PUBLISHED,
        ).order_by('built_in', 'title')
        return [self._to_definition(chart) for chart in charts]

    def get_chart(self, chart_id: str) -> ChartDefinition:
        return self._to_definition(BugTrendChartDefinition.objects.select_related('evidence_contract').get(chart_id=chart_id))

    def validate_chart_for_publish(self, chart: BugTrendChartDefinition) -> ChartValidationResult:
        errors = []
        if chart.renderer_type not in {BugTrendChartDefinition.RENDERER_CHARTJS, BugTrendChartDefinition.RENDERER_GRAFANA, BugTrendChartDefinition.RENDERER_STATIC_IMAGE}:
            errors.append('Renderer type is not approved.')
        if chart.integration_route not in {BugTrendChartDefinition.ROUTE_REFERENCE, BugTrendChartDefinition.ROUTE_C_STOCK, BugTrendChartDefinition.ROUTE_C_PLUGIN}:
            errors.append('Integration route is not approved.')
        errors.extend(self._validate_evidence_contract(chart.evidence_contract))
        errors.extend(self._validate_chart_spec(chart.chart_spec, chart.evidence_contract))
        return ChartValidationResult(not errors, errors)

    def record_renderer_route_decision(self, chart_id: str, same_page_evidence_required: bool,
                                       c_stock_same_page_capable: bool, supported_c_stock_capabilities: List[str],
                                       decision_summary: str,
                                       renderer_route: str = BugTrendChartDefinition.ROUTE_C_STOCK) -> RendererRouteDecisionResult:
        if renderer_route not in {BugTrendChartDefinition.ROUTE_REFERENCE, BugTrendChartDefinition.ROUTE_C_STOCK, BugTrendChartDefinition.ROUTE_C_PLUGIN}:
            raise ValueError('Renderer route is not approved.')
        chart = BugTrendChartDefinition.objects.get(chart_id=chart_id)
        trigger_p2c_spike = same_page_evidence_required and not c_stock_same_page_capable
        decision = BugTrendRendererRouteDecision.objects.create(
            chart=chart,
            renderer_route=renderer_route,
            same_page_evidence_required=same_page_evidence_required,
            c_stock_same_page_capable=c_stock_same_page_capable,
            supported_c_stock_capabilities=supported_c_stock_capabilities,
            trigger_p2c_spike=trigger_p2c_spike,
            decision_summary=decision_summary,
        )
        return self._to_decision_result(decision)

    def latest_renderer_route_decision(self, chart_id: str) -> RendererRouteDecisionResult | None:
        decision = BugTrendRendererRouteDecision.objects.select_related('chart').filter(chart__chart_id=chart_id).order_by('-created_at').first()
        if decision is None:
            return None
        return self._to_decision_result(decision)

    def create_ai_chart_draft(self, request: AiChartDraftRequest) -> ChartDefinition:
        contract = BugTrendEvidenceContract.objects.get(contract_id=request.evidence_contract_id)
        errors = self._validate_chart_spec(request.spec, contract)
        if errors:
            self._record_chart_audit('chart_validation_failed', request.actor, request.chart_id, {'errors': errors})
            raise ValueError(errors)
        self._record_chart_audit('chart_draft_created', request.actor, request.chart_id, {'renderer_type': request.renderer_type, 'integration_route': request.integration_route})
        chart = BugTrendChartDefinition.objects.create(
            chart_id=request.chart_id,
            title=request.title,
            renderer_type=request.renderer_type,
            integration_route=request.integration_route,
            evidence_contract=contract,
            status=BugTrendChartDefinition.STATUS_DRAFT,
            enabled=False,
            built_in=False,
            created_by='ai',
            owner=request.actor,
            visibility='personal',
            chart_spec=request.spec,
            validation_summary={'ai_spec_validated': True},
        )
        validation = self.validate_chart_for_publish(chart)
        if not validation.valid:
            self._record_chart_audit('chart_validation_failed', request.actor, request.chart_id, {'errors': validation.errors})
            chart.delete()
            raise ValueError(validation.errors)
        self._record_chart_audit('chart_validation_passed', request.actor, request.chart_id, {'chart_version': chart.chart_version})
        return self._to_definition(chart)

    def publish_chart(self, chart_id: str, actor: str, governance_mode: str) -> ChartPublishResult:
        if governance_mode not in self.APPROVED_GOVERNANCE_MODES:
            raise ValueError('Chart publish governance mode is not approved.')
        chart = BugTrendChartDefinition.objects.get(chart_id=chart_id)
        validation = self.validate_chart_for_publish(chart)
        if not validation.valid:
            raise ValueError(validation.errors)
        if governance_mode == 'cloud':
            request = BugTrendChartPublishRequest.objects.create(
                chart=chart,
                actor=actor,
                governance_mode=governance_mode,
                status=BugTrendChartPublishRequest.STATUS_PENDING,
                request_summary={'chart_id': chart.chart_id, 'chart_version': chart.chart_version},
            )
            self._record_chart_audit('chart_publish_requested', actor, chart.chart_id, {'governance_mode': governance_mode, 'chart_version': chart.chart_version})
            return ChartPublishResult(chart.chart_id, request.status, governance_mode, False)
        chart.status = BugTrendChartDefinition.STATUS_PUBLISHED
        chart.enabled = True
        chart.owner = actor
        chart.visibility = 'personal'
        chart.save(update_fields=['status', 'enabled', 'owner', 'visibility', 'updated_at'])
        BugTrendAuditEvent.objects.create(
            event_type='chart_published',
            actor=actor,
            chart_id=chart.chart_id,
            request_summary={'governance_mode': governance_mode, 'chart_version': chart.chart_version},
        )
        return ChartPublishResult(chart.chart_id, chart.status, governance_mode, True)

    def _record_chart_audit(self, event_type: str, actor: str, chart_id: str, request_summary: dict) -> None:
        BugTrendAuditEvent.objects.create(
            event_type=event_type,
            actor=actor,
            chart_id=chart_id,
            request_summary=request_summary,
        )

    def _validate_evidence_contract(self, contract: BugTrendEvidenceContract) -> List[str]:
        if contract.capability == BugTrendEvidenceContract.CAPABILITY_SUMMARY_ONLY:
            return [] if contract.unsupported_reason else ['Summary-only charts must explain why ticket evidence is unsupported.']
        errors = []
        if contract.membership_source != 'bug_trend_bucket_issue':
            errors.append('Evidence contract must use an approved Metrics-owned membership source.')
        if contract.capability == BugTrendEvidenceContract.CAPABILITY_BUCKET_SERIES and not contract.series_dimension:
            errors.append('Bucket-series evidence requires a series dimension.')
        return errors

    def _validate_chart_spec(self, spec: dict, evidence_contract: BugTrendEvidenceContract) -> List[str]:
        errors = []
        forbidden_fragments = ['select ', ' from ', ' join ', 'token', 'password', 'secret', 'pat', 'api_key']
        spec_text = str(spec).lower()
        for fragment in forbidden_fragments:
            if fragment in spec_text:
                errors.append('Chart specs must not include SQL, secrets, or direct data-source logic.')
                break
        if 'evidence_contract_id' not in spec:
            errors.append('Chart specs must reference a Metrics evidence contract.')
        elif spec.get('evidence_contract_id') != evidence_contract.contract_id:
            errors.append('Chart spec evidence contract must match the catalog evidence contract.')
        series = spec.get('series', [])
        if evidence_contract.capability != BugTrendEvidenceContract.CAPABILITY_SUMMARY_ONLY and not series:
            errors.append('Chart specs with ticket evidence must declare at least one series.')
        if series and (not isinstance(series, list) or any(not isinstance(item, str) for item in series)):
            errors.append('Chart specs series must be a list of series names.')
        elif series:
            known_series = {item.series_name for item in BUG_TREND_SERIES}
            unknown_series = sorted(set(series) - known_series)
            if unknown_series:
                errors.append(f'Chart specs reference unknown Bug Trend series: {", ".join(unknown_series)}.')
        return errors

    def _to_definition(self, chart: BugTrendChartDefinition) -> ChartDefinition:
        return ChartDefinition(
            chart_id=chart.chart_id,
            chart_version=chart.chart_version,
            title=chart.title,
            renderer_type=chart.renderer_type,
            integration_route=chart.integration_route,
            status=chart.status,
            enabled=chart.enabled,
            built_in=chart.built_in,
            chart_spec=dict(chart.chart_spec),
            evidence_contract=EvidenceContractDefinition(
                contract_id=chart.evidence_contract.contract_id,
                capability=chart.evidence_contract.capability,
                membership_source=chart.evidence_contract.membership_source,
                allowed_list_filters=list(chart.evidence_contract.allowed_list_filters),
                unsupported_reason=chart.evidence_contract.unsupported_reason,
            ),
        )

    def _to_decision_result(self, decision: BugTrendRendererRouteDecision) -> RendererRouteDecisionResult:
        return RendererRouteDecisionResult(
            chart_id=decision.chart.chart_id,
            renderer_route=decision.renderer_route,
            same_page_evidence_required=decision.same_page_evidence_required,
            c_stock_same_page_capable=decision.c_stock_same_page_capable,
            supported_c_stock_capabilities=list(decision.supported_c_stock_capabilities),
            trigger_p2c_spike=decision.trigger_p2c_spike,
            decision_summary=decision.decision_summary,
        )