from dataclasses import dataclass
from typing import Dict, List


PROVIDER_CHART_CONTRACT_VERSION = '0.2'
FIRST_JIRA_PROFILE_ID = 'chiplet-2a-jira'
FIRST_HSDES_PROFILE_ID = 'nvu-ttl-hsdes'
MAPPING_VERSION = 1
STATIC_SCOPE_LABEL_SOURCE = 'user_configured_static_text'
SOURCE_POPULATION_FIELDS = (
    'profile_id',
    'provider_id',
    'ownership_type',
    'source_query_ref',
    'source_query_hash',
    'source_query_name',
    'native_query_text',
    'tenant_or_site',
    'subject_or_issue_type',
    'criteria_operator',
    'criteria_snapshot',
    'exclusion_snapshot',
    'permission_assumptions',
    'observed_result_contract',
    'mapping_version',
    'mapping_version_hash',
    'fact_snapshot_id',
)

FIRST_HSDES_SOURCE_QUERY_NAME = 'NVU All Bugs'
FIRST_HSDES_QUERY_ID = '15017652869'
FIRST_HSDES_TENANT = 'ip_fw_sw_sensing.tenant'
FIRST_HSDES_SUBJECT = 'ip_fw_sw_sensing.bug'
FIRST_HSDES_CRITERIA_OPERATOR = 'All'
FIRST_HSDES_CRITERIA_SNAPSHOT = 'id > 0; family in NVU-FW; HSD_type in bug; release in NVU-FW.trunk,NVU-FW1.0_RZL,NVU-FW1.0_TTL'
FIRST_HSDES_EXCLUSION_SNAPSHOT = 'component not in sw.val,sw.val.tools,ip.sw.val.tool; title does not contain [chrome]; title does not start with [catalog]'
FIRST_HSDES_PERMISSION_ASSUMPTIONS = 'provider saved query is readable by configured HSD-ES credentials'
FIRST_HSDES_OBSERVED_RESULT_CONTRACT = 'HSD-ES article search returns ip_fw_sw_sensing.bug rows with stable id and revision fields.'

FIRST_PROVIDER_STATIC_SCOPE_LABELS = {
    FIRST_JIRA_PROFILE_ID: {
        'ip': 'chiplet_ip',
        'project_or_product': 'chiplet',
        'milestone': '2a',
    },
    FIRST_HSDES_PROFILE_ID: {
        'ip': 'NVU',
        'project_or_product': 'NVU1.0_TTL',
        'milestone': 'NVU_TTL_FWSW0.8',
    },
}

SUPPORTED_JIRA_CHARTS = frozenset({
    'component_bug',
    'rolling_valid_bug',
    'open_bug_trend',
    'total_bug_trend',
    'open_bug_aging',
    'daily_new_standard_bug_count',
})

SUPPORTED_HSDES_SEED_CHARTS = frozenset({
    'component_bug',
    'rolling_valid_bug',
    'open_bug_trend',
    'total_bug_trend',
    'open_bug_aging',
    'daily_new_standard_bug_count',
})

PROVIDER_CHART_EVIDENCE_CAPABILITIES = {
    'component_bug': 'range_only',
    'rolling_valid_bug': 'summary_only',
    'open_bug_trend': 'bucket_series',
    'total_bug_trend': 'range_only',
    'open_bug_aging': 'range_only',
    'daily_new_standard_bug_count': 'range_only',
    'execution_statistics': 'summary_only',
    'milestone_schedule': 'summary_only',
    'milestone_progress': 'summary_only',
    'automation_statistics': 'summary_only',
    'shift_left_statistics': 'summary_only',
    'internal_escaped_bugs': 'summary_only',
    'external_escaped_bugs': 'summary_only',
    'escaped_bug_details': 'summary_only',
}

PROVIDER_CHART_EVIDENCE_SERIES_ALIASES = {
    'open_bug_trend': {
        'all_open_bugs',
        'all_open_critical_high',
        'new_critical_high',
        'new_medium_low',
        'fixed_or_closed_bugs',
    },
}

DEFERRED_CHART_REASONS = {
    'execution_statistics': 'Execution semantics require provider-specific execution/test field mappings and are deferred in the first wave.',
    'milestone_schedule': 'Milestone schedule semantics require schedule artifact mappings and are deferred in the first wave.',
    'milestone_progress': 'Milestone progress semantics require execution progress mappings and are deferred in the first wave.',
    'automation_statistics': 'Automation semantics require coverage field mappings and are deferred in the first wave.',
    'shift_left_statistics': 'Shift-left semantics require project-specific classification mappings and are deferred in the first wave.',
    'internal_escaped_bugs': 'Internal escaped bug semantics require escaped classification mappings and are deferred in the first wave.',
    'external_escaped_bugs': 'External escaped bug semantics require escaped classification mappings and are deferred in the first wave.',
    'escaped_bug_details': 'Escaped bug evidence requires escaped classification mappings and is deferred in the first wave.',
}


@dataclass(frozen=True, slots=True)
class ProviderChartAggregateQuery:
    provider_id: str
    profile_id: str
    begin_ww: str
    end_ww: str
    chart_id: str
    chart_version: int = 1
    fact_snapshot_id: str = ''
    range_mode: str = 'ww'
    begin_date: str = ''
    end_date: str = ''


