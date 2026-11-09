from dataclasses import dataclass
from typing import List, Union, Optional


@dataclass(slots=True)
class ChartDatasetData:
    label: str
    data: List[Union[float, int]]
    is_done: bool = False


@dataclass(slots=True)
class ChartData:
    labels: List[str]
    datasets: List[ChartDatasetData]
    min_date: Optional[str] = None
    max_date: Optional[str] = None