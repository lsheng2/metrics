from dataclasses import dataclass
from typing import List


@dataclass(frozen=True, slots=True)
class BugTrendSeriesDefinition:
    series_name: str
    chart_type: str
    count_field: str
    color: str
    chart_sign: int = 1
    requires_severity_mapping: bool = False

    def chart_values(self, buckets):
        return [self.chart_sign * getattr(bucket, self.count_field) for bucket in buckets]

    def count_value(self, bucket) -> int:
        return getattr(bucket, self.count_field)


BUG_TREND_SERIES: List[BugTrendSeriesDefinition] = [
    BugTrendSeriesDefinition('all_open_bugs', 'line', 'open_count', '#f2c94c'),
    BugTrendSeriesDefinition('all_open_critical_high', 'line', 'open_critical_high_count', '#f2994a', requires_severity_mapping=True),
    BugTrendSeriesDefinition('new_critical_high', 'bar', 'new_critical_high_count', '#eb5757', requires_severity_mapping=True),
    BugTrendSeriesDefinition('new_medium_low', 'bar', 'new_medium_low_count', '#56ccf2'),
    BugTrendSeriesDefinition('fixed_or_closed_bugs', 'bar', 'fixed_or_closed_count', '#bdbdbd', chart_sign=-1),
]


def active_bug_trend_series(scope) -> List[BugTrendSeriesDefinition]:
    return [series for series in BUG_TREND_SERIES if not series.requires_severity_mapping or (scope.severity_field and scope.critical_high_values)]