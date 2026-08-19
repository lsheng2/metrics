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
class BugTrendDrilldownData:
    calculation_run_id: str
    bucket_id: str
    series_name: str
    rows: List[object]
    display_fields: List[str]
