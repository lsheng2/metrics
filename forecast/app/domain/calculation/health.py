from typing import Optional

from sd_metrics_lib.utils.enums import HealthStatus
from sd_metrics_lib.utils.time import Duration, TimePolicy


class HealthStatusCalculator:

    @staticmethod
    def calculate(estimation_time: Duration, total_spent_time: Optional[Duration]) -> HealthStatus:
        if not total_spent_time:
            return HealthStatus.GREEN

        if estimation_time <= Duration.zero():
            return HealthStatus.GRAY

        estimation_seconds = estimation_time.to_seconds(TimePolicy.BUSINESS_HOURS)
        spent_seconds = total_spent_time.to_seconds(TimePolicy.BUSINESS_HOURS)

        ratio = spent_seconds / estimation_seconds

        if ratio <= 1.0:
            return HealthStatus.GREEN
        elif ratio <= 1.4:
            return HealthStatus.YELLOW
        elif ratio <= 2:
            return HealthStatus.ORANGE
        else:
            return HealthStatus.RED
