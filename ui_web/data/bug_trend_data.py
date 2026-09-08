from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class BugTrendScopeOption:
    id: int
    name: str
    label: str
    profile_id: str = ''
    provider_id: str = ''
    binding_status: str = ''
    binding_blockers: list = None


@dataclass(slots=True)
class BugTrendScopeBindingData:
    profile_id: str
    provider_id: str
    status: str
    provenance_summary: str
    blockers: list
    can_confirm: bool
    can_edit: bool


@dataclass(slots=True)
class BugTrendScopeLibraryScopeData:
    id: str
    name: str
    ip: str
    project_label: str
    enabled: bool
    config_version_hash: str


@dataclass(slots=True)
class BugTrendScopeLibraryRow:
    scope: BugTrendScopeLibraryScopeData
    binding: BugTrendScopeBindingData
    delete_impact: dict = None
    delete_confirmation: str = ''


@dataclass(slots=True)
class BugTrendProviderProfileChoice:
    profile_id: str
    provider_id: str
    display_name: str
    connection_settings: dict = None
    scope_labels: dict = None
    source_population: dict = None
    mapping_version_hash: str = ''


@dataclass(slots=True)
class BugTrendProviderSetupOption:
    provider_id: str
    label: str
    summary: str
    color: str
    selected: bool
    enabled: bool
    profile_count: int
    metadata_supported: bool
    metadata_summary: str


@dataclass(slots=True)
class BugTrendProviderSetupDetail:
    label: str
    value: str
    help_text: str


@dataclass(slots=True)
class BugTrendProviderProfileRow:
    profile_id: str
    provider_id: str
    provider_label: str
    provider_color: str
    display_name: str
    lifecycle_state: str
    source_kind: str
    source_summary: str
    mapping_version_hash: str
    source_version_hash: str
    delete_impact: dict
    delete_confirmation: str


@dataclass(slots=True)
class BugTrendProviderSetupEditor:
    profile: object
    provider_options: list
    selected_provider_id: str
    provider_label: str
    provider_color: str
    provider_summary: str
    source_query_label: str
    source_query_help: str
    metadata_supported: bool
    metadata_summary: str
    detail_rows: list
    json_fields: list
    connection_settings_json: str
    connection_status_label: str


@dataclass(slots=True)
class BugTrendScopeConfigProviderContext:
    profile_id: str
    provider_id: str
    status: str
    provenance_summary: str
    blockers: list
    profile_choices: list
    has_saved_scope: bool
    metadata_provider_id: str
    metadata_supported: bool
    metadata_summary: str
    selected_provider_id: str
    selected_profile_id: str
    selected_profile_choices: list
    provider_options: list
    provider_label: str
    provider_color: str
    provider_summary: str
    source_query_label: str
    source_query_help: str
    detail_rows: list


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
