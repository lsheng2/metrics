from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class BugTrendScopeOption:
    id: int
    name: str
    label: str
    profile_id: str = ''
    provider_id: str = ''


@dataclass(slots=True)
class BugTrendChartOption:
    chart_id: str
    title: str
    capability: str
    unsupported_reason: str = ''


@dataclass(slots=True)
class BugTrendChartData:
    chart_id: str
    scope_id: int
    contract_version: str
    calculation_run_id: str
    labels: List[str]
    bucket_ids: List[str]
    datasets: List[dict]
    bucket_starts: List[str] = None
    bucket_ends: List[str] = None
    bucket_granularity: str = ''
    unavailable_reason: str = ''
    run_metadata: dict = None
    current_evidence_available: bool = False


@dataclass(slots=True)
class BugTrendEvidenceData:
    rows: List[object]
    total_count: int
    shown_count: int
    selection_title: str
    display_fields: List[str]
    scope_id: int
    calculation_run_id: str
    begin: str
    end: str
    has_selection: bool
    bucket_id: str = ''
    series_name: str = ''
    owner: str = ''
    status: str = ''
    severity: str = ''
    component: str = ''
    text: str = ''
    active_chart_id: str = 'default_bug_trend'


@dataclass(slots=True)
class BugTrendScopeAuditData:
    scope_id: int
    scope_name: str
    config_version_hash: str
    observed_values: List[object]
    coverage: object
