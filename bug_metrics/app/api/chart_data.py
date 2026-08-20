from dataclasses import dataclass
from typing import List, Optional


@dataclass(slots=True)
class BugTrendDataset:
    series_name: str
    chart_type: str
    values: List[int]
    color: str


@dataclass(slots=True)
class BugTrendRunMetadata:
    calculation_run_id: str
    run_config_version_hash: str
    current_config_version_hash: str
    freshness_status: str
    source_coverage_start: str
    source_coverage_end: str
    completed_at: str


@dataclass(slots=True)
class BugTrendChart:
    scope_id: int
    calculation_run_id: Optional[str]
    labels: List[str]
    bucket_ids: List[str]
    datasets: List[BugTrendDataset]
    unavailable_reason: str = ''
    run_metadata: Optional[BugTrendRunMetadata] = None
    current_evidence_available: bool = False