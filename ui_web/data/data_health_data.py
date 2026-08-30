from dataclasses import dataclass
from typing import List


@dataclass(slots=True)
class DataHealthPageData:
    sync_health: List[object]
    calculation_health: List[object]
    provider_sync_health: List[object]
    scope_count: int
    stale_scope_count: int
    failed_sync_count: int
    failed_provider_sync_count: int
    failed_calculation_count: int