@dataclass(frozen=True, slots=True)
class ProviderChartEvidenceQuery:
    provider_id: str
    profile_id: str
    begin_ww: str
    end_ww: str
    chart_id: str
    calculation_run_id: str
    selected_bucket_id: str = ''
    selected_series_name: str = ''
    chart_version: int = 1
    fact_snapshot_id: str = ''
    owner: str = ''
    status: str = ''
    severity: str = ''
    component: str = ''
    text: str = ''
    range_mode: str = 'ww'
    begin_date: str = ''
    end_date: str = ''


@dataclass(slots=True)
class ProviderAggregateRow:
    metric_id: str
    chart_id: str
    chart_version: int
    provider_id: str
    profile_id: str
    source_scope_ref: str
    begin_ww: str
    end_ww: str
    bucket_grain: str
    bucket_start: str
    bucket_end: str
    bucket_ww: str
    bucket_date: str
    dimensions: Dict[str, str]
    series: str
    value: float
    fact_snapshot_id: str
    calculation_run_id: str
    mapping_version: int
    mapping_version_hash: str
    source_query: Dict[str, str]
    bucket_id: str = ''

    def to_dict(self) -> dict:
        return {
            'metric_id': self.metric_id,
            'chart_id': self.chart_id,
            'chart_version': self.chart_version,
            'provider_id': self.provider_id,
            'profile_id': self.profile_id,
            'source_scope_ref': self.source_scope_ref,
            'begin_ww': self.begin_ww,
            'end_ww': self.end_ww,
            'bucket_grain': self.bucket_grain,
            'bucket_id': self.bucket_id,
            'bucket_start': self.bucket_start,
            'bucket_end': self.bucket_end,
            'bucket_ww': self.bucket_ww,
            'bucket_date': self.bucket_date,
            'dimensions': self.dimensions,
            'series': self.series,
            'value': self.value,
            'fact_snapshot_id': self.fact_snapshot_id,
            'calculation_run_id': self.calculation_run_id,
            'mapping_version': self.mapping_version,
            'mapping_version_hash': self.mapping_version_hash,
            'source_query': self.source_query,
        }


@dataclass(slots=True)
class ProviderChartAggregateResult:
    contract_version: str
    provider_id: str
    profile_id: str
    chart_id: str
    chart_version: int
    begin_ww: str
    end_ww: str
    status: str
    reason: str
    fact_snapshot_id: str
    source_population: Dict[str, str]
    scope_labels: Dict[str, dict]
    run_metadata: Dict[str, str]
    rows: List[ProviderAggregateRow]
    grafana_rows: List[dict]
    range_mode: str = 'ww'
    begin_date: str = ''
    end_date: str = ''

    def to_dict(self) -> dict:
        return {
            'contract_version': self.contract_version,
            'provider_id': self.provider_id,
            'profile_id': self.profile_id,
            'chart_id': self.chart_id,
            'chart_version': self.chart_version,
            'evidence_capability': evidence_capability_for_result(self.chart_id, self.status),
            'begin_ww': self.begin_ww,
            'end_ww': self.end_ww,
            'range_mode': self.range_mode,
            'begin_date': self.begin_date,
            'end_date': self.end_date,
            'status': self.status,
            'reason': self.reason,
            'fact_snapshot_id': self.fact_snapshot_id,
            'source_population': self.source_population,
            'scope_labels': self.scope_labels,
            'run_metadata': self.run_metadata,
            'rows': [row.to_dict() for row in self.rows],
            'grafana_rows': self.grafana_rows,
            'provider_series_state': [{
                'provider_id': self.provider_id,
                'profile_id': self.profile_id,
                'chart_id': self.chart_id,
                'chart_version': self.chart_version,
                'evidence_capability': evidence_capability_for_result(self.chart_id, self.status),
                'begin_ww': self.begin_ww,
                'end_ww': self.end_ww,
                'range_mode': self.range_mode,
                'begin_date': self.begin_date,
                'end_date': self.end_date,
                'status': self.status,
                'reason': self.reason,
                'fact_snapshot_id': self.fact_snapshot_id,
        }],
    }


def evidence_capability_for_result(chart_id: str, status: str) -> str:
    if status != 'supported':
        return 'summary_only'
    return PROVIDER_CHART_EVIDENCE_CAPABILITIES.get(chart_id, 'summary_only')


def provider_series_to_evidence_series(provider_id: str, chart_id: str, series_name: str) -> str:
    normalized = series_name.removeprefix(f'{provider_id}_')
    if normalized in PROVIDER_CHART_EVIDENCE_SERIES_ALIASES.get(chart_id, set()):
        return normalized
    return series_name


def static_scope_labels_for_profile(profile_id: str, fallback_dimensions: Dict[str, str] | None = None) -> Dict[str, dict]:
    labels = FIRST_PROVIDER_STATIC_SCOPE_LABELS.get(profile_id, fallback_dimensions or {})
    return {
        name: {
            'value': value,
            'source': STATIC_SCOPE_LABEL_SOURCE,
            'mapping_version': MAPPING_VERSION,
        }
        for name, value in labels.items()
    }


def scope_label_dimensions(scope_labels: Dict[str, dict]) -> Dict[str, str]:
    return {
        name: str(label.get('value', ''))
        for name, label in scope_labels.items()
    }
