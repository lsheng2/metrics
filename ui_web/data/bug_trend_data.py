from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class BugTrendScopeOption:
    id: int
    name: str
    label: str


@dataclass(slots=True)
class BugTrendChartData:
    scope_id: int
    calculation_run_id: str
    labels: List[str]
    bucket_ids: List[str]
    datasets: List[dict]
    unavailable_reason: str = ''


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
