from typing import List, Optional

from ..data.chart_data import ChartData
from ..data.developer_series_data import DeveloperSeriesData
from .color_utils import CHART_PALETTE_SIZE


class DeveloperSeriesUtils:

    @staticmethod
    def from_chart(chart: Optional[ChartData], selected_developers: str) -> List[DeveloperSeriesData]:
        """Legend entries in dataset order; a selection naming no charted developer shows everyone."""
        if not chart or not chart.labels:
            return []
        names = [dataset.label for dataset in chart.datasets]
        selected = {name.strip() for name in selected_developers.split(',') if name.strip()}
        if not selected.intersection(names):
            selected = set(names)
        return [
            DeveloperSeriesData(name=name, palette_slot=index % CHART_PALETTE_SIZE + 1, shown=name in selected)
            for index, name in enumerate(names)
        ]
